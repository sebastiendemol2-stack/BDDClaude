"""
Claude Brain — mémoire persistante sessions Claude Code <-> Supabase.

Usage:
    python brain.py load
    python brain.py save --summary "..." --mode full
    python brain.py save --mode autosave
    python brain.py save --mode close

Modes:
    full      — write memory + summary, close session, delete session-id
    autosave  — write memory only, keep session open, NO summary
    close     — close session only (no memory write), delete session-id
"""

import os
import re
import sys
import json
import glob
import uuid
import argparse
import functools
import traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent / "lib"))

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv
from utils import _require_env, _validate_uuid, _validate_slug, _truncate_by_section

load_dotenv(Path(__file__).parent / ".env")

_DEFAULT_DIR = str(Path(__file__).parent.parent)

# Load configuration
CONFIG_PATH = Path(__file__).parent / "config.json"
CONFIG = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}


@functools.lru_cache
def _get_brain_url() -> str:
    return _require_env("BRAIN_URL")

@functools.lru_cache
def _get_brain_key() -> str:
    return _require_env("BRAIN_SERVICE_KEY")

@functools.lru_cache
def _get_headers() -> dict:
    key = _get_brain_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

@functools.lru_cache
def _get_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        CONFIG.get("timeout_seconds", 5.0),
        connect=CONFIG.get("connect_timeout", 2.0)
    )

def _get_limits() -> dict:
    return CONFIG.get("memory_limits", {"preference": 10, "decision": 15, "state": 15, "pattern": 10})

def _get_max_context_chars() -> int:
    return CONFIG.get("context_limits", {}).get("preference_chars", 12000)

VAULT_PATH = Path(os.environ.get("VAULT_PATH", _DEFAULT_DIR))

LOCK_STALE_SECONDS = CONFIG.get("lock_stale_seconds", 300)

# Jan Memory Sync constants
JAN_MEMORY_KEYS = {
    "agent_profile": ["instructions", "constraints", "preferences", "piiMode"],
    "agent_memory": ["shortTerm", "longTerm", "ttl", "maxBytes"],
}


def _sanitize_message(message: str) -> str:
    """Strip API keys and sensitive patterns from log messages."""
    # Supabase JWT (eyJ... base64)
    message = re.sub(r'eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+', '[KEY_REDACTED]', message)
    # OpenAI keys (sk-...)
    message = re.sub(r'sk-[a-zA-Z0-9]{20,}', '[KEY_REDACTED]', message)
    # Bearer tokens
    message = re.sub(r'Bearer\s+[a-zA-Z0-9._-]{20,}', 'Bearer [KEY_REDACTED]', message)
    # Generic API key patterns
    message = re.sub(r'(api[_-]?key|apikey|secret)[=:]\s*["\']?[a-zA-Z0-9_\-]{20,}', r'\1=[REDACTED]', message, flags=re.IGNORECASE)
    return message


def _validate_working_dir(working_dir: str) -> bool:
    """Validate that working_dir is within VAULT_PATH (prevents path traversal)."""
    try:
        resolved = Path(working_dir).resolve()
        vault_resolved = VAULT_PATH.resolve()
        return resolved == vault_resolved or resolved.is_relative_to(vault_resolved)
    except (ValueError, OSError):
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def rest(method: str, path: str, **kwargs) -> httpx.Response:
    url = f"{_get_brain_url()}/rest/v1/{path}"
    r = httpx.request(method, url, headers=_get_headers(), timeout=_get_timeout(), **kwargs)
    r.raise_for_status()
    return r


def log_error(working_dir: str, message: str, **extra) -> None:
    try:
        log_dir = Path(working_dir) / ".brain" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "errors.log"
        ts = datetime.now(timezone.utc).isoformat()
        # Sanitize
        message = _sanitize_message(message)
        sanitized_extra = {k: _sanitize_message(str(v)) if isinstance(v, str) else v for k, v in extra.items()}
        entry = {"timestamp": ts, "message": message, **sanitized_extra}
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
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


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


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
        try:
            content = json.dumps({"pid": os.getpid(), "created_at": datetime.now(timezone.utc).isoformat()})
            os.write(fd, content.encode("utf-8"))
        finally:
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
    slug = _validate_slug(config["slug"])
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
            existing_id = _validate_uuid(session_file.read_text(encoding="utf-8"))
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
    session_id = _validate_uuid(session_id)
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
    return r.is_success


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load(working_dir: str, with_jan: bool = False) -> int:
    if not _validate_working_dir(working_dir):
        print(f"[ERROR] Invalid path: {working_dir} — must be within VAULT_PATH", file=sys.stderr)
        return 1
    try:
        config = load_project_config(working_dir)
        project = get_or_create_project(config, working_dir)
        project_id = _validate_uuid(project["id"])
        session = get_or_resume_session(project_id, working_dir)

        limits = _get_limits()
        memory_by_type: dict[str, list] = {t: [] for t in limits}

        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {}
            for type_, limit in limits.items():
                fut = ex.submit(
                    rest, "GET",
                    f"claude_memory?project_id=eq.{project_id}&type=eq.{type_}"
                    f"&select=key,value,updated_at&order=updated_at.desc&limit={limit}"
                )
                futures[fut] = type_
            for future in as_completed(futures):
                type_ = futures[future]
                try:
                    memory_by_type[type_] = future.result().json()
                except Exception:
                    memory_by_type[type_] = []

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
            f"date: {ts[:10]}",
            "tags: [brain, session]",
            "type: concept",
            "status: active",
            "confidence: high",
            "source_type: extraction",
            "freshness: evergreen",
            "sensitivity: internal",
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

        for type_ in limits:
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

        output_path = VAULT_PATH / "wiki" / "Context" / "context-session.md"
        _atomic_write(output_path, content)

        # Jan memory integration
        if with_jan or os.environ.get("BRAIN_IMPORT_JAN", "").lower() == "true":
            import_jan_memory(working_dir)

        total = sum(len(v) for v in memory_by_type.values())
        print(f"[OK] Context loaded -> {output_path}")
        print(f"  {total} memory entries | session: {session['id'][:8]}...")
        return 0
    except Exception as e:
        log_error(working_dir, f"load error: {traceback.format_exc()}")
        print(f"[ERROR] Load failed: {e}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save(working_dir: str, summary: Optional[str], mode: str) -> int:
    if not _validate_working_dir(working_dir):
        print(f"[ERROR] Invalid path: {working_dir} — must be within VAULT_PATH", file=sys.stderr)
        return 1
    brain_dir = Path(working_dir) / ".brain"
    session_file = brain_dir / "session-id"

    # close mode: tolerate missing session-id
    if mode == "close" and not session_file.exists():
        log_autosave(working_dir, "close skipped: no session-id")
        print("[OK] close skipped: no active session")
        return 0

    if not acquire_lock(working_dir):
        print("[WARN] Could not acquire lock, skipping save")
        return 0

    try:
        config = load_project_config(working_dir)
        project = get_or_create_project(config, working_dir)
        project_id = _validate_uuid(project["id"])
        session = get_or_resume_session(project_id, working_dir)
        session_id = session["id"]

        if mode in ("full", "autosave"):
            # Write standard memory entries
            source = "autosave" if mode == "autosave" else "manual"
            today = datetime.now(timezone.utc).date().isoformat()
            call_upsert_rpc(project_id, "state", "last-session-date", today, source, session_id)

            if mode == "full" and summary:
                call_upsert_rpc(project_id, "state", "last-session-summary", summary, source, session_id)

        log_autosave(working_dir, f"save mode={mode} session={session_id[:8]}")

        if mode in ("full", "close"):
            close_session(session_id, summary if mode == "full" else None, working_dir)
            print(f"[OK] Session closed (mode: {mode}) | {session_id[:8]}...")
            return 0
        else:
            print(f"[OK] Autosave complete | session: {session_id[:8]}... (still open)")
            return 0

    except Exception as e:
        log_error(working_dir, f"save error: {traceback.format_exc()}")
        print(f"[ERROR] Save failed: {e}", file=sys.stderr)
        return 1
    finally:
        release_lock(working_dir)


# ---------------------------------------------------------------------------
# Jan Memory Sync
# ---------------------------------------------------------------------------

def _find_jan_files(working_dir: str) -> dict:
    """Scan for Jan memory files in the vault."""
    result = {
        "subagent_memory": None,
        "copilot_conversations": [],
    }
    base = VAULT_PATH

    # Look for subagent-memory.json in .brain/ or wiki/_system/
    for p in [Path(working_dir) / ".brain", base / "wiki" / "_system"]:
        candidate = p / "subagent-memory.json"
        if candidate.exists():
            try:
                result["subagent_memory"] = json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                pass

    # Look for copilot conversations
    conv_dir = base / "copilot" / "copilot-conversations"
    if conv_dir.exists():
        for f in sorted(conv_dir.glob("*.md")):
            try:
                content = f.read_text(encoding="utf-8")
                result["copilot_conversations"].append({
                    "file": f.name,
                    "content": content,
                })
            except Exception:
                pass

    return result


def _summarize_conversation(content: str) -> str:
    """Extract a brief summary from a copilot conversation markdown file."""
    lines = content.split("\n")
    messages = []
    in_frontmatter = False
    for line in lines:
        if line.strip() == "---":
            in_frontmatter = not in_frontmatter
            continue
        if not in_frontmatter and line.startswith("**user**:"):
            messages.append(line.replace("**user**:", "").strip())
        elif not in_frontmatter and line.startswith("**ai**:"):
            ai_text = line.replace("**ai**:", "").strip()
            if ai_text and not ai_text.startswith("<error"):
                messages.append(f"→ {ai_text[:200]}")
        if len(messages) >= 5:
            break
    return "; ".join(messages) if messages else "(empty conversation)"


def _parse_jan_memory(jan_files: dict) -> dict:
    """Parse Jan memory files into vault-compatible format."""
    memory = {
        "agent_profile": {},
        "agent_memory": {},
        "conversations": [],
        "preferences": [],
        "decisions": [],
    }

    sm = jan_files.get("subagent_memory")
    if sm:
        for key in JAN_MEMORY_KEYS["agent_profile"]:
            if key in sm:
                memory["agent_profile"][key] = sm[key]
        for key in JAN_MEMORY_KEYS["agent_memory"]:
            if key in sm:
                memory["agent_memory"][key] = sm[key]
        if "preferences" in sm:
            memory["preferences"] = sm["preferences"]
        if "decisions" in sm:
            memory["decisions"] = sm["decisions"]

    for conv in jan_files.get("copilot_conversations", []):
        memory["conversations"].append({
            "file": conv["file"],
            "summary": _summarize_conversation(conv["content"]),
        })

    return memory


def _build_jan_section(memory: dict) -> str:
    """Build a Markdown section for Jan memory to append to context-session.md."""
    lines = ["", "# Jan Memory", ""]

    if memory["agent_profile"]:
        lines.append("## Agent Profile")
        for k, v in memory["agent_profile"].items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    if memory["agent_memory"]:
        lines.append("## Agent Memory")
        for k, v in memory["agent_memory"].items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    if memory["preferences"]:
        lines.append("## Preferences (Jan)")
        for p in memory["preferences"][:10]:
            lines.append(f"- {p}")
        lines.append("")

    if memory["decisions"]:
        lines.append("## Decisions (Jan)")
        for d in memory["decisions"][:10]:
            lines.append(f"- {d}")
        lines.append("")

    if memory["conversations"]:
        lines.append("## Recent Jan Conversations")
        for conv in memory["conversations"][:10]:
            lines.append(f"- **{conv['file']}**: {conv['summary']}")
        lines.append("")

    return "\n".join(lines)


def import_jan_memory(working_dir: str) -> bool:
    """Import Jan agent memory into the vault.

    Scans for Jan memory files (subagent-memory.json, copilot conversations),
    parses them into vault-compatible format, appends to context-session.md,
    and syncs to Supabase via existing RPC.
    """
    if not _validate_working_dir(working_dir):
        print(f"[ERROR] Invalid path: {working_dir} — must be within VAULT_PATH", file=sys.stderr)
        return False
    try:
        jan_files = _find_jan_files(working_dir)
        has_any = jan_files["subagent_memory"] is not None or jan_files["copilot_conversations"]

        if not has_any:
            print("[INFO] No Jan memory files found")
            return False

        memory = _parse_jan_memory(jan_files)
        jan_section = _build_jan_section(memory)

        # Append to context-session.md (replace existing Jan section if present)
        output_path = VAULT_PATH / "wiki" / "Context" / "context-session.md"
        if output_path.exists():
            existing = output_path.read_text(encoding="utf-8")
            existing = re.sub(r"(^|\n)# Jan Memory\n.*?(?=\n# |\n\Z|\Z)", "", existing, flags=re.DOTALL)
            content = existing.rstrip() + jan_section
        else:
            content = jan_section

        _atomic_write(output_path, content)

        print(f"[OK] Jan memory imported -> {output_path}")

        # Sync to Supabase via existing RPC if project available
        try:
            config = load_project_config(working_dir)
            project = get_or_create_project(config, working_dir)
            project_id = _validate_uuid(project["id"])
            session = get_or_resume_session(project_id, working_dir)
            session_id = session["id"]

            for pref in memory.get("preferences", []):
                if isinstance(pref, dict) and "key" in pref and "value" in pref:
                    call_upsert_rpc(project_id, "preference", pref["key"], str(pref["value"]), "jan-import", session_id)
            for decision in memory.get("decisions", []):
                if isinstance(decision, dict) and "key" in decision and "value" in decision:
                    call_upsert_rpc(project_id, "decision", decision["key"], str(decision["value"]), "jan-import", session_id)
        except Exception as e:
            log_error(working_dir, f"jan import supabase sync: {e}")

        return True
    except Exception as e:
        log_error(working_dir, f"jan import error: {traceback.format_exc()}")
        print(f"[ERROR] Jan import failed: {e}", file=sys.stderr)
        return False


def _extract_section(content: str, title: str) -> str:
    """Extract a markdown section by title."""
    pattern = rf"#+\s*{re.escape(title)}\s*\n(.*?)(?=\n#+\s|\Z)"
    m = re.search(pattern, content, re.DOTALL)
    return m.group(1).strip()[:500] if m else ""


def _extract_preferences(content: str) -> list:
    """Extract preference-like entries from a markdown context section."""
    prefs = []
    for line in content.split("\n"):
        line = line.strip()
        m = re.match(r"-\s*\[(?:preference|decision|state|pattern)\]\s*(.*?)\s*:\s*(.*)", line)
        if m:
            prefs.append({"key": m.group(1).strip(), "value": m.group(2).strip()})
    return prefs


def export_jan_memory(working_dir: str) -> bool:
    """Export vault context to Jan-compatible format.

    Reads wiki/Context/context-session.md, converts to Jan agent_profile
    + agent_memory format, writes to jan-memory-export.json.
    """
    if not _validate_working_dir(working_dir):
        print(f"[ERROR] Invalid path: {working_dir} — must be within VAULT_PATH", file=sys.stderr)
        return False
    try:
        context_path = VAULT_PATH / "wiki" / "Context" / "context-session.md"
        if not context_path.exists():
            print("[WARN] No context-session.md found to export")
            return False

        content = context_path.read_text(encoding="utf-8")

        profile = {
            "instructions": _extract_section(content, "Persistent Memory"),
            "constraints": "",
            "preferences": _extract_preferences(content),
            "piiMode": "standard",
        }

        memory = {
            "shortTerm": _extract_section(content, "Current Session"),
            "longTerm": _extract_section(content, "Last Session Summary"),
            "ttl": 86400,
            "maxBytes": 512000,
        }

        jan_output = {
            "agent_profile": profile,
            "agent_memory": memory,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "source": "vault-database",
        }

        output_path = Path(working_dir) / "jan-memory-export.json"
        output_path.write_text(json.dumps(jan_output, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[OK] Jan memory exported -> {output_path}")
        return True
    except Exception as e:
        log_error(working_dir, f"jan export error: {traceback.format_exc()}")
        print(f"[ERROR] Jan export failed: {e}", file=sys.stderr)
        return False





# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _validate_payload_size(payload: dict, max_depth: int = 3) -> None:
    """Reject oversized or deeply nested payloads before sending to Supabase."""
    if len(json.dumps(payload, ensure_ascii=False)) > 100000:
        raise ValueError("Payload too large (max 100KB)")
    def _check_depth(obj, depth):
        if depth > max_depth:
            raise ValueError(f"Payload nested too deep (max {max_depth} levels)")
        if isinstance(obj, dict):
            for v in obj.values():
                _check_depth(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                _check_depth(item, depth + 1)
    _check_depth(payload, 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Claude Brain")
    sub = parser.add_subparsers(dest="command", required=True)

    p_load = sub.add_parser("load")
    p_load.add_argument("--dir", default=_DEFAULT_DIR)
    p_load.add_argument("--with-jan", action="store_true", help="Also import Jan memory")

    p_save = sub.add_parser("save")
    p_save.add_argument("--dir", default=_DEFAULT_DIR)
    p_save.add_argument("--summary", default=None)
    p_save.add_argument("--mode", default="full", choices=["full", "autosave", "close"])

    p_import_jan = sub.add_parser("import-jan")
    p_import_jan.add_argument("--dir", required=True)

    p_export_jan = sub.add_parser("export-jan")
    p_export_jan.add_argument("--dir", required=True)

    p_rag = sub.add_parser("rag-retrieve")
    p_rag.add_argument("--query", required=True)
    p_rag.add_argument("--top-k", type=int, default=5)
    p_rag.add_argument("--context", action="store_true",
                       help="Output structured context block")

    p_rag_ctx = sub.add_parser("rag-context")
    p_rag_ctx.add_argument("--query", required=True)
    p_rag_ctx.add_argument("--top-k", type=int, default=3)

    p_events = sub.add_parser("events")
    p_events_sub = p_events.add_subparsers(dest="event_command", required=True)

    p_events_push = p_events_sub.add_parser("push")
    p_events_push.add_argument("--type", required=True, choices=[
        "session_start", "session_end", "message", "feedback", "ingest", "custom"])
    p_events_push.add_argument("--payload", required=True, help="JSON string")
    p_events_push.add_argument("--source", default="jan")
    p_events_push.add_argument("--project-slug")
    p_events_push.add_argument("--session-id")

    p_events_process = p_events_sub.add_parser("process")
    p_events_process.add_argument("--limit", type=int, default=50)

    p_events_status = p_events_sub.add_parser("status")

    # S4 — Memory Store
    p_memories = sub.add_parser("memories")
    p_memories_sub = p_memories.add_subparsers(dest="memory_command", required=True)

    p_mem_store = p_memories_sub.add_parser("store")
    p_mem_store.add_argument("--session-id", required=True)
    p_mem_store.add_argument("--summary", default="")
    p_mem_store.add_argument("--decisions", default="[]")
    p_mem_store.add_argument("--patterns", default="[]")
    p_mem_store.add_argument("--project-slug", default="default")

    p_mem_search = p_memories_sub.add_parser("search")
    p_mem_search.add_argument("--query", required=True)
    p_mem_search.add_argument("--top-k", type=int, default=5)
    p_mem_search.add_argument("--project-slug")

    p_mem_context = p_memories_sub.add_parser("context")
    p_mem_context.add_argument("--query", required=True)
    p_mem_context.add_argument("--top-k", type=int, default=3)
    p_mem_context.add_argument("--project-slug")

    # S5 — Feedback Pipeline
    p_feedback = sub.add_parser("feedback")
    p_feedback_sub = p_feedback.add_subparsers(dest="feedback_command", required=True)

    p_fb_collect = p_feedback_sub.add_parser("collect")
    p_fb_collect.add_argument("--event-id", required=True)
    p_fb_collect.add_argument("--content", required=True)
    p_fb_collect.add_argument("--positive", type=lambda x: x.lower() == "true", required=True)
    p_fb_collect.add_argument("--source", default="jan")

    p_fb_validate = p_feedback_sub.add_parser("validate")
    p_fb_validate.add_argument("--threshold", type=int, default=3)

    p_fb_promote = p_feedback_sub.add_parser("promote")
    p_fb_promote.add_argument("--project-id", required=True)
    p_fb_promote.add_argument("--session-id", required=True)
    p_fb_promote.add_argument("--max", type=int, default=10, dest="max_")

    p_fb_status = p_feedback_sub.add_parser("status")

    # S6 — Graph Extractor
    p_graph = sub.add_parser("graph")
    p_graph_sub = p_graph.add_subparsers(dest="graph_command", required=True)

    p_graph_extract = p_graph_sub.add_parser("extract")
    p_graph_extract.add_argument("--path", default=str(VAULT_PATH / "wiki"))

    p_graph_query = p_graph_sub.add_parser("query")
    p_graph_query.add_argument("--note", required=True)

    p_graph_status = p_graph_sub.add_parser("status")

    args = parser.parse_args()

    if args.command == "load":
        return load(args.dir, with_jan=args.with_jan)
    elif args.command == "save":
        return save(args.dir, args.summary, args.mode)
    elif args.command == "import-jan":
        import_jan_memory(args.dir)
    elif args.command == "export-jan":
        export_jan_memory(args.dir)
    elif args.command == "rag-retrieve":
        from rag_bridge import cmd_rag_retrieve
        cmd_rag_retrieve(args.query, args.top_k, getattr(args, 'context', False))
    elif args.command == "rag-context":
        from rag_bridge import cmd_rag_context
        cmd_rag_context(args.query, args.top_k)
    elif args.command == "events":
        from event_log import push_event, process_events, cmd_status
        if args.event_command == "push":
            import json as _json
            try:
                payload = _json.loads(args.payload)
                _validate_payload_size(payload)
            except _json.JSONDecodeError as e:
                print(f"[ERROR] Invalid JSON payload: {e}")
                return 1
            except ValueError as e:
                print(f"[ERROR] {e}")
                return 1
            push_event(args.type, payload, source=args.source,
                       project_slug=args.project_slug, session_id=args.session_id)
        elif args.event_command == "process":
            process_events(limit=args.limit)
        elif args.event_command == "status":
            cmd_status()
    elif args.command == "memories":
        from memory_store import cmd_store, cmd_search, cmd_context
        if args.memory_command == "store":
            cmd_store(args.session_id, args.summary, args.decisions,
                      args.patterns, args.project_slug)
        elif args.memory_command == "search":
            cmd_search(args.query, args.top_k, args.project_slug)
        elif args.memory_command == "context":
            cmd_context(args.query, args.top_k, args.project_slug)
    elif args.command == "feedback":
        from feedback_pipeline import collect_feedback, validate_feedback, promote_memory, cmd_status as fb_status
        if args.feedback_command == "collect":
            collect_feedback(args.event_id, args.content, args.positive, args.source)
        elif args.feedback_command == "validate":
            validate_feedback(args.threshold)
        elif args.feedback_command == "promote":
            promote_memory(args.project_id, args.session_id, args.max_)
        elif args.feedback_command == "status":
            fb_status()
    elif args.command == "graph":
        from graph_extractor import extract_relations, query_relations, cmd_status as graph_status
        if args.graph_command == "extract":
            extract_relations(args.path)
        elif args.graph_command == "query":
            results = query_relations(args.note)
            print(json.dumps(results, indent=2, ensure_ascii=False))
        elif args.graph_command == "status":
            graph_status()
    return 0

if __name__ == "__main__":
    sys.exit(main())
