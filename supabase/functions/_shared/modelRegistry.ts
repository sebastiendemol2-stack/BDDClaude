import { createClient } from 'jsr:@supabase/supabase-js@2'

export const MODEL_STATUSES = ['active', 'inactive', 'deprecated', 'error'] as const
export const MODEL_KINDS = ['embedding', 'chat', 'reranker', 'vision', 'audio', 'tool'] as const

export type ModelStatus = typeof MODEL_STATUSES[number]
export type ModelKind = typeof MODEL_KINDS[number]

export type ModelFilter = {
  id?: string
  name?: string
  provider?: string
  version?: string
}

export type ModelPayload = ModelFilter & {
  kind?: ModelKind
  source_hash?: string | null
  dimension?: number
  endpoint?: string | null
  api_key_env?: string | null
  priority?: number
  fallback_order?: number
  rollout_percent?: number
  status?: ModelStatus
  config?: Record<string, unknown>
}

export const MODEL_PUBLIC_COLUMNS = [
  'id',
  'name',
  'provider',
  'version',
  'kind',
  'source_hash',
  'dimension',
  'priority',
  'fallback_order',
  'rollout_percent',
  'status',
  'config',
  'last_used_at',
  'error_message',
  'created_at',
  'updated_at',
].join(',')

export function createServiceClient() {
  return createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
  )
}

export async function isAdminRequest(req: Request): Promise<boolean> {
  const serviceRole = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')
  const adminToken = Deno.env.get('MODEL_REGISTRY_ADMIN_TOKEN')
  const auth = req.headers.get('authorization') ?? ''
  const bearer = auth.toLowerCase().startsWith('bearer ') ? auth.slice(7).trim() : ''

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

export function isModelStatus(value: unknown): value is ModelStatus {
  return typeof value === 'string' && MODEL_STATUSES.includes(value as ModelStatus)
}

export function isModelKind(value: unknown): value is ModelKind {
  return typeof value === 'string' && MODEL_KINDS.includes(value as ModelKind)
}

export function requireNonEmptyText(value: unknown, field: string): string {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`${field} is required`)
  }
  return value.trim()
}

export function parsePositiveInt(value: unknown, field: string, fallback?: number): number {
  if (value === undefined || value === null || value === '') {
    if (fallback !== undefined) return fallback
    throw new Error(`${field} is required`)
  }
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed <= 0) throw new Error(`${field} must be a positive integer`)
  return parsed
}

export function parseIntRange(value: unknown, field: string, min: number, max: number, fallback: number): number {
  if (value === undefined || value === null || value === '') return fallback
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    throw new Error(`${field} must be an integer between ${min} and ${max}`)
  }
  return parsed
}

export function targetModelFilter(body: Record<string, unknown>): ModelFilter {
  const id = typeof body.id === 'string' ? body.id.trim() : ''
  if (id) return { id }

  return {
    name: requireNonEmptyText(body.name, 'name'),
    provider: requireNonEmptyText(body.provider, 'provider'),
    version: typeof body.version === 'string' && body.version.trim() ? body.version.trim() : '1.0.0',
  }
}
