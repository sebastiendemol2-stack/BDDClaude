import { createClient } from 'jsr:@supabase/supabase-js@2'
import { handleCors, jsonResponse } from '../_shared/cors.ts'

const validRelationTypes = ['references', 'decides', 'depends_on', 'related_to']

Deno.serve(async (req: Request) => {
  const cors = handleCors(req)
  if (cors) return cors

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
  )

  try {
    const body = await req.json()
    const { source_entry_id, target_entry_id, relation_type, confidence, metadata } = body

    if (!source_entry_id || !target_entry_id || !relation_type) {
      return jsonResponse(
        { error: 'source_entry_id, target_entry_id, and relation_type are required' },
        400,
      )
    }

    if (!validRelationTypes.includes(relation_type)) {
      return jsonResponse(
        { error: `relation_type must be one of: ${validRelationTypes.join(', ')}` },
        400,
      )
    }

    const { data, error } = await supabase
      .from('vault_relations')
      .upsert(
        {
          source_entry_id, target_entry_id, relation_type,
          confidence: confidence ?? 0.5,
          metadata: metadata ?? {},
        },
        { onConflict: 'source_entry_id,target_entry_id,relation_type', ignoreDuplicates: false },
      )
      .select('id')
      .single()

    if (error) throw error
    return jsonResponse({ id: data.id })
  } catch (err) {
    return jsonResponse({ error: err instanceof Error ? err.message : 'Unknown' }, 400)
  }
})
