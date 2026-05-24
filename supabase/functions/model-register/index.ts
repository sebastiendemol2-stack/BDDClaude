import { handleCors, jsonResponse } from '../_shared/cors.ts'
import {
  createServiceClient,
  isAdminRequest,
  isModelKind,
  isModelStatus,
  MODEL_PUBLIC_COLUMNS,
  parseIntRange,
  parsePositiveInt,
  requireNonEmptyText,
} from '../_shared/modelRegistry.ts'

Deno.serve(async (req: Request) => {
  const cors = handleCors(req)
  if (cors) return cors

  if (!(await isAdminRequest(req))) {
    return jsonResponse({ error: 'Admin authorization required' }, 401)
  }

  try {
    const body = await req.json()
    const name = requireNonEmptyText(body.name, 'name')
    const provider = requireNonEmptyText(body.provider, 'provider')
    const version = typeof body.version === 'string' && body.version.trim() ? body.version.trim() : '1.0.0'
    const kind = body.kind === undefined ? 'embedding' : body.kind
    const status = body.status === undefined ? 'active' : body.status

    if (!isModelKind(kind)) return jsonResponse({ error: 'Invalid model kind' }, 400)
    if (!isModelStatus(status)) return jsonResponse({ error: 'Invalid model status' }, 400)

    const config = body.config === undefined ? {} : body.config
    if (typeof config !== 'object' || config === null || Array.isArray(config)) {
      return jsonResponse({ error: 'config must be an object' }, 400)
    }

    const payload = {
      name,
      provider,
      version,
      kind,
      status,
      source_hash: typeof body.source_hash === 'string' ? body.source_hash.trim() || null : null,
      dimension: parsePositiveInt(body.dimension, 'dimension'),
      endpoint: typeof body.endpoint === 'string' && body.endpoint.trim() ? body.endpoint.trim() : null,
      api_key_env: typeof body.api_key_env === 'string' && body.api_key_env.trim() ? body.api_key_env.trim() : null,
      priority: parseIntRange(body.priority, 'priority', -1000, 1000, 0),
      fallback_order: parseIntRange(body.fallback_order, 'fallback_order', 0, 1000, 100),
      rollout_percent: parseIntRange(body.rollout_percent, 'rollout_percent', 0, 100, 0),
      config,
      error_message: typeof body.error_message === 'string' && body.error_message.trim() ? body.error_message.trim() : null,
    }

    const supabase = createServiceClient()
    const { data, error } = await supabase
      .from('vault_models')
      .upsert(payload, { onConflict: 'provider,name,version', ignoreDuplicates: false })
      .select(MODEL_PUBLIC_COLUMNS)
      .single()

    if (error) throw error
    return jsonResponse({ model: data })
  } catch (err) {
    return jsonResponse({ error: err instanceof Error ? err.message : String(err) }, 400)
  }
})
