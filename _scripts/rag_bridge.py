"""RAG Bridge — retrieval augmenté via embeddings Jan locaux.

Usage (CLI):
    python rag_bridge.py retrieve --query "..." --top-k 5

Usage (lib):
    from rag_bridge import retrieve
    results = retrieve("ma question", top_k=3)
"""

import os
import re
import sys
import json
import math
import time
import glob
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import httpx
from dotenv import load_dotenv
from utils import extract_body

sys.path.insert(0, str(Path(__file__).parent / "lib"))
_ENV_LOADED = load_dotenv(Path(__file__).parent / ".env", override=True)

_JAN_BASE = os.environ.get("JAN_BASE", "http://localhost:1337")
_EMBED_MODEL = os.environ.get("JAN_EMBED_MODEL", "text-embedding-ada-002")
_VAULT_PATH = Path(os.environ.get("VAULT_PATH", str(Path(__file__).parent.parent))).resolve()
_EMBED_TIMEOUT = float(os.environ.get("RAG_EMBED_TIMEOUT", "5.0"))
_TOP_K_DEFAULT = 5


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def chunk_by_sections(markdown_text: str, max_tokens: int = 512) -> list[dict]:
    """Split markdown by ## sections. Each chunk has header + content."""
    body = extract_body(markdown_text)
    if not body.strip():
        return []

    if body.strip() == '---' or not body.strip():
        return []

    sections = re.split(r'\n(?=## )', body)
    chunks = []
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        lines = sec.split('\n')
        first = lines[0].strip() if lines else ""
        header = first.lstrip('#').strip() if first.startswith('#') else ""
        content = sec
        chunk = {"header": header, "content": content, "token_estimate": len(content) // 4}
        chunks.append(chunk)

    if not chunks and body.strip():
        chunks.append({"header": "", "content": body.strip(), "token_estimate": len(body) // 4})

    return chunks


def _load_wiki_chunks(vault_path: Path) -> list[dict]:
    """Load all wiki .md files and chunk them by section."""
    wiki_dir = vault_path / "wiki"
    if not wiki_dir.exists():
        return []

    chunks = []
    for md_file in sorted(wiki_dir.rglob("*.md")):
        rel = md_file.relative_to(vault_path)
        if any(part.startswith("_") for part in rel.parts):
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        file_chunks = chunk_by_sections(text)
        rel_posix = rel.as_posix()
        for c in file_chunks:
            c["path"] = rel_posix
            c["file"] = md_file.name
        chunks.extend(file_chunks)

    return chunks


def _embed_text(text: str, base_url: str = _JAN_BASE) -> list[float] | None:
    """Embed text via Jan /v1/embeddings (OpenAI-compatible)."""
    url = f"{base_url.rstrip('/')}/v1/embeddings"
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


def _log_retrieval(query: str, results: list[dict], latency_ms: float,
                   fallback: bool, vault_path: Path) -> None:
    log_dir = vault_path / "wiki" / "_system" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = log_dir / f"rag_{today}.jsonl"

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "top_k": len(results),
        "latency_ms": round(latency_ms, 1),
        "fallback": fallback,
        "results": [
            {"path": r["path"], "score": round(r["score"], 4), "header": r["header"]}
            for r in results
        ],
    }
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def retrieve(query: str, top_k: int = _TOP_K_DEFAULT,
             vault_path: Optional[Path] = None) -> list[dict]:
    """Retrieve top-k wiki chunks relevant to query via embedding similarity.

    Returns list of dicts with keys: path, header, content, score.
    """
    if vault_path is None:
        vault_path = _VAULT_PATH

    start = time.monotonic()
    fallback_used = False

    chunks = _load_wiki_chunks(vault_path)
    if not chunks:
        return []

    query_embedding = _embed_text(query)
    if query_embedding is None:
        fallback_used = True
        return _fallback_bm25(query, chunks, top_k, vault_path)

    chunk_embeddings = []
    for c in chunks:
        emb = _embed_text(c["content"])
        if emb is None:
            continue
        chunk_embeddings.append((c, emb))

    if not chunk_embeddings:
        return []

    scored = []
    for c, emb in chunk_embeddings:
        score = _cosine_similarity(query_embedding, emb)
        if score > 0.0:
            scored.append((c, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:top_k]

    results = [
        {"path": c["path"], "header": c["header"],
         "content": c["content"][:500], "score": s}
        for c, s in top
    ]

    latency = (time.monotonic() - start) * 1000
    _log_retrieval(query, results, latency, fallback_used, vault_path)

    return results


def _fallback_bm25(query: str, chunks: list[dict], top_k: int,
                   vault_path: Path) -> list[dict]:
    """Simple BM25-like fallback when embeddings unavailable."""
    query_terms = set(query.lower().split())
    if not query_terms:
        return []

    scored = []
    for c in chunks:
        body_lower = c["content"].lower()
        matches = sum(1 for t in query_terms if t in body_lower)
        if matches > 0:
            score = matches / (len(body_lower.split()) ** 0.5 + 1)
            scored.append((c, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:top_k]

    results = [
        {"path": c["path"], "header": c["header"],
         "content": c["content"][:500], "score": s}
        for c, s in top
    ]

    latency = 0.0
    _log_retrieval(query, results, latency, True, vault_path)
    return results


def format_context(results: list[dict], max_results: int = 3,
                   max_tokens: int = 512) -> dict:
    """Format retrieve results as a structured context block for LLM injection.

    Returns {role: "context", content: [{source, section, content, score}]}
    Truncates total content to max_tokens.
    """
    results = results[:max_results]
    items = []
    total_chars = max_tokens * 4

    for r in results:
        source = r.get("path", "unknown")
        section = r.get("header", "")
        score = round(r.get("score", 0.0), 4)
        content = r.get("content", "")

        max_content_chars = max(0, min(len(content), total_chars // max(1, len(items) + 1)))
        item = {
            "source": source,
            "section": section,
            "content": content[:max_content_chars].rstrip(),
            "score": score,
        }
        items.append(item)
        total_chars -= len(item["content"])

    return {"role": "context", "content": items}


def _safe_print(obj) -> None:
    """Print JSON, falling back to utf-8 bytes if stdout encoding can't handle chars."""
    out = json.dumps(obj, indent=2, ensure_ascii=False)
    try:
        print(out)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((out + "\n").encode("utf-8", errors="replace"))


def cmd_rag_retrieve(query: str, top_k: int = _TOP_K_DEFAULT,
                     context: bool = False) -> None:
    results = retrieve(query, top_k)
    if context:
        _safe_print(format_context(results))
    else:
        _safe_print(results)


def cmd_rag_context(query: str, top_k: int = _TOP_K_DEFAULT) -> None:
    results = retrieve(query, top_k)
    _safe_print(format_context(results))


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="RAG Bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    p_retrieve = sub.add_parser("retrieve")
    p_retrieve.add_argument("--query", required=True)
    p_retrieve.add_argument("--top-k", type=int, default=_TOP_K_DEFAULT)
    p_retrieve.add_argument("--context", action="store_true",
                            help="Output structured context block instead of raw results")

    p_context = sub.add_parser("context")
    p_context.add_argument("--query", required=True)
    p_context.add_argument("--top-k", type=int, default=_TOP_K_DEFAULT)

    args = parser.parse_args()

    if args.command == "retrieve":
        cmd_rag_retrieve(args.query, args.top_k, args.context)
    elif args.command == "context":
        cmd_rag_context(args.query, args.top_k)


if __name__ == "__main__":
    main()
