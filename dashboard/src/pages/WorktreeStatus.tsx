import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

interface WorktreeReport {
  id: string
  report: {
    timestamp: string
    total_worktrees: number
    stale_count: number
    lock_count: number
    uncommitted_count: number
    worktrees: Array<{
      path: string
      branch: string
      head: string
      is_main: boolean
      last_commit_date: string | null
      days_since_last_commit: number | null
      has_uncommitted: boolean
      has_lock: boolean
      is_stale: boolean
      lock_reason: string | null
      uncommitted_files: string[]
      uncommitted_count: number
    }>
  }
  summary: {
    total_worktrees: number
    stale_count: number
    lock_count: number
    uncommitted_count: number
  }
  created_at: string
}

function ageColor(days: number | null): string {
  if (days === null) return 'gray'
  if (days > 30) return 'red'
  if (days > 7) return 'yellow'
  return 'green'
}

export default function WorktreeStatus() {
  const [latest, setLatest] = useState<WorktreeReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    supabase
      .from('vault_worktree_reports')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(1)
      .single()
      .then(({ data, error: err }) => {
        if (err && err.code !== 'PGRST116') {
          setError(err.message)
        } else if (data) {
          setLatest(data as WorktreeReport)
        }
        setLoading(false)
      })

    const sub = supabase
      .channel('worktree_reports_changes')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'vault_worktree_reports' }, (payload) => {
        setLatest(payload.new as WorktreeReport)
      })
      .subscribe()

    return () => { sub.unsubscribe() }
  }, [])

  if (loading) return <div><h1>Worktree Status</h1><p>Loading...</p></div>
  if (error) return <div><h1>Worktree Status</h1><p className="error">{error}</p></div>
  if (!latest) {
    return (
      <div>
        <h1>Worktree Status</h1>
        <p className="empty">
          No report available. Run{' '}
          <code>scripts/inspect_worktrees.ps1 -PushReport</code> to generate the first report.
        </p>
      </div>
    )
  }

  const { report, summary, created_at } = latest

  return (
    <div>
      <h1>Worktree Status</h1>
      <p className="meta">Last updated: {new Date(created_at).toLocaleString()}</p>

      <div className="grid-3">
        <div className="card">
          <strong>{summary.total_worktrees}</strong>
          <span>Total worktrees</span>
        </div>
        <div className="card" data-color={summary.stale_count > 0 ? 'red' : 'green'}>
          <strong>{summary.stale_count}</strong>
          <span>Stale (&gt;30d)</span>
        </div>
        <div className="card" data-color={summary.lock_count > 0 ? 'red' : 'green'}>
          <strong>{summary.lock_count}</strong>
          <span>Locked</span>
        </div>
      </div>

      <h2>Worktrees</h2>
      <table>
        <thead>
          <tr>
            <th>Branch</th>
            <th>Path</th>
            <th>Age</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {report.worktrees.map((wt) => {
            const branchShort = wt.branch.replace('refs/heads/', '')
            const status = wt.is_main ? 'main' : wt.has_lock ? 'locked' : wt.is_stale ? 'stale' : wt.has_uncommitted ? 'dirty' : 'clean'
            return (
              <tr key={wt.branch}>
                <td>{branchShort}</td>
                <td title={wt.path}>{wt.path.split('/').pop()}</td>
                <td>
                  <span className="badge" data-color={ageColor(wt.days_since_last_commit)}>
                    {wt.days_since_last_commit !== null ? `${wt.days_since_last_commit}d` : '?'}
                  </span>
                </td>
                <td>
                  <span className="badge" data-color={status === 'main' ? 'green' : status === 'locked' ? 'red' : status === 'stale' ? 'yellow' : status === 'dirty' ? 'yellow' : 'green'}>
                    {status}
                  </span>
                  {wt.has_uncommitted && <span className="count">{wt.uncommitted_count} files</span>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {report.worktrees.filter(w => w.has_lock).length > 0 && (
        <>
          <h2>Lock details</h2>
          {report.worktrees.filter(w => w.has_lock).map(wt => (
            <div key={wt.branch} className="card" data-color="red">
              <strong>{wt.branch.replace('refs/heads/', '')}</strong>
              <p>{wt.lock_reason}</p>
              <ul>
                {wt.uncommitted_files.map(f => <li key={f}>{f}</li>)}
              </ul>
            </div>
          ))}
        </>
      )}
    </div>
  )
}
