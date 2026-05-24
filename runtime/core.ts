import { createClient } from '@supabase/supabase-js'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface StoredMemory {
  session_id: string
  project_slug: string
  summary: string
  decisions?: Array<{ title: string; description: string }>
  patterns?: string[]
  embedding?: number[]
}

export interface FeedbackEntry {
  event_id?: string
  content: string
  positive?: boolean
  source?: string
}

export interface RelationEntry {
  source_entry_id: string
  target_entry_id: string
  relation_type: 'references' | 'decides' | 'depends_on' | 'related_to'
  confidence?: number
  metadata?: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Core Runtime — in-process API
// ---------------------------------------------------------------------------

export class CognitiveRuntime {
  private supabase

  constructor(supabaseUrl: string, supabaseKey: string) {
    this.supabase = createClient(supabaseUrl, supabaseKey)
  }

  async storeMemory(memory: StoredMemory) {
    const { data, error } = await this.supabase
      .from('vault_memories')
      .insert({
        session_id: memory.session_id,
        project_slug: memory.project_slug,
        summary: memory.summary,
        decisions: memory.decisions ?? [],
        patterns: memory.patterns ?? [],
        ...(memory.embedding ? { embedding: memory.embedding } : {}),
      })
      .select('id')
      .single()

    if (error) throw new Error(`storeMemory failed: ${error.message}`)
    return data
  }

  async collectFeedback(feedback: FeedbackEntry) {
    const { data, error } = await this.supabase
      .from('vault_feedback')
      .insert({
        event_id: feedback.event_id,
        content: feedback.content,
        positive: feedback.positive ?? true,
        source: feedback.source ?? 'runtime',
      })
      .select('id')
      .single()

    if (error) throw new Error(`collectFeedback failed: ${error.message}`)
    return data
  }

  async addRelation(relation: RelationEntry) {
    const { data, error } = await this.supabase
      .from('vault_relations')
      .upsert(
        {
          source_entry_id: relation.source_entry_id,
          target_entry_id: relation.target_entry_id,
          relation_type: relation.relation_type,
          confidence: relation.confidence ?? 0.5,
          metadata: relation.metadata ?? {},
        },
        {
          onConflict: 'source_entry_id,target_entry_id,relation_type',
          ignoreDuplicates: false,
        },
      )
      .select('id')
      .single()

    if (error) throw new Error(`addRelation failed: ${error.message}`)
    return data
  }

  async searchMemories(projectSlug: string, query?: string, limit = 10) {
    let q = this.supabase
      .from('vault_memories')
      .select('*')
      .eq('project_slug', projectSlug)
      .order('created_at', { ascending: false })
      .limit(limit)

    if (query) {
      q = q.textSearch('summary', query)
    }

    const { data, error } = await q
    if (error) throw new Error(`searchMemories failed: ${error.message}`)
    return data
  }
}
