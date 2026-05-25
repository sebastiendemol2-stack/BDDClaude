CREATE OR REPLACE FUNCTION public.query_vector_hybrid(req json)
RETURNS TABLE (
    id uuid,
    title text,
    snippet text,
    score double precision
) LANGUAGE plpgsql SECURITY DEFINER SET search_path = 'public', 'extensions' AS $func$
DECLARE
    q text := req->>'query';
    vec text := req->>'embedding';
    lim int := COALESCE((req->>'limit')::int, 10);
    tenant_filter uuid := NULLIF(req->>'tenant_id', '')::uuid;
    tenant_clause text := CASE
        WHEN tenant_filter IS NULL THEN ''
        ELSE format('AND e.tenant_id = %L::uuid', tenant_filter)
    END;
    sql text;
BEGIN
    IF vec IS NOT NULL THEN
        sql := format(
            $inner$
            SELECT e.id, e.title,
                   ts_headline('english', e.content, plainto_tsquery('english', %L)) AS snippet,
                   0.7 * (1 - (e.embedding_vector <=> %L::extensions.vector)) +
                   0.3 * ts_rank_cd(to_tsvector('english', e.content), plainto_tsquery('english', %L)) AS score
            FROM vault_entries e
            WHERE e.embedding_vector IS NOT NULL
              %s
            ORDER BY score DESC
            LIMIT %s
            $inner$,
            q, vec, q, tenant_clause, lim
        );
    ELSE
        sql := format(
            $inner$
            SELECT e.id, e.title,
                   ts_headline('english', e.content, plainto_tsquery('english', %L)) AS snippet,
                   ts_rank_cd(to_tsvector('english', e.content), plainto_tsquery('english', %L)) AS score
            FROM vault_entries e
            WHERE TRUE
              %s
            ORDER BY score DESC
            LIMIT %s
            $inner$,
            q, q, tenant_clause, lim
        );
    END IF;
    RETURN QUERY EXECUTE sql;
END;
$func$;
