"""
M8 Task 11 — End-to-end validation of multi-tenant isolation.

Scenario:
    1. Create tenants A and B (idempotent — re-uses existing tenants if found).
    2. Seed each tenant with one section + one entry.
    3. Verify reads scoped to A see A's row only; same for B.
    4. Export tenant A to a bundle, import into B with --on-conflict=overwrite.
    5. Verify B now contains both rows (its original + the imported A row).
    6. Run query_vector_hybrid with tenant_id filter and assert no leakage.
    7. Clean up everything created during the run.

This script is destructive on its test tenants but never touches `personal`.
Default test tenant slugs are `e2e-alpha` and `e2e-beta`.

Usage:
    python tenant_e2e_validation.py [--keep] [--source-slug alpha] [--target-slug beta]

Exit codes:
    0  — all assertions pass
    1  — one or more assertions failed (report is printed before exit)
    2  — environment / connection error
"""

import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

import tenant_bundle as tb  # noqa: E402


SOURCE_SLUG_DEFAULT = "e2e-alpha"
TARGET_SLUG_DEFAULT = "e2e-beta"


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.stderr.write(f"[e2e] Missing env var: {name}\n")
        raise SystemExit(2)
    return value


def _headers(key: str, *, repr_: bool = False) -> dict:
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if repr_:
        h["Prefer"] = "return=representation"
    return h


def ensure_tenant(url: str, key: str, slug: str) -> str:
    """Idempotent tenant creation. Returns tenant uuid."""
    existing = httpx.get(
        f"{url}/rest/v1/vault_tenants?select=id&slug=eq.{slug}",
        headers=_headers(key), timeout=10.0,
    )
    existing.raise_for_status()
    rows = existing.json()
    if rows:
        return rows[0]["id"]

    created = httpx.post(
        f"{url}/rest/v1/vault_tenants",
        headers=_headers(key, repr_=True),
        json={
            "slug": slug,
            "name": f"E2E test tenant {slug}",
            "status": "active",
            "metadata": {"created_by": "tenant_e2e_validation"},
        },
        timeout=10.0,
    )
    if created.status_code not in (200, 201):
        raise RuntimeError(f"ensure_tenant({slug}) failed [{created.status_code}]: {created.text[:200]}")
    return created.json()[0]["id"]


def seed_entry(url: str, key: str, tenant_id: str, obsidian_path: str, title: str, content: str) -> str:
    """Upsert one vault_entries row for a tenant. Returns its id."""
    payload = {
        "tenant_id": tenant_id,
        "obsidian_path": obsidian_path,
        "title": title,
        "content": content,
        "tags": [],
        "type": "note",
        "status": "active",
        "section_slug": "notes-perso",
    }
    r = httpx.post(
        f"{url}/rest/v1/vault_entries?on_conflict=obsidian_path",
        headers={**_headers(key, repr_=True), "Prefer": "resolution=merge-duplicates,return=representation"},
        json=payload, timeout=15.0,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"seed_entry failed [{r.status_code}]: {r.text[:200]}")
    return r.json()[0]["id"]


def count_entries(url: str, key: str, tenant_id: str) -> int:
    r = httpx.get(
        f"{url}/rest/v1/vault_entries?select=id&tenant_id=eq.{tenant_id}",
        headers={**_headers(key), "Prefer": "count=exact"},
        timeout=10.0,
    )
    r.raise_for_status()
    return len(r.json())


def query_vector_hybrid(url: str, key: str, question: str, tenant_id: str, limit: int = 10) -> list[dict]:
    """Call the RPC with a tenant filter and return result rows."""
    r = httpx.post(
        f"{url}/rest/v1/rpc/query_vector_hybrid",
        headers=_headers(key),
        json={"req": {"query": question, "tenant_id": tenant_id, "limit": limit}},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json() or []


def delete_entry(url: str, key: str, entry_id: str) -> None:
    httpx.delete(
        f"{url}/rest/v1/vault_entries?id=eq.{entry_id}",
        headers=_headers(key), timeout=10.0,
    )


def delete_tenant(url: str, key: str, tenant_id: str) -> None:
    """Best-effort tenant deletion. Cascades drop members; entries are wiped first."""
    httpx.delete(
        f"{url}/rest/v1/vault_entries?tenant_id=eq.{tenant_id}",
        headers=_headers(key), timeout=15.0,
    )
    httpx.delete(
        f"{url}/rest/v1/vault_tenants?id=eq.{tenant_id}",
        headers=_headers(key), timeout=10.0,
    )


def run(*, source_slug: str, target_slug: str, keep: bool) -> dict:
    url = _require_env("SUPABASE_URL")
    key = _require_env("SUPABASE_SERVICE_ROLE_KEY")

    findings: list[str] = []
    created_entries: list[str] = []
    created_tenants: list[str] = []

    try:
        # 1. Provision two tenants.
        a_id = ensure_tenant(url, key, source_slug)
        b_id = ensure_tenant(url, key, target_slug)
        created_tenants = [a_id, b_id]

        # 2. Seed unique entries per tenant. Suffix obsidian_path with the slug so the
        # global UNIQUE(obsidian_path) doesn't collide across runs of this script.
        marker = uuid.uuid4().hex[:8]
        a_path = f"wiki/Context/e2e-{source_slug}-{marker}.md"
        b_path = f"wiki/Context/e2e-{target_slug}-{marker}.md"
        a_entry = seed_entry(url, key, a_id, a_path, "E2E A", "alpha note body")
        b_entry = seed_entry(url, key, b_id, b_path, "E2E B", "beta note body")
        created_entries = [a_entry, b_entry]

        # 3. Isolation: tenant-scoped reads must not leak.
        a_count = count_entries(url, key, a_id)
        b_count = count_entries(url, key, b_id)
        if a_count != 1:
            findings.append(f"tenant A count != 1 (got {a_count})")
        if b_count != 1:
            findings.append(f"tenant B count != 1 (got {b_count})")

        # 4. Export A to a temp bundle, import into B with overwrite.
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = Path(tmp) / "bundle"
            # cmd_export reads env again -- inject our service role to ensure it sees it.
            os.environ["SUPABASE_URL"] = url
            os.environ["SUPABASE_SERVICE_ROLE_KEY"] = key
            manifest = tb.cmd_export(source_slug, bundle_dir)
            if manifest["tables"]["vault_entries"] < 1:
                findings.append("export produced 0 entries for tenant A")
            report = tb.cmd_import(target_slug, bundle_dir, on_conflict="overwrite")
            if report["imported"]["vault_entries"] < 1:
                findings.append("import wrote 0 entries into tenant B")

        # 5. Tenant B must now own both its original entry and the imported one.
        b_count_after = count_entries(url, key, b_id)
        if b_count_after < 2:
            findings.append(f"tenant B count after import = {b_count_after}, expected >= 2")

        # Track imported row for cleanup.
        find_url = (
            f"{url}/rest/v1/vault_entries?select=id&tenant_id=eq.{b_id}"
            f"&obsidian_path=eq.{a_path}"
        )
        r = httpx.get(find_url, headers=_headers(key), timeout=10.0)
        r.raise_for_status()
        for row in r.json():
            created_entries.append(row["id"])

        # 6. RPC isolation: query_vector_hybrid with tenant filter must not surface
        #    rows owned by the other tenant.
        rpc_a = query_vector_hybrid(url, key, "alpha note", a_id, limit=5)
        rpc_b = query_vector_hybrid(url, key, "alpha note", b_id, limit=5)
        a_titles = {r.get("title") for r in rpc_a}
        b_titles = {r.get("title") for r in rpc_b}
        # Imported copy lives under tenant B, so B may legitimately surface it.
        # What must never happen: tenant A surfacing tenant B's *original* note.
        if "E2E B" in a_titles:
            findings.append("query_vector_hybrid leaked tenant B row into tenant A scope")

        return {
            "ok": not findings,
            "findings": findings,
            "tenants": {source_slug: a_id, target_slug: b_id},
            "isolation_counts": {"A": a_count, "B_before": b_count, "B_after": b_count_after},
        }
    finally:
        if not keep:
            for eid in created_entries:
                delete_entry(url, key, eid)
            for tid in created_tenants:
                delete_tenant(url, key, tid)


def _parse_argv(argv: list[str]) -> dict:
    opts = {"keep": False, "source_slug": SOURCE_SLUG_DEFAULT, "target_slug": TARGET_SLUG_DEFAULT}
    i = 0
    while i < len(argv):
        token = argv[i]
        if token == "--keep":
            opts["keep"] = True; i += 1
        elif token == "--source-slug" and i + 1 < len(argv):
            opts["source_slug"] = argv[i + 1]; i += 2
        elif token == "--target-slug" and i + 1 < len(argv):
            opts["target_slug"] = argv[i + 1]; i += 2
        elif token in ("-h", "--help"):
            print(__doc__); raise SystemExit(0)
        else:
            raise SystemExit(f"Unknown arg: {token}")
    if opts["source_slug"] == "personal" or opts["target_slug"] == "personal":
        raise SystemExit("Refusing to run E2E against the personal tenant — pick distinct slugs.")
    return opts


if __name__ == "__main__":
    opts = _parse_argv(sys.argv[1:])
    report = run(source_slug=opts["source_slug"], target_slug=opts["target_slug"], keep=opts["keep"])
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["ok"] else 1)
