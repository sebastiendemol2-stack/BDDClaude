import { createClient } from 'jsr:@supabase/supabase-js@2'
import { handleCors, jsonResponse } from '../_shared/cors.ts'

Deno.serve(async (req: Request) => {
  const cors = handleCors(req)
  if (cors) return cors

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
  )

  try {
    const body = await req.json()
    const { session_id, project_slug, summary, decisions, patterns, embedding } = body

    if (!session_id || !project_slug || !summary) {
      return jsonResponse({ error: 'session_id, project_slug, and summary are required' }, 400)
    }

    const { data, error } = await supabase
      .from('vault_memories')
      .upsert(
        {
          session_id, project_slug, summary,
          decisions: decisions ?? [],
          patterns: patterns ?? [],
          ...(embedding ? { embedding } : {}),
        },
        { onConflict: 'session_id', ignoreDuplicates: false },
      )
      .select('id')
      .single()

    if (error) throw error
    return jsonResponse({ id: data.id })
  } catch (err) {
    return jsonResponse({ error: err instanceof Error ? err.message : 'Unknown' }, 400)
  }
})
