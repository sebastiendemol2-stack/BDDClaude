import httpx
import sys

TOKEN = sys.argv[1] if len(sys.argv) > 1 else "sbp_fc6d5cceb86a5fd47e429ff5010fae94ff48477c"
REF = "wusyqgxzyqifpgmxxbkf"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# 1. Check tables exist
sql = """SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('vault_memories','vault_feedback','vault_relations')
ORDER BY table_name;"""

r = httpx.post(f"https://api.supabase.com/v1/projects/{REF}/database/query",
               headers=HEADERS, json={"query": sql}, timeout=10.0)
r.raise_for_status()
rows = r.json()

print("=== Tables found ===")
for row in rows:
    print(f"  [OK] {row['table_name']}")
print(f"  Total: {len(rows)}/3")

# 2. Check columns for vault_memories
sql2 = """SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'vault_memories'
ORDER BY ordinal_position;"""

r2 = httpx.post(f"https://api.supabase.com/v1/projects/{REF}/database/query",
                headers=HEADERS, json={"query": sql2}, timeout=10.0)
r2.raise_for_status()
cols = r2.json()

print("\n=== vault_memories columns ===")
for c in cols:
    print(f"  {c['column_name']:20s} {c['data_type']:15s} nullable={c['is_nullable']}")

# 3. Check constraints
sql3 = """SELECT tc.table_name, tc.constraint_type, cc.check_clause
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.check_constraints cc ON tc.constraint_name = cc.constraint_name
WHERE tc.table_name IN ('vault_feedback','vault_relations')
AND tc.constraint_type IN ('CHECK', 'PRIMARY KEY')
ORDER BY tc.table_name, tc.constraint_type;"""

r3 = httpx.post(f"https://api.supabase.com/v1/projects/{REF}/database/query",
                headers=HEADERS, json={"query": sql3}, timeout=10.0)
r3.raise_for_status()
constr = r3.json()

print("\n=== Constraints ===")
for c in constr:
    print(f"  {c['table_name']:20s} {c['constraint_type']:15s} {c.get('check_clause', '') or ''}")

# 4. Check RLS is enabled
sql4 = """SELECT relname AS table_name, relrowsecurity AS rls_enabled
FROM pg_class
WHERE relname IN ('vault_memories','vault_feedback','vault_relations')
ORDER BY relname;"""

r4 = httpx.post(f"https://api.supabase.com/v1/projects/{REF}/database/query",
                headers=HEADERS, json={"query": sql4}, timeout=10.0)
r4.raise_for_status()
rls = r4.json()

print("\n=== RLS enabled ===")
for row in rls:
    print(f"  {row['table_name']:20s} RLS={row['rls_enabled']}")

print("\n✅ Verification complete")
