# /promote

Promote a draft through the Cognitive Runtime Platform lifecycle.

## Scope

Use this skill only for drafts under `context/_drafts/`.

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

1. Read `agents/_policy.yaml`.
2. Confirm the source file exists under `context/_drafts/`.
3. Parse frontmatter and verify `status: draft`.
4. Confirm lifecycle transition `draft -> review` is allowed.
5. Confirm `promotion.runtime_direct_write_forbidden` is true.
6. Confirm no direct write to `reflection/` will occur.
7. Compute an idempotency key from `promote_draft|source_path|draft_hash`.
8. Check `runtime/events/*.jsonl` for the same idempotency key.
9. Acquire `runtime/locks/promote.lock`.
10. Update the draft frontmatter status to `review` in place.
11. Emit `draft.promoted` with `tools/scripts/emit-event.ps1`.
12. Create a run YAML in `runtime/runs/`.
13. Release `runtime/locks/promote.lock`.

## Execution

Prefer the checked helper:

```powershell
tools/scripts/promote-draft.ps1 -Path context/_drafts/<file>.md
```

## Destination

P0 promotion moves a document from `draft` to `review` without moving it into `reflection/`.
Reviewed reflection writes are a later controlled promotion step.

## Failure Policy

Fail closed if:
- The transition is not allowed.
- A lock already exists.
- The idempotency key already exists.
- The source path is outside `context/_drafts/`.
- The source frontmatter is missing or not `draft`.

Never delete drafts on failure.
