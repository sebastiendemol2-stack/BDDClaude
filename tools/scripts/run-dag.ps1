param(
  [Parameter(Mandatory = $true)]
  [string]$DagPath,

  [string]$CorrelationId = ([guid]::NewGuid().ToString()),
  [string]$CausationId = $null,
  [string]$Root = (Resolve-Path ".").Path,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Get-Sha256Hex {
  param([Parameter(Mandatory = $true)][string]$Text)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $hash = $sha.ComputeHash($bytes)
    return (($hash | ForEach-Object { $_.ToString("x2") }) -join "")
  }
  finally {
    $sha.Dispose()
  }
}

function Get-RelativePath {
  param(
    [Parameter(Mandatory = $true)][string]$Base,
    [Parameter(Mandatory = $true)][string]$FullPath
  )
  $baseUri = [System.Uri]((Resolve-Path -LiteralPath $Base).Path.TrimEnd('\') + '\')
  $resolvedFullPath = if (Test-Path -LiteralPath $FullPath) {
    (Resolve-Path -LiteralPath $FullPath).Path
  }
  else {
    [System.IO.Path]::GetFullPath($FullPath)
  }
  $pathUri = [System.Uri]$resolvedFullPath
  return [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($pathUri).ToString()).Replace('/', '\')
}

function ConvertTo-YamlScalar {
  param([AllowNull()][string]$Value)
  if ($null -eq $Value) {
    return "null"
  }
  return '"' + ($Value -replace '\\', '\\' -replace '"', '\"') + '"'
}

function Add-OrSetProperty {
  param(
    [Parameter(Mandatory = $true)]$Object,
    [Parameter(Mandatory = $true)][string]$Name,
    [AllowNull()]$Value
  )
  $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value -Force
}

function Resolve-DagOrder {
  param([Parameter(Mandatory = $true)]$Steps)

  $stepList = @($Steps)
  if ($stepList.Count -lt 1 -or $stepList.Count -gt 20) {
    throw "DAG refused: steps count must be between 1 and 20"
  }

  $stepById = @{}
  $idOrder = @()
  for ($i = 0; $i -lt $stepList.Count; $i++) {
    $step = $stepList[$i]
    if (-not $step.id -or $step.id -notmatch '^[A-Za-z0-9_-]{1,64}$') {
      throw "DAG refused: invalid step id"
    }
    if ($stepById.ContainsKey($step.id)) {
      throw "DAG refused: duplicate step id $($step.id)"
    }
    if (-not $step.query -or -not $step.query.ToString().Trim()) {
      throw "DAG refused: step $($step.id) has an empty query"
    }
    if ($null -eq $step.depends_on) {
      Add-OrSetProperty -Object $step -Name "depends_on" -Value @()
    }
    $stepById[$step.id] = $step
    $idOrder += $step.id
  }

  foreach ($step in $stepList) {
    foreach ($dependency in @($step.depends_on)) {
      if (-not $stepById.ContainsKey($dependency)) {
        throw "DAG refused: step $($step.id) depends on unknown step $dependency"
      }
      if ($dependency -eq $step.id) {
        throw "DAG refused: step $($step.id) depends on itself"
      }
    }
  }

  $remaining = @{}
  foreach ($id in $idOrder) {
    $remaining[$id] = $true
  }

  $completed = @{}
  $ordered = @()

  while ($remaining.Count -gt 0) {
    $ready = @()
    foreach ($id in @($remaining.Keys)) {
      $deps = @($stepById[$id].depends_on)
      $allDepsCompleted = $true
      foreach ($dep in $deps) {
        if (-not $completed.ContainsKey($dep)) {
          $allDepsCompleted = $false
          break
        }
      }
      if ($allDepsCompleted) {
        $ready += $id
      }
    }

    if ($ready.Count -eq 0) {
      throw "DAG refused: cycle detected"
    }

    $ready = $ready | Sort-Object { [array]::IndexOf($idOrder, $_) }
    foreach ($id in $ready) {
      $ordered += $stepById[$id]
      $completed[$id] = $true
      $remaining.Remove($id)
    }
  }

  return $ordered
}

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$manifestPath = Join-Path $rootPath "runtime.manifest.json"
$registryPath = Join-Path $rootPath "tools/registry.json"
$emitScript = Join-Path $rootPath "tools/scripts/emit-event.ps1"
$invokeScript = Join-Path $rootPath "tools/scripts/invoke-agent.ps1"
$dagRoot = Join-Path $rootPath "runtime/scheduler/dags"

foreach ($requiredPath in @($manifestPath, $registryPath, $emitScript, $invokeScript)) {
  if (-not (Test-Path -LiteralPath $requiredPath)) {
    throw "DAG refused: missing $requiredPath"
  }
}
New-Item -ItemType Directory -Force -Path $dagRoot | Out-Null

$resolvedDagPath = (Resolve-Path -LiteralPath $DagPath).Path
$resolvedDagRoot = (Resolve-Path -LiteralPath $dagRoot).Path
if (-not $resolvedDagPath.StartsWith($resolvedDagRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "DAG refused: DagPath must be under runtime/scheduler/dags/"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$registry = Get-Content -LiteralPath $registryPath -Raw | ConvertFrom-Json

if ($manifest.features.run_dag -ne "phase_3_local_dag") {
  throw "DAG refused: run_dag feature is not phase_3_local_dag"
}
if (-not $registry.tools.run_dag -or $registry.tools.run_dag.trust_level -ne "safe_write") {
  throw "DAG refused: run_dag must be registered as safe_write"
}

$dag = Get-Content -LiteralPath $resolvedDagPath -Raw | ConvertFrom-Json
if ($dag.schema_version -ne "1.0.0") {
  throw "DAG refused: schema_version must be 1.0.0"
}
if (-not $dag.id -or $dag.id -notmatch '^[A-Za-z0-9_-]{1,64}$') {
  throw "DAG refused: invalid dag id"
}

$orderedSteps = @(Resolve-DagOrder -Steps $dag.steps)
$relativeDagPath = Get-RelativePath -Base $rootPath -FullPath $resolvedDagPath
$dagRunId = [guid]::NewGuid().ToString()
$runStamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$dagRunPath = Join-Path (Join-Path $rootPath "runtime/runs") "$runStamp-dag-$dagRunId.yaml"

if ($DryRun) {
  $routes = @()
  foreach ($step in $orderedSteps) {
    $routeJson = & $invokeScript `
      -Root $rootPath `
      -Query $step.query `
      -CorrelationId "$CorrelationId-$($step.id)" `
      -DryRun
    $route = $routeJson | ConvertFrom-Json
    $routes += [pscustomobject]@{
      id = $step.id
      depends_on = @($step.depends_on)
      agent = $route.agent
      reason = $route.reason
      matches = @($route.matches)
    }
  }

  [pscustomobject]@{
    status = "dry_run"
    dag_id = $dag.id
    dag_path = $relativeDagPath
    step_count = $orderedSteps.Count
    order = @($orderedSteps | ForEach-Object { $_.id })
    routes = $routes
    run_path = (Get-RelativePath -Base $rootPath -FullPath $dagRunPath)
    correlation_id = $CorrelationId
  } | ConvertTo-Json -Depth 20
  exit 0
}

$lockDir = Join-Path $rootPath "runtime/locks"
New-Item -ItemType Directory -Force -Path $lockDir | Out-Null
$lockPath = Join-Path $lockDir "dag.lock"
$lockAcquired = $false
$dagStatus = "completed"
$dagError = $null
$stepResults = @()
$eventIds = @()
$startedAt = (Get-Date).ToUniversalTime().ToString("o")

try {
  New-Item -ItemType File -Path $lockPath -Value "pid=$PID`ndag=$($dag.id)`ncreated_at=$startedAt`n" -ErrorAction Stop | Out-Null
  $lockAcquired = $true

  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dagRunPath) | Out-Null
  $startedJson = & $emitScript `
    -Event "run.started" `
    -Actor "dag-runner" `
    -Target (Get-RelativePath -Base $rootPath -FullPath $dagRunPath) `
    -CorrelationId $CorrelationId `
    -CausationId $CausationId `
    -IdempotencyKey (Get-Sha256Hex -Text "run_dag|$($dag.id)|$dagRunId|run.started") `
    -MetaJson (@{ dag_id = $dag.id; dag_path = $relativeDagPath; step_count = $orderedSteps.Count } | ConvertTo-Json -Compress) `
    -Root $rootPath
  $startedEvent = $startedJson | ConvertFrom-Json
  $eventIds += $startedEvent.id

  foreach ($step in $orderedSteps) {
    $invokeJson = & $invokeScript `
      -Root $rootPath `
      -Query $step.query `
      -CorrelationId $CorrelationId `
      -CausationId $startedEvent.id
    $invoke = $invokeJson | ConvertFrom-Json
    $eventIds += @($invoke.events)
    $stepResults += [pscustomobject]@{
      id = $step.id
      status = $invoke.status
      agent = $invoke.agent
      run_path = $invoke.run_path
      query_hash = (Get-Sha256Hex -Text $step.query)
      depends_on = @($step.depends_on)
    }
  }
}
catch {
  $dagStatus = "failed"
  $dagError = @{ message = $_.Exception.Message }
}
finally {
  $endedAt = (Get-Date).ToUniversalTime().ToString("o")
  $errorJson = if ($dagError) { $dagError | ConvertTo-Json -Compress } else { $null }
  $endedJson = & $emitScript `
    -Event "run.ended" `
    -Actor "dag-runner" `
    -Target (Get-RelativePath -Base $rootPath -FullPath $dagRunPath) `
    -CorrelationId $CorrelationId `
    -CausationId $(if ($eventIds.Count -gt 0) { $eventIds[-1] } else { $CausationId }) `
    -IdempotencyKey (Get-Sha256Hex -Text "run_dag|$($dag.id)|$dagRunId|run.ended") `
    -MetaJson (@{ dag_id = $dag.id; status = $dagStatus; completed_steps = $stepResults.Count } | ConvertTo-Json -Compress) `
    -ErrorJson $errorJson `
    -Root $rootPath
  $endedEvent = $endedJson | ConvertFrom-Json
  $eventIds += $endedEvent.id

  $stepYaml = ""
  foreach ($result in $stepResults) {
    $deps = (@($result.depends_on) | ForEach-Object { ConvertTo-YamlScalar $_ }) -join ", "
    $stepYaml += "  - id: $(ConvertTo-YamlScalar $result.id)`n"
    $stepYaml += "    status: $($result.status)`n"
    $stepYaml += "    agent: $($result.agent)`n"
    $stepYaml += "    run_path: $(ConvertTo-YamlScalar $result.run_path)`n"
    $stepYaml += "    query_hash: $($result.query_hash)`n"
    $stepYaml += "    depends_on: [$deps]`n"
  }
  if (-not $stepYaml) {
    $stepYaml = "  []`n"
  }

  $errorScalar = if ($dagError) { ConvertTo-YamlScalar ($dagError.message) } else { "null" }
  $runContent = @"
---
schema_version: "1.0.0"
id: $dagRunId
run_type: dag
dag_id: $($dag.id)
dag_path: $(ConvertTo-YamlScalar $relativeDagPath)
correlation_id: $CorrelationId
parent_run_id: null
status: $dagStatus
started_at: $startedAt
ended_at: $endedAt
step_count: $($orderedSteps.Count)
completed_steps: $($stepResults.Count)
tools_used: [emit_event, invoke_agent]
events: [$($eventIds -join ", ")]
steps:
$stepYaml
error: $errorScalar
---
"@

  Set-Content -LiteralPath $dagRunPath -Value $runContent -Encoding UTF8

  if ($lockAcquired -and (Test-Path -LiteralPath $lockPath)) {
    Remove-Item -LiteralPath $lockPath -Force
  }
}

if ($dagStatus -ne "completed") {
  throw "DAG failed: $($dagError.message)"
}

[pscustomobject]@{
  status = $dagStatus
  dag_id = $dag.id
  run_path = (Get-RelativePath -Base $rootPath -FullPath $dagRunPath)
  step_count = $orderedSteps.Count
  completed_steps = $stepResults.Count
  steps = $stepResults
  events = $eventIds
  correlation_id = $CorrelationId
} | ConvertTo-Json -Depth 20
