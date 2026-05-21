"""
Claude Brain — mémoire persistante sessions Claude Code <-> Supabase.

Usage:
    python brain.py load --dir "D:\\Dev\\base-de-donnees"
    python brain.py save --dir "D:\\Dev\\base-de-donnees" --summary "..." --mode full
    python brain.py save --dir "D:\\Dev\\base-de-donnees" --mode autosave
    python brain.py save --dir "D:\\Dev\\base-de-donnees" --mode close

Modes:
    full      — write memory + summary, close session, delete session-id
    autosave  — write memory only, keep session open, NO summary
    close     — close session only (no memory write), delete session-id
"""

import os
import re
import sys
import json
import uuid
import argparse
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent / "lib"))

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

BRAIN_URL = os.environ["BRAIN_URL"]
BRAIN_KEY = os.environ["BRAIN_SERVICE_KEY"]
VAULT_PATH = Path(os.environ.get("VAULT_PATH", str(Path(__file__).parent.parent)))

HEADERS = {
    "apikey": BRAIN_KEY,
    "Authorization": f"Bearer {BRAIN_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

TIMEOUT = httpx.Timeout(5.0, connect=2.0)

LIMITS = {"preference": 10, "decision": 15, "state": 15, "pattern": 10}
MAX_CONTEXT_CHARS = 12000
LOCK_STALE_SECONDS = 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def rest(method: str, path: str, **kwargs) -> httpx.Response:
    url = f"{BRAIN_URL}/rest/v1/{path}"
    r = httpx.request(method, url, headers=HEADERS, timeout=TIMEOUT, **kwargs)
    r.raise_for_status()
    return r


def log_error(working_dir: str, message: str) -> None:
    try:
        log_dir = Path(working_dir) / ".brain" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "errors.log"
        ts = datetime.now(timezone.utc).isoformat()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{ts} {message}\n")
    except Exception:
        pass


def log_autosave(working_dir: str, message: str) -> None:
    try:
        log_dir = Path(working_dir) / ".brain" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "autosave.log"
        ts = datetime.now(timezone.utc).isoformat()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{ts} {message}\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Lock
# ---------------------------------------------------------------------------

def acquire_lock(working_dir: str) -> bool:
    brain_dir = Path(working_dir) / ".brain"
    brain_dir.mkdir(parents=True, exist_ok=True)
    lock_path = brain_dir / "save.lock"

    # Check for stale lock
    if lock_path.exists():
        try:
            data = json.loads(lock_path.read_text(encoding="utf-8"))
            created = datetime.fromisoformat(data["created_at"])
            if datetime.now(timezone.utc) - created < timedelta(seconds=LOCK_STALE_SECONDS):
                log_error(working_dir, f"lock acquisition failed: lock held by pid {data.get('pid')}")
                return False
            # Stale lock — remove it
            lock_path.unlink(missing_ok=True)
        except Exception:
            lock_path.unlink(missing_ok=True)

    # Atomic creation
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        content = json.dumps({"pid": os.getpid(), "created_at": datetime.now(timezone.utc).isoformat()})
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        return True
    except FileExistsError:
        log_error(working_dir, "lock acquisition failed: race condition")
        return False


def release_lock(working_dir: str) -> None:
    lock_path = Path(working_dir) / ".brain" / "save.lock"
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

def load_project_config(working_dir: str) -> dict:
    config_path = Path(working_dir) / ".brain" / "project.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    slug = Path(working_dir).name.lower().replace(" ", "-")
    slug = re.sub(r'[^a-z0-9\-]', '-', slug)
    return {"slug": slug, "name": Path(working_dir).name, "version": 1}


def get_or_create_project(config: dict, working_dir: str) -> dict:
    slug = config["slug"]
    r = rest("GET", f"projects?slug=eq.{slug}&select=*")
    rows = r.json()
    if rows:
        return rows[0]
    r = rest("POST", "projects", json={
        "slug": slug,
        "name": config.get("name", slug),
        "working_dir": working_dir,
        "status": "active",
    })
    return r.json()[0]


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def get_or_resume_session(project_id: str, working_dir: str) -> dict:
    brain_dir = Path(working_dir) / ".brain"
    brain_dir.mkdir(parents=True, exist_ok=True)
    session_file = brain_dir / "session-id"

    if session_file.exists():
        try:
            existing_id = session_file.read_text(encoding="utf-8").strip()
            r = rest("GET", f"sessions?id=eq.{existing_id}&ended_at=is.null&select=*")
            rows = r.json()
            if rows:
                return rows[0]
        except Exception:
            pass

    # Create new session
    r = rest("POST", "sessions", json={"project_id": project_id})
    session = r.json()[0]
    session_file.write_text(session["id"], encoding="utf-8")
    return session


def close_session(session_id: str, summary: Optional[str], working_dir: str) -> None:
    patch: dict = {"ended_at": datetime.now(timezone.utc).isoformat()}
    if summary:
        patch["summary"] = summary
    rest("PATCH", f"sessions?id=eq.{session_id}", json=patch)
    session_file = Path(working_dir) / ".brain" / "session-id"
    try:
        session_file.unlink(missing_ok=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

def call_upsert_rpc(project_id: str, type_: str, key: str, value: str,
                    source: str, session_id: str) -> bool:
    r = rest("POST", "rpc/upsert_memory_with_history", json={
        "p_project_id": project_id,
        "p_type": type_,
        "p_key": key,
        "p_value": value,
        "p_source": source,
        "p_session_id": session_id,
    })
    result = r.json()
    return result.get("changed", False)


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load(working_dir: str) -> None:
    try:
        config = load_project_config(working_dir)
        project = get_or_create_project(config, working_dir)
        project_id = project["id"]
        session = get_or_resume_session(project_id, working_dir)

        memory_by_type: dict[str, list] = {t: [] for t in LIMITS}

        for type_, limit in LIMITS.items():
            r = rest(
                "GET",
                f"claude_memory?project_id=eq.{project_id}&type=eq.{type_}"
                f"&select=key,value,updated_at&order=updated_at.desc&limit={limit}"
            )
            memory_by_type[type_] = r.json()

        # Last session summary
        r_sessions = rest(
            "GET",
            f"sessions?project_id=eq.{project_id}&ended_at=not.is.null"
            f"&summary=not.is.null&select=summary,ended_at&order=ended_at.desc&limit=1"
        )
        last_sessions = r_sessions.json()
        last_summary = last_sessions[0]["summary"] if last_sessions else None

        # Build context-session.md content
        ts = datetime.now(timezone.utc).isoformat()
        lines = [
            "---",
            "type: context-session",
            f"generated: {ts}",
            f"project: {config['slug']}",
            "---",
            "",
            "# Project",
            f"**Slug:** {config['slug']} | **Repertoire:** {working_dir}",
            "",
            "# Current Session",
            f"**ID:** {session['id']} | **Demarre:** {session.get('started_at', ts)}",
            "",
            "# Persistent Memory",
        ]

        for type_ in LIMITS:
            entries = memory_by_type[type_]
            section = type_.capitalize() + "s"
            lines.append(f"## {section}")
            if entries:
                for e in entries:
                    lines.append(f"- [{type_}] {e['key']} : {e['value']}")
            else:
                lines.append("_Aucune entree._")
            lines.append("")

        lines += [
            "# Last Session Summary",
            last_summary if last_summary else "_Aucun resume disponible._",
            "",
        ]

        content = "\n".join(lines)

        # Truncate if needed
        if len(content) > MAX_CONTEXT_CHARS:
            content = content[:MAX_CONTEXT_CHARS] + "\n\n_[tronque]_\n"

        # Atomic write
        output_path = VAULT_PATH / "wiki" / "context-session.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = output_path.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(output_path)

        total = sum(len(v) for v in memory_by_type.values())
        print(f"[OK] Contexte charge -> {output_path}")
        print(f"  {total} entrees memoire | session: {session['id'][:8]}...")
    except Exception as e:
        log_error(working_dir, f"load error: {traceback.format_exc()}")
        print(f"[ERROR] Load failed: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save(working_dir: str, summary: Optional[str], mode: str) -> None:
    brain_dir = Path(working_dir) / ".brain"
    session_file = brain_dir / "session-id"

    # close mode: tolerate missing session-id
    if mode == "close" and not session_file.exists():
        log_autosave(working_dir, "close skipped: no session-id")
        print("[OK] close skipped: no active session")
        return

    if not acquire_lock(working_dir):
        print("[WARN] Could not acquire lock, skipping save")
        return

    try:
        config = load_project_config(working_dir)
        project = get_or_create_project(config, working_dir)
        project_id = project["id"]
        session = get_or_resume_session(project_id, working_dir)
        session_id = session["id"]

        if mode in ("full", "autosave"):
            # Write standard memory entries
            source = "autosave" if mode == "autosave" else "manual"
            today = datetime.now(timezone.utc).date().isoformat()
            call_upsert_rpc(project_id, "state", "last-session-date", today, source, session_id)

            if mode == "full" and summary:
                call_upsert_rpc(project_id, "state", "last-session-summary", summary, source, session_id)

        if mode in ("full", "close"):
            close_session(session_id, summary if mode == "full" else None, working_dir)
            print(f"[OK] Session closed (mode: {mode}) | {session_id[:8]}...")
        else:
            print(f"[OK] Autosave complete | session: {session_id[:8]}... (still open)")

        log_autosave(working_dir, f"save mode={mode} session={session_id[:8]}")

    except Exception as e:
        log_error(working_dir, f"save error: {traceback.format_exc()}")
        print(f"[ERROR] Save failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        release_lock(working_dir)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Claude Brain")
    sub = parser.add_subparsers(dest="command", required=True)

    p_load = sub.add_parser("load")
    p_load.add_argument("--dir", required=True)

    p_save = sub.add_parser("save")
    p_save.add_argument("--dir", required=True)
    p_save.add_argument("--summary", default=None)
    p_save.add_argument("--mode", default="full", choices=["full", "autosave", "close"])

    args = parser.parse_args()

    if args.command == "load":
        load(args.dir)
    elif args.command == "save":
        save(args.dir, args.summary, args.mode)


if __name__ == "__main__":
    main()
