-- schema/migrations/20260521_ukp_v1_2_reconcile.sql
-- UKP v1.2 — Réconciliation schema remote ↔ local
-- Idempotent (re-run safe)
--
-- Drifts corrigés :
--   1. query_vector_hybrid RPC manquant (path vectoriel cassé dans ukp-query)
--   2. vault_embeddings manque chunking_strategy + tokenizer_hash

-- ============================================================
-- 1. query_vector_hybrid — RPC appelé par ukp-query Edge Function
-- ============================================================

create or replace function query_vector_hybrid(
    query_text text,
    match_count int default 10
) returns jsonb language plpgsql search_path = '' as \$\$
declare
    result jsonb;
begin
    select jsonb_build_object(
        'results', coalesce(jsonb_agg(
            jsonb_build_object(
                'id', e.id,
                'title', e.title,
                'content', e.content,
                'tags', e.tags,
                'type', e.type,
                'obsidian_path', e.obsidian_path,
                'section_slug', e.section_slug,
                'summary', e.summary,
                'freshness', e.freshness,
                'confidence', e.confidence,
                'updated_at', e.updated_at,
                '_score', round(ts_rank(e.content_search, query)::numeric, 4)::real,
                '_method', 'fts'
            )
            order by ts_rank(e.content_search, query) desc
        ), '[]'::jsonb)
    ) into result
    from vault_entries e,
        plainto_tsquery('french', query_text) query
    where e.content_search @@ query
        and e.status = 'active'
    limit match_count;

    return result;
end;
\$\$;

revoke execute on function query_vector_hybrid from public, anon, authenticated;
grant execute on function query_vector_hybrid to service_role, authenticated;

-- ============================================================
-- 2. vault_embeddings — add columns manquantes
-- ============================================================

do \$\$
begin
    if not exists (select 1 from information_schema.columns
        where table_name = 'vault_embeddings' and column_name = 'chunking_strategy')
    then
        alter table vault_embeddings add column chunking_strategy text default 'section';
    end if;

    if not exists (select 1 from information_schema.columns
        where table_name = 'vault_embeddings' and column_name = 'tokenizer_hash')
    then
        alter table vault_embeddings add column tokenizer_hash text;
    end if;
end;
\$\$;

-- ============================================================
-- 3. Index supplémentaires pour performance UKP runtime
-- ============================================================

create index if not exists idx_tool_calls_ide on tool_calls(client_ide, created_at);
create index if not exists idx_session_events_type_ts on session_events(event_type, created_at desc);
create index if not exists idx_ide_clients_ping on ide_clients(last_ping) where last_ping is not null;

