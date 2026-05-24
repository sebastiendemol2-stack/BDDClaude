import { handleCors, jsonResponse } from '../_shared/cors.ts'
import {
  createServiceClient,
  isAdminRequest,
  isModelStatus,
  MODEL_PUBLIC_COLUMNS,
  targetModelFilter,
} from '../_shared/modelRegistry.ts'

Deno.serve(async (req: Request) => {
  const cors = handleCors(req)
  if (cors) return cors

  if (!(await isAdminRequest(req))) {
    return jsonResponse({ error: 'Admin authorization required' }, 401)
  }

  try {
    const body = await req.json()
    const target = targetModelFilter(body)
    const status = body.status ?? 'inactive'

    if (!isModelStatus(status)) return jsonResponse({ error: 'Invalid model status' }, 400)

    const updates: Record<string, unknown> = {
      status,
      error_message: typeof body.error_message === 'string' && body.error_message.trim()
        ? body.error_message.trim()
        : null,
    }

    const supabase = createServiceClient()
    let query = supabase.from('vault_models').update(updates).select(MODEL_PUBLIC_COLUMNS)

    if (target.id) {
      query = query.eq('id', target.id)
    } else {
      query = query.eq('name', target.name).eq('provider', target.provider).eq('version', target.version)
    }

    const { data, error } = await query.single()
    if (error) throw error

    return jsonResponse({ model: data })
  } catch (err) {
    return jsonResponse({ error: err instanceof Error ? err.message : String(err) }, 400)
  }
})
