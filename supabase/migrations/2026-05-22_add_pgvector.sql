-- 2026-05-22 Add pgvector extension and vector column to vault_entries
-- This migration assumes the pgvector extension is available in the Supabase project.

-- Enable extension (if not already)
CREATE EXTENSION IF NOT EXISTS vector;

-- Add vector column (store embeddings as float4 vectors, dimension 1536 as example)
ALTER TABLE vault_entries
    ADD COLUMN IF NOT EXISTS embedding_vector vector(1536);

-- Optional: backfill existing embeddings from vault_embeddings table into the new column (to be done by a separate script)
-- INSERT INTO vault_entries (id, embedding_vector)
-- SELECT entry_id, embedding FROM vault_embeddings;

-- Set RLS policy allowing only authenticated users to read/write vectors (example placeholder)
-- ALTER TABLE vault_entries ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY vector_access ON vault_entries
--   FOR ALL USING (auth.role() <> 'anonymous');

COMMIT;