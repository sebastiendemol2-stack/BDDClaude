"""Feedback Pipeline — 3-state feedback loop with occurrence gate (S5).

States:
    raw_feedback       → first occurrence, stored from events
    validated_precedent → ≥ 3 occurrences of same feedback
    promoted_memory    → written to claude_memory (confidence: medium max)

Usage:
    python feedback_pipeline.py collect --event-id <uuid> --content "..." --positive true
    python feedback_pipeline.py validate
    python feedback_pipeline.py promote --project-id <uuid> --session-id <uuid>
    python feedback_pipeline.py status
"""

import os
import re
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv
from utils import _require_env, _validate_uuid, _validate_slug

sys.path.insert(0, str(Path(__file__).parent / "lib"))
load_dotenv(Path(__file__).parent / ".env", override=True)

_BRAIN_URL = _require_env("BRAIN_URL")
_BRAIN_KEY = _require_env("BRAIN_SERVICE_KEY")

_HEADERS = {
    "apikey": _BRAIN_KEY,
    "Authorization": f"Bearer {_BRAIN_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
_TIMEOUT = httpx.Timeout(10.0, connect=3.0)

VALID_STATUSES = {"raw_feedback", "validated_precedent", "promoted_memory"}
PROMOTION_THRESHOLD = 3


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def _rest(method: str, path: str, **kwargs) -> httpx.Response:
    url = f"{_BRAIN_URL}/rest/v1/{path}"
    r = httpx.request(method, url, headers=_HEADERS, timeout=_TIMEOUT, **kwargs)
    r.raise_for_status()
    return r


def _normalize_content(content: str) -> str:
    """Normalize feedback content for dedup grouping."""
    return content.strip().lower()[:200]


def collect_feedback(event_id: str, content: str, positive: bool,
                     source: str = "jan") -> dict | None:
    """Collect a raw feedback entry from an event.

    Stores in vault_feedback with status=raw_feedback, occurrences=1.
    If a similar feedback (same normalized content + positive flag) already
    exists in raw or validated state, increments occurrences instead.
    """
    try:
        event_id = _validate_uuid(event_id)
    except ValueError:
        print(f"[ERROR] Invalid event_id: {event_id}")
        return None

    norm = _normalize_content(content)
    project_slug = source

    # Check existing un-promoted feedback with same normalized content
    try:
        r = _rest(
            "GET",
            f"vault_feedback?status=in.(raw_feedback,validated_precedent)"
            f"&positive=eq.{str(positive).lower()}"
            f"&order=created_at.desc&limit=10"
        )
        existing = r.json()
    except Exception:
        existing = []

    match = None
    for fb in existing:
        existing_norm = _normalize_content(fb.get("content", ""))
        if existing_norm == norm:
            match = fb
            break

    if match:
        new_count = (match.get("occurrences", 0) or 0) + 1
        new_status = "validated_precedent" if new_count >= PROMOTION_THRESHOLD else "raw_feedback"
        fb_id = match["id"]
        try:
            r = _rest("PATCH", f"vault_feedback?id=eq.{fb_id}", json={
                "occurrences": new_count,
                "status": new_status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            row = r.json()[0] if r.json() else match
            print(f"[OK] Feedback incremented ({new_count}x), status={new_status} (id={fb_id[:8]}...)")
            return row
        except Exception as e:
            print(f"[ERROR] Failed to update feedback: {e}")
            return None

    body = {
        "event_id": event_id,
        "content": content[:1000],
        "positive": positive,
        "occurrences": 1,
        "status": "raw_feedback",
        "source": source,
    }
    try:
        r = _rest("POST", "vault_feedback", json=body)
        row = r.json()[0]
        print(f"[OK] Feedback collected (id={row['id'][:8]}...)")
        return row
    except Exception as e:
        print(f"[ERROR] Failed to collect feedback: {e}")
        return None


def validate_feedback(threshold: int = PROMOTION_THRESHOLD) -> int:
    """Scan raw_feedback entries and promote to validated_precedent if >= threshold.

    Returns count of promoted entries.
    """
    try:
        r = _rest(
            "GET",
            "vault_feedback?status=eq.raw_feedback&occurrences=gte.2&order=created_at.asc"
        )
        rows = r.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch feedback: {e}")
        return 0

    promoted = 0
    for fb in rows:
        occ = fb.get("occurrences", 0) or 0
        if occ >= threshold:
            fb_id = fb["id"]
            try:
                _rest("PATCH", f"vault_feedback?id=eq.{fb_id}", json={
                    "status": "validated_precedent",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                promoted += 1
                print(f"  [OK] {fb_id[:8]}... -> validated_precedent ({occ}x)")
            except Exception as e:
                print(f"[ERROR] Failed to promote {fb_id[:8]}...: {e}")

    print(f"[OK] {promoted}/{len(rows)} feedbacks promoted to validated_precedent")
    return promoted


def promote_memory(project_id: str, session_id: str,
                   max_promote: int = 10) -> int:
    """Promote validated_precedent entries to claude_memory.

    Writes each as a 'pattern' memory with confidence capped at 'medium'.
    Returns count promoted.
    """
    try:
        project_id = _validate_uuid(project_id)
        session_id = _validate_uuid(session_id)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return 0

    try:
        r = _rest(
            "GET",
            f"vault_feedback?status=eq.validated_precedent&order=occurrences.desc&limit={max_promote}"
        )
        rows = r.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch validated feedback: {e}")
        return 0

    promoted = 0
    for fb in rows:
        fb_id = fb["id"]
        content = fb.get("content", "")[:500]
        positive = fb.get("positive", True)
        occurrences = fb.get("occurrences", 0) or 0
        source = fb.get("source", "feedback-pipeline")

        if not content:
            continue

        key = f"feedback-{_slugify(content[:40])}"
        value = f"[{'positive' if positive else 'negative'}] {content} (x{occurrences})"

        try:
            _rest("POST", "rpc/upsert_memory_with_history", json={
                "p_project_id": project_id,
                "p_type": "pattern",
                "p_key": key,
                "p_value": value,
                "p_source": source,
                "p_session_id": session_id,
            })
        except Exception as e:
            print(f"[ERROR] Failed to upsert memory for {fb_id[:8]}...: {e}")
            continue

        try:
            _rest("PATCH", f"vault_feedback?id=eq.{fb_id}", json={
                "status": "promoted_memory",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            print(f"[WARN] Failed to mark {fb_id[:8]}... as promoted: {e}")

        promoted += 1
        print(f"  [OK] {fb_id[:8]}... -> promoted_memory (key={key})")

    print(f"[OK] {promoted}/{len(rows)} feedbacks promoted to claude_memory")
    return promoted


def cmd_status() -> None:
    """Show feedback pipeline status."""
    try:
        r = _rest(
            "GET",
            "vault_feedback?select=status,count:id&order=status.asc"
        )
        raw_count = 0
        validated_count = 0
        promoted_count = 0
        for s in r.json():
            status = s.get("status", "")
            cnt = s.get("count", 0) or 0
            if status == "raw_feedback":
                raw_count = cnt
            elif status == "validated_precedent":
                validated_count = cnt
            elif status == "promoted_memory":
                promoted_count = cnt

        print("=== Feedback Pipeline Status ===")
        print(f"  raw_feedback:        {raw_count}")
        print(f"  validated_precedent: {validated_count}")
        print(f"  promoted_memory:     {promoted_count}")
        print(f"  total:               {raw_count + validated_count + promoted_count}")
        print(f"  threshold:           {PROMOTION_THRESHOLD} occurrences")
    except Exception as e:
        print(f"[ERROR] {e}")


def _slugify(text: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', text).strip('-').lower()
    return slug[:50]


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Feedback Pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_collect = sub.add_parser("collect")
    p_collect.add_argument("--event-id", required=True)
    p_collect.add_argument("--content", required=True)
    p_collect.add_argument("--positive", type=lambda x: x.lower() == "true", required=True)
    p_collect.add_argument("--source", default="jan")

    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--threshold", type=int, default=PROMOTION_THRESHOLD)

    p_promote = sub.add_parser("promote")
    p_promote.add_argument("--project-id", required=True)
    p_promote.add_argument("--session-id", required=True)
    p_promote.add_argument("--max", type=int, default=10)

    p_status = sub.add_parser("status")

    args = parser.parse_args()

    if args.command == "collect":
        collect_feedback(args.event_id, args.content, args.positive, args.source)
    elif args.command == "validate":
        validate_feedback(args.threshold)
    elif args.command == "promote":
        promote_memory(args.project_id, args.session_id, args.max)
    elif args.command == "status":
        cmd_status()


if __name__ == "__main__":
    main()
