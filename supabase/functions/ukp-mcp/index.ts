import { createClient } from 'jsr:@supabase/supabase-js@2';

interface JsonRpcRequest {
  jsonrpc: '2.0';
  method: string;
  id: number | string | null;
  params?: Record<string, unknown>;
}

interface JsonRpcResponse {
  jsonrpc: '2.0';
  id: number | string | null;
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
}

interface McpTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

interface McpResource {
  uri: string;
  name: string;
  description?: string;
  mimeType?: string;
}

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, x-client-ide',
  'Content-Type': 'application/json',
};

function jsonRpcError(code: number, message: string, data?: unknown): JsonRpcResponse {
  return { jsonrpc: '2.0', id: null, error: { code, message, data } };
}

function jsonRpcSuccess(id: number | string | null, result: unknown): JsonRpcResponse {
  return { jsonrpc: '2.0', id, result };
}

function getSupabase() {
  return createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  );
}

async function handleToolQuery(supabase: any, params: Record<string, unknown>, sessionId: string | null) {
  const query = params.query as string;
  const maxResults = Math.min((params.max_results as number) ?? 10, 50);
  if (!query) throw new Error('query parameter is required');

  const { data: results, error } = await supabase.rpc('search_vault', {
    search_query: query, limit_n: maxResults
  });
  if (error) throw new Error(error.message);

  return {
    results: (results ?? []).map((r: any) => ({
      id: r.id, title: r.title, content: r.content?.substring(0, 500),
      tags: r.tags, type: r.type, obsidian_path: r.obsidian_path,
      section: r.section_slug, score: r._score, summary: r.summary,
      freshness: r.freshness, confidence: r.confidence, updated_at: r.updated_at,
    })),
    total: (results ?? []).length, query,
  };
}

async function handleToolPrime(supabase: any, _params: Record<string, unknown>) {
  const [entriesResult, sectionsResult, toolsResult] = await Promise.all([
    supabase.from('vault_entries').select('id, title, type, section_slug, tags, status, freshness, updated_at').eq('status', 'active').order('updated_at', { ascending: false }).limit(200),
    supabase.from('vault_sections').select('slug, name, description, icon'),
    supabase.from('tools_registry').select('name, description, version, category, tags').eq('enabled', true),
  ]);

  const notesBySection: Record<string, number> = {};
  for (const entry of entriesResult.data ?? []) {
    const sec = entry.section_slug ?? 'uncategorized';
    notesBySection[sec] = (notesBySection[sec] ?? 0) + 1;
  }

  return {
    vault_stats: {
      notes_total: entriesResult.data?.length ?? 0,
      sections: sectionsResult.data?.length ?? 0,
      notes_by_section: notesBySection,
    },
    sections: sectionsResult.data ?? [],
    available_tools: toolsResult.data ?? [],
  };
}

async function handleToolSession(supabase: any, params: Record<string, unknown>) {
  const action = params.action as string;
  if (!action) throw new Error('action parameter is required (begin, end, inject)');

  switch (action) {
    case 'begin': {
      const slug = (params.project_slug as string) ?? 'default';
      const profileName = (params.profile as string) ?? 'default';
      let { data: project } = await supabase.from('projects').select('id').eq('slug', slug).single();
      if (!project) {
        const { data: np } = await supabase.from('projects').insert({ slug, name: slug, status: 'active' }).select('id').single();
        project = np;
      }
      const { data: session } = await supabase.from('sessions').insert({ project_id: project.id }).select('id, started_at').single();
      const { data: profile } = await supabase.from('context_profiles').select('*').eq('name', profileName).single();
      await supabase.rpc('ukp_emit_session_event', {
        p_session_id: session.id, p_event_type: 'session.started',
        p_payload: { project_slug: slug, profile: profileName, source: 'mcp' }, p_project_slug: slug,
      });
      return {
        session_id: session.id, started_at: session.started_at, project_slug: slug,
        profile_loaded: profileName, token_budget: profile?.token_budget ?? 12000,
        auto_enable_tools: profile?.tools_config?.auto_enable ?? ['query'],
      };
    }
    case 'end': {
      const sid = params.session_id as string;
      if (!sid) throw new Error('session_id is required');
      await supabase.from('sessions').update({ ended_at: new Date().toISOString(), summary: (params.summary as string) ?? '' }).eq('id', sid);
      await supabase.rpc('ukp_emit_session_event', {
        p_session_id: sid, p_event_type: 'session.ended',
        p_payload: { summary: params.summary, source: 'mcp' }, p_project_slug: (params.project_slug as string) ?? null,
      });
      return { session_id: sid, ended: true };
    }
    case 'inject': {
      const sid = params.session_id as string;
      if (!sid) throw new Error('session_id is required');
      const contextQuery = params.context_query as string | undefined;
      const limit = (params.max_chunks as number) ?? 24;
      let contextChunks: any[] = [];
      if (contextQuery) {
        const { data: ftsResults } = await supabase.rpc('search_vault', { search_query: contextQuery, limit_n: limit });
        contextChunks = (ftsResults ?? []).slice(0, limit).map((r: any) => ({
          title: r.title, content: r.content?.substring(0, 1000), type: r.type, section: r.section_slug, score: r._score,
        }));
      }
      await supabase.rpc('ukp_emit_session_event', {
        p_session_id: sid, p_event_type: 'context.injected',
        p_payload: { context_chunks: contextChunks.length, context_query: contextQuery, source: 'mcp' },
        p_project_slug: (params.project_slug as string) ?? null,
      });
      return { session_id: sid, context_chunks: contextChunks };
    }
    default: throw new Error(`Unknown session action: ${action}`);
  }
}

const TOOL_HANDLERS: Record<string, (supabase: any, params: Record<string, unknown>, sessionId: string | null, clientIde: string | null) => Promise<unknown>> = {
  query: async (sb, p, sid) => handleToolQuery(sb, p, sid),
  prime: async (sb, p) => handleToolPrime(sb, p),
  session: async (sb, p) => handleToolSession(sb, p),
};

async function executeTool(supabase: any, toolName: string, params: Record<string, unknown>, sessionId: string | null, clientIde: string | null) {
  const handler = TOOL_HANDLERS[toolName];
  if (!handler) throw new Error(`Unknown tool: ${toolName}`);

  const startedAt = Date.now();
  let status = 'success';
  let errorMessage: string | null = null;
  let result: unknown;

  try {
    result = await handler(supabase, params, sessionId, clientIde);
  } catch (err: any) {
    status = 'error';
    errorMessage = err.message;
    result = { error: err.message };
  }

  await supabase.rpc('ukp_record_tool_call', {
    p_session_id: sessionId, p_tool_name: toolName, p_input_payload: params,
    p_output_payload: result, p_status: status,
    p_duration_ms: Date.now() - startedAt, p_error_message: errorMessage,
    p_project_slug: (params.project_slug ?? params.project) ?? null, p_client_ide: clientIde,
  }).catch(() => {});

  if (status === 'error') throw new Error(errorMessage!);
  return result;
}

async function readResource(supabase: any, uri: string) {
  const noteMatch = uri.match(/^vault:\/\/notes\/(.+)$/);
  if (noteMatch) {
    const path = decodeURIComponent(noteMatch[1]);
    const { data, error } = await supabase.from('vault_entries')
      .select('id, title, content, tags, type, status, freshness, confidence, summary, obsidian_path, section_slug, updated_at, created_at')
      .or(`obsidian_path.eq.${path},canonical_slug.eq.${path.replace(/\.md$/, '')}`)
      .eq('status', 'active').single();
    if (error || !data) throw new Error(`Note not found: ${path}`);
    return { uri, mimeType: 'text/markdown', text: `# ${data.title}\n\n${data.content ?? ''}`, metadata: { id: data.id, type: data.type, tags: data.tags, section: data.section_slug, freshness: data.freshness, confidence: data.confidence, updated_at: data.updated_at } };
  }
  const projectMatch = uri.match(/^vault:\/\/projects\/(.+)$/);
  if (projectMatch) {
    const slug = decodeURIComponent(projectMatch[1]);
    const { data: project } = await supabase.from('projects').select('*').eq('slug', slug).single();
    if (!project) throw new Error(`Project not found: ${slug}`);
    const { data: notes } = await supabase.from('vault_entries').select('title, type, tags, updated_at').eq('section_slug', slug).eq('status', 'active').order('updated_at', { ascending: false }).limit(50);
    return { uri, mimeType: 'application/json', text: JSON.stringify({ project, notes: notes ?? [] }, null, 2) };
  }
  const sectionMatch = uri.match(/^vault:\/\/sections\/(.+)$/);
  if (sectionMatch) {
    const slug = decodeURIComponent(sectionMatch[1]);
    const { data: section } = await supabase.from('vault_sections').select('*').eq('slug', slug).single();
    if (!section) throw new Error(`Section not found: ${slug}`);
    const { data: notes } = await supabase.from('vault_entries').select('id, title, type, tags, status, freshness, updated_at').eq('section_slug', slug).eq('status', 'active').order('updated_at', { ascending: false });
    return { uri, mimeType: 'application/json', text: JSON.stringify({ section, notes: notes ?? [] }, null, 2) };
  }
  if (uri === 'vault://session/current') {
    const { data: session } = await supabase.from('sessions').select('id, started_at, ended_at, summary, projects(slug, name)').is('ended_at', null).order('started_at', { ascending: false }).limit(1).single();
    return { uri, mimeType: 'application/json', text: JSON.stringify(session ?? { active: false }, null, 2) };
  }
  const memoryMatch = uri.match(/^vault:\/\/memory\/(.+)$/);
  if (memoryMatch) {
    const project = decodeURIComponent(memoryMatch[1]);
    const { data: memories } = await supabase.from('claude_memory').select('type, key, value, source, created_at').order('created_at', { ascending: false }).limit(50);
    return { uri, mimeType: 'application/json', text: JSON.stringify({ project, memories: memories ?? [] }, null, 2) };
  }
  throw new Error(`Unsupported resource URI: ${uri}`);
}

async function handleInitialize(supabase: any) {
  const [toolsResult, resourcesResult] = await Promise.all([
    supabase.from('tools_registry').select('name, description, input_schema, version, category, tags').eq('enabled', true),
    supabase.from('resources_registry').select('uri_pattern, name, description, mime_type, category, is_dynamic').eq('is_dynamic', true),
  ]);
  return {
    protocolVersion: '2024-11-05',
    capabilities: { tools: { listChanged: false }, resources: { listChanged: false } },
    serverInfo: { name: 'UKP MCP Server', version: '1.0.0' },
    meta: { tools_available: toolsResult.data?.length ?? 0, resources_available: resourcesResult.data?.length ?? 0 },
  };
}

async function handleToolsList(supabase: any) {
  const { data, error } = await supabase.from('tools_registry').select('name, description, input_schema, version, category, tags').eq('enabled', true);
  if (error) throw new Error(error.message);
  return { tools: (data ?? []).map((t: any) => ({ name: t.name, description: t.description, inputSchema: t.input_schema ?? { type: 'object', properties: {} } })) };
}

async function handleToolsCall(supabase: any, params: Record<string, unknown>, sessionId: string | null, clientIde: string | null) {
  const toolName = params.name as string;
  const toolArgs = (params.arguments ?? {}) as Record<string, unknown>;
  if (!toolName) throw new Error('Tool name is required');
  const result = await executeTool(supabase, toolName, toolArgs, sessionId, clientIde);
  return { content: [{ type: 'text', text: typeof result === 'string' ? result : JSON.stringify(result, null, 2) }] };
}

async function handleResourcesList(supabase: any) {
  const { data, error } = await supabase.from('resources_registry').select('uri_pattern, name, description, mime_type, category, is_dynamic');
  if (error) throw new Error(error.message);
  return { resources: (data ?? []).map((r: any) => ({ uri: r.uri_pattern, name: r.name, description: r.description, mimeType: r.mime_type ?? 'text/markdown' })) };
}

async function handleResourcesRead(supabase: any, params: Record<string, unknown>) {
  const uri = params.uri as string;
  if (!uri) throw new Error('uri parameter is required');
  return { contents: [await readResource(supabase, uri)] };
}

const METHOD_HANDLERS: Record<string, (supabase: any, params: Record<string, unknown>, sessionId: string | null, clientIde: string | null) => Promise<unknown>> = {
  initialize: (sb) => handleInitialize(sb),
  'tools/list': (sb) => handleToolsList(sb),
  'tools/call': (sb, p, sid, ide) => handleToolsCall(sb, p, sid, ide),
  'resources/list': (sb) => handleResourcesList(sb),
  'resources/read': (sb, p) => handleResourcesRead(sb, p),
};

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS_HEADERS });
  if (req.method !== 'POST') return new Response(JSON.stringify(jsonRpcError(-32600, 'only POST is supported')), { status: 405, headers: CORS_HEADERS });

  const supabase = getSupabase();
  const clientIde = req.headers.get('x-client-ide');

  let body: JsonRpcRequest | JsonRpcRequest[];
  try { body = await req.json(); } catch {
    return new Response(JSON.stringify(jsonRpcError(-32700, 'Parse error')), { status: 400, headers: CORS_HEADERS });
  }

  const requests = Array.isArray(body) ? body : [body];
  const responses: JsonRpcResponse[] = [];

  for (const request of requests) {
    if (request.jsonrpc !== '2.0') {
      responses.push({ ...jsonRpcError(-32600, 'jsonrpc must be "2.0"'), id: request.id ?? null });
      continue;
    }
    const handler = METHOD_HANDLERS[request.method];
    if (!handler) {
      responses.push({ ...jsonRpcError(-32601, `Method not found: ${request.method}`), id: request.id ?? null });
      continue;
    }
    try {
      const params = request.params ?? {};
      const sessionId = (params.session_id as string) ?? null;
      const result = await handler(supabase, params as Record<string, unknown>, sessionId, clientIde);
      responses.push(jsonRpcSuccess(request.id ?? null, result));
    } catch (err: any) {
      responses.push({ ...jsonRpcError(-32603, err.message ?? 'Internal error'), id: request.id ?? null });
    }
  }

  return new Response(JSON.stringify(Array.isArray(body) ? responses : responses[0]), { headers: CORS_HEADERS });
});
