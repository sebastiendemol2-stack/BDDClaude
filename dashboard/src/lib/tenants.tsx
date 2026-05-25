import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { supabase } from './supabase'
import { useAuth } from './auth'

export type Tenant = {
  id: string
  slug: string
  name: string
  status: string
}

type TenantsContextValue = {
  tenants: Tenant[]
  selectedTenant: Tenant | null
  setSelectedTenant: (tenant: Tenant | null) => void
  loading: boolean
}

const TenantsContext = createContext<TenantsContextValue | undefined>(undefined)

function persistKey(userId: string) {
  return `bddclaude:selected_tenant:${userId}`
}

export function TenantsProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth()
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [selectedTenant, setSelectedTenantState] = useState<Tenant | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (authLoading) {
      setLoading(true)
      return
    }

    if (!user) {
      setTenants([])
      setSelectedTenantState(null)
      setLoading(false)
      return
    }

    setLoading(true)

    supabase
      .from('vault_tenants')
      .select('id, slug, name, status')
      .eq('status', 'active')
      .then(({ data, error }) => {
        const nextTenants = !error && data ? (data as Tenant[]) : []
        setTenants(nextTenants)

        const stored = localStorage.getItem(persistKey(user.id))
        const match = stored ? nextTenants.find((t) => t.id === stored) : null
        setSelectedTenantState(match ?? (nextTenants[0] ?? null))
        setLoading(false)
      })
  }, [authLoading, user])

  const setSelectedTenant = (tenant: Tenant | null) => {
    setSelectedTenantState(tenant)
    if (user && tenant) {
      localStorage.setItem(persistKey(user.id), tenant.id)
    }
  }

  const value = useMemo(() => ({ tenants, selectedTenant, setSelectedTenant, loading }), [tenants, selectedTenant, loading])

  return <TenantsContext.Provider value={value}>{children}</TenantsContext.Provider>
}

export function useTenant(): TenantsContextValue {
  const ctx = useContext(TenantsContext)
  if (!ctx) throw new Error('useTenant must be used inside a TenantsProvider')
  return ctx
}
