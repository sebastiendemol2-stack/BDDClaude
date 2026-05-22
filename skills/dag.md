# /dag

Run a local Cognitive Runtime Platform DAG.

## Scope

Use this skill for P3 local DAG orchestration only. A DAG is a JSON file under `runtime/scheduler/dags/` with sequentially executable steps and explicit dependencies.

P3 DAG execution:

- validates the DAG file
- resolves dependency order
- calls `/invoke` for each step
- emits a parent `run.started` and `run.ended`
- writes one DAG run YAML to `runtime/runs/`

It does not call an LLM directly, does not use Supabase, and does not run as a daemon.

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

## DAG Format

```json
{
  "schema_version": "1.0.0",
  "id": "example-dag",
  "name": "Example DAG",
  "steps": [
    {
      "id": "analyse",
      "query": "analyse le sujet",
      "depends_on": []
    },
    {
      "id": "resume",
      "query": "resume le sujet",
      "depends_on": ["analyse"]
    }
  ]
}
```

## Required Checks

1. Read `runtime.manifest.json`.
2. Confirm `features.run_dag: phase_3_local_dag`.
3. Read `tools/registry.json`.
4. Confirm `run_dag` is registered as `safe_write`.
5. Confirm the DAG file is under `runtime/scheduler/dags/`.
6. Validate unique step ids.
7. Validate dependencies reference existing steps.
8. Reject dependency cycles.
9. Preview with `-DryRun`.
10. Run explicitly without `-DryRun`.

## Execution

Preview a DAG:

```powershell
tools/scripts/run-dag.ps1 -DagPath runtime/scheduler/dags/<file>.json -DryRun
```

Run a DAG:

```powershell
tools/scripts/run-dag.ps1 -DagPath runtime/scheduler/dags/<file>.json
```

Run the P3 smoke test suite:

```powershell
tools/scripts/test-dag.ps1
```

## Failure Policy

Fail closed if:

- `run_dag` is not enabled in `runtime.manifest.json`.
- `run_dag` is not registered as `safe_write`.
- The DAG path is outside `runtime/scheduler/dags/`.
- A step id is duplicated or invalid.
- A dependency is missing.
- A dependency cycle is detected.
- The DAG lock is already held.

Never delete DAG files on failure.
