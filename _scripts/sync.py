"""
Sync bidirectionnel entre le vault Obsidian local et Supabase.

 Usage:
    python sync.py push              # Local -> Supabase
    python sync.py pull              # Supabase -> Local
    python sync.py pull --force      # Force overwrite local files with remote
    python sync.py status            # Compare les deux

 Tenant scoping (M8):
    --tenant <slug>                  # Override active tenant (default: env VAULT_TENANT or "personal")
    Refuses push of notes with sensitivity in {private, sensitive}.

 Embedding:
    Set EMBED_ON_PUSH=1 (or "true"/"yes") to trigger one batch
    embed-backfill Edge Function call with all pushed entry ids.
"""

import os
import sys
import re
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

# Add local lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv
from utils import _require_env, _validate_path, WikiNote, compute_content_hash, parse_frontmatter, extract_body, extract_wiki_links, build_frontmatter, compute_confidence_score, compute_lineage_depth, check_source_stale, EXCLUDED_SCAN_DIRS

load_dotenv(Path(__file__).parent / ".env", override=True)

# Load configuration
CONFIG_PATH = Path(__file__).parent / "config.json"
CONFIG = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}

SUPABASE_URL = _require_env("SUPABASE_URL")
SUPABASE_KEY = _require_env("SUPABASE_ANON_KEY")
VAULT_PATH = Path(_require_env("VAULT_PATH"))
WIKI_PATH = VAULT_PATH / "wiki"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

TIMEOUT = httpx.Timeout(
    CONFIG.get("timeout_seconds", 10.0),
    connect=CONFIG.get("connect_timeout", 3.0)
)

DEFAULT_TENANT_SLUG = "personal"
TENANT_SLUG = os.environ.get("VAULT_TENANT") or DEFAULT_TENANT_SLUG
_TENANT_ID_CACHE: dict[str, str] = {}
BLOCKED_SENSITIVITIES = ("private", "sensitive")


def _resolve_tenant_id(slug: str | None = None) -> str:
    """Resolve a tenant slug to its uuid via REST. Cached per process."""
    target = slug or TENANT_SLUG
    if target in _TENANT_ID_CACHE:
        return _TENANT_ID_CACHE[target]
    url = f"{SUPABASE_URL}/rest/v1/vault_tenants?select=id&slug=eq.{target}&limit=1"
    r = httpx.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise RuntimeError(
            f'Tenant "{target}" not found. Apply the M8 bootstrap migration or pass --tenant <slug>.'
        )
    tenant_id = rows[0]["id"]
    _TENANT_ID_CACHE[target] = tenant_id
    return tenant_id


FOLDER_TO_SECTION = {
    "Context": "projets",
    "Intelligence": "notes-perso",
    "Resources": "prompts",
    "Daily": "journal",
}

SECTION_TO_FOLDER = {v: k for k, v in FOLDER_TO_SECTION.items()}


def get_local_notes() -> list[dict]:
    notes = []
    for folder in FOLDER_TO_SECTION.keys():
        folder_path = WIKI_PATH / folder
        if not folder_path.exists():
            continue
        for f in folder_path.glob("*.md"):
            if f.name == "README.md":
                continue
            text = f.read_text(encoding="utf-8")
            fm = parse_frontmatter(text)
            body = extract_body(text)
            rel = f.relative_to(VAULT_PATH).as_posix()
            section = FOLDER_TO_SECTION.get(folder, "notes-perso")
            title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
            title = title_match.group(1) if title_match else f.stem
            content_hash = compute_content_hash(body)
            links_to = extract_wiki_links(body)

            # Phase 1 — Derived confidence score
            source_hash = fm.get("source_hash")
            source_path = fm.get("source_path")
            conf = compute_confidence_score(
                fm, body,
                source_hash=source_hash,
                source_path=source_path,
                vault_path=VAULT_PATH,
                created_at=fm.get("date") or fm.get("last_ingested_at"),
            )

            # Phase 1 — Lineage depth
            derived_from = fm.get("derived_from", [])
            lineage_depth = compute_lineage_depth(derived_from if isinstance(derived_from, list) else [])

            # Phase 1 — Stale detection
            stale = False
            stale_status: str | None = None
            stale_reason: str | None = None
            if source_hash and source_path:
                stale, detail, stale_status = check_source_stale(source_hash, source_path, VAULT_PATH)
                if stale:
                    stale_reason = detail

            # Phase 1 — Review status (human validation workflow)
            review_status = fm.get("review_status", "draft")

            notes.append({
                "obsidian_path": rel,
                "section_slug": section,
                "title": title,
                "content": body,
                "tags": fm.get("tags", []),
                "type": fm.get("type") or "note",
                "status": fm.get("status") or "active",
                "source": fm.get("source_type", "obsidian"),
                "content_hash": content_hash,
                "source_hash": source_hash,
                "source_path": source_path,
                "links_to": links_to,
                "canonical_slug": fm.get("canonical_slug"),
                "token_count": fm.get("token_count"),
                "summary": fm.get("summary"),
                "last_ingested_at": fm.get("last_ingested_at"),
                "freshness": fm.get("freshness", "volatile"),
                "memory_tier": fm.get("memory_tier", "working"),
                "decay_score": fm.get("decay_score", 0.0),
                "sensitivity": fm.get("sensitivity", "internal"),
                "confidence": fm.get("confidence", "medium"),
                "confidence_score": conf["score"],
                "confidence_signals": conf["signals"],
                "lineage_depth": lineage_depth,
                "derived_from": derived_from,
                "source_type": fm.get("source_type", "synthesis"),
                "review_status": review_status,
                "stale_status": stale_status,
                "stale_reason": stale_reason,
            })
    return notes


def get_remote_entries() -> list[dict]:
    tenant_id = _resolve_tenant_id()
    all_entries = []
    limit = 1000
    offset = 0
    while True:
        url = (
            f"{SUPABASE_URL}/rest/v1/vault_entries"
            f"?select=*&tenant_id=eq.{tenant_id}&limit={limit}&offset={offset}"
        )
        r = httpx.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        batch = r.json()
        all_entries.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return all_entries


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def upsert_remote(entry: dict) -> str | None:
    """Atomic upsert via POST with resolution=merge-duplicates — no TOCTOU race.

    Requires a UNIQUE constraint on vault_entries(obsidian_path) AND the
    ?on_conflict=obsidian_path query param to tell PostgREST which column to
    resolve on (default is PK = id, which would always conflict).

    Returns the id of the upserted row, or None if the response is empty or
    cannot be parsed.
    """
    _validate_path(entry["obsidian_path"])
    url = f"{SUPABASE_URL}/rest/v1/vault_entries?on_conflict=obsidian_path"
    headers = {
        **HEADERS,
        "Prefer": "resolution=merge-duplicates,return=representation",
    }
    resp = httpx.post(url, headers=headers, json=entry, timeout=TIMEOUT)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"upsert_remote failed [{resp.status_code}]: {resp.text[:200]}")
    try:
        rows = resp.json()
        if isinstance(rows, list) and rows:
            return rows[0].get("id")
    except json.JSONDecodeError:
        logging.warning(
            "upsert_remote: could not parse response body for %s — skipping id extraction",
            entry.get("obsidian_path"),
        )
    return None


def write_local(entry: dict):
    path = entry.get("obsidian_path")
    if not path:
        section = entry.get("section_slug", "notes-perso")
        folder = SECTION_TO_FOLDER.get(section, "Intelligence")
        slug = re.sub(r"[^a-z0-9-]", "-", entry["title"].lower().strip())
        slug = re.sub(r"-+", "-", slug).strip("-")
        path = f"wiki/{folder}/{slug}.md"

    _validate_path(path)  # Validate format first

    full_path = VAULT_PATH / path
    # Prevent path traversal attacks
    if not full_path.resolve().is_relative_to(VAULT_PATH.resolve()):
        raise ValueError(f"Chemin dangereux détecté : {path}")

    # Validate entry structure
    try:
        note = WikiNote.model_validate(entry)
    except Exception as e:
        raise ValueError(f"Entrée invalide : {e}")

    full_path.parent.mkdir(parents=True, exist_ok=True)

    tags = note.tags
    if isinstance(tags, str):
        tags = [tags]

    fm = {
        "date": note.date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "tags": tags,
        "type": note.type,
        "status": note.status,
        "review_status": note.review_status,
        "confidence": note.confidence,
        "confidence_score": note.confidence_score,
        "source_type": note.source_type,
        "freshness": note.freshness,
        "sensitivity": note.sensitivity,
        "lineage_depth": note.lineage_depth,
    }
    if note.source_path:
        fm["source_path"] = note.source_path
    if note.source_hash:
        fm["source_hash"] = note.source_hash
    if note.derived_from:
        fm["derived_from"] = note.derived_from
    if note.summary:
        fm["summary"] = note.summary
    if note.stale_status:
        fm["stale_status"] = note.stale_status
    if note.stale_reason:
        fm["stale_reason"] = note.stale_reason
    # Include confidence_signals if present
    if note.confidence_signals:
        fm["confidence_signals"] = note.confidence_signals
    content = build_frontmatter(fm) + "\n\n" + note.content
    full_path.write_text(content, encoding="utf-8")
    return str(full_path)


def cmd_status():
    local = get_local_notes()
    remote = get_remote_entries()

    local_paths = {n["obsidian_path"] for n in local}
    remote_paths = {e["obsidian_path"] for e in remote if e.get("obsidian_path")}

    only_local = local_paths - remote_paths
    only_remote = remote_paths - local_paths
    both = local_paths & remote_paths

    print(f"=== Sync Status ===")
    print(f"Local notes:  {len(local)}")
    print(f"Remote entries: {len(remote)}")
    print(f"Synced (both): {len(both)}")
    if only_local:
        print(f"\nLocal only ({len(only_local)}):")
        for p in sorted(only_local):
            print(f"  + {p}")
    if only_remote:
        print(f"\nRemote only ({len(only_remote)}):")
        for p in sorted(only_remote):
            print(f"  - {p}")
    if not only_local and not only_remote:
        print("\nAll synced!")


def _get_remote_content_hashes() -> dict[str, str | None]:
    """Fetch dict of obsidian_path -> content_hash from remote, scoped to the active tenant."""
    tenant_id = _resolve_tenant_id()
    url = (
        f"{SUPABASE_URL}/rest/v1/vault_entries"
        f"?select=obsidian_path,content_hash&tenant_id=eq.{tenant_id}"
    )
    r = httpx.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return {e["obsidian_path"]: e.get("content_hash") for e in r.json() if e.get("obsidian_path")}


def cmd_push():
    local = get_local_notes()
    tenant_id = _resolve_tenant_id()
    remote_hashes = _get_remote_content_hashes()
    print(f"Pushing {len(local)} local notes to Supabase (tenant: {TENANT_SLUG})...")
    skipped = 0
    blocked = 0
    pushed_ids: list[str] = []
    for note in local:
        sensitivity = (note.get("sensitivity") or "internal").lower()
        if sensitivity in BLOCKED_SENSITIVITIES:
            print(f"  BLOCK (sensitivity={sensitivity}) {note['obsidian_path']}")
            blocked += 1
            continue
        # Tenant scoping: every pushed row carries the active tenant_id.
        note["tenant_id"] = tenant_id
        h = note.get("content_hash", "")
        remote_hash = remote_hashes.get(note["obsidian_path"])
        if remote_hash and remote_hash == h:
            print(f"  SKIP (unchanged) {note['obsidian_path']} [{h[:12]}...]")
            skipped += 1
            continue
        print(f"  PUSH {note['obsidian_path']} [{h[:12]}...]")
        try:
            entry_id = upsert_remote(note)
            print(f"    OK")
            if entry_id:
                pushed_ids.append(entry_id)
        except Exception as e:
            print(f"    FAIL {note['obsidian_path']}: {e}")
    pushed = len(local) - skipped - blocked
    print(f"Push complete: {pushed} pushed, {skipped} skipped (unchanged), {blocked} blocked (sensitive).")
    embed_on_push = os.environ.get("EMBED_ON_PUSH", "").lower() in ("1", "true", "yes")
    if embed_on_push and pushed_ids:
        _trigger_embed_backfill(pushed_ids)


def _trigger_embed_backfill(ids: list[str]) -> None:
    """POST a batch of entry ids to the embed-backfill Edge Function.

    Called once after cmd_push finishes, so OpenAI is invoked once for the
    whole batch rather than once per note. Never raises — push remains the
    source of truth even if embedding refresh fails.
    """
    if os.environ.get("EMBED_ON_PUSH", "").lower() not in ("1", "true", "yes"):
        return
    url = f"{SUPABASE_URL}/functions/v1/embed-backfill"
    try:
        resp = httpx.post(url, headers=HEADERS, json={"ids": ids}, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        mode = data.get("mode", "unknown")
        success = data.get("success", 0)
        processed = data.get("processed", 0)
        errors = data.get("errors", [])
        print(f"Embed-backfill ({mode}): {success}/{processed}, {len(errors)} errors")
    except Exception as e:
        print(f"  warn: embed-backfill failed: {e}")


def cmd_pull(force: bool = False):
    remote = get_remote_entries()
    local = get_local_notes()
    local_map = {n["obsidian_path"]: n for n in local}
    local_paths = set(local_map.keys())
    remote_map = {e["obsidian_path"]: e for e in remote if e.get("obsidian_path")}

    to_pull = {}
    conflicts = []

    for path, entry in remote_map.items():
        if path not in local_paths:
            to_pull[path] = entry
        elif force:
            local_hash = local_map[path].get("content_hash", "")
            remote_hash = entry.get("content_hash", "")
            if remote_hash and remote_hash != local_hash:
                to_pull[path] = entry
                print(f"  UPDATE (force) : {path} — hash différent, écrasement.")
            else:
                print(f"  SKIP (unchanged) : {path}")
        else:
            conflicts.append(entry)
            print(f"  SKIP (conflit) : {path} — fichier local existant. Lancez push ou --force.")

    pulled = 0
    for path, entry in to_pull.items():
        try:
            path_out = write_local(entry)
            print(f"  OK {path_out}")
            pulled += 1
        except Exception as e:
            print(f"  FAIL {entry.get('title')}: {e}")

    print(f"Pull terminé : {pulled} fichier(s) créé(s)/mis à jour, {len(conflicts)} conflit(s) ignoré(s).")


def cmd_rebuild_alias_registry():
    """Scan wiki/ and build wiki/_meta/alias_registry.yaml."""
    import yaml

    # Collect per-file info and link graph
    registry: dict[str, dict] = {}
    link_graph: dict[str, set[str]] = {}  # source_key -> set of target keys

    for f in WIKI_PATH.rglob("*.md"):
        rel = f.relative_to(WIKI_PATH).as_posix()
        parts = rel.split("/")
        if parts and parts[0] in EXCLUDED_SCAN_DIRS:
            continue

        key = f.stem
        text = f.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        body = extract_body(text)

        title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        title = title_match.group(1) if title_match else (fm.get("title") or f.stem)

        aliases = fm.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]

        registry[key] = {
            "title": title,
            "aliases": aliases,
            "canonical": None,
            "linked_from": [],
        }

        links = extract_wiki_links(body)
        link_graph.setdefault(key, set()).update(links)

    # Invert link graph to build linked_from
    for source_key, targets in link_graph.items():
        for target in targets:
            if target in registry:
                registry[target]["linked_from"].append(source_key)

    # Sort linked_from lists
    for entry in registry.values():
        entry["linked_from"].sort()

    # Cross-reference with entities.yaml
    entities_path = WIKI_PATH / "_meta" / "entities.yaml"
    if entities_path.exists():
        with open(entities_path, "r", encoding="utf-8") as f:
            entities_data = yaml.safe_load(f)
        ents = entities_data.get("entities", {}) if entities_data else {}

        alias_to_canonical: dict[str, str] = {}
        for ekey, einfo in ents.items():
            cname = einfo.get("canonical_name")
            if not cname:
                continue
            alias_to_canonical[ekey.replace("_", "-").lower()] = cname
            for alias in einfo.get("aliases", []):
                norm = alias.lower().replace(" ", "-").replace("_", "-")
                alias_to_canonical[norm] = cname

        for key in registry:
            canon = alias_to_canonical.get(key.lower())
            if canon:
                registry[key]["canonical"] = canon

    # Build YAML output manually to match desired format
    lines = [
        "# AUTO-GENERATED by sync.py --rebuild-alias-registry",
        "# DO NOT EDIT MANUALLY",
        f'generated_at: "{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}"',
        "aliases:",
    ]
    for key in sorted(registry.keys()):
        entry = registry[key]
        lines.append(f"  {key}:")
        lines.append(f'    title: {json.dumps(entry["title"], ensure_ascii=False)}')
        if entry.get("aliases"):
            lines.append("    aliases:")
            for alias in entry["aliases"]:
                lines.append(f"      - {json.dumps(alias, ensure_ascii=False)}")
        else:
            lines.append("    aliases: []")
        lines.append(f"    canonical: {json.dumps(entry.get('canonical'), ensure_ascii=False)}")
        if entry.get("linked_from"):
            lines.append("    linked_from:")
            for ref in entry["linked_from"]:
                lines.append(f"      - {ref}")
        else:
            lines.append("    linked_from: []")

    content = "\n".join(lines) + "\n"
    alias_registry_path = WIKI_PATH / "_meta" / "alias_registry.yaml"
    alias_registry_path.write_text(content, encoding="utf-8")
    print(f"Alias registry written to {alias_registry_path}")
    print(f"  {len(registry)} entries, {sum(len(v['linked_from']) for v in registry.values())} link references")


def cmd_rename_suggest():
    """Suggest kebab-case renames for non-compliant wiki files."""
    import re as _re

    kebab_re = _re.compile(r'^[a-z0-9][a-z0-9-]*\.md$')
    suggestions = []

    for f in WIKI_PATH.rglob("*.md"):
        rel = f.relative_to(WIKI_PATH).as_posix()
        parts = rel.split("/")
        if parts and parts[0] in EXCLUDED_SCAN_DIRS:
            continue

        if not kebab_re.match(f.name):
            stem = f.stem
            new_name = _re.sub(r"[^a-z0-9-]", "-", stem.lower().strip())
            new_name = _re.sub(r"-+", "-", new_name).strip("-")
            new_name = new_name[:64] + ".md"
            parent = str(f.parent.relative_to(WIKI_PATH)).replace("\\", "/")
            if parent == ".":
                suggestions.append(f"{f.name} → {new_name}")
            else:
                suggestions.append(f"{parent}/{f.name} → {parent}/{new_name}")

    if suggestions:
        print("=== Rename Suggestions (kebab-case) ===")
        for s in suggestions:
            print(f"  {s}")
    else:
        print("All wiki files already comply with kebab-case naming.")


def _parse_tenant_flag(argv: list[str]) -> tuple[list[str], str | None]:
    """Extract `--tenant <slug>` from argv. Returns (cleaned_argv, slug_or_none)."""
    slug: str | None = None
    cleaned: list[str] = []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token == "--tenant":
            if i + 1 >= len(argv):
                raise SystemExit("--tenant requires a slug argument")
            slug = argv[i + 1]
            i += 2
            continue
        if token.startswith("--tenant="):
            slug = token.split("=", 1)[1]
            i += 1
            continue
        cleaned.append(token)
        i += 1
    return cleaned, slug


if __name__ == "__main__":
    argv, tenant_override = _parse_tenant_flag(sys.argv[1:])
    if tenant_override:
        TENANT_SLUG = tenant_override

    if not argv:
        print("Usage: python sync.py [--tenant <slug>] [push|pull|status|--rebuild-alias-registry|--rename-suggest]")
        sys.exit(1)

    cmd = argv[0]
    if cmd == "status":
        cmd_status()
    elif cmd == "push":
        cmd_push()
    elif cmd == "pull":
        force = "--force" in argv
        cmd_pull(force=force)
    elif cmd == "--rebuild-alias-registry":
        cmd_rebuild_alias_registry()
    elif cmd == "--rename-suggest":
        cmd_rename_suggest()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
