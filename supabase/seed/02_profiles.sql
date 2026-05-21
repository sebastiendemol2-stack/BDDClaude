-- supabase/seed/02_profiles.sql
-- UKP Context Profiles — seed data

insert into context_profiles (name, description, system_prompt, is_default, token_budget,
  retrieval_config, compression_config, memory_config, tools_config) values
('default', 'Profil RAG par défaut — hybride FTS/vector, 12k tokens', null, true, 12000,
 '{"hybrid":true,"fts_weight":0.4,"vector_weight":0.6,"max_chunks":24,"rerank":true}'::jsonb,
 '{"strategy":"semantic","target_tokens":12000}'::jsonb,
 '{"short_term_limit":25,"episodic_limit":10,"include_decisions":true,"include_patterns":true}'::jsonb,
 '{"auto_enable":["query","prime","ingest"]}'::jsonb),
('rag-default', 'Profil RAG complet — reranking, mémoires session', null, false, 16000,
 '{"hybrid":true,"fts_weight":0.3,"vector_weight":0.7,"max_chunks":32,"rerank":true}'::jsonb,
 '{"strategy":"semantic","target_tokens":16000}'::jsonb,
 '{"short_term_limit":35,"episodic_limit":15,"include_decisions":true,"include_patterns":true}'::jsonb,
 '{"auto_enable":["query","prime","session","ingest"]}'::jsonb),
('minimal', 'Profil minimal — FTS only, 4k tokens', null, false, 4000,
 '{"hybrid":false,"max_chunks":8,"rerank":false}'::jsonb,
 '{"strategy":"truncate","target_tokens":4000}'::jsonb,
 '{"short_term_limit":5,"episodic_limit":3,"include_decisions":false,"include_patterns":false}'::jsonb,
 '{"auto_enable":["query"]}'::jsonb)
on conflict (name) do nothing;
