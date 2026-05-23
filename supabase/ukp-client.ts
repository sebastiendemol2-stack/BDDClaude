/**
 * UKPClient — Universal Knowledge Protocol SDK
 *
 * Zero-dependency TypeScript SDK for any IDE (Claude Code, VS Code, Cursor, etc.)
 * to interact with UKP Supabase backend.
 *
 * @example
 * ```ts
 * const client = new UKPClient({
 *   url: 'https://ottoqbwctcpzzdfzewdi.supabase.co',
 *   key: process.env.SUPABASE_KEY!,
 *   clientIde: 'claude-code'
 * });
 * await client.prime();
 * const results = await client.query('vault sync');
 * ```
 */

// ─── Types ──────────────────────────────────────────────────────────────

export interface UKPConfig {
  url: string;
  key: string;
  profile?: string;
  project?: string;
  clientIde?: string;
  functionsPath?: string;
  timeout?: number;
  maxRetries?: number;
}

export interface QueryResult {
  id: string; title: string; content: string | null;
  tags: string[]; type: string; obsidian_path: string | null;
  section: string | null; score: number; method: string;
  summary: string | null; freshness: string | null;
  confidence: string | null; updated_at: string | null;
}

export interface QueryResponse {
  results: QueryResult[]; total: number; took_ms: number; profile_used: string;
}

export interface SessionInfo {
  session_id: string; started_at: string; project_slug: string;
  profile_loaded: string; token_budget: number;
  auto_enable_tools: string[]; took_ms: number;
}

export interface ToolDefinition {
  id: string; name: string; description: string; version: string;
  category: 'knowledge'|'memory'|'session'|'context'|'system';
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>; endpoint: string | null;
  auth_level: 'anon'|'authenticated'|'service_role'; tags: string[];
}

export interface ResourceDefinition {
  id: string; uri_pattern: string; name: string;
  description: string | null; mime_type: string;
  category: string; is_dynamic: boolean;
}

export interface ContextProfile {
  id: string; name: string; description: string | null;
  is_default: boolean; token_budget: number;
}

export interface DiscoveryResponse {
  protocol: string; version: string;
  tools: ToolDefinition[]; resources: ResourceDefinition[];
  profiles: ContextProfile[];
  server_info: { name: string; supports_streaming: boolean; supports_mcp: boolean; max_token_budget: number };
}

export interface PrimeResponse {
  project: string;
  vault_stats: { notes_total: number; sections: string[]; notes_by_section: Record<string, number> };
  available_tools: Array<{ name: string; description: string; version: string; category: string; tags: string[] }>;
  available_profiles: ContextProfile[]; resources_uri: string[]; took_ms: number;
}

export interface QueryOptions {
  maxResults?: number; profile?: string; mode?: 'hybrid'|'fts'|'vector'; project?: string;
}

export interface EndSessionOptions {
  summary?: string; decisions?: string[]; patterns?: string[];
}

export interface EndSessionResponse {
  session_id: string; ended: boolean; decisions_persisted: number; patterns_persisted: number; took_ms: number;
}

export interface InjectContextResponse {
  session_id: string;
  memories: Array<{ type: string; key: string|null; value: string|null; source: string|null; created_at: string|null }>;
  context_chunks: Array<{ title: string; content: string|null; type: string|null; section: string|null; score: number|null }>;
  profile_used: string; took_ms: number;
}

export type ModelStatus = 'active' | 'inactive' | 'deprecated' | 'error';
export type ModelKind = 'embedding' | 'chat' | 'reranker' | 'vision' | 'audio' | 'tool';

export interface VaultModel {
  id: string;
  name: string;
  provider: string;
  version: string;
  kind: ModelKind;
  source_hash: string | null;
  dimension: number;
  priority: number;
  fallback_order: number;
  rollout_percent: number;
  status: ModelStatus;
  config: Record<string, unknown>;
  last_used_at: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface ListModelsOptions {
  status?: ModelStatus;
  minDimension?: number;
  provider?: string;
  kind?: ModelKind;
  includeInactive?: boolean;
}

export interface RegisterModelParams {
  name: string;
  provider: string;
  dimension: number;
  version?: string;
  kind?: ModelKind;
  source_hash?: string;
  endpoint?: string;
  api_key_env?: string;
  priority?: number;
  fallback_order?: number;
  rollout_percent?: number;
  status?: ModelStatus;
  config?: Record<string, unknown>;
}

export interface SelectModelOptions {
  name?: string;
  provider?: string;
  kind?: ModelKind;
  minDimension?: number;
}

export interface UpdateModelStatusParams {
  id?: string;
  name?: string;
  provider?: string;
  version?: string;
  status?: ModelStatus;
  error_message?: string;
}

export interface ModelListResponse {
  models: VaultModel[];
  active: VaultModel[];
  total: number;
  admin?: boolean;
}

export interface ModelLatestResponse {
  model: VaultModel | null;
  fallbacks: VaultModel[];
  total: number;
}

// ─── Error ──────────────────────────────────────────────────────────────

export class UKPError extends Error {
  constructor(public readonly code: string, message: string, public readonly details?: Record<string, unknown>, public readonly statusCode?: number) {
    super(message); this.name = 'UKPError';
  }
}

// ─── Retry ──────────────────────────────────────────────────────────────

async function withRetry<T>(fn: () => Promise<T>, maxRetries = 3, baseDelayMs = 500): Promise<T> {
  let lastError: Error | null = null;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try { return await fn(); }
    catch (err) {
      lastError = err as Error;
      if (err instanceof UKPError && err.statusCode && err.statusCode >= 400 && err.statusCode < 500) throw err;
      if (attempt < maxRetries) await new Promise(r => setTimeout(r, baseDelayMs * Math.pow(2, attempt) + Math.random() * 100));
    }
  }
  throw lastError ?? new UKPError('MAX_RETRIES', `Failed after ${maxRetries + 1} attempts`);
}

// ─── Client ─────────────────────────────────────────────────────────────

export class UKPClient {
  public readonly url: string;
  public readonly key: string;
  public readonly profile: string;
  public readonly project?: string;
  public readonly clientIde?: string;
  public readonly functionsPath: string;
  public readonly timeout: number;
  public readonly maxRetries: number;

  private _discoveryCache: DiscoveryResponse | null = null;
  private _discoveryCacheTime = 0;
  private readonly CACHE_TTL = 5 * 60 * 1000;

  constructor(config: UKPConfig) {
    this.url = config.url.replace(/\/+$/, '');
    this.key = config.key;
    this.profile = config.profile ?? 'rag-default';
    this.project = config.project;
    this.clientIde = config.clientIde;
    this.functionsPath = config.functionsPath ?? '/functions/v1';
    this.timeout = config.timeout ?? 30000;
    this.maxRetries = config.maxRetries ?? 3;
  }

  private functionUrl(slug: string): string {
    return `${this.url}${this.functionsPath}/${slug}`;
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = {
      'Content-Type': 'application/json', apikey: this.key, Authorization: `Bearer ${this.key}`,
    };
    if (this.clientIde) h['x-client-ide'] = this.clientIde;
    return h;
  }

  private async callFunction<T>(slug: string, method: 'GET'|'POST' = 'GET', body?: Record<string, unknown>): Promise<T> {
    return withRetry(async () => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeout);
      try {
        const opts: RequestInit = { method, headers: this.headers(), signal: controller.signal };
        if (body && method === 'POST') opts.body = JSON.stringify(body);
        const res = await fetch(this.functionUrl(slug), opts);
        if (!res.ok) {
          let errBody: Record<string, unknown> | null = null;
          try { errBody = await res.json(); } catch {}
          throw new UKPError(`HTTP_${res.status}`, (errBody?.error as string) ?? `Request failed: ${res.status}`, errBody ?? undefined, res.status);
        }
        return res.json() as Promise<T>;
      } finally { clearTimeout(timeoutId); }
    }, this.maxRetries);
  }

  async prime(): Promise<DiscoveryResponse & { vault: PrimeResponse }> {
    const [discovery, vault] = await Promise.all([
      this.getDiscovery(),
      this.callFunction<PrimeResponse>('ukp-session', 'POST', {
        action: 'prime', project_slug: this.project, profile: this.profile, client_ide: this.clientIde,
      }),
    ]);
    return { ...discovery, vault };
  }

  async query(search: string, options?: QueryOptions): Promise<QueryResponse> {
    if (!search?.trim()) throw new UKPError('INVALID_QUERY', 'Search query cannot be empty');
    return this.callFunction<QueryResponse>('ukp-query', 'POST', {
      query: search.trim(), project: options?.project ?? this.project,
      max_results: options?.maxResults ?? 10, profile: options?.profile ?? this.profile,
      mode: options?.mode ?? 'hybrid',
    });
  }

  async beginSession(projectOverride?: string, profileOverride?: string): Promise<SessionInfo> {
    return this.callFunction<SessionInfo>('ukp-session', 'POST', {
      action: 'begin', project_slug: projectOverride ?? this.project,
      profile: profileOverride ?? this.profile, client_ide: this.clientIde,
    });
  }

  async endSession(sessionId: string, options?: EndSessionOptions): Promise<EndSessionResponse> {
    if (!sessionId) throw new UKPError('MISSING_SESSION_ID', 'session_id is required');
    return this.callFunction<EndSessionResponse>('ukp-session', 'POST', {
      action: 'end', session_id: sessionId, project_slug: this.project,
      summary: options?.summary, decisions: options?.decisions,
      patterns: options?.patterns, client_ide: this.clientIde,
    });
  }

  async injectContext(sessionId: string, contextQuery?: string, profileOverride?: string): Promise<InjectContextResponse> {
    if (!sessionId) throw new UKPError('MISSING_SESSION_ID', 'session_id is required');
    return this.callFunction<InjectContextResponse>('ukp-session', 'POST', {
      action: 'inject', session_id: sessionId, project_slug: this.project,
      profile: profileOverride ?? this.profile, context_query: contextQuery, client_ide: this.clientIde,
    });
  }

  async getTools(): Promise<ToolDefinition[]> { return (await this.getDiscovery()).tools; }
  async getResources(): Promise<ResourceDefinition[]> { return (await this.getDiscovery()).resources; }
  async getProfiles(): Promise<ContextProfile[]> { return (await this.getDiscovery()).profiles; }

  async mcpCall(method: string, params?: Record<string, unknown>): Promise<unknown> {
    return this.callFunction('ukp-mcp', 'POST', { jsonrpc: '2.0', id: 1, method, params });
  }

  async getDiscovery(): Promise<DiscoveryResponse> {
    const now = Date.now();
    if (this._discoveryCache && now - this._discoveryCacheTime < this.CACHE_TTL) return this._discoveryCache;
    this._discoveryCache = await this.callFunction<DiscoveryResponse>('ukp-discover');
    this._discoveryCacheTime = now;
    return this._discoveryCache;
  }

  invalidateCache(): void { this._discoveryCache = null; this._discoveryCacheTime = 0; }

  async buildContextPrompt(query: string, maxTokens = 12000): Promise<string> {
    const results = await this.query(query, { maxResults: 10 });
    const contextParts: string[] = [];
    let usedTokens = 0;
    const maxChars = maxTokens * 4;

    for (const r of results.results) {
      const entry = [
        `## ${r.title}`,
        `Type: ${r.type} | Section: ${r.section ?? 'N/A'} | Score: ${r.score?.toFixed(3) ?? 'N/A'}`,
        r.tags.length > 0 ? `Tags: ${r.tags.join(', ')}` : null,
        r.summary ? `Summary: ${r.summary}` : null,
        r.content ? r.content : null,
      ].filter(Boolean).join('\n');

      if ((usedTokens + entry.length / 4) > maxTokens) break;
      contextParts.push(entry);
      usedTokens += entry.length / 4;
    }

    return [
      '# UKP Context — Injected Knowledge', '', `Query: "${query}"`,
      `Results: ${results.results.length} entries | ${Math.round(usedTokens)} tokens | ${results.took_ms}ms`,
      `Profile: ${results.profile_used}`, '', '---', '',
      contextParts.length > 0 ? contextParts.join('\n\n---\n\n') : 'No relevant context found.',
      '', '---', '', 'Use the above context to inform your response.',
    ].join('\n');
  }

  // ─── Model Registry ─────────────────────────────────────────────────────

  async listModels(options?: ListModelsOptions): Promise<ModelListResponse> {
    return this.callFunction<ModelListResponse>('model-list', 'POST', {
      ...(options?.status ? { status: options.status } : {}),
      ...(options?.minDimension ? { min_dimension: options.minDimension } : {}),
      ...(options?.provider ? { provider: options.provider } : {}),
      ...(options?.kind ? { kind: options.kind } : {}),
      ...(options?.includeInactive ? { include_inactive: options.includeInactive } : {}),
    });
  }

  async registerModel(params: RegisterModelParams): Promise<{ model: VaultModel }> {
    if (!params.name || !params.provider || !params.dimension) throw new UKPError('INVALID_MODEL', 'name, provider, and dimension are required');
    return this.callFunction<{ model: VaultModel }>('model-register', 'POST', params as unknown as Record<string, unknown>);
  }

  async latestModel(options?: SelectModelOptions): Promise<ModelLatestResponse> {
    return this.callFunction<ModelLatestResponse>('model-latest', 'POST', {
      ...(options?.name ? { name: options.name } : {}),
      ...(options?.provider ? { provider: options.provider } : {}),
      kind: options?.kind ?? 'embedding',
      ...(options?.minDimension ? { min_dimension: options.minDimension } : {}),
    });
  }

  async selectModel(options?: SelectModelOptions): Promise<VaultModel | null> {
    const { model } = await this.latestModel(options);
    return model;
  }

  async getModelFallbackChain(options?: SelectModelOptions): Promise<VaultModel[]> {
    const { model, fallbacks } = await this.latestModel(options);
    return model ? [model, ...fallbacks] : [];
  }

  async updateModelStatus(params: UpdateModelStatusParams): Promise<{ model: VaultModel }> {
    if (!params.id && (!params.name || !params.provider)) {
      throw new UKPError('INVALID_MODEL_TARGET', 'id or name/provider is required');
    }
    return this.callFunction<{ model: VaultModel }>('model-deactivate', 'POST', params as unknown as Record<string, unknown>);
  }

  async deactivateModel(params: Omit<UpdateModelStatusParams, 'status'>): Promise<{ model: VaultModel }> {
    return this.updateModelStatus({ ...params, status: 'inactive' });
  }

  async healthCheck(): Promise<boolean> {
    try { await this.getDiscovery(); return true; } catch { return false; }
  }
}

export default UKPClient;
