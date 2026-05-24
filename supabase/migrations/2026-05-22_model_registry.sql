-- Model Registry & Versioning (M7)
-- Idempotent migration for a versioned AI model catalog.

CREATE TABLE IF NOT EXISTS public.vault_models (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name              text NOT NULL,
    provider          text NOT NULL,
    version           text NOT NULL DEFAULT '1.0.0',
    kind              text NOT NULL DEFAULT 'embedding',
    source_hash       text,
    dimension         integer NOT NULL,
    endpoint          text,
    api_key_env       text,
    priority          integer NOT NULL DEFAULT 0,
    fallback_order    integer NOT NULL DEFAULT 100,
    rollout_percent   integer NOT NULL DEFAULT 0,
    status            text NOT NULL DEFAULT 'active',
    config            jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_used_at      timestamptz,
    error_message     text,
    created_at        timestamptz DEFAULT now(),
    updated_at        timestamptz DEFAULT now()
);

ALTER TABLE public.vault_models
    ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'embedding',
    ADD COLUMN IF NOT EXISTS source_hash text,
    ADD COLUMN IF NOT EXISTS fallback_order integer NOT NULL DEFAULT 100,
    ADD COLUMN IF NOT EXISTS rollout_percent integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS config jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS last_used_at timestamptz,
    ADD COLUMN IF NOT EXISTS error_message text,
    ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

ALTER TABLE public.vault_models DROP CONSTRAINT IF EXISTS vault_models_name_key;
ALTER TABLE public.vault_models DROP CONSTRAINT IF EXISTS vault_models_provider_name_version_key;
ALTER TABLE public.vault_models ADD CONSTRAINT vault_models_provider_name_version_key UNIQUE (provider, name, version);

ALTER TABLE public.vault_models DROP CONSTRAINT IF EXISTS ck_vault_models_status;
ALTER TABLE public.vault_models ADD CONSTRAINT ck_vault_models_status
    CHECK (status IN ('active', 'inactive', 'deprecated', 'error'));

ALTER TABLE public.vault_models DROP CONSTRAINT IF EXISTS ck_vault_models_kind;
ALTER TABLE public.vault_models ADD CONSTRAINT ck_vault_models_kind
    CHECK (kind IN ('embedding', 'chat', 'reranker', 'vision', 'audio', 'tool'));

ALTER TABLE public.vault_models DROP CONSTRAINT IF EXISTS ck_vault_models_dimension;
ALTER TABLE public.vault_models ADD CONSTRAINT ck_vault_models_dimension
    CHECK (dimension > 0);

ALTER TABLE public.vault_models DROP CONSTRAINT IF EXISTS ck_vault_models_rollout_percent;
ALTER TABLE public.vault_models ADD CONSTRAINT ck_vault_models_rollout_percent
    CHECK (rollout_percent BETWEEN 0 AND 100);

ALTER TABLE public.vault_embeddings
    ADD COLUMN IF NOT EXISTS model_id uuid REFERENCES public.vault_models(id);

CREATE INDEX IF NOT EXISTS idx_models_status_priority ON public.vault_models(status, priority DESC, fallback_order ASC);
CREATE INDEX IF NOT EXISTS idx_models_kind_provider ON public.vault_models(kind, provider);
CREATE INDEX IF NOT EXISTS idx_embeddings_model ON public.vault_embeddings(model_id);

CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS vault_models_updated_at ON public.vault_models;
CREATE TRIGGER vault_models_updated_at
    BEFORE UPDATE ON public.vault_models
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

ALTER TABLE public.vault_models ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "models_select_anon" ON public.vault_models;
DROP POLICY IF EXISTS "models_insert_service_role" ON public.vault_models;
DROP POLICY IF EXISTS "models_update_service_role" ON public.vault_models;
DROP POLICY IF EXISTS models_select_active ON public.vault_models;
DROP POLICY IF EXISTS service_all_models ON public.vault_models;

CREATE POLICY models_select_active ON public.vault_models
    FOR SELECT
    TO anon, authenticated
    USING (status = 'active');

CREATE POLICY service_all_models ON public.vault_models
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

GRANT SELECT ON TABLE public.vault_models TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.vault_models TO service_role;

INSERT INTO public.vault_models (name, provider, version, kind, dimension, priority, fallback_order, rollout_percent, status, config)
VALUES
    ('text-embedding-3-small', 'openai', '1.0.0', 'embedding', 1536, 30, 20, 100, 'active', '{"usage":"default-embedding"}'::jsonb),
    ('text-embedding-3-large', 'openai', '1.0.0', 'embedding', 3072, 40, 10, 100, 'active', '{"usage":"production-embedding-pilot","query_dimensions":1536,"pilot_activated_at":"2026-05-22"}'::jsonb),
    ('text-embedding-ada-002', 'openai', '2.0.0', 'embedding', 1536, 10, 90, 0, 'deprecated', '{"usage":"legacy-fallback"}'::jsonb)
ON CONFLICT (provider, name, version) DO UPDATE
SET kind = EXCLUDED.kind,
    dimension = EXCLUDED.dimension,
    priority = EXCLUDED.priority,
    fallback_order = EXCLUDED.fallback_order,
    rollout_percent = EXCLUDED.rollout_percent,
    status = EXCLUDED.status,
    config = public.vault_models.config || EXCLUDED.config,
    updated_at = now();
