param(
  [string]$Root = (Resolve-Path ".").Path
)

$ErrorActionPreference = "Stop"

function Assert-True {
  param(
    [Parameter(Mandatory = $true)][bool]$Condition,
    [Parameter(Mandatory = $true)][string]$Message
  )
  if (-not $Condition) {
    throw $Message
  }
}

function Get-EventLineCount {
  param([Parameter(Mandatory = $true)][string]$RootPath)
  $eventsDir = Join-Path $RootPath "runtime/events"
  if (-not (Test-Path -LiteralPath $eventsDir)) {
    return 0
  }
  $count = 0
  foreach ($file in Get-ChildItem -LiteralPath $eventsDir -Filter "*.jsonl" -File -ErrorAction SilentlyContinue) {
    $count += @(Get-Content -LiteralPath $file.FullName -ErrorAction SilentlyContinue).Count
  }
  return $count
}

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$manifest = Get-Content -LiteralPath (Join-Path $rootPath "runtime.manifest.json") -Raw | ConvertFrom-Json
$registry = Get-Content -LiteralPath (Join-Path $rootPath "tools/registry.json") -Raw | ConvertFrom-Json

Assert-True ($manifest.features.run_dag -eq "phase_3_local_dag") "run_dag is not phase_3_local_dag"
Assert-True ($registry.tools.run_dag.trust_level -eq "safe_write") "run_dag is not safe_write"

$dagRoot = Join-Path $rootPath "runtime/scheduler/dags"
New-Item -ItemType Directory -Force -Path $dagRoot | Out-Null

$suffix = [guid]::NewGuid().ToString()
$dagId = "smoke-dag-$suffix"
$dagPath = Join-Path $dagRoot "$dagId.json"
$dag = [ordered]@{
  schema_version = "1.0.0"
  id = $dagId
  name = "Smoke DAG"
  steps = @(
    [ordered]@{
      id = "analyse"
      query = "analyse dag smoke test $suffix"
      depends_on = @()
    },
    [ordered]@{
      id = "resume"
      query = "resume dag smoke test $suffix"
      depends_on = @("analyse")
    }
  )
}
Set-Content -LiteralPath $dagPath -Value ($dag | ConvertTo-Json -Depth 20) -Encoding UTF8

$runDagScript = Join-Path $rootPath "tools/scripts/run-dag.ps1"
$dry = (& $runDagScript -Root $rootPath -DagPath $dagPath -DryRun) | ConvertFrom-Json
Assert-True ($dry.status -eq "dry_run") "DAG dry-run did not stay dry-run"
Assert-True ($dry.step_count -eq 2) "DAG dry-run step count mismatch"
Assert-True ($dry.order[0] -eq "analyse") "DAG dry-run first step mismatch"
Assert-True ($dry.order[1] -eq "resume") "DAG dry-run second step mismatch"
Assert-True ($dry.routes[0].agent -eq "analysis") "DAG analyse step did not route to analysis"
Assert-True ($dry.routes[1].agent -eq "synthesis") "DAG resume step did not route to synthesis"

$beforeEvents = Get-EventLineCount -RootPath $rootPath
$result = (& $runDagScript -Root $rootPath -DagPath $dagPath) | ConvertFrom-Json
Assert-True ($result.status -eq "completed") "DAG did not complete"
Assert-True ($result.step_count -eq 2) "DAG step count mismatch"
Assert-True ($result.completed_steps -eq 2) "DAG completed step count mismatch"
Assert-True ($result.steps[0].id -eq "analyse") "DAG result first step mismatch"
Assert-True ($result.steps[1].id -eq "resume") "DAG result second step mismatch"

$runPath = Join-Path $rootPath $result.run_path
Assert-True (Test-Path -LiteralPath $runPath) "DAG run file is missing"
$runText = Get-Content -LiteralPath $runPath -Raw
Assert-True ($runText -match "run_type: dag") "DAG run file missing run_type"
Assert-True ($runText -match "status: completed") "DAG run file missing completed status"

$afterEvents = Get-EventLineCount -RootPath $rootPath
Assert-True ($afterEvents -ge ($beforeEvents + 8)) "DAG did not emit expected event count"

[pscustomobject]@{
  status = "passed"
  checks = 14
  dag_path = $dry.dag_path
  run_path = $result.run_path
  event_lines_before = $beforeEvents
  event_lines_after = $afterEvents
} | ConvertTo-Json -Depth 10
