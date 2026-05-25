import { handleCors, jsonResponse } from '../_shared/cors.ts'
import {
  createServiceClient,
  getTenantBySlug,
  hasTenantManagementRole,
  isPlatformAdmin,
  isTenantMemberRole,
  isTenantMemberStatus,
  isValidTenantSlug,
  requireNonEmptyText,
  resolveCallerUserId,
} from '../_shared/tenants.ts'

Deno.serve(async (req: Request) => {
  const cors = handleCors(req)
  if (cors) return cors

  try {
    const body = await req.json()

    const tenantSlug = body.tenant_slug
    if (!isValidTenantSlug(tenantSlug)) {
      return jsonResponse({ error: 'tenant_slug must be a valid tenant slug' }, 400)
    }

    const userId = requireNonEmptyText(body.user_id, 'user_id')

    const role = body.role === undefined ? 'member' : body.role
    if (!isTenantMemberRole(role)) {
      return jsonResponse({ error: 'Invalid role' }, 400)
    }

    const status = body.status === undefined ? 'active' : body.status
    if (!isTenantMemberStatus(status)) {
      return jsonResponse({ error: 'Invalid member status' }, 400)
    }

    const supabase = createServiceClient()
    const tenant = await getTenantBySlug(supabase, tenantSlug)
    if (!tenant) {
      return jsonResponse({ error: `Tenant "${tenantSlug}" not found` }, 404)
    }
    if (tenant.status !== 'active') {
      return jsonResponse({ error: `Tenant "${tenantSlug}" is not active` }, 409)
    }

    // Authorization: platform admin OR an active owner/admin member of this tenant.
    let authorized = await isPlatformAdmin(req)
    let callerUserId: string | null = null
    if (!authorized) {
      callerUserId = await resolveCallerUserId(req)
      if (!callerUserId) {
        return jsonResponse({ error: 'Authentication required' }, 401)
      }
      authorized = await hasTenantManagementRole(supabase, tenant.id, callerUserId)
    }
    if (!authorized) {
      return jsonResponse({ error: 'Tenant owner or admin role required' }, 403)
    }

    // Only platform admins (or the original owner) may assign the owner role.
    if (role === 'owner' && callerUserId !== null) {
      const ownerByCaller = tenant.owner_user_id === callerUserId
      if (!ownerByCaller) {
        return jsonResponse({ error: 'Only platform admin or tenant owner may assign owner role' }, 403)
      }
    }

    const { data: member, error: upsertError } = await supabase
      .from('vault_tenant_members')
      .upsert(
        {
          tenant_id: tenant.id,
          user_id: userId,
          role,
          status,
        },
        { onConflict: 'tenant_id,user_id', ignoreDuplicates: false },
      )
      .select('id,tenant_id,user_id,role,status,created_at,updated_at')
      .single()
    if (upsertError) throw upsertError

    return jsonResponse({ tenant: { id: tenant.id, slug: tenant.slug }, member })
  } catch (err) {
    return jsonResponse({ error: err instanceof Error ? err.message : String(err) }, 400)
  }
})
