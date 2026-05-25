"""
M8 — Tenant export/import pipeline.

Usage:
    python tenant_bundle.py export --tenant <slug> --out <dir>
    python tenant_bundle.py import --tenant <slug> --in <dir> [--on-conflict skip|overwrite]

Bundle layout (v1):
    <dir>/
        manifest.json
        tables/
            vault_sections.jsonl
            vault_entries.jsonl
        markdown/
            wiki/<folder>/<slug>.md

Scope (v1):
- Exports vault_sections + vault_entries scoped to the source tenant.
- vault_chunks / vault_embeddings / snapshots are deferred to v2 because they
  are recomputable from content and we want a small auditable v1.
- Import requires the target tenant to already exist (use tenant-create).
- Cross-tenant collisions on vault_entries.obsidian_path are reported. The
  global uniqueness constraint stays in place until the M8 acceptance gate
  passes, so duplicate paths are refused unless --on-conflict=overwrite.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add local lib to path (same convention as sync.py)
sys.path.insert(0, str(Path(__file__).parent / "lib"))

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

SCHEMA_VERSION = "1.0.0"
EXPORTED_TABLES = ("vault_sections", "vault_entries")
ON_CONFLICT_STRATEGIES = ("skip", "overwrite")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.stderr.write(
            f"[tenant_bundle] Missing required environment variable: {name}\n"
            f"  Set it in _scripts/.env or your shell environment.\n"
        )
        raise SystemExit(2)
    return value


def _headers(supabase_key: str, *, return_repr: bool = False) -> dict:
    h = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }
    if return_repr:
        h["Prefer"] = "return=representation"
    return h


def resolve_tenant_id(supabase_url: str, supabase_key: str, slug: str) -> str:
    """Look up a tenant uuid by slug. Raises if absent or inactive."""
    url = f"{supabase_url}/rest/v1/vault_tenants?select=id,status&slug=eq.{slug}&limit=1"
    r = httpx.get(url, headers=_headers(supabase_key), timeout=10.0)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise RuntimeError(f'Tenant "{slug}" not found. Create it first with tenant-create.')
    if rows[0].get("status") != "active":
        raise RuntimeError(f'Tenant "{slug}" is not active (status={rows[0].get("status")}).')
    return rows[0]["id"]


def fetch_tenant_rows(supabase_url: str, supabase_key: str, table: str, tenant_id: str) -> list[dict]:
    """Page through a table for a tenant. Returns all rows."""
    rows: list[dict] = []
    limit = 1000
    offset = 0
    while True:
        url = (
            f"{supabase_url}/rest/v1/{table}"
            f"?select=*&tenant_id=eq.{tenant_id}&limit={limit}&offset={offset}"
        )
        r = httpx.get(url, headers=_headers(supabase_key), timeout=30.0)
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def export_markdown(out_dir: Path, entries: list[dict]) -> int:
    """Reconstruct markdown files from vault_entries rows. Returns count written."""
    count = 0
    for entry in entries:
        obs_path = entry.get("obsidian_path")
        content = entry.get("content")
        if not obs_path or content is None:
            continue
        # Mirror obsidian_path exactly so the bundle is round-trippable into a vault.
        target = out_dir / obs_path
        # Refuse escapes outside the bundle root.
        if not target.resolve().is_relative_to(out_dir.resolve()):
            raise ValueError(f"Refusing unsafe path in obsidian_path: {obs_path!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        count += 1
    return count


def cmd_export(tenant_slug: str, out_dir: Path) -> dict:
    supabase_url = _require_env("SUPABASE_URL")
    supabase_key = _require_env("SUPABASE_SERVICE_ROLE_KEY")

    tenant_id = resolve_tenant_id(supabase_url, supabase_key, tenant_slug)

    out_dir.mkdir(parents=True, exist_ok=True)
    table_counts: dict[str, int] = {}
    entries: list[dict] = []

    for table in EXPORTED_TABLES:
        rows = fetch_tenant_rows(supabase_url, supabase_key, table, tenant_id)
        write_jsonl(out_dir / "tables" / f"{table}.jsonl", rows)
        table_counts[table] = len(rows)
        if table == "vault_entries":
            entries = rows

    markdown_count = export_markdown(out_dir / "markdown", entries)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "tenant_slug": tenant_slug,
            "tenant_id": tenant_id,
            "supabase_url": supabase_url,
        },
        "tables": table_counts,
        "markdown_files": markdown_count,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def _strip_server_fields(row: dict) -> dict:
    """Drop fields the destination server must regenerate (id, audit timestamps)."""
    return {k: v for k, v in row.items() if k not in ("id", "created_at", "updated_at")}


def _detect_entry_conflicts(
    supabase_url: str,
    supabase_key: str,
    entries: list[dict],
    target_tenant_id: str,
) -> list[dict]:
    """Return entries whose obsidian_path already exists in another tenant.

    Until (tenant_id, obsidian_path) replaces the global unique on obsidian_path,
    such rows cannot be imported without overwriting the existing one.
    """
    if not entries:
        return []
    conflicts: list[dict] = []
    paths = [e["obsidian_path"] for e in entries if e.get("obsidian_path")]
    # Batch by 50 paths to keep URLs short.
    for i in range(0, len(paths), 50):
        batch = paths[i : i + 50]
        in_clause = ",".join(f'"{p}"' for p in batch)
        url = (
            f"{supabase_url}/rest/v1/vault_entries"
            f"?select=obsidian_path,tenant_id&obsidian_path=in.({in_clause})"
        )
        r = httpx.get(url, headers=_headers(supabase_key), timeout=30.0)
        r.raise_for_status()
        for existing in r.json():
            if existing.get("tenant_id") != target_tenant_id:
                conflicts.append(existing)
    return conflicts


def _upsert_rows(
    supabase_url: str,
    supabase_key: str,
    table: str,
    rows: list[dict],
    on_conflict_column: str,
    strategy: str,
) -> int:
    """Upsert rows in batches. Returns count attempted (network success != row write)."""
    if not rows:
        return 0
    prefer = "resolution=merge-duplicates" if strategy == "overwrite" else "resolution=ignore-duplicates"
    headers = {**_headers(supabase_key, return_repr=True), "Prefer": prefer}
    url = f"{supabase_url}/rest/v1/{table}?on_conflict={on_conflict_column}"
    total = 0
    for i in range(0, len(rows), 100):
        batch = rows[i : i + 100]
        r = httpx.post(url, headers=headers, json=batch, timeout=60.0)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Upsert into {table} failed [{r.status_code}]: {r.text[:200]}")
        total += len(batch)
    return total


def cmd_import(tenant_slug: str, in_dir: Path, on_conflict: str) -> dict:
    if on_conflict not in ON_CONFLICT_STRATEGIES:
        raise ValueError(f"--on-conflict must be one of {ON_CONFLICT_STRATEGIES}")

    supabase_url = _require_env("SUPABASE_URL")
    supabase_key = _require_env("SUPABASE_SERVICE_ROLE_KEY")

    manifest_path = in_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Bundle schema_version {manifest.get('schema_version')!r} "
            f"!= expected {SCHEMA_VERSION!r}"
        )

    target_tenant_id = resolve_tenant_id(supabase_url, supabase_key, tenant_slug)

    sections = read_jsonl(in_dir / "tables" / "vault_sections.jsonl")
    entries = read_jsonl(in_dir / "tables" / "vault_entries.jsonl")

    # Rewrite tenant_id and strip server-managed fields.
    rewritten_sections = [
        {**_strip_server_fields(s), "tenant_id": target_tenant_id} for s in sections
    ]
    rewritten_entries = [
        {**_strip_server_fields(e), "tenant_id": target_tenant_id} for e in entries
    ]

    conflicts = _detect_entry_conflicts(supabase_url, supabase_key, rewritten_entries, target_tenant_id)
    blocking_conflicts = [c for c in conflicts if on_conflict != "overwrite"]
    if blocking_conflicts:
        raise RuntimeError(
            f"{len(blocking_conflicts)} obsidian_path collision(s) with other tenants. "
            f"Re-run with --on-conflict=overwrite to replace them, or rename in source."
        )

    # Sections come first (vault_entries.section_slug may FK to them in future schemas).
    sections_written = _upsert_rows(
        supabase_url, supabase_key, "vault_sections", rewritten_sections,
        on_conflict_column="slug", strategy=on_conflict,
    )
    entries_written = _upsert_rows(
        supabase_url, supabase_key, "vault_entries", rewritten_entries,
        on_conflict_column="obsidian_path", strategy=on_conflict,
    )

    return {
        "target_tenant_slug": tenant_slug,
        "target_tenant_id": target_tenant_id,
        "imported": {
            "vault_sections": sections_written,
            "vault_entries": entries_written,
        },
        "cross_tenant_conflicts": len(conflicts),
        "on_conflict": on_conflict,
        "source_manifest": {
            "schema_version": manifest.get("schema_version"),
            "source_tenant_slug": manifest.get("source", {}).get("tenant_slug"),
            "exported_at": manifest.get("exported_at"),
        },
    }


def _parse_argv(argv: list[str]) -> dict:
    """Tiny arg parser. Returns dict with command + options."""
    if not argv:
        raise SystemExit(_USAGE)
    cmd = argv[0]
    if cmd not in ("export", "import"):
        raise SystemExit(_USAGE)
    opts: dict = {"cmd": cmd, "on_conflict": "skip"}
    i = 1
    while i < len(argv):
        token = argv[i]
        if token == "--tenant" and i + 1 < len(argv):
            opts["tenant"] = argv[i + 1]; i += 2; continue
        if token == "--out" and i + 1 < len(argv):
            opts["out"] = argv[i + 1]; i += 2; continue
        if token == "--in" and i + 1 < len(argv):
            opts["in"] = argv[i + 1]; i += 2; continue
        if token == "--on-conflict" and i + 1 < len(argv):
            opts["on_conflict"] = argv[i + 1]; i += 2; continue
        raise SystemExit(f"Unknown or malformed argument near: {token}\n\n{_USAGE}")
    if "tenant" not in opts:
        raise SystemExit("--tenant <slug> is required\n\n" + _USAGE)
    if cmd == "export" and "out" not in opts:
        raise SystemExit("--out <dir> is required for export\n\n" + _USAGE)
    if cmd == "import" and "in" not in opts:
        raise SystemExit("--in <dir> is required for import\n\n" + _USAGE)
    return opts


_USAGE = (
    "Usage:\n"
    "  python tenant_bundle.py export --tenant <slug> --out <dir>\n"
    "  python tenant_bundle.py import --tenant <slug> --in <dir> [--on-conflict skip|overwrite]\n"
)


if __name__ == "__main__":
    opts = _parse_argv(sys.argv[1:])
    if opts["cmd"] == "export":
        manifest = cmd_export(opts["tenant"], Path(opts["out"]))
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    else:
        report = cmd_import(opts["tenant"], Path(opts["in"]), opts["on_conflict"])
        print(json.dumps(report, indent=2, ensure_ascii=False))
