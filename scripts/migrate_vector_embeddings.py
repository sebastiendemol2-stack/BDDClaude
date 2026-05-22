#!/usr/bin/env python3
"""Migrate existing embeddings into the new `embedding_vector` column.

The script:
  1. Connects to Supabase using the service role key (env var SUPABASE_SERVICE_ROLE_KEY).
  2. Queries `vault_embeddings` for each entry_id and its embedding (bytea).
  3. Converts the byte array (assumed to be a list of float32) into a Postgres vector literal.
  4. Updates `vault_entries.embedding_vector` for the matching row.
  5. Prints a short summary.

Run in dry‑run mode first to see the transformations without persisting:
    python scripts/migrate_vector_embeddings.py --dry-run

When satisfied, run without the flag to apply changes.
"""

import os
import argparse
import struct
import base64
import json
from typing import List

import psycopg2
from psycopg2.extras import RealDictCursor


def fetch_embeddings(conn) -> List[dict]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT entry_id, embedding FROM vault_embeddings;")
        return cur.fetchall()


def bytes_to_vector_literal(b: bytes) -> str:
    # Assume little‑endian float32 array
    floats = struct.unpack('<%df' % (len(b) // 4), b)
    # Postgres vector literal format: '[1,2,3]'
    return "[" + ",".join(f"{f:.6f}" for f in floats) + "]"


def update_entry(conn, entry_id: int, vector_literal: str, dry_run: bool):
    if dry_run:
        print(f"[dry‑run] Would update entry {entry_id} with vector {vector_literal[:30]}…")
        return
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE vault_entries SET embedding_vector = %s WHERE id = %s;",
            (vector_literal, entry_id),
        )


def main():
    parser = argparse.ArgumentParser(description="Backfill embedding_vector column.")
    parser.add_argument('--dry-run', action='store_true', help='Do not write to the database')
    args = parser.parse_args()

    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        raise RuntimeError('SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars must be set')

    conn = psycopg2.connect(dsn=url, password=key, sslmode='require')
    try:
        embeddings = fetch_embeddings(conn)
        print(f"Fetched {len(embeddings)} embeddings.")
        for rec in embeddings:
            vector_lit = bytes_to_vector_literal(rec['embedding'])
            update_entry(conn, rec['entry_id'], vector_lit, args.dry_run)
        if not args.dry_run:
            conn.commit()
            print('All updates committed.')
    finally:
        conn.close()

if __name__ == '__main__':
    main()
