interface HybridSearchParams {
  query: string;
  embedding?: number[];
  limit?: number;
}

interface HybridSearchResult {
  id: string;
  title: string;
  snippet: string;
  score: number;
}

export class VectorSearch {
  private url: string;
  private key: string;

  constructor(supabaseUrl: string, supabaseKey: string) {
    this.url = supabaseUrl.replace(/\/$/, '');
    this.key = supabaseKey;
  }

  async hybridSearch(params: HybridSearchParams): Promise<HybridSearchResult[]> {
    const payload: Record<string, unknown> = {
      query: params.query,
      limit: params.limit ?? 10,
    };

    if (params.embedding && params.embedding.length > 0) {
      payload.embedding = `[${params.embedding.join(',')}]`;
    }

    const res = await fetch(`${this.url}/rest/v1/rpc/query_vector_hybrid`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'apikey': this.key,
        'Authorization': `Bearer ${this.key}`,
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`Hybrid search failed: ${res.status} ${await res.text()}`);
    }

    return res.json();
  }
}
