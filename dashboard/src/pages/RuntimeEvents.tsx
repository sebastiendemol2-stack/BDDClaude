import { useEffect, useState } from 'react'
import { supabase, type VaultMemory, type VaultFeedback } from '../lib/supabase'
import { useTenant } from '../lib/tenants'

export default function RuntimeEvents() {
  const [memories, setMemories] = useState<VaultMemory[]>([])
  const [feedback, setFeedback] = useState<VaultFeedback[]>([])
  const { selectedTenant, loading: tenantsLoading } = useTenant()
  const tenantId = selectedTenant?.id

  function buildMemoriesQuery(activeTenantId: string) {
    return supabase
      .from('vault_memories')
      .select('*')
      .eq('tenant_id', activeTenantId)
      .order('created_at', { ascending: false })
      .limit(20)
  }

  function buildFeedbackQuery(activeTenantId: string) {
    return supabase
      .from('vault_feedback')
      .select('*')
      .eq('tenant_id', activeTenantId)
      .order('created_at', { ascending: false })
      .limit(20)
  }

  useEffect(() => {
    if (tenantsLoading) return
    if (!tenantId) {
      setMemories([])
      setFeedback([])
      return
    }

    Promise.all([
      buildMemoriesQuery(tenantId),
      buildFeedbackQuery(tenantId),
    ]).then(([memRes, fbRes]) => {
      if (!memRes.error && memRes.data) setMemories(memRes.data as VaultMemory[])
      if (!fbRes.error && fbRes.data) setFeedback(fbRes.data as VaultFeedback[])
    })

    const channelFilter = `tenant_id=eq.${tenantId}`

    const memSub = supabase
      .channel('memories_changes')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'vault_memories', filter: channelFilter }, (payload) => {
        const mem = payload.new as VaultMemory
        if (mem.tenant_id !== tenantId) return
        setMemories((prev) => [mem, ...prev].slice(0, 20))
      })
      .subscribe()

    const fbSub = supabase
      .channel('feedback_changes')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'vault_feedback', filter: channelFilter }, (payload) => {
        const fb = payload.new as VaultFeedback
        if (fb.tenant_id !== tenantId) return
        setFeedback((prev) => [fb, ...prev].slice(0, 20))
      })
      .subscribe()

    return () => {
      memSub.unsubscribe()
      fbSub.unsubscribe()
    }
  }, [tenantId, tenantsLoading])

  return (
    <div>
      <h1>Runtime Events</h1>

      <section>
        <h2>Memories ({memories.length})</h2>
        {memories.length === 0 ? (
          <p className="empty">No memories stored yet</p>
        ) : (
          <table>
            <thead>
              <tr><th>Project</th><th>Summary</th><th>Created</th></tr>
            </thead>
            <tbody>
              {memories.map((m) => (
                <tr key={m.id}>
                  <td>{m.project_slug}</td>
                  <td>{m.summary}</td>
                  <td>{new Date(m.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h2>Feedback ({feedback.length})</h2>
        {feedback.length === 0 ? (
          <p className="empty">No feedback collected yet</p>
        ) : (
          <table>
            <thead>
              <tr><th>Content</th><th>Positive</th><th>Source</th><th>Created</th></tr>
            </thead>
            <tbody>
              {feedback.map((f) => (
                <tr key={f.id}>
                  <td>{f.content}</td>
                  <td>{f.positive ? '👍' : '👎'}</td>
                  <td>{f.source}</td>
                  <td>{new Date(f.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
