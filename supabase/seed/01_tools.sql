-- supabase/seed/01_tools.sql
-- UKP Tools Registry — seed data

insert into tools_registry (name, description, category, input_schema, output_schema, endpoint, auth_level, tags) values
('query', 'Recherche hybride FTS + vector dans le vault', 'knowledge',
 '{"type":"object","properties":{"query":{"type":"string"},"max_results":{"type":"integer","default":10},"project":{"type":"string"},"profile":{"type":"string"}},"required":["query"]}'::jsonb,
 '{"type":"object","properties":{"results":{"type":"array"},"total":{"type":"integer"},"took_ms":{"type":"integer"}}}'::jsonb,
 '/functions/v1/ukp-query', 'authenticated', '{search,rag,knowledge}'),
('prime', 'Charger le contexte vault (index + outils + profiles)', 'context',
 '{"type":"object","properties":{"project_slug":{"type":"string"},"profile":{"type":"string"}}}'::jsonb,
 '{"type":"object","properties":{"project":{"type":"string"},"vault_stats":{"type":"object"},"available_tools":{"type":"array"}}}'::jsonb,
 '/functions/v1/ukp-session', 'authenticated', '{context,prime}'),
('session', 'Cycle de vie des sessions (begin/inject/end)', 'session',
 '{"type":"object","properties":{"action":{"type":"string","enum":["begin","inject","end","prime"]},"session_id":{"type":"string"},"project_slug":{"type":"string"},"profile":{"type":"string"},"summary":{"type":"string"}},"required":["action"]}'::jsonb,
 '{"type":"object","properties":{"session_id":{"type":"string"},"started_at":{"type":"string"},"took_ms":{"type":"integer"}}}'::jsonb,
 '/functions/v1/ukp-session', 'authenticated', '{session,orchestration}'),
('discover', 'Auto-découverte outils/resources/profiles', 'system',
 '{"type":"object","properties":{}}'::jsonb,
 '{"type":"object","properties":{"tools":{"type":"array"},"resources":{"type":"array"},"profiles":{"type":"array"},"server_info":{"type":"object"}}}'::jsonb,
 '/functions/v1/ukp-discover', 'anon', '{system,discovery,mcp}'),
('ingest', 'Compiler des sources raw vers le wiki', 'knowledge',
 '{"type":"object","properties":{"source_paths":{"type":"array","items":{"type":"string"}},"project":{"type":"string"}}}'::jsonb,
 '{"type":"object","properties":{"created":{"type":"array"},"enriched":{"type":"array"},"errors":{"type":"array"}}}'::jsonb,
 '/functions/v1/ukp-ingest', 'service_role', '{ingest,knowledge}')
on conflict (name) do nothing;
