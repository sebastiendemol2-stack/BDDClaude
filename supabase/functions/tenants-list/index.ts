import { corsHeaders, jsonResponse } from '../_shared/cors.ts'
import { createClient } from 'jsr:@supabase/supabase-js@2'

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: corsHeaders })
  if (req.method !== 'GET' && req.method !== 'POST') {
    return jsonResponse({ error: 'Method not allowed' }, 405)
  }

  try {
    const authHeader = req.headers.get('Authorization')
    if (!authHeader?.startsWith('Bearer ')) {
      return jsonResponse({ error: 'Missing or invalid Authorization header' }, 401)
    }

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_ANON_KEY')!,
      { global: { headers: { Authorization: authHeader } } },
    )

    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) {
      return jsonResponse({ error: 'Unauthorized' }, 401)
    }

    const supabaseAdmin = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
    )

    const { data: memberships, error: membershipsError } = await supabaseAdmin
      .from('vault_tenant_members')
      .select('tenant_id, role, status, tenants:vault_tenants(slug, name, status)')
      .eq('user_id', user.id)
      .eq('status', 'active')

    if (membershipsError) throw membershipsError

    const tenants = (memberships ?? []).map((m: Record<string, unknown>) => ({
      id: m.tenant_id,
      role: m.role,
      ...((m.tenants ?? {}) as Record<string, unknown>),
    }))

    return jsonResponse({ tenants, total: tenants.length })
  } catch (err) {
    return jsonResponse({ error: err instanceof Error ? err.message : String(err) }, 500)
  }
})
