"""RAG Bridge — retrieval augmenté via embeddings Jan locaux.

Usage (CLI):
    python rag_bridge.py retrieve --query "..." --top-k 5
    python rag_bridge.py answer --query "..." --top-k 5
    python rag_bridge.py answer --query "..." --top-k 5 --no-log
    python rag_bridge.py answer --query "..." --embed-base-url http://127.0.0.1:1338

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
import http.client
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from utils import extract_body

sys.path.insert(0, str(Path(__file__).parent / "lib"))
_ENV_LOADED = load_dotenv(Path(__file__).parent / ".env", override=True)

_JAN_BASE = os.environ.get("JAN_BASE_URL") or os.environ.get("JAN_BASE", "http://localhost:1337")
_JAN_EMBED_BASE = (
    os.environ.get("JAN_EMBED_BASE_URL")
    or os.environ.get("JAN_EMBED_BASE")
    or _JAN_BASE
)
_JAN_API_KEY = os.environ.get("JAN_API_KEY", "secret-key-123")
_JAN_EMBED_API_KEY = os.environ.get("JAN_EMBED_API_KEY", _JAN_API_KEY)
_JAN_CHAT_MODEL = os.environ.get("JAN_CHAT_MODEL", "")
_EMBED_MODEL = os.environ.get("JAN_EMBED_MODEL", "sentence-transformer-mini")
_VAULT_PATH = Path(os.environ.get("VAULT_PATH", str(Path(__file__).parent.parent))).resolve()
_EMBED_TIMEOUT = float(os.environ.get("RAG_EMBED_TIMEOUT", "5.0"))
_CHAT_TIMEOUT = float(os.environ.get("RAG_CHAT_TIMEOUT", "180.0"))
_TOP_K_DEFAULT = 5


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _jan_headers(api_key: str | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = api_key if api_key is not None else _JAN_API_KEY
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request_jan_json(method: str, base_url: str, path: str,
                      payload: dict | None = None,
                      api_key: str | None = None,
                      timeout: float | None = None) -> dict:
    """Call Jan with stdlib HTTP; some Jan builds hang with httpx/requests."""
    parsed = urlparse(base_url.rstrip("/"))
    scheme = parsed.scheme or "http"
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if scheme == "https" else 80)
    conn_cls = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
    body = None
    headers = _jan_headers(api_key)

    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Length"] = str(len(body))

    request_timeout = timeout if timeout is not None else (
        _CHAT_TIMEOUT if method == "POST" else _EMBED_TIMEOUT
    )
    conn = conn_cls(host, port, timeout=request_timeout)
    try:
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        text = response.read().decode("utf-8", errors="replace")
        if response.status >= 400:
            raise RuntimeError(f"Jan returned {response.status}: {text}")
        return json.loads(text) if text.strip() else {}
    finally:
        conn.close()


def _get_jan_json(base_url: str, path: str,
                  api_key: str | None = None,
                  timeout: float | None = None) -> dict:
    return _request_jan_json("GET", base_url, path, api_key=api_key, timeout=timeout)


def _post_jan_json(base_url: str, path: str, payload: dict,
                   api_key: str | None = None,
                   timeout: float | None = None) -> dict:
    return _request_jan_json(
        "POST", base_url, path, payload, api_key=api_key, timeout=timeout
    )


def _select_chat_model(base_url: str = _JAN_BASE) -> str:
    """Pick a usable Jan chat model, preferring explicit env configuration."""
    if _JAN_CHAT_MODEL:
        return _JAN_CHAT_MODEL

    try:
        models = _get_jan_json(base_url, "/v1/models").get("data", [])
    except Exception:
        return ""

    for model in models:
        if model.get("owned_by") != "remote" and model.get("id"):
            return str(model["id"])
    return str(models[0]["id"]) if models else ""


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


def _embed_text(text: str, base_url: str = _JAN_EMBED_BASE) -> list[float] | None:
    """Embed text via Jan /v1/embeddings (OpenAI-compatible)."""
    try:
        data = _post_jan_json(
            base_url,
            "/v1/embeddings",
            {"model": _EMBED_MODEL, "input": text[:2048]},
            api_key=_JAN_EMBED_API_KEY,
            timeout=_EMBED_TIMEOUT,
        )
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
             vault_path: Optional[Path] = None, log: bool = True,
             embed_base_url: str | None = None) -> list[dict]:
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

    query_embedding = _embed_text(query, embed_base_url or _JAN_EMBED_BASE)
    if query_embedding is None:
        fallback_used = True
        return _fallback_bm25(query, chunks, top_k, vault_path, log=log)

    chunk_embeddings = []
    for c in chunks:
        emb = _embed_text(c["content"], embed_base_url or _JAN_EMBED_BASE)
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
    if log:
        _log_retrieval(query, results, latency, fallback_used, vault_path)

    return results


def _fallback_bm25(query: str, chunks: list[dict], top_k: int,
                   vault_path: Path, log: bool = True) -> list[dict]:
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
    if log:
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


def generate_answer(query: str, results: list[dict], base_url: str = _JAN_BASE,
                    model: str | None = None, max_tokens: int = 512) -> dict:
    """Generate a grounded answer with Jan's OpenAI-compatible chat API."""
    selected_model = model or _select_chat_model(base_url)
    if not selected_model:
        raise RuntimeError("No Jan chat model available. Start Jan and load a local model.")

    context = format_context(results, max_results=len(results), max_tokens=1200)
    context_text = "\n\n".join(
        [
            f"Source: {item['source']} | Section: {item['section']} | Score: {item['score']}\n{item['content']}"
            for item in context["content"]
        ]
    )
    if not context_text.strip():
        context_text = "No matching vault context was found."

    payload = {
        "model": selected_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Tu es un assistant RAG local. Reponds uniquement avec le contexte fourni. "
                    "Si le contexte ne contient pas l'information, dis que la donnee manque. "
                    "Cite les chemins de sources pertinents."
                ),
            },
            {
                "role": "user",
                "content": f"Question:\n{query}\n\nContexte vault:\n{context_text}",
            },
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }

    data = _post_jan_json(base_url, "/v1/chat/completions", payload)

    message = data.get("choices", [{}])[0].get("message", {})
    content = message.get("content", "")
    if not content and message.get("reasoning_content"):
        content = (
            "Jan a retourne du raisonnement interne sans reponse finale. "
            "Augmente RAG_CHAT_TIMEOUT/max_tokens ou utilise un modele non-reasoning."
        )
    return {
        "answer": content,
        "model": selected_model,
        "sources": format_context(results)["content"],
        "usage": data.get("usage", {}),
    }


def _safe_print(obj) -> None:
    """Print JSON, falling back to utf-8 bytes if stdout encoding can't handle chars."""
    out = json.dumps(obj, indent=2, ensure_ascii=False)
    try:
        print(out)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((out + "\n").encode("utf-8", errors="replace"))


def cmd_rag_retrieve(query: str, top_k: int = _TOP_K_DEFAULT,
                     context: bool = False, no_log: bool = False,
                     embed_base_url: str | None = None) -> None:
    results = retrieve(query, top_k, log=not no_log, embed_base_url=embed_base_url)
    if context:
        _safe_print(format_context(results))
    else:
        _safe_print(results)


def cmd_rag_context(query: str, top_k: int = _TOP_K_DEFAULT,
                    no_log: bool = False,
                    embed_base_url: str | None = None) -> None:
    results = retrieve(query, top_k, log=not no_log, embed_base_url=embed_base_url)
    _safe_print(format_context(results))


def cmd_rag_answer(query: str, top_k: int = _TOP_K_DEFAULT,
                   model: str | None = None, no_log: bool = False,
                   embed_base_url: str | None = None) -> None:
    results = retrieve(query, top_k, log=not no_log, embed_base_url=embed_base_url)
    _safe_print(generate_answer(query, results, model=model))


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="RAG Bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    p_retrieve = sub.add_parser("retrieve")
    p_retrieve.add_argument("--query", required=True)
    p_retrieve.add_argument("--top-k", type=int, default=_TOP_K_DEFAULT)
    p_retrieve.add_argument("--context", action="store_true",
                            help="Output structured context block instead of raw results")
    p_retrieve.add_argument("--no-log", action="store_true",
                            help="Do not write retrieval logs under wiki/_system/logs")
    p_retrieve.add_argument("--embed-base-url", default=None,
                            help="Dedicated Jan/llama.cpp embeddings endpoint")

    p_context = sub.add_parser("context")
    p_context.add_argument("--query", required=True)
    p_context.add_argument("--top-k", type=int, default=_TOP_K_DEFAULT)
    p_context.add_argument("--no-log", action="store_true",
                           help="Do not write retrieval logs under wiki/_system/logs")
    p_context.add_argument("--embed-base-url", default=None,
                           help="Dedicated Jan/llama.cpp embeddings endpoint")

    p_answer = sub.add_parser("answer")
    p_answer.add_argument("--query", required=True)
    p_answer.add_argument("--top-k", type=int, default=_TOP_K_DEFAULT)
    p_answer.add_argument("--model", default=None,
                          help="Jan chat model id. Defaults to JAN_CHAT_MODEL or first local Jan model.")
    p_answer.add_argument("--no-log", action="store_true",
                          help="Do not write retrieval logs under wiki/_system/logs")
    p_answer.add_argument("--embed-base-url", default=None,
                          help="Dedicated Jan/llama.cpp embeddings endpoint")

    args = parser.parse_args()

    if args.command == "retrieve":
        cmd_rag_retrieve(
            args.query, args.top_k, args.context, args.no_log, args.embed_base_url
        )
    elif args.command == "context":
        cmd_rag_context(args.query, args.top_k, args.no_log, args.embed_base_url)
    elif args.command == "answer":
        cmd_rag_answer(
            args.query, args.top_k, args.model, args.no_log, args.embed_base_url
        )


if __name__ == "__main__":
    main()
