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
    const { event_id, content, positive, source } = body

    if (!content) {
      return jsonResponse({ error: 'content is required' }, 400)
    }

    const { data, error } = await supabase
      .from('vault_feedback')
      .insert({
        event_id: event_id ?? null,
        content,
        positive: positive ?? true,
        source: source ?? 'runtime',
      })
      .select('id')
      .single()

    if (error) throw error
    return jsonResponse({ id: data.id })
  } catch (err) {
    return jsonResponse({ error: err instanceof Error ? err.message : 'Unknown' }, 400)
  }
})
