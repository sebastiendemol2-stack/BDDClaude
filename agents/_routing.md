# Agent Routing v1

## Implementation

Routing is **algorithmic** — `tools/scripts/route.ps1` reads `agents/registry.json` and matches
keywords against the lowercased input string. Highest hit count wins; tie-broken by priority.

```powershell
# Usage
tools/scripts/route.ps1 -Input "analyse le runtime"
# → {"agent":"analysis","path":"agents/analysis.md","routing_reason":"keyword","matched_keyword":"analyse","score":1}

tools/scripts/route.ps1 -Input "analyse le runtime" -Emit
# → same, plus emits agent.invoked event to runtime/events/
```

No match → falls through to highest-priority agent (research) as catch-all.

## Priority table (from agents/registry.json)

| Priority | Agent     | Keywords |
|----------|-----------|----------|
| 100      | research  | cherche, trouve, compare, veille, source, research |
| 90       | synthesis | resume, synthese, extrait, consolide, compile |
| 80       | analysis  | analyse, audit, diagnostic, debug, performance |

## Constraints

- `runtime/` is never included in RAG or context assembly.
- `agents/`, `tools/`, `capabilities/` are control-plane: read-only for agents.
- `wiki/` and `reflection/` are knowledge-plane inputs for RAG.
- `raw/private/` and `raw/sensitive/` are never read by LLMs or scripts.

## Fallbacks

- `research` falls back to `analysis` on failure.
- `synthesis` and `analysis` fail closed.

## Roadmap

- Phase 2: Hybrid scoring — embedding (0.5) + keyword (0.3) + context (0.2).
- Phase 3: Meta-agent orchestrator with DAG fanout (research + analysis → synthesis).
