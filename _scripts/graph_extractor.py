"""Graph Extractor — extraction relations entre notes vault (S6).

Filtre: confidence >0.7 OU type=decision sur la note source.
Stocke dans vault_relations. Jamais injecté automatiquement dans contexte LLM.

Usage:
    python graph_extractor.py extract [--path <vault_path>]
    python graph_extractor.py query --note <obsidian_path>
    python graph_extractor.py status
"""

import os
import re
import sys
import json
import glob
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv
from utils import _require_env, _validate_uuid, _validate_slug, _validate_path, extract_wiki_links, parse_frontmatter

sys.path.insert(0, str(Path(__file__).parent / "lib"))
load_dotenv(Path(__file__).parent / ".env", override=True)

_BRAIN_URL = _require_env("BRAIN_URL")
_BRAIN_KEY = _require_env("BRAIN_SERVICE_KEY")
_SUPABASE_URL = os.environ.get("SUPABASE_URL", _BRAIN_URL)
_SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", _BRAIN_KEY)
_DEFAULT_VAULT_PATH = str((Path(__file__).parent.parent / "wiki").resolve())

_HEADERS = {
    "apikey": _BRAIN_KEY,
    "Authorization": f"Bearer {_BRAIN_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
_TIMEOUT = httpx.Timeout(10.0, connect=3.0)

# Read-only headers for SUPABASE_URL (vault_entries queries)
_SUPABASE_HEADERS = {
    "apikey": _SUPABASE_KEY,
    "Authorization": f"Bearer {_SUPABASE_KEY}",
    "Content-Type": "application/json",
}

_EXCLUDED_DIRS = {"_system", "_meta", "_staging", "_compressed"}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def _rest(method: str, path: str, **kwargs) -> httpx.Response:
    url = f"{_BRAIN_URL}/rest/v1/{path}"
    r = httpx.request(method, url, headers=_HEADERS, timeout=_TIMEOUT, **kwargs)
    r.raise_for_status()
    return r


def _rest_vault(method: str, path: str, **kwargs) -> httpx.Response:
    """Read-only REST call to SUPABASE_URL (vault_entries)."""
    url = f"{_SUPABASE_URL}/rest/v1/{path}"
    r = httpx.request(method, url, headers=_SUPABASE_HEADERS, timeout=_TIMEOUT, **kwargs)
    r.raise_for_status()
    return r


def _load_local_entries(vault_path: str) -> list[dict]:
    """Load all wiki markdown files with frontmatter and wiki links."""
    wiki_dir = Path(vault_path)
    if not wiki_dir.exists():
        return []

    entries = []
    for md_file in sorted(wiki_dir.rglob("*.md")):
        rel = md_file.relative_to(wiki_dir.parent)
        rel_str = str(rel.as_posix())

        if any(part.startswith("_") for part in rel.parts):
            continue

        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        fm = parse_frontmatter(text)
        body = text.split("---", 2)[-1].strip() if text.startswith("---") else text

        type_ = fm.get("type", "concept")
        confidence = fm.get("confidence", "medium")

        links_to = []
        if fm.get("links_to"):
            links_to = fm["links_to"] if isinstance(fm["links_to"], list) else [fm["links_to"]]

        wiki_links = extract_wiki_links(body)
        all_links = list(set(links_to + wiki_links))

        entries.append({
            "obsidian_path": rel_str,
            "title": fm.get("title", md_file.stem),
            "type": type_,
            "confidence": confidence,
            "links_to": all_links,
            "file_path": str(md_file),
        })

    return entries


def _should_extract(entry: dict) -> bool:
    """Extract relations only if confidence >0.7 or type=decision."""
    type_ = entry.get("type", "")
    confidence = entry.get("confidence", "medium")

    if type_ == "decision":
        return True

    conf_map = {"high": 0.8, "medium": 0.5, "low": 0.2}
    conf_score = conf_map.get(confidence, 0.5)
    return conf_score > 0.7


def extract_relations(vault_path: str = _DEFAULT_VAULT_PATH) -> int:
    """Extract relations from all wiki notes and sync to vault_relations.

    Returns count of relations extracted.
    """
    entries = _load_local_entries(vault_path)

    # Fetch existing remote entries to resolve obsidian_path (read from SUPABASE_URL)
    try:
        r = _rest_vault("GET", "vault_entries?select=obsidian_path")
        remote_paths = {row["obsidian_path"] for row in r.json()}
    except Exception:
        remote_paths = set()

    relation_count = 0
    for entry in entries:
        if not _should_extract(entry):
            continue

        source_path = entry["obsidian_path"]
        if source_path not in remote_paths:
            continue

        for target_link in entry["links_to"]:
            target_path = _resolve_target_path(target_link, source_path)
            if target_path not in remote_paths:
                continue

            relation_type = "references"
            if entry["type"] == "decision":
                relation_type = "decides"

            try:
                _rest("POST", "vault_relations", json={
                    "source_entry_id": source_path,
                    "target_entry_id": target_path,
                    "relation_type": relation_type,
                    "confidence": _confidence_score(entry["confidence"]),
                })
                relation_count += 1
            except Exception:
                continue

    print(f"[OK] {relation_count} relations extracted")
    return relation_count


def _resolve_target_path(target_link: str, source_path: str) -> str:
    """Resolve a wiki link or short name to an obsidian_path."""
    link = target_link.replace(".md", "")

    if link.startswith("wiki/"):
        return link + ".md"

    if "/" in link:
        return link + ".md"

    source_dir = Path(source_path).parent
    candidate = source_dir / f"{link}.md"
    cand_str = candidate.as_posix()
    if not cand_str.startswith("wiki/"):
        cand_str = f"wiki/{cand_str}"
    return cand_str


def _confidence_score(level: str) -> float:
    return {"high": 0.8, "medium": 0.5, "low": 0.2}.get(level, 0.5)


def query_relations(obsidian_path: str) -> list[dict]:
    """Query all relations for a given note (incoming + outgoing)."""
    try:
        path = _validate_path(obsidian_path)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return []

    try:
        r = _rest(
            "GET",
            f"vault_relations?or=(source_entry_id.eq.{path},target_entry_id.eq.{path})"
            f"&select=source_entry_id,target_entry_id,relation_type,confidence"
        )
        return r.json()
    except Exception as e:
        print(f"[ERROR] Failed to query relations: {e}")
        return []


def cmd_status() -> None:
    """Show graph statistics."""
    try:
        r = _rest("GET", "vault_relations?select=relation_type,count:id&order=relation_type.asc")
        counts = {}
        for row in r.json():
            rt = row.get("relation_type", "unknown")
            cnt = row.get("count", 0) or 0
            counts[rt] = cnt

        total = sum(counts.values())
        print("=== Graph Status ===")
        print(f"  Total relations: {total}")
        for rt, cnt in sorted(counts.items()):
            print(f"    {rt}: {cnt}")

        r2 = _rest("GET", "vault_relations?select=source_entry_id&distinct=true")
        unique_sources = len(r2.json())
        print(f"  Unique source notes: {unique_sources}")
    except Exception as e:
        print(f"[ERROR] {e}")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Graph Extractor")
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract")
    p_extract.add_argument("--path", default=_DEFAULT_VAULT_PATH)

    p_query = sub.add_parser("query")
    p_query.add_argument("--note", required=True)

    p_status = sub.add_parser("status")

    args = parser.parse_args()

    if args.command == "extract":
        extract_relations(args.path)
    elif args.command == "query":
        results = query_relations(args.note)
        print(json.dumps(results, indent=2, ensure_ascii=False))
    elif args.command == "status":
        cmd_status()


if __name__ == "__main__":
    main()
