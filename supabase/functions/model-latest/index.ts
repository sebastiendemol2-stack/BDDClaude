import { corsHeaders, jsonResponse } from '../_shared/cors.ts'
import { createServiceClient, MODEL_PUBLIC_COLUMNS } from '../_shared/modelRegistry.ts'

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: corsHeaders })
  if (req.method !== 'GET' && req.method !== 'POST') {
    return jsonResponse({ error: 'Method not allowed' }, 405)
  }

  try {
    const body = req.method === 'POST' ? await req.json().catch(() => ({})) : {}
    const url = new URL(req.url)
    const provider = body.provider ?? url.searchParams.get('provider')
    const kind = body.kind ?? url.searchParams.get('kind') ?? 'embedding'
    const minDimension = body.min_dimension ?? url.searchParams.get('min_dimension')
    const name = body.name ?? url.searchParams.get('name')

    const supabase = createServiceClient()
    let query = supabase
      .from('vault_models')
      .select(MODEL_PUBLIC_COLUMNS)
      .eq('status', 'active')
      .eq('kind', kind)
      .order('priority', { ascending: false })
      .order('fallback_order', { ascending: true })
      .order('created_at', { ascending: false })
      .limit(10)

    if (provider) query = query.eq('provider', provider)
    if (name) query = query.eq('name', name)
    if (minDimension) query = query.gte('dimension', Number(minDimension))

    const { data, error } = await query
    if (error) throw error

    const models = data ?? []
    return jsonResponse({
      model: models[0] ?? null,
      fallbacks: models.slice(1),
      total: models.length,
    })
  } catch (err) {
    return jsonResponse({ error: err instanceof Error ? err.message : String(err) }, 500)
  }
})
