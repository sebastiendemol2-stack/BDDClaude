-- M8 Multi-tenant Vaults: non-destructive tenant bootstrap.
-- Creates tenant metadata and membership tables only; existing vault data tables
-- are not altered in this first slice.

CREATE TABLE IF NOT EXISTS public.vault_tenants (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug              text NOT NULL,
    name              text NOT NULL,
    status            text NOT NULL DEFAULT 'active',
    owner_user_id     uuid,
    metadata          jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.vault_tenants DROP CONSTRAINT IF EXISTS vault_tenants_slug_key;
ALTER TABLE public.vault_tenants ADD CONSTRAINT vault_tenants_slug_key UNIQUE (slug);

ALTER TABLE public.vault_tenants DROP CONSTRAINT IF EXISTS ck_vault_tenants_slug;
ALTER TABLE public.vault_tenants ADD CONSTRAINT ck_vault_tenants_slug
    CHECK (slug ~ '^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$' OR slug ~ '^[a-z0-9]$');

ALTER TABLE public.vault_tenants DROP CONSTRAINT IF EXISTS ck_vault_tenants_status;
ALTER TABLE public.vault_tenants ADD CONSTRAINT ck_vault_tenants_status
    CHECK (status IN ('active', 'suspended', 'archived'));

CREATE TABLE IF NOT EXISTS public.vault_tenant_members (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid NOT NULL REFERENCES public.vault_tenants(id) ON DELETE CASCADE,
    user_id           uuid NOT NULL,
    role              text NOT NULL DEFAULT 'member',
    status            text NOT NULL DEFAULT 'active',
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.vault_tenant_members DROP CONSTRAINT IF EXISTS vault_tenant_members_tenant_user_key;
ALTER TABLE public.vault_tenant_members ADD CONSTRAINT vault_tenant_members_tenant_user_key
    UNIQUE (tenant_id, user_id);

ALTER TABLE public.vault_tenant_members DROP CONSTRAINT IF EXISTS ck_vault_tenant_members_role;
ALTER TABLE public.vault_tenant_members ADD CONSTRAINT ck_vault_tenant_members_role
    CHECK (role IN ('owner', 'admin', 'member', 'viewer'));

ALTER TABLE public.vault_tenant_members DROP CONSTRAINT IF EXISTS ck_vault_tenant_members_status;
ALTER TABLE public.vault_tenant_members ADD CONSTRAINT ck_vault_tenant_members_status
    CHECK (status IN ('active', 'invited', 'suspended'));

CREATE INDEX IF NOT EXISTS idx_vault_tenant_members_user ON public.vault_tenant_members(user_id);
CREATE INDEX IF NOT EXISTS idx_vault_tenant_members_tenant ON public.vault_tenant_members(tenant_id);
CREATE INDEX IF NOT EXISTS idx_vault_tenants_status ON public.vault_tenants(status);

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

DROP TRIGGER IF EXISTS vault_tenants_updated_at ON public.vault_tenants;
CREATE TRIGGER vault_tenants_updated_at
    BEFORE UPDATE ON public.vault_tenants
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

DROP TRIGGER IF EXISTS vault_tenant_members_updated_at ON public.vault_tenant_members;
CREATE TRIGGER vault_tenant_members_updated_at
    BEFORE UPDATE ON public.vault_tenant_members
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

ALTER TABLE public.vault_tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vault_tenant_members ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenants_select_memberships ON public.vault_tenants;
DROP POLICY IF EXISTS service_all_tenants ON public.vault_tenants;
DROP POLICY IF EXISTS tenant_members_select_self ON public.vault_tenant_members;
DROP POLICY IF EXISTS service_all_tenant_members ON public.vault_tenant_members;

CREATE POLICY tenants_select_memberships ON public.vault_tenants
    FOR SELECT
    TO authenticated
    USING (
        status = 'active'
        AND EXISTS (
            SELECT 1
            FROM public.vault_tenant_members m
            WHERE m.tenant_id = public.vault_tenants.id
              AND m.user_id = (SELECT auth.uid())
              AND m.status = 'active'
        )
    );

CREATE POLICY service_all_tenants ON public.vault_tenants
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY tenant_members_select_self ON public.vault_tenant_members
    FOR SELECT
    TO authenticated
    USING (user_id = (SELECT auth.uid()));

CREATE POLICY service_all_tenant_members ON public.vault_tenant_members
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

GRANT SELECT ON TABLE public.vault_tenants TO authenticated;
GRANT SELECT ON TABLE public.vault_tenant_members TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.vault_tenants TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.vault_tenant_members TO service_role;

INSERT INTO public.vault_tenants (slug, name, status, metadata)
VALUES (
    'personal',
    'Personal Vault',
    'active',
    '{"purpose":"default-single-user-backfill-target","created_by":"m8-bootstrap"}'::jsonb
)
ON CONFLICT (slug) DO UPDATE
SET name = EXCLUDED.name,
    status = EXCLUDED.status,
    metadata = public.vault_tenants.metadata || EXCLUDED.metadata,
    updated_at = now();
