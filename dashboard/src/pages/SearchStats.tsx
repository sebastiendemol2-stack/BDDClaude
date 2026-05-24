import { useEffect, useState } from 'react'
import { supabase, type VaultEntry } from '../lib/supabase'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function SearchStats() {
  const [entries, setEntries] = useState<VaultEntry[]>([])

  useEffect(() => {
    supabase
      .from('vault_entries')
      .select('id, title, type, status, created_at')
      .order('created_at', { ascending: false })
      .limit(100)
      .then(({ data }) => {
        if (data) setEntries(data as VaultEntry[])
      })
  }, [])

  const byFreshness = entries.reduce<Record<string, number>>((acc, e) => {
    acc[e.status] = (acc[e.status] || 0) + 1
    return acc
  }, {})

  const chartData = Object.entries(byFreshness).map(([name, value]) => ({ name, value }))

  return (
    <div>
      <h1>Search Stats</h1>
      <p>{entries.length} vault entries indexed</p>

      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData}>
          <XAxis dataKey="name" />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Bar dataKey="value" fill="var(--accent)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>

      <h2>Recent entries</h2>
      <table>
        <thead>
          <tr><th>Title</th><th>Type</th><th>Status</th><th>Created</th></tr>
        </thead>
        <tbody>
          {entries.slice(0, 20).map((e) => (
            <tr key={e.id}>
              <td>{e.title}</td>
              <td>{e.type}</td>
              <td>{e.status}</td>
              <td>{new Date(e.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
