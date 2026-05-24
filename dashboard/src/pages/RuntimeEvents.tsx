import { useEffect, useState } from 'react'
import { supabase, type VaultMemory, type VaultFeedback } from '../lib/supabase'

export default function RuntimeEvents() {
  const [memories, setMemories] = useState<VaultMemory[]>([])
  const [feedback, setFeedback] = useState<VaultFeedback[]>([])

  useEffect(() => {
    Promise.all([
      supabase.from('vault_memories').select('*').order('created_at', { ascending: false }).limit(20),
      supabase.from('vault_feedback').select('*').order('created_at', { ascending: false }).limit(20),
    ]).then(([memRes, fbRes]) => {
      if (!memRes.error && memRes.data) setMemories(memRes.data as VaultMemory[])
      if (!fbRes.error && fbRes.data) setFeedback(fbRes.data as VaultFeedback[])
    })

    const memSub = supabase
      .channel('memories_changes')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'vault_memories' }, (payload) => {
        setMemories((prev) => [payload.new as VaultMemory, ...prev].slice(0, 20))
      })
      .subscribe()

    const fbSub = supabase
      .channel('feedback_changes')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'vault_feedback' }, (payload) => {
        setFeedback((prev) => [payload.new as VaultFeedback, ...prev].slice(0, 20))
      })
      .subscribe()

    return () => {
      memSub.unsubscribe()
      fbSub.unsubscribe()
    }
  }, [])

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
