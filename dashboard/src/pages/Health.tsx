import { useEffect, useState } from 'react'
import { supabase, type VaultEntry } from '../lib/supabase'

function getHealthColor(entries: VaultEntry[]) {
  const total = entries.length
  if (total === 0) return 'gray'
  const active = entries.filter((e) => e.status === 'active').length
  const ratio = active / total
  if (ratio >= 0.9) return 'green'
  if (ratio >= 0.7) return 'yellow'
  return 'red'
}

export default function Health() {
  const [entries, setEntries] = useState<VaultEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase
      .from('vault_entries')
      .select('id, title, type, status, freshness, sensitivity, created_at')
      .order('created_at', { ascending: false })
      .limit(50)
      .then(({ data, error }) => {
        if (!error && data) setEntries(data as VaultEntry[])
        setLoading(false)
      })

    const sub = supabase
      .channel('vault_entries_changes')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'vault_entries' }, () => {
        supabase
          .from('vault_entries')
          .select('id, title, type, status, freshness, sensitivity, created_at')
          .order('created_at', { ascending: false })
          .limit(50)
          .then(({ data }) => {
            if (data) setEntries(data as VaultEntry[])
          })
      })
      .subscribe()

    return () => { sub.unsubscribe() }
  }, [])

  const color = getHealthColor(entries)
  const activeCount = entries.filter((e) => e.status === 'active').length
  const staleCount = entries.filter((e) => e.freshness === 'deprecated').length
  const byType = entries.reduce<Record<string, number>>((acc, e) => {
    acc[e.type] = (acc[e.type] || 0) + 1
    return acc
  }, {})

  return (
    <div>
      <h1>Vault Health</h1>
      <div className="health-badge" data-color={color}>
        <span className="dot" />
        {color === 'green' ? 'Healthy' : color === 'yellow' ? 'Degraded' : color === 'red' ? 'Unhealthy' : 'Unknown'}
      </div>

      {loading ? (
        <p>Loading entries…</p>
      ) : (
        <div className="grid-3">
          <div className="card">
            <strong>{entries.length}</strong>
            <span>Total entries</span>
          </div>
          <div className="card">
            <strong>{activeCount}</strong>
            <span>Active</span>
          </div>
          <div className="card">
            <strong>{staleCount}</strong>
            <span>Deprecated</span>
          </div>
        </div>
      )}

      <h2>By type</h2>
      <table>
        <thead>
          <tr><th>Type</th><th>Count</th></tr>
        </thead>
        <tbody>
          {Object.entries(byType).map(([type, count]) => (
            <tr key={type}><td>{type}</td><td>{count}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
