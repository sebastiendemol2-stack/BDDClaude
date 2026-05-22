# /invoke

Invoke the Cognitive Runtime Platform phase 1 keyword router.

## Scope

Use this skill to route a user request to one declared local agent:

- `research`
- `synthesis`
- `analysis`

P1 invocation is local control-plane execution only. It selects the agent, builds the agent input payload, emits runtime events, and creates a run file. It does not call an LLM, does not execute external network calls, and does not write directly to `reflection/`.

Do not read or write:

- `raw/`
- `raw/private/`
- `raw/sensitive/`
- `runtime/` as RAG input
- `.git/`
- `.env`
- `_scripts/`
- `schema/`
- `supabase/`

## Required Checks

1. Read `index.json`.
2. Confirm `routing.strategy: keyword` and `routing.phase: 1`.
3. Read `tools/registry.json`.
4. Confirm `emit_event` is registered as `safe_write`.
5. Select the highest-priority matching agent by `keywords`.
6. If no keyword matches, fall back to `analysis`.
7. Build the payload for the selected agent input schema.
8. Emit `run.started`.
9. Emit `agent.invoked`.
10. Emit `run.ended`.
11. Create a YAML run record in `runtime/runs/`.

## Execution

Preview the route without writing:

```powershell
tools/scripts/invoke-agent.ps1 -Query "<request>" -DryRun
```

Create runtime events and a run record:

```powershell
tools/scripts/invoke-agent.ps1 -Query "<request>"
```

Run the P1 smoke test suite without writing runtime events:

```powershell
tools/scripts/test-runtime.ps1
```

## Routing

Routing is declared in `index.json`.

Priority order is data-driven through each agent's `priority` field. The initial P1 strategy is keyword matching only:

- `research`: cherche, trouve, compare, veille, source
- `synthesis`: resume, synthese, extrait, consolide
- `analysis`: analyse, audit, diagnostic, debug

Fallback is `analysis` when no keyword matches.

## Failure Policy

Fail closed if:

- `index.json` is missing or routing is not keyword phase 1.
- `tools/registry.json` is missing.
- `emit_event` is not registered as `safe_write`.
- The selected agent file is missing.
- Event emission fails.

Never create reflection notes directly from `/invoke`.
