import { useEffect, useRef, useState } from 'react'
import { Network, type Options } from 'vis-network'
import { DataSet } from 'vis-data'
import { supabase, type VaultEntry, type VaultRelation } from '../lib/supabase'

type GraphStatus = 'loading' | 'ready' | 'error'
type FilterType = 'all' | 'references' | 'decides' | 'depends_on' | 'related_to'

const TYPE_COLORS: Record<string, string> = {
  concept: '#6366f1',
  projet: '#f59e0b',
  decision: '#ef4444',
  contexte: '#8b5cf6',
  recherche: '#06b6d4',
  ressource: '#10b981',
  personne: '#ec4899',
  daily: '#78716c',
  index: '#1e293b',
}

export default function Graph() {
  const containerRef = useRef<HTMLDivElement>(null)
  const networkRef = useRef<Network | null>(null)
  const [status, setStatus] = useState<GraphStatus>('loading')
  const [error, setError] = useState<string>('')
  const [nodeCount, setNodeCount] = useState(0)
  const [edgeCount, setEdgeCount] = useState(0)
  const [filterType, setFilterType] = useState<FilterType>('all')
  const [selectedNode, setSelectedNode] = useState<VaultEntry | null>(null)
  const nodesRef = useRef<DataSet<{ id: string; label: string; group: string; title: string; value: number }>>(new DataSet())
  const edgesRef = useRef<DataSet<{ id: string; from: string; to: string; label: string; color: string; dashes: boolean }>>(new DataSet())

  const loadGraph = async (filter: FilterType) => {
    setStatus('loading')
    try {
      const [entriesRes, relationsRes] = await Promise.all([
        supabase.from('vault_entries').select('id, obsidian_path, title, type, status').in('type', ['concept', 'projet', 'decision', 'contexte', 'recherche', 'ressource', 'personne', 'daily', 'index']),
        supabase.from('vault_relations').select('*'),
      ])
      if (entriesRes.error) throw entriesRes.error
      if (relationsRes.error) throw relationsRes.error

      const entries = entriesRes.data as (VaultEntry & { obsidian_path: string })[]
      const relations = relationsRes.data as VaultRelation[]

      const filtered = filter === 'all' ? relations : relations.filter(r => r.relation_type === filter)

      const entryMap = new Map(entries.map(e => [e.obsidian_path, e]))
      const nodeDegrees = new Map<string, number>()
      for (const rel of filtered) {
        nodeDegrees.set(rel.source_entry_id, (nodeDegrees.get(rel.source_entry_id) || 0) + 1)
        nodeDegrees.set(rel.target_entry_id, (nodeDegrees.get(rel.target_entry_id) || 0) + 1)
      }

      const maxDegree = Math.max(...nodeDegrees.values(), 1)
      const nodes = entries
        .filter(e => nodeDegrees.has(e.obsidian_path))
        .map(e => ({
          id: e.obsidian_path,
          label: e.title || e.obsidian_path.split('/').pop()?.replace('.md', '') || e.obsidian_path,
          group: e.type,
          title: `${e.title || 'Untitled'}\nType: ${e.type}\nStatus: ${e.status}\nConnections: ${nodeDegrees.get(e.obsidian_path) || 0}`,
          value: 10 + ((nodeDegrees.get(e.obsidian_path) || 0) / maxDegree) * 40,
        }))

      const edges = filtered.map(r => ({
        id: r.id,
        from: r.source_entry_id,
        to: r.target_entry_id,
        label: r.relation_type,
        color: RELATION_COLORS[r.relation_type] || '#94a3b8',
        dashes: r.relation_type === 'references',
      }))

      nodesRef.current.clear()
      edgesRef.current.clear()
      nodesRef.current.add(nodes)
      edgesRef.current.add(edges)

      setNodeCount(nodes.length)
      setEdgeCount(edges.length)
      setStatus('ready')

      if (containerRef.current && !networkRef.current) {
        const options: Options = {
          nodes: {
            shape: 'dot',
            size: 20,
            font: { size: 12, color: '#e2e8f0' },
            borderWidth: 2,
            color: {
              border: '#334155',
              background: '#475569',
            },
          },
          edges: {
            width: 1.5,
            font: { size: 10, color: '#94a3b8', strokeWidth: 0 },
            arrows: { to: { enabled: true, scaleFactor: 0.6 } },
            smooth: { enabled: true, type: 'continuous', roundness: 0.5 },
          },
          physics: {
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
              gravitationalConstant: -40,
              centralGravity: 0.005,
              springLength: 200,
              springConstant: 0.02,
              damping: 0.4,
            },
            stabilization: { iterations: 100 },
          },
          interaction: {
            hover: true,
            tooltipDelay: 200,
            navigationButtons: true,
            keyboard: true,
          },
          groups: Object.fromEntries(
            Object.entries(TYPE_COLORS).map(([key, color]) => [
              key,
              { color: { background: color, border: color }, font: { color: '#e2e8f0' } },
            ])
          ),
        }
        networkRef.current = new Network(containerRef.current, { nodes: nodesRef.current, edges: edgesRef.current }, options)
        networkRef.current.on('click', (params) => {
          if (params.nodes.length > 0) {
            const nodeId = params.nodes[0]
            const entry = entryMap.get(nodeId)
            if (entry) setSelectedNode(entry)
          } else {
            setSelectedNode(null)
          }
        })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load graph')
      setStatus('error')
    }
  }

  useEffect(() => {
    loadGraph(filterType)
    return () => {
      if (networkRef.current) {
        networkRef.current.destroy()
        networkRef.current = null
      }
    }
  }, [filterType])

  return (
    <div className="graph-page">
      <div className="graph-header">
        <h1>Memory Graph</h1>
        <div className="graph-controls">
          <span className="graph-info">{nodeCount} nodes · {edgeCount} edges</span>
          <div className="filter-buttons">
            {(['all', 'references', 'decides', 'depends_on', 'related_to'] as FilterType[]).map(t => (
              <button key={t} className={`filter-btn ${filterType === t ? 'active' : ''}`} onClick={() => { setFilterType(t); networkRef.current = null }}>
                {t === 'all' ? 'All' : t.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="graph-body">
        <div ref={containerRef} className="graph-canvas">
          {status === 'loading' && <div className="graph-loading">Loading graph…</div>}
          {status === 'error' && <div className="graph-error">Error: {error}</div>}
        </div>

        <aside className="graph-sidebar">
          <h3>Legend</h3>
          <div className="legend-list">
            {Object.entries(TYPE_COLORS).map(([type, color]) => (
              <div key={type} className="legend-item">
                <span className="legend-dot" style={{ background: color }} />
                <span>{type}</span>
              </div>
            ))}
          </div>

          <h3>Relation Types</h3>
          <div className="legend-list">
            {Object.entries(RELATION_COLORS).map(([type, color]) => (
              <div key={type} className="legend-item">
                <span className="legend-dot" style={{ background: color }} />
                <span style={{ borderBottom: type === 'references' ? '2px dashed ' + color : 'none' }}>{type}</span>
              </div>
            ))}
          </div>

          {selectedNode && (
            <div className="node-detail">
              <h3>Selected Note</h3>
              <p><strong>Title:</strong> {selectedNode.title || 'Untitled'}</p>
              <p><strong>Type:</strong> {selectedNode.type}</p>
              <p><strong>Status:</strong> {selectedNode.status}</p>
              <p><strong>Path:</strong> {(selectedNode as unknown as Record<string, string>).obsidian_path}</p>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}

const RELATION_COLORS: Record<string, string> = {
  references: '#94a3b8',
  decides: '#ef4444',
  depends_on: '#f59e0b',
  related_to: '#6366f1',
}
