import { createClient } from '@supabase/supabase-js'

/**
 * Hybrid search with automatic fallback to BM25 on vector failure.
 *
 * 1. Attempt vector + BM25 hybrid via `query_vector_hybrid` RPC.
 * 2. On any error (DB timeout, bad embedding, etc.), retry as BM25-only.
 * 3. If BM25 also fails, throw.
 */
export async function queryVectorWithFallback({
  supabaseUrl,
  supabaseKey,
  query,
  embedding,
  limit = 10,
  signal,
}: {
  supabaseUrl: string
  supabaseKey: string
  query: string
  embedding?: number[]
  limit?: number
  signal?: AbortSignal
}) {
  const supabase = createClient(supabaseUrl, supabaseKey)

  // Attempt 1: hybrid (vector + BM25)
  if (embedding) {
    try {
      const payload = { query, embedding: JSON.stringify(embedding), limit }
      const { data, error } = await supabase.rpc('query_vector_hybrid', payload)
      if (!error && data) return data
    } catch {
      // fall through to BM25-only
    }
  }

  // Attempt 2: BM25-only fallback
  const payload = { query, limit }
  const { data, error } = await supabase.rpc('query_vector_hybrid', payload)
  if (error) throw new Error(`Fallback BM25 query failed: ${error.message}`)
  return data
}
