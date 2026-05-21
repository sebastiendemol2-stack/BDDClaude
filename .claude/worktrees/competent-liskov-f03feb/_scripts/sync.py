"""
Sync bidirectionnel entre le vault Obsidian local et Supabase.

Usage:
    python sync.py push     # Local -> Supabase
    python sync.py pull     # Supabase -> Local
    python sync.py status   # Compare les deux
"""

import os
import sys
import re
import json
from pathlib import Path
from datetime import datetime, timezone

# Add local lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_ANON_KEY"]
VAULT_PATH = Path(os.environ["VAULT_PATH"])
WIKI_PATH = VAULT_PATH / "wiki"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

FOLDER_TO_SECTION = {
    "Context": "projets",
    "Intelligence": "notes-perso",
    "Resources": "prompts",
    "Daily": "journal",
}

SECTION_TO_FOLDER = {v: k for k, v in FOLDER_TO_SECTION.items()}
SECTION_TO_FOLDER["doc-technique"] = "Resources"


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                val = [t.strip() for t in val[1:-1].split(",") if t.strip()]
            fm[key] = val
    return fm, m.group(2).strip()


def build_frontmatter(fm: dict) -> str:
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(v)}]")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def get_local_notes() -> list[dict]:
    notes = []
    for folder in ["Context", "Intelligence", "Resources", "Daily"]:
        folder_path = WIKI_PATH / folder
        if not folder_path.exists():
            continue
        for f in folder_path.glob("*.md"):
            if f.name == "README.md":
                continue
            text = f.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(text)
            rel = f.relative_to(VAULT_PATH).as_posix()
            section = FOLDER_TO_SECTION.get(folder, "notes-perso")
            title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
            title = title_match.group(1) if title_match else f.stem
            notes.append({
                "obsidian_path": rel,
                "section_slug": section,
                "title": title,
                "content": body,
                "tags": fm.get("tags", []),
                "type": fm.get("type", "note"),
                "status": fm.get("status", "active"),
                "source": "obsidian",
                "mtime": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            })
    return notes


def get_remote_entries() -> list[dict]:
    url = f"{SUPABASE_URL}/rest/v1/vault_entries?select=*"
    r = httpx.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def upsert_remote(entry: dict):
    url = f"{SUPABASE_URL}/rest/v1/vault_entries"
    headers = {**HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"}
    payload = {
        "section_slug": entry["section_slug"],
        "title": entry["title"],
        "content": entry["content"],
        "tags": entry["tags"] if isinstance(entry["tags"], list) else [],
        "source": entry.get("source", "obsidian"),
        "obsidian_path": entry["obsidian_path"],
        "type": entry.get("type", "note"),
        "status": entry.get("status", "active"),
    }
    # Try update by obsidian_path first
    check_url = f"{SUPABASE_URL}/rest/v1/vault_entries?obsidian_path=eq.{entry['obsidian_path']}"
    existing = httpx.get(check_url, headers=HEADERS).json()
    if existing:
        patch_url = f"{SUPABASE_URL}/rest/v1/vault_entries?obsidian_path=eq.{entry['obsidian_path']}"
        r = httpx.patch(patch_url, headers=HEADERS, json=payload)
    else:
        r = httpx.post(url, headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()


def write_local(entry: dict):
    path = entry.get("obsidian_path")
    if not path:
        section = entry.get("section_slug", "notes-perso")
        folder = SECTION_TO_FOLDER.get(section, "Intelligence")
        slug = re.sub(r"[^a-z0-9-]", "-", entry["title"].lower().strip())
        slug = re.sub(r"-+", "-", slug).strip("-")
        path = f"wiki/{folder}/{slug}.md"

    full_path = VAULT_PATH / path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    tags = entry.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    fm = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "tags": tags,
        "type": entry.get("type", "note"),
        "status": entry.get("status", "active"),
    }
    content = build_frontmatter(fm) + "\n\n" + entry.get("content", "")
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


def cmd_push():
    local = get_local_notes()
    print(f"Pushing {len(local)} local notes to Supabase...")
    for note in local:
        try:
            upsert_remote(note)
            print(f"  OK {note['obsidian_path']}")
        except Exception as e:
            print(f"  FAIL {note['obsidian_path']}: {e}")
    print("Push complete.")


def cmd_pull():
    remote = get_remote_entries()
    local_paths = {n["obsidian_path"] for n in get_local_notes()}
    to_pull = [e for e in remote if e.get("obsidian_path") and e["obsidian_path"] not in local_paths]
    print(f"Pulling {len(to_pull)} remote entries to local...")
    for entry in to_pull:
        try:
            path = write_local(entry)
            print(f"  OK {path}")
        except Exception as e:
            print(f"  FAIL {entry.get('title')}: {e}")
    print("Pull complete.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sync.py [push|pull|status]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "status":
        cmd_status()
    elif cmd == "push":
        cmd_push()
    elif cmd == "pull":
        cmd_pull()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
