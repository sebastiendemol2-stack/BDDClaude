# /schedule

Queue and process local Cognitive Runtime Platform runs.

## Scope

Use this skill for P2 local scheduling only. The scheduler is a file-backed queue under `runtime/queue/` and must be run explicitly. It is not a background daemon.

Allowed queue states:

- `pending`
- `processing`
- `done`
- `dead-letter`

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

1. Read `runtime.manifest.json`.
2. Confirm `features.scheduler: phase_2_local_queue`.
3. Read `tools/registry.json`.
4. Confirm `enqueue_run` and `process_queue` are registered as `safe_write`.
5. Queue work with `tools/scripts/enqueue-run.ps1`.
6. Preview processing with `tools/scripts/process-queue.ps1 -DryRun`.
7. Process explicitly with `tools/scripts/process-queue.ps1`.
8. Confirm completed items move to `runtime/queue/done/`.
9. Confirm failed max-attempt items move to `runtime/queue/dead-letter/`.

## Execution

Queue a request due immediately:

```powershell
tools/scripts/enqueue-run.ps1 -Query "<request>"
```

Queue a request for a future time:

```powershell
tools/scripts/enqueue-run.ps1 -Query "<request>" -DueAt "2026-05-21T23:30:00Z"
```

Preview due work without writing:

```powershell
tools/scripts/process-queue.ps1 -DryRun
```

Process due work:

```powershell
tools/scripts/process-queue.ps1 -Limit 5
```

Process one known queue item:

```powershell
tools/scripts/process-queue.ps1 -QueueId "<queue-id>" -Limit 1
```

Run the P2 smoke test suite:

```powershell
tools/scripts/test-scheduler.ps1
```

## Guarantees

- Enqueue writes a single JSON item to `runtime/queue/pending/`.
- Processing acquires `runtime/locks/queue.lock`.
- Processing calls `/invoke` through `tools/scripts/invoke-agent.ps1`.
- Completed items are moved to `runtime/queue/done/`.
- The scheduler emits `tool.called`; the invoked run emits `run.started`, `agent.invoked`, and `run.ended`.

## Failure Policy

Fail closed if:

- Scheduler is not enabled in `runtime.manifest.json`.
- Queue tools are not registered as `safe_write`.
- The queue lock is already held.
- The selected queue item is malformed.

Never delete queue items on failure.
