import { corsHeaders, jsonResponse } from '../_shared/cors.ts'
import { createServiceClient, isAdminRequest, isModelStatus, MODEL_PUBLIC_COLUMNS } from '../_shared/modelRegistry.ts'

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: corsHeaders })
  if (req.method !== 'GET' && req.method !== 'POST') {
    return jsonResponse({ error: 'Method not allowed' }, 405)
  }

  try {
    const body = req.method === 'POST' ? await req.json().catch(() => ({})) : {}
    const url = new URL(req.url)
    const status = body.status ?? url.searchParams.get('status')
    const minDimension = body.min_dimension ?? url.searchParams.get('min_dimension')
    const provider = body.provider ?? url.searchParams.get('provider')
    const kind = body.kind ?? url.searchParams.get('kind')
    const includeInactive = body.include_inactive === true || url.searchParams.get('include_inactive') === 'true'
    const isAdmin = await isAdminRequest(req)

    if (status !== undefined && status !== null && status !== '' && !isModelStatus(status)) {
      return jsonResponse({ error: 'Invalid model status' }, 400)
    }

    const supabase = createServiceClient()
    let query = supabase
      .from('vault_models')
      .select(MODEL_PUBLIC_COLUMNS)
      .order('priority', { ascending: false })
      .order('fallback_order', { ascending: true })
      .order('created_at', { ascending: false })

    if (status) query = query.eq('status', status)
    if (!status && (!includeInactive || !isAdmin)) query = query.eq('status', 'active')
    if (provider) query = query.eq('provider', provider)
    if (kind) query = query.eq('kind', kind)
    if (minDimension) query = query.gte('dimension', Number(minDimension))

    const { data, error } = await query
    if (error) throw error

    const models = data ?? []
    const active = models.filter((m: { status: string }) => m.status === 'active')

    return jsonResponse({
      models,
      active,
      total: models.length,
      admin: isAdmin,
    })
  } catch (err) {
    return jsonResponse({ error: err instanceof Error ? err.message : String(err) }, 500)
  }
})
