import { handleCors, jsonResponse } from '../_shared/cors.ts'
import {
  createServiceClient,
  isPlatformAdmin,
  isTenantStatus,
  isValidTenantSlug,
  requireNonEmptyText,
} from '../_shared/tenants.ts'

Deno.serve(async (req: Request) => {
  const cors = handleCors(req)
  if (cors) return cors

  if (!(await isPlatformAdmin(req))) {
    return jsonResponse({ error: 'Platform admin authorization required' }, 401)
  }

  try {
    const body = await req.json()

    const slug = body.slug
    if (!isValidTenantSlug(slug)) {
      return jsonResponse(
        { error: 'slug must match ^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$ or a single [a-z0-9] character' },
        400,
      )
    }

    const name = requireNonEmptyText(body.name, 'name')

    const status = body.status === undefined ? 'active' : body.status
    if (!isTenantStatus(status)) {
      return jsonResponse({ error: 'Invalid tenant status' }, 400)
    }

    const ownerUserId = body.owner_user_id === undefined || body.owner_user_id === null
      ? null
      : requireNonEmptyText(body.owner_user_id, 'owner_user_id')

    const metadata = body.metadata === undefined ? {} : body.metadata
    if (typeof metadata !== 'object' || metadata === null || Array.isArray(metadata)) {
      return jsonResponse({ error: 'metadata must be an object' }, 400)
    }

    const supabase = createServiceClient()

    const { data: existing, error: existingError } = await supabase
      .from('vault_tenants')
      .select('id,slug')
      .eq('slug', slug)
      .maybeSingle()
    if (existingError) throw existingError
    if (existing) {
      return jsonResponse({ error: `Tenant slug "${slug}" already exists` }, 409)
    }

    const { data: tenant, error: insertError } = await supabase
      .from('vault_tenants')
      .insert({
        slug,
        name,
        status,
        owner_user_id: ownerUserId,
        metadata: { ...metadata, created_by: 'tenant-create' },
      })
      .select('id,slug,name,status,owner_user_id,metadata,created_at,updated_at')
      .single()
    if (insertError) throw insertError

    let ownerMember = null
    if (ownerUserId) {
      const { data: member, error: memberError } = await supabase
        .from('vault_tenant_members')
        .insert({
          tenant_id: tenant.id,
          user_id: ownerUserId,
          role: 'owner',
          status: 'active',
        })
        .select('id,tenant_id,user_id,role,status,created_at,updated_at')
        .single()
      if (memberError) {
        // Rollback the tenant insert to avoid an owner-less tenant row.
        await supabase.from('vault_tenants').delete().eq('id', tenant.id)
        throw memberError
      }
      ownerMember = member
    }

    return jsonResponse({ tenant, owner_member: ownerMember }, 201)
  } catch (err) {
    return jsonResponse({ error: err instanceof Error ? err.message : String(err) }, 400)
  }
})
