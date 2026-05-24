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
  version: string
  kind: string
  dimension: number
  priority: number
  fallback_order: number
  rollout_percent: number
  status: string
  config: Record<string, unknown> | null
}

function selectedModelPayload(model: VaultModel | null, queryDimensions: number | null) {
  if (!model) return null
  return {
    id: model.id,
    provider: model.provider,
    name: model.name,
    version: model.version,
    kind: model.kind,
    dimension: model.dimension,
    query_dimensions: queryDimensions,
  }
}

function getQueryDimensions(model: VaultModel): number {
  const configured = Number(model.config?.query_dimensions ?? Deno.env.get('EMBEDDING_QUERY_DIMENSIONS'))
  return Number.isInteger(configured) && configured > 0 ? configured : 1536
}

async function selectEmbeddingModel(supabase: ReturnType<typeof createClient>): Promise<VaultModel | null> {
  const { data, error } = await supabase
    .from('vault_models')
    .select('id,name,provider,version,kind,dimension,priority,fallback_order,rollout_percent,status,config')
    .eq('status', 'active')
    .eq('kind', 'embedding')
    .order('priority', { ascending: false })
    .order('fallback_order', { ascending: true })
    .order('created_at', { ascending: false })
    .limit(1)
    .maybeSingle()

  if (error) throw error
  return data as VaultModel | null
}

async function createEmbedding(question: string, model: VaultModel): Promise<{ embedding: number[] | null; error?: string; dimensions: number }> {
  const dimensions = getQueryDimensions(model)
  const apiKey = Deno.env.get('OPENAI_API_KEY')

  if (!apiKey) return { embedding: null, dimensions, error: 'OPENAI_API_KEY not configured' }
  if (model.provider !== 'openai') return { embedding: null, dimensions, error: `Unsupported embedding provider: ${model.provider}` }

  const response = await fetch('https://api.openai.com/v1/embeddings', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      input: question,
      model: model.name,
      dimensions,
      encoding_format: 'float',
    }),
  })

  if (!response.ok) {
    return { embedding: null, dimensions, error: `Embedding request failed: ${response.status}` }
  }

  const payload = await response.json()
  const embedding = payload?.data?.[0]?.embedding
  return Array.isArray(embedding)
    ? { embedding, dimensions }
    : { embedding: null, dimensions, error: 'Embedding response did not include a vector' }
}

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders })
  }
  if (req.method !== 'POST') {
    return jsonResponse({ error: 'Method not allowed' }, 405)
  }

  try {
    const body = await req.json()
    const question = (body.question || '').trim()

    if (!question) {
      return jsonResponse({ error: 'question is required' }, 400)
    }

    const parsedLimit = Number(body.max_sources)
    const limit = Number.isInteger(parsedLimit) && parsedLimit > 0 ? Math.min(parsedLimit, 20) : 5

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
    )

    const selectedModel = await selectEmbeddingModel(supabase)
    const embeddingResult = selectedModel
      ? await createEmbedding(question, selectedModel)
      : { embedding: null, dimensions: null, error: 'No active embedding model found' }

    if (selectedModel) {
      await supabase
        .from('vault_models')
        .update({ last_used_at: new Date().toISOString(), error_message: embeddingResult.error ?? null })
        .eq('id', selectedModel.id)
    }

    const rpcReq: Record<string, unknown> = { query: question, limit }
    if (embeddingResult.embedding) rpcReq.embedding = JSON.stringify(embeddingResult.embedding)

    const { data, error } = await supabase.rpc('query_vector_hybrid', {
      req: rpcReq,
    })

    if (error) throw error

    const sources = (data || []).map((r: Record<string, unknown>) => ({
      title: String(r.title || ''),
      snippet: String(r.snippet || '').replace(/<[^>]+>/g, ''),
      score: Number(r.score || 0),
    }))

    const answer = sources.length === 0
      ? 'Aucune information trouvée dans le vault.'
      : ['Réponse basée sur le vault :', '',
         ...sources.map((s, i) =>
           `[${i + 1}] ${s.title} (score: ${(s.score * 100).toFixed(0)}%)\n${s.snippet}`),
        ].join('\n')

    return jsonResponse({
      answer,
      sources,
      llm_used: false,
      embedding_used: Boolean(embeddingResult.embedding),
      embedding_error: embeddingResult.error ?? null,
      selected_model: selectedModelPayload(selectedModel, embeddingResult.dimensions),
    })
  } catch (err) {
    const msg = err instanceof Error ? err.message : JSON.stringify(err)
    return jsonResponse({ error: msg }, 500)
  }
})
