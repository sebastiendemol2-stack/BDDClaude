import { createClient } from 'jsr:@supabase/supabase-js@2';

interface SessionPayload {
  action: 'begin' | 'inject' | 'end' | 'prime';
  project_slug?: string;
  session_id?: string;
  profile?: string;
  summary?: string;
  decisions?: string[];
  patterns?: string[];
  context_query?: string;
  client_ide?: string;
}

Deno.serve(async (req: Request) => {
  const payload: SessionPayload = await req.json().catch(() => ({ action: 'begin' }));
  const started_at = Date.now();

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  );

  try {
    switch (payload.action) {
      case 'begin':
        return await beginSession(supabase, payload, started_at, req);
      case 'inject':
        return await injectContext(supabase, payload, started_at);
      case 'end':
        return await endSession(supabase, payload, started_at);
      case 'prime':
        return await primeContext(supabase, payload, started_at);
      default:
        return new Response(JSON.stringify({ error: `Unknown action: ${payload.action}` }), {
          status: 400, headers: { 'Content-Type': 'application/json' }
        });
    }
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500, headers: { 'Content-Type': 'application/json' }
    });
  }
});

async function beginSession(supabase: any, payload: SessionPayload, started_at: number, req: Request) {
  const slug = payload.project_slug ?? 'default';
  const { data: project } = await supabase.from('projects')
    .select('id').eq('slug', slug).single();

  let projectId = project?.id;
  if (!projectId) {
    const { data: newProject } = await supabase.from('projects')
      .insert({ slug, name: slug, status: 'active' })
      .select('id').single();
    projectId = newProject?.id;
  }

  const { data: session } = await supabase.from('sessions')
    .insert({ project_id: projectId })
    .select('id, started_at').single();

  const profileName = payload.profile ?? 'default';
  const { data: profile } = await supabase.from('context_profiles')
    .select('*').eq('name', profileName).single();

  await supabase.rpc('ukp_emit_session_event', {
    p_session_id: session.id,
    p_event_type: 'session.started',
    p_payload: { project_slug: slug, profile: profileName },
    p_project_slug: slug
  });

  await supabase.rpc('ukp_emit_session_event', {
    p_session_id: session.id,
    p_event_type: 'profile.loaded',
    p_payload: { profile: profileName, token_budget: profile?.token_budget },
    p_project_slug: slug
  });

  const took_ms = Date.now() - started_at;

  return new Response(JSON.stringify({
    session_id: session.id,
    started_at: session.started_at,
    project_slug: slug,
    profile_loaded: profileName,
    token_budget: profile?.token_budget ?? 12000,
    auto_enable_tools: profile?.tools_config?.auto_enable ?? ['query'],
    took_ms
  }), { headers: { 'Content-Type': 'application/json' } });
}

async function injectContext(supabase: any, payload: SessionPayload, started_at: number) {
  if (!payload.session_id) {
    return new Response(JSON.stringify({ error: 'session_id is required' }), {
      status: 400, headers: { 'Content-Type': 'application/json' }
    });
  }

  const profileName = payload.profile ?? 'default';
  const { data: profile } = await supabase.from('context_profiles')
    .select('*').eq('name', profileName).single();

  const cfg = profile?.retrieval_config ?? { max_chunks: 24 };
  const limit = cfg.max_chunks ?? 24;

  const { data: memories } = await supabase.from('claude_memory')
    .select('type, key, value, source, created_at')
    .order('created_at', { ascending: false })
    .limit(25);

  let context_chunks: any[] = [];

  if (payload.context_query) {
    const { data: ftsResults } = await supabase.rpc('search_vault', {
      search_query: payload.context_query,
      limit_n: limit
    });
    context_chunks = (ftsResults ?? []).slice(0, limit).map((r: any) => ({
      title: r.title,
      content: r.content?.substring(0, 1000),
      type: r.type,
      section: r.section_slug,
      score: r._score
    }));
  }

  await supabase.rpc('ukp_emit_session_event', {
    p_session_id: payload.session_id,
    p_event_type: 'context.injected',
    p_payload: {
      memory_count: memories?.length ?? 0,
      context_chunks: context_chunks.length,
      profile: profileName,
      context_query: payload.context_query
    },
    p_project_slug: payload.project_slug
  });

  const took_ms = Date.now() - started_at;

  return new Response(JSON.stringify({
    session_id: payload.session_id,
    memories: memories ?? [],
    context_chunks,
    profile_used: profileName,
    took_ms
  }), { headers: { 'Content-Type': 'application/json' } });
}

async function endSession(supabase: any, payload: SessionPayload, started_at: number) {
  if (!payload.session_id) {
    return new Response(JSON.stringify({ error: 'session_id is required' }), {
      status: 400, headers: { 'Content-Type': 'application/json' }
    });
  }

  await supabase.from('sessions')
    .update({ ended_at: new Date().toISOString(), summary: payload.summary ?? '' })
    .eq('id', payload.session_id);

  if (payload.decisions && payload.decisions.length > 0) {
    for (const decision of payload.decisions) {
      await supabase.rpc('upsert_memory_with_history', {
        p_project_id: undefined,
        p_type: 'decision',
        p_key: `decision-${Date.now()}`,
        p_value: decision,
        p_source: 'ukp-session',
        p_session_id: payload.session_id
      }).catch(() => {});
    }
  }

  if (payload.patterns && payload.patterns.length > 0) {
    for (const pattern of payload.patterns) {
      await supabase.rpc('upsert_memory_with_history', {
        p_project_id: undefined,
        p_type: 'pattern',
        p_key: `pattern-${Date.now()}`,
        p_value: pattern,
        p_source: 'ukp-session',
        p_session_id: payload.session_id
      }).catch(() => {});
    }
  }

  await supabase.rpc('ukp_emit_session_event', {
    p_session_id: payload.session_id,
    p_event_type: 'session.ended',
    p_payload: {
      summary: payload.summary,
      decisions_count: payload.decisions?.length ?? 0,
      patterns_count: payload.patterns?.length ?? 0
    },
    p_project_slug: payload.project_slug
  });

  const took_ms = Date.now() - started_at;

  return new Response(JSON.stringify({
    session_id: payload.session_id,
    ended: true,
    decisions_persisted: payload.decisions?.length ?? 0,
    patterns_persisted: payload.patterns?.length ?? 0,
    took_ms
  }), { headers: { 'Content-Type': 'application/json' } });
}

async function primeContext(supabase: any, payload: SessionPayload, started_at: number) {
  const slug = payload.project_slug ?? 'default';

  const [entriesResult, toolsResult, profilesResult] = await Promise.all([
    supabase.from('vault_entries')
      .select('title, type, section_slug, tags, summary, status, freshness')
      .eq('status', 'active')
      .order('updated_at', { ascending: false })
      .limit(100),
    supabase.from('tools_registry')
      .select('name, description, version, category, tags')
      .eq('enabled', true),
    supabase.from('context_profiles')
      .select('name, description, is_default, token_budget')
  ]);

  const sections: Record<string, any[]> = {};
  for (const entry of entriesResult.data ?? []) {
    const sec = entry.section_slug ?? 'uncategorized';
    if (!sections[sec]) sections[sec] = [];
    sections[sec].push({
      title: entry.title,
      type: entry.type,
      tags: entry.tags,
      freshness: entry.freshness
    });
  }

  const took_ms = Date.now() - started_at;

  return new Response(JSON.stringify({
    project: slug,
    vault_stats: {
      notes_total: entriesResult.data?.length ?? 0,
      sections: Object.keys(sections),
      notes_by_section: Object.fromEntries(
        Object.entries(sections).map(([k, v]) => [k, v.length])
      )
    },
    available_tools: toolsResult.data ?? [],
    available_profiles: profilesResult.data ?? [],
    resources_uri: [
      'vault://notes/{path}',
      'vault://projects/{slug}',
      'vault://sections/{slug}',
      'vault://session/current',
      'vault://memory/{project}'
    ],
    took_ms
  }), { headers: { 'Content-Type': 'application/json' } });
}
