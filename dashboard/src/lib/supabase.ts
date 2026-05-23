import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || ''
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

export const supabase = createClient(supabaseUrl, supabaseKey)

export type VaultEntry = {
  id: string
  title: string
  type: string
  status: string
  freshness: string
  sensitivity: string
  created_at: string
}

export type VaultMemory = {
  id: string
  session_id: string
  project_slug: string
  summary: string
  created_at: string
}

export type VaultFeedback = {
  id: string
  content: string
  positive: boolean
  source: string
  created_at: string
}

export type VaultRelation = {
  id: string
  source_entry_id: string
  target_entry_id: string
  relation_type: 'references' | 'decides' | 'depends_on' | 'related_to'
  confidence: number
  metadata?: Record<string, unknown>
  created_at: string
}

export type VaultModelStatus = 'active' | 'inactive' | 'deprecated' | 'error'
export type VaultModelKind = 'embedding' | 'chat' | 'reranker' | 'vision' | 'audio' | 'tool'

export type VaultModel = {
  id: string
  name: string
  provider: string
  version: string
  kind: VaultModelKind
  source_hash: string | null
  dimension: number
  priority: number
  fallback_order: number
  rollout_percent: number
  status: VaultModelStatus
  config: Record<string, unknown>
  last_used_at: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}
