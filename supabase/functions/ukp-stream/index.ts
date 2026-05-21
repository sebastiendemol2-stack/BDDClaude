import { createClient } from 'jsr:@supabase/supabase-js@2';

interface StreamSubscription {
  session_id: string;
  channels: string[];
  client_ide: string | null;
}

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, x-client-ide',
};

function getSupabase() {
  return createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  );
}

function sseMessage(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: CORS_HEADERS });
  }

  const url = new URL(req.url);
  const path = url.pathname.replace(/^\/.*\/ukp-stream/, '');
  const supabase = getSupabase();
  const clientIde = req.headers.get('x-client-ide');

  // POST /subscribe — Register a subscription
  if (req.method === 'POST' && (path === '/subscribe' || path === '')) {
    const { session_id, channels } = await req.json().catch(() => ({}));
    if (!session_id) {
      return new Response(JSON.stringify({ error: 'session_id is required' }), {
        status: 400, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }

    const sub: StreamSubscription = {
      session_id,
      channels: channels ?? ['events', 'tools', 'context'],
      client_ide: clientIde,
    };

    // Create SSE stream
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        controller.enqueue(encoder.encode(sseMessage('connected', {
          session_id, channels: sub.channels, server_time: new Date().toISOString(),
        })));

        // Poll session_events for this session
        let lastId = 0;
        const poll = async () => {
          try {
            const { data: events } = await supabase.from('session_events')
              .select('id, event_type, payload, created_at')
              .eq('session_id', session_id)
              .gt('id', lastId)
              .order('id', { ascending: true });

            if (events) {
              for (const event of events) {
                lastId = event.id;
                controller.enqueue(encoder.encode(sseMessage(event.event_type, {
                  id: event.id, type: event.event_type, payload: event.payload, created_at: event.created_at,
                })));
              }
            }
          } catch {}
        };

        // Poll every 2 seconds
        const interval = setInterval(poll, 2000);
        poll();

        // Keepalive every 30s
        const keepalive = setInterval(() => {
          controller.enqueue(encoder.encode(': keepalive\n\n'));
        }, 30000);

        // Cleanup on close
        req.signal.addEventListener('abort', () => {
          clearInterval(interval);
          clearInterval(keepalive);
        });
      },
    });

    return new Response(stream, {
      headers: {
        ...CORS_HEADERS,
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });
  }

  // GET /health — Health check
  if (req.method === 'GET' && path === '/health') {
    return new Response(JSON.stringify({ status: 'ok', time: new Date().toISOString() }), {
      headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
    });
  }

  // POST /emit — Emit an event (for internal use)
  if (req.method === 'POST' && (path === '/emit' || path === '')) {
    const { session_id, event_type, payload } = await req.json().catch(() => ({}));
    if (!session_id || !event_type) {
      return new Response(JSON.stringify({ error: 'session_id and event_type are required' }), {
        status: 400, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }
    const { data, error } = await supabase.rpc('ukp_emit_session_event', {
      p_session_id: session_id, p_event_type: event_type,
      p_payload: payload ?? {}, p_project_slug: payload?.project_slug ?? null,
    });
    if (error) throw error;
    return new Response(JSON.stringify({ id: data, event_type }), {
      headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
    });
  }

  return new Response(JSON.stringify({ error: 'not found' }), {
    status: 404, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
  });
});
