import { createClient } from '@supabase/supabase-js';

/**
 * Wrapper around the `query_vector_hybrid` RPC.
 *
 * Parameters:
 *   - query: full‑text query string (required)
 *   - embedding?: number[] (optional vector)
 *   - limit?: number (default 10)
 */
export async function queryVector({
  supabaseUrl,
  supabaseKey,
  query,
  embedding,
  limit = 10,
}: {
  supabaseUrl: string;
  supabaseKey: string;
  query: string;
  embedding?: number[];
  limit?: number;
}) {
  const supabase = createClient(supabaseUrl, supabaseKey);
  const payload = {
    query,
    limit,
    ...(embedding ? { embedding: JSON.stringify(embedding) } : {}),
  } as any;

  const { data, error } = await supabase.rpc('query_vector_hybrid', payload);
  if (error) {
    throw new Error(`Supabase RPC error: ${error.message}`);
  }
  return data;
}
