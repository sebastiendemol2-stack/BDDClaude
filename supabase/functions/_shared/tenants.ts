import { createClient, SupabaseClient } from 'jsr:@supabase/supabase-js@2'

export const TENANT_MEMBER_ROLES = ['owner', 'admin', 'member', 'viewer'] as const
export const TENANT_MEMBER_STATUSES = ['active', 'invited', 'suspended'] as const
export const TENANT_STATUSES = ['active', 'suspended', 'archived'] as const

export type TenantMemberRole = typeof TENANT_MEMBER_ROLES[number]
export type TenantMemberStatus = typeof TENANT_MEMBER_STATUSES[number]
export type TenantStatus = typeof TENANT_STATUSES[number]

const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$|^[a-z0-9]$/

export function isValidTenantSlug(value: unknown): value is string {
  return typeof value === 'string' && SLUG_RE.test(value)
}

export function isTenantMemberRole(value: unknown): value is TenantMemberRole {
  return typeof value === 'string' && TENANT_MEMBER_ROLES.includes(value as TenantMemberRole)
}

export function isTenantMemberStatus(value: unknown): value is TenantMemberStatus {
  return typeof value === 'string' && TENANT_MEMBER_STATUSES.includes(value as TenantMemberStatus)
}

export function isTenantStatus(value: unknown): value is TenantStatus {
  return typeof value === 'string' && TENANT_STATUSES.includes(value as TenantStatus)
}

export function createServiceClient(): SupabaseClient {
  return createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
  )
}

function extractBearer(req: Request): string {
  const auth = req.headers.get('authorization') ?? ''
  return auth.toLowerCase().startsWith('bearer ') ? auth.slice(7).trim() : ''
}

export async function resolveCallerUserId(req: Request): Promise<string | null> {
  const bearer = extractBearer(req)
  if (!bearer || bearer === Deno.env.get('SUPABASE_ANON_KEY') || bearer === Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')) {
    return null
  }
  const userClient = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_ANON_KEY')!, {
    global: { headers: { Authorization: `Bearer ${bearer}` } },
  })
  const { data, error } = await userClient.auth.getUser()
  if (error || !data.user) return null
  return data.user.id
}

export async function isPlatformAdmin(req: Request): Promise<boolean> {
  const serviceRole = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')
  const adminToken = Deno.env.get('TENANT_ADMIN_TOKEN')
  const bearer = extractBearer(req)

  if (serviceRole && bearer === serviceRole) return true
  if (adminToken && req.headers.get('x-admin-token') === adminToken) return true

  if (!bearer || bearer === Deno.env.get('SUPABASE_ANON_KEY')) return false

  const userClient = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_ANON_KEY')!, {
    global: { headers: { Authorization: `Bearer ${bearer}` } },
  })
  const { data, error } = await userClient.auth.getUser()
  if (error || !data.user) return false

  const metadata = data.user.app_metadata ?? {}
  const roles = Array.isArray(metadata.roles) ? metadata.roles : []
  return metadata.role === 'admin' || roles.includes('admin') || metadata.is_admin === true
}

export type TenantRow = {
  id: string
  slug: string
  name: string
  status: TenantStatus
  owner_user_id: string | null
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export async function getTenantBySlug(supabase: SupabaseClient, slug: string): Promise<TenantRow | null> {
  const { data, error } = await supabase
    .from('vault_tenants')
    .select('id,slug,name,status,owner_user_id,metadata,created_at,updated_at')
    .eq('slug', slug)
    .maybeSingle()
  if (error) throw error
  return (data as TenantRow | null) ?? null
}

export async function hasTenantManagementRole(
  supabase: SupabaseClient,
  tenantId: string,
  userId: string,
): Promise<boolean> {
  const { data, error } = await supabase
    .from('vault_tenant_members')
    .select('role,status')
    .eq('tenant_id', tenantId)
    .eq('user_id', userId)
    .eq('status', 'active')
    .maybeSingle()
  if (error) throw error
  if (!data) return false
  return data.role === 'owner' || data.role === 'admin'
}

export function requireNonEmptyText(value: unknown, field: string): string {
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error(`${field} must be a non-empty string`)
  }
  return value.trim()
}
