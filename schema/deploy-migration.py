"""
Deploy migration v3.2 to Supabase remote.

Usage:
    python schema/deploy-migration.py
    python schema/deploy-migration.py --migration schema/migration-v3.2.sql

Requires:
    - SUPABASE_ACCESS_TOKEN env var (Personal Access Token from
      https://app.supabase.com/account/tokens)
    - Or --token argument
"""

import os
import sys
import json
import argparse
from pathlib import Path

import httpx

SUPABASE_REF = "ottoqbwctcpzzdfzewdi"
BRAIN_REF = "wusyqgxzyqifpgmxxbkf"
MANAGEMENT_API = "https://api.supabase.com"


def deploy_sql(project_ref: str, sql: str, token: str) -> bool:
    url = f"{MANAGEMENT_API}/v1/projects/{project_ref}/database/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    print(f"  [..] Deploying to project {project_ref}...")
    try:
        r = httpx.post(url, headers=headers, json={"query": sql}, timeout=30.0)
        r.raise_for_status()
        print(f"  [OK] Success ({r.status_code})")
        return True
    except httpx.HTTPStatusError as e:
        print(f"  [ERR] HTTP {e.response.status_code}: {e.response.text[:500]}")
        return False
    except Exception as e:
        print(f"  [ERR] {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Deploy migration to Supabase")
    parser.add_argument("--migration", default="schema/migration-v3.2.sql",
                        help="Path to SQL migration file")
    parser.add_argument("--token",
                        help="Supabase Personal Access Token")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print SQL without executing")
    args = parser.parse_args()

    token = args.token or os.environ.get("SUPABASE_ACCESS_TOKEN")
    if not token and not args.dry_run:
        print("ERROR: No Supabase access token provided.")
        print("  Get one at https://app.supabase.com/account/tokens")
        sys.exit(1)

    migration_path = Path(args.migration)
    if not migration_path.exists():
        print(f"ERROR: Migration file not found: {migration_path}")
        sys.exit(1)

    sql = migration_path.read_text(encoding="utf-8")
    print(f"[MIGRATION] {migration_path.name} ({len(sql)} chars)")

    if args.dry_run:
        print("\n--- SQL (dry-run) ---")
        print(sql)
        print("--- (dry-run, not executed) ---")
        return

    print("\n[DEPLOY] Deploying to BRAIN_URL (wusyqgxzyqifpgmxxbkf)...")
    ok = deploy_sql(BRAIN_REF, sql, token)

    if ok:
        print("\n[DEPLOY] Migration v3.2 deployed successfully!")
        print("         Tables: vault_memories, vault_feedback, vault_relations")
        print("         Target: BRAIN_URL (service_role key)")
    else:
        print("\n[DEPLOY] Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
