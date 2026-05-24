CREATE INDEX IF NOT EXISTS idx_vault_entries_embedding_hnsw
ON vault_entries
USING hnsw (embedding_vector vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

ALTER FUNCTION public.query_vector_hybrid(json) SET search_path = 'public';
