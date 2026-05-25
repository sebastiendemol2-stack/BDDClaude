import { useEffect, useRef, useState, useCallback } from 'react'
import { Network, type Options } from 'vis-network'
import { DataSet } from 'vis-data'
import { supabase, type VaultEntry, type VaultRelation } from '../lib/supabase'
import { useTenant } from '../lib/tenants'

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

const RELATION_COLORS: Record<string, string> = {
  references: '#94a3b8',
  decides: '#ef4444',
  depends_on: '#f59e0b',
  related_to: '#6366f1',
}

type GraphStats = {
  totalNodes: number
  totalEdges: number
  connectedNodes: number
  isolatedNodes: number
  density: string
  avgDegree: string
  maxDegree: number
  components: number
}

export default function Graph() {
  const containerRef = useRef<HTMLDivElement>(null)
  const networkRef = useRef<Network | null>(null)
  const [status, setStatus] = useState<GraphStatus>('loading')
  const [error, setError] = useState('')
  const [nodeCount, setNodeCount] = useState(0)
  const [edgeCount, setEdgeCount] = useState(0)
  const [filterType, setFilterType] = useState<FilterType>('all')
  const [selectedNode, setSelectedNode] = useState<VaultEntry | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showIsolated, setShowIsolated] = useState(false)
  const [stats, setStats] = useState<GraphStats | null>(null)
  const [zoom, setZoom] = useState(1)
  const nodesRef = useRef(new DataSet<{ id: string; label: string; group: string; title: string; value: number }>())
  const edgesRef = useRef(new DataSet<{ id: string; from: string; to: string; label: string; color: string; dashes: boolean }>())
  const { selectedTenant, loading: tenantsLoading } = useTenant()
  const tenantId = selectedTenant?.id
  const allEntriesRef = useRef<VaultEntry[]>([])

  const loadGraph = useCallback(async (filter: FilterType, isolated: boolean) => {
    setStatus('loading')
    try {
      if (tenantsLoading || !tenantId) {
        nodesRef.current.clear()
        edgesRef.current.clear()
        if (networkRef.current) {
          networkRef.current.setData({ nodes: nodesRef.current, edges: edgesRef.current })
        }
        allEntriesRef.current = []
        setSelectedNode(null)
        setNodeCount(0)
        setEdgeCount(0)
        setStats(null)
        setStatus(tenantsLoading ? 'loading' : 'ready')
        return
      }

      const entriesQuery = supabase
        .from('vault_entries')
        .select('id, obsidian_path, title, type, status, freshness, sensitivity, summary')
        .eq('tenant_id', tenantId)
      const relationsQuery = supabase
        .from('vault_relations')
        .select('*')
        .eq('tenant_id', tenantId)
      const [entriesRes, relationsRes] = await Promise.all([entriesQuery, relationsQuery])
      if (entriesRes.error) throw entriesRes.error
      if (relationsRes.error) throw relationsRes.error

      const entries = entriesRes.data as unknown as VaultEntry[]
      const relations = relationsRes.data as VaultRelation[]
      allEntriesRef.current = entries

      const relevantPathSet = new Set<string>()
      const nodeDegrees = new Map<string, number>()

      const filtered = filter === 'all' ? relations : relations.filter(r => r.relation_type === filter)

      for (const rel of filtered) {
        relevantPathSet.add(rel.source_entry_id)
        relevantPathSet.add(rel.target_entry_id)
        nodeDegrees.set(rel.source_entry_id, (nodeDegrees.get(rel.source_entry_id) || 0) + 1)
        nodeDegrees.set(rel.target_entry_id, (nodeDegrees.get(rel.target_entry_id) || 0) + 1)
      }

      const maxDegree = Math.max(...nodeDegrees.values(), 1)
      let visibleEntries = entries

      if (!isolated) {
        visibleEntries = entries.filter(e => e.obsidian_path && relevantPathSet.has(e.obsidian_path))
      }

      const nodes = visibleEntries
        .filter(e => e.obsidian_path)
        .map(e => ({
          id: e.obsidian_path!,
          label: e.title || e.obsidian_path!.split('/').pop()?.replace('.md', '') || e.obsidian_path!,
          group: e.type,
          title: [
            e.title || 'Untitled',
            `Type: ${e.type}`,
            `Status: ${e.status}`,
            `Freshness: ${e.freshness || 'unknown'}`,
            `Sensitivity: ${e.sensitivity || 'unknown'}`,
            e.summary ? `Summary: ${e.summary.substring(0, 120)}` : '',
            `Connections: ${nodeDegrees.get(e.obsidian_path!) || 0}`,
          ].filter(Boolean).join('\n'),
          value: nodeDegrees.has(e.obsidian_path!)
            ? 10 + ((nodeDegrees.get(e.obsidian_path!) || 0) / maxDegree) * 40
            : 5,
        }))

      const edges = filtered.map(r => ({
        id: r.id,
        from: r.source_entry_id,
        to: r.target_entry_id,
        label: r.relation_type,
        color: RELATION_COLORS[r.relation_type] || '#94a3b8',
        dashes: r.relation_type === 'references',
      }))

      const connectedNodeIds = new Set(filtered.flatMap(r => [r.source_entry_id, r.target_entry_id]))
      const totalConnected = entries.filter(e => e.obsidian_path && connectedNodeIds.has(e.obsidian_path)).length
      const totalIsolated = entries.length - totalConnected
      const n = entries.length
      const maxE = n * (n - 1) / 2
      const density = maxE > 0 ? (edges.length / maxE) : 0
      const avgDeg = entries.length > 0 ? (nodeDegrees.size > 0 ? [...nodeDegrees.values()].reduce((a, b) => a + b, 0) / entries.length : 0) : 0

      const visited = new Set<string>()
      let components = 0
      if (filtered.length > 0) {
        const adj = new Map<string, string[]>()
        for (const rel of filtered) {
          if (!adj.has(rel.source_entry_id)) adj.set(rel.source_entry_id, [])
          if (!adj.has(rel.target_entry_id)) adj.set(rel.target_entry_id, [])
          adj.get(rel.source_entry_id)!.push(rel.target_entry_id)
          adj.get(rel.target_entry_id)!.push(rel.source_entry_id)
        }
        for (const node of adj.keys()) {
          if (!visited.has(node)) {
            components++
            const queue = [node]
            visited.add(node)
            while (queue.length > 0) {
              const cur = queue.shift()!
              for (const nb of adj.get(cur) || []) {
                if (!visited.has(nb)) {
                  visited.add(nb)
                  queue.push(nb)
                }
              }
            }
          }
        }
      }

      setStats({
        totalNodes: entries.length,
        totalEdges: edges.length,
        connectedNodes: totalConnected,
        isolatedNodes: totalIsolated,
        density: density.toFixed(6),
        avgDegree: avgDeg.toFixed(2),
        maxDegree,
        components,
      })

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
            color: { border: '#334155', background: '#475569' },
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
            const entry = entries.find(e => e.obsidian_path === nodeId)
            if (entry) setSelectedNode(entry)
          } else {
            setSelectedNode(null)
          }
        })

        networkRef.current.on('zoom', () => {
          if (networkRef.current) {
            setZoom(networkRef.current.getScale())
          }
        })
      } else if (networkRef.current) {
        networkRef.current.setData({ nodes: nodesRef.current, edges: edgesRef.current })
        networkRef.current.fit()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load graph')
      setStatus('error')
    }
  }, [tenantId, tenantsLoading])

  useEffect(() => {
    loadGraph(filterType, showIsolated)
    return () => {
      if (networkRef.current) {
        networkRef.current.destroy()
        networkRef.current = null
      }
    }
  }, [filterType, showIsolated, tenantId, tenantsLoading, loadGraph])

  const handleSearch = (query: string) => {
    setSearchQuery(query)
    if (!networkRef.current || !query.trim()) {
      if (networkRef.current) {
        networkRef.current.selectNodes([])
      }
      return
    }

    const q = query.toLowerCase()
    const entries = allEntriesRef.current
    const matches = entries.filter(e =>
      (e.title && e.title.toLowerCase().includes(q)) ||
      (e.obsidian_path && e.obsidian_path.toLowerCase().includes(q))
    )

    if (matches.length > 0) {
      const nodeIds = matches.map(e => e.obsidian_path).filter(Boolean) as string[]
      const existingNodeIds = nodesRef.current.getIds() as string[]
      const found = nodeIds.filter(id => existingNodeIds.includes(id))
      networkRef.current.selectNodes(found)
      if (found.length > 0) {
        networkRef.current.focus(found[0], { scale: 2, animation: true })
      }
    }
  }

  const handleExportPng = () => {
    if (!networkRef.current) return
    const canvas = containerRef.current?.querySelector('canvas')
    if (!canvas) return
    const link = document.createElement('a')
    link.download = `memory-graph-${new Date().toISOString().slice(0, 10)}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  }

  const handleResetZoom = () => {
    if (networkRef.current) {
      networkRef.current.fit({ animation: true })
    }
  }

  return (
    <div className="graph-page">
      <div className="graph-header">
        <h1>Memory Graph</h1>
        <div className="graph-controls">
          <div className="graph-search">
            <input
              type="text"
              placeholder="Search nodes…"
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="graph-search-input"
            />
          </div>
          <label className="graph-toggle">
            <input
              type="checkbox"
              checked={showIsolated}
              onChange={(e) => { setShowIsolated(e.target.checked); networkRef.current = null }}
            />
            <span>Isolated</span>
          </label>
          <span className="graph-info">{nodeCount} nodes · {edgeCount} edges</span>
          <div className="filter-buttons">
            {(['all', 'references', 'decides', 'depends_on', 'related_to'] as FilterType[]).map(t => (
              <button
                key={t}
                className={`filter-btn ${filterType === t ? 'active' : ''}`}
                onClick={() => { setFilterType(t); networkRef.current = null }}
              >
                {t === 'all' ? 'All' : t.replace('_', ' ')}
              </button>
            ))}
          </div>
          <button className="filter-btn" onClick={handleExportPng} title="Export as PNG">
            Export PNG
          </button>
          <button className="filter-btn" onClick={handleResetZoom} title="Reset view">
            Reset
          </button>
        </div>
      </div>

      <div className="graph-body">
        <div ref={containerRef} className="graph-canvas">
          {status === 'loading' && <div className="graph-loading">Loading graph…</div>}
          {status === 'error' && <div className="graph-error">Error: {error}</div>}
        </div>

        <aside className="graph-sidebar">
          {stats && (
            <>
              <h3>Statistics</h3>
              <div className="graph-stats">
                <div className="stat-row"><span>Total notes</span><span>{stats.totalNodes}</span></div>
                <div className="stat-row"><span>Edges</span><span>{stats.totalEdges}</span></div>
                <div className="stat-row"><span>Connected</span><span>{stats.connectedNodes}</span></div>
                <div className="stat-row"><span>Isolated</span><span>{stats.isolatedNodes}</span></div>
                <div className="stat-row"><span>Density</span><span>{stats.density}</span></div>
                <div className="stat-row"><span>Avg degree</span><span>{stats.avgDegree}</span></div>
                <div className="stat-row"><span>Max degree</span><span>{stats.maxDegree}</span></div>
                <div className="stat-row"><span>Components</span><span>{stats.components}</span></div>
              </div>
            </>
          )}

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

          <div className="zoom-display">
            Zoom: {(zoom * 100).toFixed(0)}%
          </div>

          {selectedNode && (
            <div className="node-detail">
              <h3>Selected Note</h3>
              <div className="node-detail-grid">
                <p><strong>Title:</strong> {selectedNode.title || 'Untitled'}</p>
                <p><strong>Type:</strong> <span className={`badge badge-${selectedNode.type}`}>{selectedNode.type}</span></p>
                <p><strong>Status:</strong> {selectedNode.status}</p>
                {selectedNode.freshness && <p><strong>Freshness:</strong> {selectedNode.freshness}</p>}
                {selectedNode.sensitivity && <p><strong>Sensitivity:</strong> {selectedNode.sensitivity}</p>}
                {selectedNode.summary && <p className="node-detail-summary"><strong>Summary:</strong> {selectedNode.summary}</p>}
                {selectedNode.obsidian_path && <p><strong>Path:</strong> <code>{String(selectedNode.obsidian_path)}</code></p>}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
