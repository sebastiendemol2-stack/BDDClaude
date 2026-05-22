/**
 * Supabase RPC: query_vector_hybrid
 *
 * This function performs a hybrid search:
 *   1. If a query vector is provided, it searches the `embedding_vector` column using
 *      the `@@` operator (vector similarity).
 *   2. It always runs a full‑text BM25 search on `content` as a fallback.
 *   3. Results are ordered by a combined score (vector similarity weighted 0.7, BM25 weighted 0.3).
 *
 * Parameters (JSON input):
 *   {
 *     "query": "string",            // full‑text query (required)
 *     "embedding": "[float,...]",   // optional vector as JSON array string
 *     "limit": 10                    // optional result limit (default 10)
 *   }
 *
 * Returns an array of objects: { id, title, snippet, score }
 */
CREATE OR REPLACE FUNCTION public.query_vector_hybrid(req json)
RETURNS TABLE (
    id uuid,
    title text,
    snippet text,
    score double precision
) LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    q text := req->>'query';
    vec text := req->>'embedding';
    lim int := COALESCE((req->>'limit')::int, 10);
    sql text;
BEGIN
    IF vec IS NOT NULL THEN
        sql := format(
            $$
            SELECT e.id, e.title,
                   ts_headline(e.content, to_tsquery('english', %L)) AS snippet,
                   0.7 * (1 - (e.embedding_vector <=> %s::vector)) +
                   0.3 * ts_rank_cd(to_tsvector('english', e.content), to_tsquery('english', %L)) AS score
            FROM vault_entries e
            WHERE e.embedding_vector IS NOT NULL
            ORDER BY score DESC
            LIMIT %s;
            $$,
            q, vec, q, lim
        );
    ELSE
        sql := format(
            $$
            SELECT e.id, e.title,
                   ts_headline(e.content, to_tsquery('english', %L)) AS snippet,
                   ts_rank_cd(to_tsvector('english', e.content), to_tsquery('english', %L)) AS score
            FROM vault_entries e
            ORDER BY score DESC
            LIMIT %s;
            $$,
            q, q, lim
        );
    END IF;
    RETURN QUERY EXECUTE sql;
END;
$$;
