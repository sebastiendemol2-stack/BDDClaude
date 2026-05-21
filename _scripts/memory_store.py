"""Memory Store — vector search sessions persistées (S4).

Usage:
    python memory_store.py store --session-id <uuid> --summary "..." --decisions '[{"key":"x","value":"y"}]'
    python memory_store.py search --query "..." --top-k 5
    python memory_store.py context --query "..." --top-k 3

Architecture:
    embed_session() via Jan /v1/embeddings
    store_session()  persist in vault_memories (Supabase)
    search_sessions() cosine similarity on embeddings
    format_session_context() -> [RELATED_SESSIONS] block
"""

import os
import re
import sys
import json
import math
import time
import uuid as uuid_mod
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
_JAN_BASE = os.environ.get("JAN_BASE", "http://localhost:1337")
_EMBED_MODEL = os.environ.get("JAN_EMBED_MODEL", "text-embedding-ada-002")
_EMBED_TIMEOUT = float(os.environ.get("RAG_EMBED_TIMEOUT", "5.0"))
_TOP_K_DEFAULT = 5
_MAX_CONTEXT_TOKENS = 1024

_HEADERS = {
    "apikey": _BRAIN_KEY,
    "Authorization": f"Bearer {_BRAIN_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
_TIMEOUT = httpx.Timeout(10.0, connect=3.0)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def _rest(method: str, path: str, **kwargs) -> httpx.Response:
    url = f"{_BRAIN_URL}/rest/v1/{path}"
    r = httpx.request(method, url, headers=_HEADERS, timeout=_TIMEOUT, **kwargs)
    r.raise_for_status()
    return r


def _embed_text(text: str) -> list[float] | None:
    """Embed text via Jan /v1/embeddings (OpenAI-compatible)."""
    url = f"{_JAN_BASE.rstrip('/')}/v1/embeddings"
    try:
        with httpx.Client(timeout=_EMBED_TIMEOUT) as client:
            r = client.post(url, json={
                "model": _EMBED_MODEL,
                "input": text[:2048],
            })
            r.raise_for_status()
            data = r.json()
            return data["data"][0]["embedding"]
    except Exception:
        return None


def _validate_session_input(session_id: str, summary: str = "",
                            decisions: list | None = None,
                            patterns: list | None = None) -> tuple[str, str, list, list]:
    sid = _validate_uuid(session_id)
    if decisions is None:
        decisions = []
    if patterns is None:
        patterns = []
    return sid, summary[:1000], decisions[:20], patterns[:20]


def store_session(session_id: str, summary: str = "",
                  decisions: list | None = None,
                  patterns: list | None = None,
                  project_slug: str = "default") -> dict | None:
    """Store a session with embedding in vault_memories.

    Returns the created memory row, or None on failure.
    """
    try:
        sid, clean_summary, clean_decisions, clean_patterns = _validate_session_input(
            session_id, summary, decisions, patterns
        )
        project_slug = _validate_slug(project_slug)
    except ValueError as e:
        print(f"[ERROR] Invalid input: {e}")
        return None

    text_for_embed = clean_summary[:1000]
    embedding = _embed_text(text_for_embed)

    body = {
        "session_id": sid,
        "project_slug": project_slug,
        "summary": clean_summary,
        "decisions": json.dumps(clean_decisions) if clean_decisions else "[]",
        "patterns": json.dumps(clean_patterns) if clean_patterns else "[]",
    }

    if embedding:
        body["embedding"] = json.dumps(embedding)

    try:
        r = _rest("POST", "vault_memories", json=body)
        row = r.json()[0]
        print(f"[OK] Session stored (id={row['id'][:8]}...)")
        return row
    except Exception as e:
        print(f"[ERROR] Failed to store session: {e}")
        return None


def search_sessions(query: str, top_k: int = _TOP_K_DEFAULT,
                    project_slug: str | None = None) -> list[dict]:
    """Search sessions by embedding similarity. Falls back to BM25 on text summary.

    Returns list of dicts with keys: session_id, summary, decisions, patterns, score.
    """
    query_embedding = _embed_text(query)

    if query_embedding:
        return _search_vector(query_embedding, top_k, project_slug)
    else:
        return _fallback_text_search(query, top_k, project_slug)


def _search_vector(query_embedding: list[float], top_k: int,
                   project_slug: str | None = None) -> list[dict]:
    """Search via Supabase vector similarity."""
    try:
        params = f"order=embedding.l2scale&limit={top_k}"
        if project_slug:
            params += f"&project_slug=eq.{_validate_slug(project_slug)}"

        r = _rest("GET", f"vault_memories?select=*&{params}")
        rows = r.json()
    except Exception:
        return _fallback_all(top_k, project_slug)

    scored = []
    for row in rows:
        emb_json = row.get("embedding")
        if not emb_json:
            continue
        try:
            emb = json.loads(emb_json) if isinstance(emb_json, str) else emb_json
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(emb, list) or len(emb) == 0:
            continue
        score = _cosine_similarity(query_embedding, emb)
        if score > 0.0:
            scored.append((row, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    results = []
    for row, score in scored[:top_k]:
        results.append({
            "session_id": row.get("session_id"),
            "summary": (row.get("summary") or "")[:300],
            "decisions": _safe_json_load(row.get("decisions", "[]")),
            "patterns": _safe_json_load(row.get("patterns", "[]")),
            "score": round(score, 4),
            "created_at": row.get("created_at", ""),
        })
    return results


def _fallback_text_search(query: str, top_k: int,
                          project_slug: str | None = None) -> list[dict]:
    """Fallback: BM25-like search on session summaries."""
    try:
        params = "select=*&order=created_at.desc"
        if project_slug:
            params += f"&project_slug=eq.{_validate_slug(project_slug)}"
        r = _rest("GET", f"vault_memories?{params}")
        rows = r.json()
    except Exception:
        return []

    query_terms = set(query.lower().split())
    if not query_terms:
        return []

    scored = []
    for row in rows:
        summary = (row.get("summary") or "").lower()
        matches = sum(1 for t in query_terms if t in summary)
        if matches > 0:
            score = matches / (len(summary.split()) ** 0.5 + 1)
            scored.append((row, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    results = []
    for row, score in scored[:top_k]:
        results.append({
            "session_id": row.get("session_id"),
            "summary": (row.get("summary") or "")[:300],
            "decisions": _safe_json_load(row.get("decisions", "[]")),
            "patterns": _safe_json_load(row.get("patterns", "[]")),
            "score": round(score, 4),
            "created_at": row.get("created_at", ""),
        })
    return results


def _fallback_all(top_k: int, project_slug: str | None = None) -> list[dict]:
    """Last resort: return most recent sessions."""
    try:
        params = "select=*&order=created_at.desc"
        if project_slug:
            params += f"&project_slug=eq.{_validate_slug(project_slug)}"
        r = _rest("GET", f"vault_memories?{params}&limit={top_k}")
        rows = r.json()
    except Exception:
        return []

    return [
        {
            "session_id": row.get("session_id"),
            "summary": (row.get("summary") or "")[:300],
            "decisions": _safe_json_load(row.get("decisions", "[]")),
            "patterns": _safe_json_load(row.get("patterns", "[]")),
            "score": 0.0,
            "created_at": row.get("created_at", ""),
        }
        for row in rows
    ]


def format_session_context(results: list[dict], max_results: int = 3,
                           max_tokens: int = _MAX_CONTEXT_TOKENS) -> dict:
    """Format session results as a [RELATED_SESSIONS] context block.

    Returns {role: "context", content: [{session_id, summary, decisions, patterns, score}]}
    """
    results = results[:max_results]
    items = []
    total_chars = max_tokens * 4

    for r in results:
        summary = r.get("summary", "")[:300]
        decisions = r.get("decisions", [])
        patterns = r.get("patterns", [])
        score = r.get("score", 0.0)

        content_parts = []
        if summary:
            content_parts.append(summary)
        if decisions:
            dec_str = "; ".join(
                f"{d.get('key', '?')}={d.get('value', '?')}" for d in decisions if isinstance(d, dict)
            )
            if dec_str:
                content_parts.append(f"Decisions: {dec_str}")
        if patterns:
            pat_str = "; ".join(
                f"{p.get('key', '?')}={p.get('value', '?')}" for p in patterns if isinstance(p, dict)
            )
            if pat_str:
                content_parts.append(f"Patterns: {pat_str}")

        full = " | ".join(content_parts)
        max_content_chars = max(0, min(len(full), total_chars // max(1, len(items) + 1)))

        item = {
            "session_id": r.get("session_id", "")[:12],
            "content": full[:max_content_chars].rstrip(),
            "score": score,
        }
        items.append(item)
        total_chars -= len(item["content"])

    return {"role": "context", "content": items}


def _safe_json_load(val: str | list | None) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def cmd_store(session_id: str, summary: str = "",
              decisions: str = "[]", patterns: str = "[]",
              project_slug: str = "default") -> None:
    try:
        dec_list = json.loads(decisions) if isinstance(decisions, str) else decisions
        pat_list = json.loads(patterns) if isinstance(patterns, str) else patterns
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON: {e}")
        return
    store_session(session_id, summary, dec_list, pat_list, project_slug)


def cmd_search(query: str, top_k: int = _TOP_K_DEFAULT,
               project_slug: str | None = None) -> None:
    results = search_sessions(query, top_k, project_slug)
    print(json.dumps(results, indent=2, ensure_ascii=False))


def cmd_context(query: str, top_k: int = 3,
                project_slug: str | None = None) -> None:
    results = search_sessions(query, top_k, project_slug)
    block = format_session_context(results)
    print(json.dumps(block, indent=2, ensure_ascii=False))


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Memory Store")
    sub = parser.add_subparsers(dest="command", required=True)

    p_store = sub.add_parser("store")
    p_store.add_argument("--session-id", required=True)
    p_store.add_argument("--summary", default="")
    p_store.add_argument("--decisions", default="[]", help="JSON array")
    p_store.add_argument("--patterns", default="[]", help="JSON array")
    p_store.add_argument("--project-slug", default="default")

    p_search = sub.add_parser("search")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--top-k", type=int, default=_TOP_K_DEFAULT)
    p_search.add_argument("--project-slug")

    p_context = sub.add_parser("context")
    p_context.add_argument("--query", required=True)
    p_context.add_argument("--top-k", type=int, default=3)
    p_context.add_argument("--project-slug")

    args = parser.parse_args()

    if args.command == "store":
        cmd_store(args.session_id, args.summary, args.decisions, args.patterns, args.project_slug)
    elif args.command == "search":
        cmd_search(args.query, args.top_k, args.project_slug)
    elif args.command == "context":
        cmd_context(args.query, args.top_k, args.project_slug)


if __name__ == "__main__":
    main()
