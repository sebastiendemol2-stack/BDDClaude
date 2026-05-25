"""
M8 acceptance gate — duplicate checks before composite-unique migration.

Before replacing the global UNIQUE constraints on:
    - vault_sections(slug)             -> (tenant_id, slug)
    - vault_entries(obsidian_path)     -> (tenant_id, obsidian_path)
    - projects(slug)                   -> (tenant_id, slug)

we must verify that the *new* composite would not be violated by the existing
rows. That sounds tautological — a global UNIQUE already forbids same-slug
collisions — but two failure modes matter:

1. Future cross-tenant duplicates may emerge during the bundle-import phase.
   This script gives us a pre-flight snapshot.

2. NULL tenant_id rows would survive the additive backfill if the migration
   was applied partially. We must catch them before any constraint flip.

Usage:
    python tenant_duplicate_check.py             # report all three tables
    python tenant_duplicate_check.py --json      # machine-readable output
    python tenant_duplicate_check.py --strict    # exit non-zero on any finding

Exit codes:
    0 — no duplicates, no NULL tenant_id (gate ready)
    1 — duplicates or NULL rows detected
    2 — environment / connection error
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)


CHECKS = (
    {"table": "vault_sections", "column": "slug"},
    {"table": "vault_entries", "column": "obsidian_path"},
    {"table": "projects", "column": "slug"},
)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.stderr.write(f"[duplicate-check] Missing env var: {name}\n")
        raise SystemExit(2)
    return value


def _headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def fetch_column(url: str, key: str, table: str, column: str) -> list[dict]:
    """Pull (tenant_id, <column>) pairs for every row of a table. Paginated."""
    rows: list[dict] = []
    limit = 1000
    offset = 0
    while True:
        req_url = (
            f"{url}/rest/v1/{table}"
            f"?select=tenant_id,{column}&limit={limit}&offset={offset}"
        )
        r = httpx.get(req_url, headers=_headers(key), timeout=30.0)
        if r.status_code == 404:
            # Table doesn't exist on this project yet. Treat as empty.
            return []
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return rows


def analyze(rows: list[dict], column: str) -> dict:
    """Compute null + composite-duplicate counts for one (table, column) pair."""
    seen: dict[tuple, int] = {}
    null_tenant = 0
    null_value = 0
    for row in rows:
        tenant_id = row.get("tenant_id")
        value = row.get(column)
        if tenant_id is None:
            null_tenant += 1
            continue
        if value is None:
            null_value += 1
            continue
        key = (tenant_id, value)
        seen[key] = seen.get(key, 0) + 1
    duplicates = {k: v for k, v in seen.items() if v > 1}
    return {
        "total_rows": len(rows),
        "null_tenant_id": null_tenant,
        "null_value": null_value,
        "unique_pairs": len(seen),
        "duplicate_pairs": len(duplicates),
        "duplicate_samples": [
            {"tenant_id": k[0], "value": k[1], "count": v}
            for k, v in list(duplicates.items())[:5]
        ],
    }


def run_checks() -> dict:
    """Run every configured check and roll up the results."""
    url = _require_env("SUPABASE_URL")
    key = _require_env("SUPABASE_SERVICE_ROLE_KEY")

    report = {"checks": [], "ok": True}
    for cfg in CHECKS:
        rows = fetch_column(url, key, cfg["table"], cfg["column"])
        analysis = analyze(rows, cfg["column"])
        passed = (
            analysis["null_tenant_id"] == 0
            and analysis["duplicate_pairs"] == 0
        )
        report["checks"].append({
            "table": cfg["table"],
            "column": cfg["column"],
            "passed": passed,
            **analysis,
        })
        if not passed:
            report["ok"] = False
    return report


def format_text(report: dict) -> str:
    lines = ["=== M8 Acceptance Gate — Duplicate Check ===", ""]
    for check in report["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(
            f"[{status}] {check['table']}({check['column']}): "
            f"{check['total_rows']} rows, {check['unique_pairs']} unique (tenant_id, value) pairs"
        )
        if check["null_tenant_id"]:
            lines.append(f"    {check['null_tenant_id']} row(s) with NULL tenant_id (apply backfill before flipping uniqueness)")
        if check["duplicate_pairs"]:
            lines.append(f"    {check['duplicate_pairs']} duplicate (tenant_id, {check['column']}) pair(s):")
            for sample in check["duplicate_samples"]:
                lines.append(
                    f"      tenant_id={sample['tenant_id']}  {check['column']}={sample['value']!r}  count={sample['count']}"
                )
    lines.append("")
    lines.append("Gate: " + ("READY — uniqueness flip is safe." if report["ok"] else "BLOCKED — resolve findings before migrating."))
    return "\n".join(lines)


def _parse_argv(argv: list[str]) -> dict:
    opts = {"json": False, "strict": False}
    for token in argv:
        if token == "--json":
            opts["json"] = True
        elif token == "--strict":
            opts["strict"] = True
        elif token in ("-h", "--help"):
            print(__doc__)
            raise SystemExit(0)
        else:
            sys.stderr.write(f"Unknown arg: {token}\n")
            raise SystemExit(2)
    return opts


if __name__ == "__main__":
    opts = _parse_argv(sys.argv[1:])
    report = run_checks()
    if opts["json"]:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(format_text(report))
    if opts["strict"] and not report["ok"]:
        raise SystemExit(1)
