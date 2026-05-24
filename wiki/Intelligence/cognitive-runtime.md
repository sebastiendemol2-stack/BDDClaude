---
title: "Cognitive Runtime Platform Core"
date: 2026-05-22
tags: [runtime, memories, feedback, relations]
type: concept
status: active
confidence: high
source_type: synthesis
freshness: evergreen
sensitivity: internal
---

# Cognitive Runtime Platform Core

The runtime core provides programmatic memory, feedback, and relation tracking for the BDDClaude agent system. It sits between the search layer and the dashboard, persisting agent activity as structured data.

## Architecture

```
Agent dispatch → runtime/core.ts → Supabase (vault_memories, vault_feedback, vault_relations)
                                     ↕
                              Edge Functions (memories-store, feedback-collect, relations-update)
                                     ↕
                              Dashboard / monitoring
```

## Tables (Supabase)

### `vault_memories`
Persists session summaries with decisions and patterns for vector-based recall.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | PK |
| session_id | uuid | Unique session identifier (upsert conflict key) |
| project_slug | text | Project namespace |
| summary | text | Free-text session summary |
| decisions | jsonb | Array of `{title, description}` objects |
| patterns | jsonb | Array of pattern strings observed |
| embedding | vector(1536) | Optional vector for similarity search |
| created_at | timestamptz | Auto-timestamp |

### `vault_feedback`
Collects positive/negative signals from agent runs, with dedup via event_id.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | PK |
| event_id | uuid | Optional link to vault_events |
| content | text | Feedback text |
| positive | boolean | Signal direction |
| occurrences | integer | Dedup counter |
| status | text | `raw_feedback` → `validated_precedent` → `promoted_memory` |
| source | text | Origin (e.g. `jan`, `runtime`, `pytest`) |

### `vault_relations`
Directed typed edges between entries for knowledge graph traversal.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | PK |
| source_entry_id | text | Source (obsidian_path or UUID) |
| target_entry_id | text | Target |
| relation_type | text | `references`, `decides`, `depends_on`, `related_to` |
| confidence | real | 0.0–1.0 |
| metadata | jsonb | Arbitrary extra data |

## In-Process API (`runtime/core.ts`)

```typescript
import { CognitiveRuntime } from './runtime/core'

const runtime = new CognitiveRuntime(SUPABASE_URL, SUPABASE_KEY)

// Store a session memory
await runtime.storeMemory({
  session_id: 'uuid',
  project_slug: 'bddclaude',
  summary: 'Implemented vector search migration',
  decisions: [{ title: 'Use pgvector', description: 'Chose pgvector over pg_embedding' }],
  patterns: ['parallel-migration', 'dry-run-first'],
})

// Collect feedback on an agent run
await runtime.collectFeedback({
  event_id: 'uuid',
  content: 'Search results relevant to query',
  positive: true,
})

// Add a relation between two vault entries
await runtime.addRelation({
  source_entry_id: 'wiki/Intelligence/vector-first-search.md',
  target_entry_id: 'wiki/Intelligence/cognitive-runtime.md',
  relation_type: 'references',
  confidence: 0.9,
})

// Search memories by project
const memories = await runtime.searchMemories('bddclaude', 'vector search', 5)
```

## Edge Functions (Remote API)

Each function at `https://{SUPABASE_URL}/functions/v1/{slug}` accepts POST with JSON body.

### `memories-store`

```bash
curl -X POST https://PROJECT.supabase.co/functions/v1/memories-store \
  -H 'Authorization: Bearer <valid-jwt>' \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"...","project_slug":"bddclaude","summary":"..."}'
```

### `feedback-collect`

```bash
curl -X POST https://PROJECT.supabase.co/functions/v1/feedback-collect \
  -H 'Authorization: Bearer <valid-jwt>' \
  -d '{"content":"Great result","positive":true}'
```

### `relations-update`

```bash
curl -X POST https://PROJECT.supabase.co/functions/v1/relations-update \
  -H 'Authorization: Bearer <valid-jwt>' \
  -d '{"source_entry_id":"a","target_entry_id":"b","relation_type":"references"}'
```

## Testing

```bash
python -m pytest _scripts/tests/test_runtime_core.py -v
# Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY env vars
```

## Error codes

| Code | Meaning | Recovery |
|------|---------|----------|
| `400` | Missing required field (`session_id`, `project_slug`, `summary`, `content`, etc.) | Check request body against API docs |
| `401` | Missing or invalid Authorization header | Provide valid JWT or service_role key |
| `409` | Duplicate session_id (upsert conflict with ignoreDuplicates) | Use unique session_id or set `ignoreDuplicates: true` |
| `500` | Server misconfiguration (missing SUPABASE_URL / KEY) | Check Edge Function environment variables |

## Rate limits

| Function | Limit | Scope |
|----------|-------|-------|
| `memories-store` | 30 req/min | Per IP (Supabase gateway) |
| `feedback-collect` | 30 req/min | Per IP |
| `relations-update` | 30 req/min | Per IP |
| `metrics` | 60 req/min | Per IP |

## Dépendances

- **Vector-first search** (Month 1) — memories store references search results
- **Dashboard** (Month 3) — consumes memories, feedback, relations data
- **Worktree cleanup** (Month 4) — independent, but relations may link worktree state

## Voir aussi

- [[Intelligence/vector-first-search]]
- [[wiki/Intelligence/0-6-month-execution-plan]]
- `runtime/core.ts`
- `issues/month-2-cognitive-runtime.md`
