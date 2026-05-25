import { useTenant } from '../lib/tenants'

export default function TenantSelector() {
  const { tenants, selectedTenant, setSelectedTenant, loading } = useTenant()

  if (loading) return <span className="muted" style={{ fontSize: '0.8rem' }}>Loading...</span>
  if (tenants.length === 0) return null

  return (
    <div style={{ padding: '0.5rem 0.75rem', borderTop: '1px solid var(--border)', marginTop: 'auto' }}>
      <label style={{ fontSize: '0.7rem', color: 'var(--gray)', display: 'block', marginBottom: 4 }}>
        Tenant
      </label>
      <select
        value={selectedTenant?.id ?? ''}
        onChange={(e) => {
          const t = tenants.find((t) => t.id === e.target.value) ?? null
          setSelectedTenant(t)
        }}
        style={{
          width: '100%',
          padding: '0.3rem 0.4rem',
          fontSize: '0.8rem',
          border: '1px solid var(--border)',
          borderRadius: 4,
          background: 'var(--card)',
          color: 'var(--text)',
        }}
      >
        {tenants.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name} ({t.slug})
          </option>
        ))}
      </select>
    </div>
  )
}
