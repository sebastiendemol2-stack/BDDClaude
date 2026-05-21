import { createClient } from 'jsr:@supabase/supabase-js@2';

Deno.serve(async (req: Request) => {
  const { query, project, max_results = 10, profile: profile_name = 'default', mode = 'hybrid' } = await req.json().catch(() => ({}));

  if (!query) {
    return new Response(JSON.stringify({ error: 'query is required' }), {
      status: 400, headers: { 'Content-Type': 'application/json' }
    });
  }

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  );

  const started_at = Date.now();

  try {
    const { data: profile } = await supabase.from('context_profiles')
      .select('*')
      .eq('name', profile_name)
      .single();

    const cfg = profile?.retrieval_config ?? {
      hybrid: true, fts_weight: 0.4, vector_weight: 0.6,
      max_chunks: 24, rerank: false
    };
    const limit = Math.min(max_results, cfg.max_chunks ?? 24);

    // 1) FTS search (French)
    const ftsQuery = supabase.rpc('search_vault', {
      search_query: query,
      limit_n: cfg.hybrid ? limit * 3 : limit
    });

    // 2) Vector search via embeddings
    let vectorResults: any[] = [];
    if (cfg.hybrid) {
      const { data: embeddings, error: embErr } = await supabase.rpc('query_vector_hybrid', {
        query_text: query,
        match_count: limit * 3
      }).maybeSingle();

      if (!embErr && embeddings) {
        vectorResults = embeddings.results ?? [];
      }
    }

    // 3) Merge results (hybrid)
    const { data: ftsResults } = await ftsQuery;
    let results: Map<string, any> = new Map();

    if (cfg.hybrid) {
      const ftsWeight = cfg.fts_weight ?? 0.4;
      const vecWeight = cfg.vector_weight ?? 0.6;

      for (const r of (ftsResults ?? [])) {
        r._score = (r._score ?? 0) * ftsWeight;
        r._method = 'fts';
        results.set(r.id, r);
      }
      for (const r of vectorResults) {
        const existing = results.get(r.id);
        if (existing) {
          existing._score = (existing._score ?? 0) + (r._score ?? 0) * vecWeight;
          existing._method = 'hybrid';
        } else {
          r._score = (r._score ?? 0) * vecWeight;
          r._method = 'vector';
          results.set(r.id, r);
        }
      }
    } else {
      for (const r of (ftsResults ?? [])) {
        r._method = 'fts';
        results.set(r.id, r);
      }
    }

    let sorted = Array.from(results.values())
      .sort((a, b) => (b._score ?? 0) - (a._score ?? 0))
      .slice(0, limit);

    await supabase.rpc('ukp_record_tool_call', {
      p_session_id: null,
      p_tool_name: 'query',
      p_input_payload: { query, max_results: limit, profile: profile_name },
      p_project_slug: project ?? null,
      p_client_ide: req.headers.get('x-client-ide') ?? null
    });

    const took_ms = Date.now() - started_at;

    return new Response(JSON.stringify({
      results: sorted.map(r => ({
        id: r.id,
        title: r.title,
        content: r.content?.substring(0, 500),
        tags: r.tags,
        type: r.type,
        obsidian_path: r.obsidian_path,
        section: r.section_slug,
        score: r._score,
        method: r._method,
        summary: r.summary,
        freshness: r.freshness,
        confidence: r.confidence,
        updated_at: r.updated_at
      })),
      total: sorted.length,
      took_ms,
      profile_used: profile_name
    }), {
      headers: { 'Content-Type': 'application/json' }
    });

  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500, headers: { 'Content-Type': 'application/json' }
    });
  }
});
