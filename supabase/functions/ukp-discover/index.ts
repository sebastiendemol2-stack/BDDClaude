import { createClient } from 'jsr:@supabase/supabase-js@2';

Deno.serve(async (req: Request) => {
  const url = new URL(req.url);
  const path = url.pathname.replace('/functions/v1/ukp-discover', '');

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  );

  try {
    const [toolsResult, resourcesResult, profilesResult] = await Promise.all([
      supabase.from('tools_registry')
        .select('id, name, description, version, category, input_schema, output_schema, endpoint, auth_level, tags')
        .eq('enabled', true)
        .order('category', { ascending: true }),
      supabase.from('resources_registry')
        .select('id, uri_pattern, name, description, mime_type, category, is_dynamic')
        .order('category', { ascending: true }),
      supabase.from('context_profiles')
        .select('id, name, description, is_default, token_budget')
        .order('is_default', { ascending: false })
    ]);

    if (toolsResult.error) throw toolsResult.error;
    if (resourcesResult.error) throw resourcesResult.error;
    if (profilesResult.error) throw profilesResult.error;

    const body = {
      protocol: 'ukp-v1',
      version: '1.0.0',
      tools: toolsResult.data,
      resources: resourcesResult.data,
      profiles: profilesResult.data,
      server_info: {
        name: 'UKP Gateway',
        supports_streaming: true,
        supports_mcp: true,
        max_token_budget: 48000
      }
    };

    const accept = req.headers.get('accept') || '';
    if (accept.includes('text/event-stream')) {
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(`event: tools\ndata: ${JSON.stringify(body.tools)}\n\n`));
          controller.enqueue(encoder.encode(`event: resources\ndata: ${JSON.stringify(body.resources)}\n\n`));
          controller.enqueue(encoder.encode(`event: profiles\ndata: ${JSON.stringify(body.profiles)}\n\n`));
          controller.enqueue(encoder.encode(`event: server_info\ndata: ${JSON.stringify(body.server_info)}\n\n`));
          controller.enqueue(encoder.encode(`event: done\ndata: {}\n\n`));
          controller.close();
        }
      });
      return new Response(stream, {
        headers: { 'Content-Type': 'text/event-stream' }
      });
    }

    return new Response(JSON.stringify(body), {
      headers: { 'Content-Type': 'application/json' }
    });

  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
});
