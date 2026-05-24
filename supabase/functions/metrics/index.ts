import { createClient } from 'jsr:@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
}

interface Metrics {
  entries: { total: number; by_type: Record<string, number>; by_status: Record<string, number>; by_freshness: Record<string, number>; by_sensitivity: Record<string, number> }
  memories: number
  feedback: number
  relations: number
  events: number
  sessions: number
  tool_calls: { total: number; by_status: Record<string, number> }
  sections: number
  last_24h_entries: number
  timestamp: string
}

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders })
  }
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  }

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
  )

  try {
    const [entries, memories, feedback, relations, events, sessions, toolCalls, sections, recent] = await Promise.all([
      supabase.from('vault_entries').select('type, status, freshness, sensitivity'),
      supabase.from('vault_memories').select('*', { count: 'exact', head: true }),
      supabase.from('vault_feedback').select('*', { count: 'exact', head: true }),
      supabase.from('vault_relations').select('*', { count: 'exact', head: true }),
      supabase.from('vault_events').select('*', { count: 'exact', head: true }),
      supabase.from('sessions').select('*', { count: 'exact', head: true }),
      supabase.from('tool_calls').select('status'),
      supabase.from('vault_sections').select('*', { count: 'exact', head: true }),
      supabase.from('vault_entries').select('id', { count: 'exact', head: true })
        .gte('created_at', new Date(Date.now() - 86400000).toISOString()),
    ])

    if (entries.error) throw entries.error

    function countBy<T extends Record<string, unknown>>(items: T[], key: string): Record<string, number> {
      const acc: Record<string, number> = {}
      for (const item of items) {
        const val = String(item[key] ?? 'unknown')
        acc[val] = (acc[val] ?? 0) + 1
      }
      return acc
    }

    const data: Metrics = {
      entries: {
        total: entries.data?.length ?? 0,
        by_type: countBy(entries.data ?? [], 'type'),
        by_status: countBy(entries.data ?? [], 'status'),
        by_freshness: countBy(entries.data ?? [], 'freshness'),
        by_sensitivity: countBy(entries.data ?? [], 'sensitivity'),
      },
      memories: memories.count ?? 0,
      feedback: feedback.count ?? 0,
      relations: relations.count ?? 0,
      events: events.count ?? 0,
      sessions: sessions.count ?? 0,
      tool_calls: {
        total: toolCalls.data?.length ?? 0,
        by_status: countBy(toolCalls.data ?? [], 'status'),
      },
      sections: sections.count ?? 0,
      last_24h_entries: recent.count ?? 0,
      timestamp: new Date().toISOString(),
    }

    const accept = req.headers.get('accept') ?? ''
    if (accept.includes('text/plain')) {
      return new Response(toPrometheus(data), {
        headers: { ...corsHeaders, 'Content-Type': 'text/plain; charset=utf-8' },
      })
    }

    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  } catch (err) {
    return new Response(JSON.stringify({ error: err instanceof Error ? err.message : 'Unknown' }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  }
})

function toPrometheus(m: Metrics): string {
  const lines: string[] = []
  lines.push('# HELP vault_entries_total Total vault entries')
  lines.push('# TYPE vault_entries_total gauge')
  lines.push(`vault_entries_total ${m.entries.total}`)
  for (const [k, v] of Object.entries(m.entries.by_type)) {
    lines.push(`vault_entries_by_type{type="${k}"} ${v}`)
  }
  for (const [k, v] of Object.entries(m.entries.by_status)) {
    lines.push(`vault_entries_by_status{status="${k}"} ${v}`)
  }
  for (const [k, v] of Object.entries(m.entries.by_freshness)) {
    lines.push(`vault_entries_by_freshness{freshness="${k}"} ${v}`)
  }
  lines.push(`vault_memories_total ${m.memories}`)
  lines.push(`vault_feedback_total ${m.feedback}`)
  lines.push(`vault_relations_total ${m.relations}`)
  lines.push(`vault_events_total ${m.events}`)
  lines.push(`sessions_total ${m.sessions}`)
  lines.push(`tool_calls_total ${m.tool_calls.total}`)
  const statusEntries = Object.entries(m.tool_calls.by_status)
  if (statusEntries.length === 0) {
    lines.push('tool_calls_by_status{status="(none)"} 0')
  } else {
    for (const [k, v] of statusEntries) {
      lines.push(`tool_calls_by_status{status="${k}"} ${v}`)
    }
  }
  lines.push(`vault_sections_total ${m.sections}`)
  lines.push(`vault_entries_last_24h ${m.last_24h_entries}`)
  lines.push(`metrics_timestamp ${new Date(m.timestamp).getTime() / 1000}`)
  return lines.join('\n') + '\n'
}
