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

Assert-True ($manifest.features.scheduler -eq "phase_2_local_queue") "scheduler is not phase_2_local_queue"
Assert-True ($registry.tools.enqueue_run.trust_level -eq "safe_write") "enqueue_run is not safe_write"
Assert-True ($registry.tools.process_queue.trust_level -eq "safe_write") "process_queue is not safe_write"

$enqueueScript = Join-Path $rootPath "tools/scripts/enqueue-run.ps1"
$processScript = Join-Path $rootPath "tools/scripts/process-queue.ps1"
$query = "analyse scheduler smoke test $([guid]::NewGuid().ToString())"
$beforeEvents = Get-EventLineCount -RootPath $rootPath

$queued = (& $enqueueScript -Root $rootPath -Query $query -MaxAttempts 1) | ConvertFrom-Json
Assert-True ($queued.status -eq "queued") "enqueue did not return queued"
Assert-True ($queued.id.Length -gt 0) "enqueue did not return an id"
Assert-True (Test-Path -LiteralPath (Join-Path $rootPath $queued.path)) "queued file is missing"

$dry = (& $processScript -Root $rootPath -QueueId $queued.id -Limit 1 -DryRun) | ConvertFrom-Json
Assert-True ($dry.status -eq "dry_run") "process dry-run did not stay dry-run"
Assert-True ($dry.due_count -eq 1) "process dry-run did not find the queued item"

$processed = (& $processScript -Root $rootPath -QueueId $queued.id -Limit 1) | ConvertFrom-Json
Assert-True ($processed.status -eq "processed") "process did not return processed"
Assert-True ($processed.processed_count -eq 1) "process did not handle one item"
Assert-True ($processed.results[0].status -eq "completed") "queue item did not complete"

$donePath = Join-Path $rootPath $processed.results[0].path
$runPath = Join-Path $rootPath $processed.results[0].run_path
Assert-True (Test-Path -LiteralPath $donePath) "completed queue item is missing"
Assert-True (Test-Path -LiteralPath $runPath) "invoked run file is missing"

$doneItem = Get-Content -LiteralPath $donePath -Raw | ConvertFrom-Json
Assert-True ($doneItem.status -eq "completed") "done item status is not completed"
Assert-True ($doneItem.run_path -eq $processed.results[0].run_path) "done item run_path mismatch"

$afterEvents = Get-EventLineCount -RootPath $rootPath
Assert-True ($afterEvents -ge ($beforeEvents + 5)) "scheduler did not emit expected event count"

[pscustomobject]@{
  status = "passed"
  checks = 12
  queue_id = $queued.id
  done_path = $processed.results[0].path
  run_path = $processed.results[0].run_path
  event_lines_before = $beforeEvents
  event_lines_after = $afterEvents
} | ConvertTo-Json -Depth 10
