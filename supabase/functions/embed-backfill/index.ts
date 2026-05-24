import { createClient } from 'jsr:@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, apikey',
}

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  })
}

type VaultModel = {
  id: string
  name: string
  provider: string
  dimension: number
  config: Record<string, unknown> | null
}

type EntryRow = { id: string; title: string | null; content: string | null }

const MAX_CHARS = 24000

async function selectActiveEmbeddingModel(supabase: ReturnType<typeof createClient>): Promise<VaultModel | null> {
  const { data, error } = await supabase
    .from('vault_models')
    .select('id,name,provider,dimension,config')
    .eq('status', 'active')
    .eq('kind', 'embedding')
    .order('priority', { ascending: false })
    .order('fallback_order', { ascending: true })
    .limit(1)
    .maybeSingle()
  if (error) throw error
  return data as VaultModel | null
}

function getQueryDimensions(model: VaultModel): number {
  const configured = Number(model.config?.query_dimensions ?? Deno.env.get('EMBEDDING_QUERY_DIMENSIONS'))
  return Number.isInteger(configured) && configured > 0 ? configured : 1536
}

async function embedBatch(
  texts: string[],
  model: VaultModel,
  dimensions: number,
): Promise<number[][]> {
  const apiKey = Deno.env.get('OPENAI_API_KEY')
  if (!apiKey) throw new Error('OPENAI_API_KEY not configured')
  if (model.provider !== 'openai') throw new Error(`Unsupported provider: ${model.provider}`)

  const resp = await fetch('https://api.openai.com/v1/embeddings', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      input: texts,
      model: model.name,
      dimensions,
      encoding_format: 'float',
    }),
  })
  if (!resp.ok) throw new Error(`OpenAI ${resp.status}: ${(await resp.text()).slice(0, 200)}`)
  const payload = await resp.json()
  return (payload?.data ?? []).map((d: { embedding: number[] }) => d.embedding)
}

function vectorLiteral(vec: number[]): string {
  return `[${vec.join(',')}]`
}

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: corsHeaders })
  if (req.method !== 'POST') return jsonResponse({ error: 'Method not allowed' }, 405)

  try {
    const body = await req.json().catch(() => ({}))
    const limit = Math.min(Number(body.limit) || 100, 200)
    const force = Boolean(body.force)
    const dryRun = Boolean(body.dry_run)

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
    )

    const model = await selectActiveEmbeddingModel(supabase)
    if (!model) return jsonResponse({ error: 'No active embedding model found' }, 400)

    const dimensions = getQueryDimensions(model)

    let query = supabase.from('vault_entries').select('id,title,content').limit(limit)
    if (!force) query = query.is('embedding_vector', null)

    const { data: rows, error } = await query
    if (error) throw error

    const entries = (rows ?? []) as EntryRow[]
    const candidates = entries.filter(e => (e.content ?? '').trim().length > 0)

    if (dryRun) {
      return jsonResponse({
        dry_run: true,
        model: { provider: model.provider, name: model.name, dimensions },
        total: entries.length,
        eligible: candidates.length,
      })
    }

    if (candidates.length === 0) {
      return jsonResponse({
        processed: 0,
        success: 0,
        errors: 0,
        model: { provider: model.provider, name: model.name, dimensions },
      })
    }

    const texts = candidates.map(e => `${e.title ?? ''}\n\n${(e.content ?? '').slice(0, MAX_CHARS)}`.trim())
    const embeddings = await embedBatch(texts, model, dimensions)

    if (embeddings.length !== candidates.length) {
      throw new Error(`Embedding count mismatch: got ${embeddings.length}, expected ${candidates.length}`)
    }

    let success = 0
    const errors: { id: string; message: string }[] = []
    for (let i = 0; i < candidates.length; i++) {
      const { error: upErr } = await supabase
        .from('vault_entries')
        .update({ embedding_vector: vectorLiteral(embeddings[i]) })
        .eq('id', candidates[i].id)
      if (upErr) errors.push({ id: candidates[i].id, message: upErr.message })
      else success++
    }

    await supabase
      .from('vault_models')
      .update({ last_used_at: new Date().toISOString(), error_message: null })
      .eq('id', model.id)

    return jsonResponse({
      processed: candidates.length,
      success,
      errors,
      model: { provider: model.provider, name: model.name, dimensions },
    })
  } catch (err) {
    const msg = err instanceof Error ? err.message : JSON.stringify(err)
    return jsonResponse({ error: msg }, 500)
  }
})
