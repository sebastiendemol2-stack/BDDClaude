"""Event Log — append-only event log central pour S3.

Usage:
    python event_log.py push --type session_end --payload '{"summary":"..."}'
    python event_log.py process
    python event_log.py status

Pattern: Jan écrit des events bruts, brain.py les processe plus tard.
Résilient : si Jan crash, les events sont déjà en base.
"""

import os
import re
import sys
import json
import traceback
from pathlib import Path
from datetime import datetime, timezone, date
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent / "lib"))
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv
from utils import _require_env, _validate_uuid, _validate_slug

load_dotenv(Path(__file__).parent / ".env", override=True)

_BRAIN_URL = _require_env("BRAIN_URL")
_BRAIN_KEY = _require_env("BRAIN_SERVICE_KEY")
_VAULT_PATH = Path(os.environ.get("VAULT_PATH", str(Path(__file__).parent.parent))).resolve()

_HEADERS = {
    "apikey": _BRAIN_KEY,
    "Authorization": f"Bearer {_BRAIN_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

_TIMEOUT = httpx.Timeout(10.0, connect=3.0)

VALID_EVENT_TYPES = {"session_start", "session_end", "message", "feedback", "ingest", "custom"}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def _rest(method: str, path: str, **kwargs) -> httpx.Response:
    url = f"{_BRAIN_URL}/rest/v1/{path}"
    r = httpx.request(method, url, headers=_HEADERS, timeout=_TIMEOUT, **kwargs)
    r.raise_for_status()
    return r


def push_event(event_type: str, payload: dict,
               source: str = "jan",
               project_slug: str | None = None,
               session_id: str | None = None) -> dict | None:
    """Push an event to the vault_events table (append-only).

    Returns the created event row, or None on failure.
    """
    if event_type not in VALID_EVENT_TYPES:
        print(f"[ERROR] Invalid event_type: {event_type}. Valid: {sorted(VALID_EVENT_TYPES)}")
        return None

    body = {
        "event_type": event_type,
        "payload": payload,
        "source": source,
        "ingested": False,
    }
    if project_slug:
        try:
            body["project_slug"] = _validate_slug(project_slug)
        except ValueError:
            print(f"[ERROR] Invalid project_slug: {project_slug}")
            return None
    if session_id:
        try:
            body["session_id"] = _validate_uuid(session_id)
        except ValueError:
            print(f"[ERROR] Invalid session_id: {session_id}")
            return None

    try:
        r = _rest("POST", "vault_events", json=body)
        row = r.json()[0]
        print(f"[OK] Event {event_type} pushed (id={row['id'][:8]}...)")
        return row
    except Exception as e:
        print(f"[ERROR] Failed to push event: {e}")
        return None


def get_unprocessed_events(limit: int = 50) -> list[dict]:
    """Fetch events where ingested=false, oldest first."""
    try:
        r = _rest(
            "GET",
            f"vault_events?ingested=eq.false&order=created_at.asc&limit={limit}"
        )
        return r.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch unprocessed events: {e}")
        return []


def mark_processed(event_id: str, error: str | None = None) -> bool:
    """Mark an event as ingested."""
    try:
        event_id = _validate_uuid(event_id)
    except ValueError:
        print(f"[ERROR] Invalid event_id: {event_id}")
        return False

    patch: dict = {
        "ingested": True,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }
    if error:
        patch["error"] = error[:500]

    try:
        _rest("PATCH", f"vault_events?id=eq.{event_id}", json=patch)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to mark event {event_id[:8]}... as processed: {e}")
        return False


def _handle_session_end(event: dict) -> bool:
    """Derive a session summary from a session_end event.

    Creates/updates a session in the sessions table, saves memory.
    """
    payload = event.get("payload", {})
    project_slug = event.get("project_slug") or payload.get("project", "default")
    session_id = event.get("session_id")

    summary = payload.get("summary", "")
    decisions = payload.get("decisions", [])
    patterns = payload.get("patterns", [])

    if not summary and not decisions and not patterns:
        print(f"[SKIP] session_end event {event['id'][:8]}... has no content")
        return False

    # Get or create project
    try:
        r = _rest("GET", f"projects?slug=eq.{_validate_slug(project_slug)}&select=*")
        rows = r.json()
        if rows:
            project = rows[0]
        else:
            r = _rest("POST", "projects", json={
                "slug": project_slug, "name": project_slug, "status": "active"
            })
            project = r.json()[0]
        project_id = project["id"]
    except Exception as e:
        print(f"[ERROR] Project lookup failed: {e}")
        return False

    # Update session or create one
    if not session_id:
        # Create a new session with summary
        try:
            r = _rest("POST", "sessions", json={
                "project_id": project_id,
                "summary": summary or "(auto session_end)",
                "ended_at": datetime.now(timezone.utc).isoformat(),
            })
            session_id = r.json()[0]["id"]
        except Exception as e:
            print(f"[ERROR] Failed to create session: {e}")
            return False
    else:
        try:
            _validate_uuid(session_id)
            _rest("PATCH", f"sessions?id=eq.{session_id}", json={
                "summary": summary or "(auto session_end)",
                "ended_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            print(f"[ERROR] Failed to update session {session_id[:8]}...: {e}")

    # Save decisions and patterns as memory
    try:
        for d in decisions:
            if isinstance(d, dict) and "key" in d:
                _rest("POST", "rpc/upsert_memory_with_history", json={
                    "p_project_id": project_id,
                    "p_type": "decision",
                    "p_key": d["key"],
                    "p_value": str(d.get("value", "")),
                    "p_source": "event-log",
                    "p_session_id": session_id,
                })
        for p in patterns:
            if isinstance(p, dict) and "key" in p:
                _rest("POST", "rpc/upsert_memory_with_history", json={
                    "p_project_id": project_id,
                    "p_type": "pattern",
                    "p_key": p["key"],
                    "p_value": str(p.get("value", "")),
                    "p_source": "event-log",
                    "p_session_id": session_id,
                })
    except Exception as e:
        print(f"[WARN] Memory save partial failure: {e}")

    print(f"[OK] Session {session_id[:8] if session_id else '?'} updated from session_end")
    return True


def _handle_feedback(event: dict) -> bool:
    """Store feedback in vault_events (future: promote to precedent in S5)."""
    payload = event.get("payload", {})
    positive = payload.get("positive", False)
    print(f"[OK] Feedback stored: {'positive' if positive else 'negative'}")
    return True


def process_events(limit: int = 50) -> int:
    """Process all unprocessed events in order. Returns count processed."""
    events = get_unprocessed_events(limit)
    if not events:
        print("[OK] No unprocessed events")
        return 0

    processed = 0
    for event in events:
        event_id = event["id"]
        event_type = event.get("event_type", "")
        error = None

        try:
            if event_type == "session_end":
                ok = _handle_session_end(event)
            elif event_type == "feedback":
                ok = _handle_feedback(event)
            else:
                ok = True  # Acknowledge unknown types without error
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            ok = False

        if ok or error:
            mark_processed(event_id, error=error)
            processed += 1
            tag = "OK" if ok else "ERR"
            print(f"  [{tag}] {event_type} ({event_id[:8]}...)")

    print(f"[OK] {processed}/{len(events)} events processed")
    return processed


def cmd_status() -> None:
    """Show event log status."""
    try:
        r = _rest("GET", "vault_events?select=event_type,ingested,created_at&order=created_at.desc&limit=10")
        events = r.json()
    except Exception as e:
        print(f"[ERROR] {e}")
        return

    total = len(events)
    pending = sum(1 for e in events if not e.get("ingested"))
    by_type: dict[str, int] = {}
    for e in events:
        et = e.get("event_type", "unknown")
        by_type[et] = by_type.get(et, 0) + 1

    print(f"=== Event Log Status ===")
    print(f"Recent events: {total} ({pending} pending)")
    print(f"By type: {by_type}")
    print()
    for e in events[:5]:
        tag = " [PENDING]" if not e.get("ingested") else ""
        print(f"  {e['created_at'][:19]} | {e['event_type']}{tag}")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Event Log")
    sub = parser.add_subparsers(dest="command", required=True)

    p_push = sub.add_parser("push")
    p_push.add_argument("--type", required=True, choices=sorted(VALID_EVENT_TYPES))
    p_push.add_argument("--payload", required=True, help="JSON string")
    p_push.add_argument("--source", default="jan")
    p_push.add_argument("--project-slug")
    p_push.add_argument("--session-id")

    p_process = sub.add_parser("process")
    p_process.add_argument("--limit", type=int, default=50)

    p_status = sub.add_parser("status")

    args = parser.parse_args()

    if args.command == "push":
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Invalid JSON payload: {e}")
            sys.exit(1)
        push_event(args.type, payload, source=args.source,
                   project_slug=args.project_slug, session_id=args.session_id)
    elif args.command == "process":
        process_events(limit=args.limit)
    elif args.command == "status":
        cmd_status()


if __name__ == "__main__":
    main()
