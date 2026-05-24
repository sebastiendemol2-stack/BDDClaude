import { useEffect, useMemo, useState } from 'react'
import type { VaultModel, VaultModelStatus } from '../lib/supabase'
import { useAuth } from '../lib/auth'

type ModelListResponse = {
  models: VaultModel[]
  active: VaultModel[]
  total: number
  admin: boolean
}

type ModelLatestResponse = {
  model: VaultModel | null
  fallbacks: VaultModel[]
  total: number
}

type ModelForm = {
  name: string
  provider: string
  version: string
  kind: VaultModel['kind']
  dimension: number
  priority: number
  fallback_order: number
  rollout_percent: number
  status: VaultModelStatus
}

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL?.replace(/\/$/, '') ?? ''
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? ''
const legacyAdminToken = import.meta.env.VITE_MODEL_REGISTRY_ADMIN_TOKEN ?? ''

const emptyForm: ModelForm = {
  name: '',
  provider: 'openai',
  version: '1.0.0',
  kind: 'embedding',
  dimension: 1536,
  priority: 0,
  fallback_order: 100,
  rollout_percent: 0,
  status: 'active',
}

function functionUrl(slug: string) {
  return `${supabaseUrl}/functions/v1/${slug}`
}

function buildHeaders({
  includeAdmin,
  accessToken,
}: {
  includeAdmin: boolean
  accessToken: string | null
}): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    apikey: anonKey,
    Authorization: `Bearer ${anonKey}`,
  }
  if (includeAdmin && accessToken) {
    headers.Authorization = `Bearer ${accessToken}`
    return headers
  }
  if (includeAdmin && legacyAdminToken) {
    headers['x-admin-token'] = legacyAdminToken
    return headers
  }
  return headers
}

function statusClass(status: VaultModelStatus) {
  if (status === 'active') return 'badge-green'
  if (status === 'inactive') return 'badge-yellow'
  return 'badge-red'
}

export default function Models() {
  const { session, isAdmin } = useAuth()
  const accessToken = session?.access_token ?? null

  const [models, setModels] = useState<VaultModel[]>([])
  const [latest, setLatest] = useState<ModelLatestResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState<ModelForm>(emptyForm)

  const canAdmin = isAdmin || Boolean(legacyAdminToken)
  const activeModels = useMemo(() => models.filter((model) => model.status === 'active'), [models])

  async function postJson<T>(
    slug: string,
    payload: Record<string, unknown>,
    includeAdmin = false,
  ): Promise<T> {
    const response = await fetch(functionUrl(slug), {
      method: 'POST',
      headers: buildHeaders({ includeAdmin, accessToken }),
      body: JSON.stringify(payload),
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error ?? `${slug} returned ${response.status}`)
    return data as T
  }

  async function loadModels() {
    setLoading(true)
    setError('')
    try {
      const [listData, latestData] = await Promise.all([
        postJson<ModelListResponse>('model-list', { include_inactive: canAdmin }, canAdmin),
        postJson<ModelLatestResponse>('model-latest', { kind: 'embedding' }),
      ])
      setModels(listData.models)
      setLatest(latestData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load model registry')
      setModels([])
      setLatest(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadModels()
  }, [canAdmin, accessToken])

  async function registerModel(event: React.FormEvent) {
    event.preventDefault()
    if (!canAdmin || saving) return

    setSaving(true)
    setError('')
    try {
      await postJson('model-register', form, true)
      setShowForm(false)
      setForm(emptyForm)
      await loadModels()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to register model')
    } finally {
      setSaving(false)
    }
  }

  async function updateStatus(model: VaultModel, status: VaultModelStatus) {
    if (!canAdmin || saving) return

    setSaving(true)
    setError('')
    try {
      await postJson('model-deactivate', { id: model.id, status }, true)
      await loadModels()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update model status')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Model Registry</h1>
          {latest?.model && (
            <p className="muted">
              Latest embedding model: <strong>{latest.model.provider}/{latest.model.name}</strong>
            </p>
          )}
          {!canAdmin && (
            <p className="muted">Sign in with an admin account to manage models.</p>
          )}
        </div>
        {canAdmin && (
          <button className="btn-primary" onClick={() => setShowForm((value) => !value)}>
            {showForm ? 'Cancel' : 'Register'}
          </button>
        )}
      </div>

      {error && <div className="alert-error">{error}</div>}

      {showForm && canAdmin && (
        <form onSubmit={registerModel} className="model-form">
          <input placeholder="Name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
          <input placeholder="Provider" value={form.provider} onChange={(event) => setForm({ ...form, provider: event.target.value })} required />
          <input placeholder="Version" value={form.version} onChange={(event) => setForm({ ...form, version: event.target.value })} required />
          <select value={form.kind} onChange={(event) => setForm({ ...form, kind: event.target.value as VaultModel['kind'] })}>
            <option value="embedding">Embedding</option>
            <option value="chat">Chat</option>
            <option value="reranker">Reranker</option>
            <option value="vision">Vision</option>
            <option value="audio">Audio</option>
            <option value="tool">Tool</option>
          </select>
          <input type="number" min={1} placeholder="Dimension" value={form.dimension} onChange={(event) => setForm({ ...form, dimension: Number(event.target.value) })} />
          <input type="number" placeholder="Priority" value={form.priority} onChange={(event) => setForm({ ...form, priority: Number(event.target.value) })} />
          <input type="number" min={0} max={1000} placeholder="Fallback" value={form.fallback_order} onChange={(event) => setForm({ ...form, fallback_order: Number(event.target.value) })} />
          <input type="number" min={0} max={100} placeholder="Rollout %" value={form.rollout_percent} onChange={(event) => setForm({ ...form, rollout_percent: Number(event.target.value) })} />
          <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as VaultModelStatus })}>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="deprecated">Deprecated</option>
            <option value="error">Error</option>
          </select>
          <button type="submit" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
        </form>
      )}

      {latest && (
        <div className="grid-3">
          <div className="card">
            <strong>{models.length}</strong>
            <span>Total models</span>
          </div>
          <div className="card">
            <strong>{activeModels.length}</strong>
            <span>Active</span>
          </div>
          <div className="card">
            <strong>{latest.fallbacks.length}</strong>
            <span>Fallbacks</span>
          </div>
        </div>
      )}

      {loading ? <p className="empty">Loading...</p> : (
        <table>
          <thead>
            <tr>
              <th>Model</th>
              <th>Kind</th>
              <th>Dims</th>
              <th>Priority</th>
              <th>Fallback</th>
              <th>Rollout</th>
              <th>Status</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {models.map((model) => (
              <tr key={model.id}>
                <td>
                  <strong>{model.provider}/{model.name}</strong>
                  <br />
                  <span className="muted">v{model.version}</span>
                </td>
                <td>{model.kind}</td>
                <td>{model.dimension}</td>
                <td>{model.priority}</td>
                <td>{model.fallback_order}</td>
                <td>{model.rollout_percent}%</td>
                <td>
                  {canAdmin ? (
                    <select className="status-select" value={model.status} disabled={saving} onChange={(event) => updateStatus(model, event.target.value as VaultModelStatus)}>
                      <option value="active">Active</option>
                      <option value="inactive">Inactive</option>
                      <option value="deprecated">Deprecated</option>
                      <option value="error">Error</option>
                    </select>
                  ) : (
                    <span className={`badge ${statusClass(model.status)}`}>{model.status}</span>
                  )}
                </td>
                <td>{new Date(model.updated_at ?? model.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
