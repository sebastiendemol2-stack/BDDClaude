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

function Test-EventCorrelationIdExists {
  param(
    [Parameter(Mandatory = $true)][string]$RootPath,
    [Parameter(Mandatory = $true)][string[]]$CorrelationIds
  )
  $eventsDir = Join-Path $RootPath "runtime/events"
  if (-not (Test-Path -LiteralPath $eventsDir)) {
    return $false
  }

  foreach ($file in Get-ChildItem -LiteralPath $eventsDir -Filter "*.jsonl" -File -ErrorAction SilentlyContinue) {
    foreach ($line in Get-Content -LiteralPath $file.FullName -ErrorAction SilentlyContinue) {
      if (-not $line.Trim()) {
        continue
      }
      try {
        $event = $line | ConvertFrom-Json
        if ($CorrelationIds -contains $event.correlation_id) {
          return $true
        }
      }
      catch {
        continue
      }
    }
  }

  return $false
}

function Invoke-DryRoute {
  param(
    [Parameter(Mandatory = $true)][string]$RootPath,
    [Parameter(Mandatory = $true)][string]$Query,
    [Parameter(Mandatory = $true)][string]$CorrelationId
  )
  $script = Join-Path $RootPath "tools/scripts/invoke-agent.ps1"
  $json = & $script -Root $RootPath -Query $Query -CorrelationId $CorrelationId -DryRun
  return $json | ConvertFrom-Json
}

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$manifestPath = Join-Path $rootPath "runtime.manifest.json"
$indexPath = Join-Path $rootPath "index.json"
$registryPath = Join-Path $rootPath "tools/registry.json"

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$index = Get-Content -LiteralPath $indexPath -Raw | ConvertFrom-Json
$registry = Get-Content -LiteralPath $registryPath -Raw | ConvertFrom-Json

Assert-True ($manifest.features.single_agent_runtime -eq "phase_1_keyword") "single_agent_runtime is not phase_1_keyword"
Assert-True ($index.routing.strategy -eq "keyword") "routing.strategy is not keyword"
Assert-True ([int]$index.routing.phase -eq 1) "routing.phase is not 1"
Assert-True ($registry.tools.emit_event.trust_level -eq "safe_write") "emit_event is not safe_write"

$correlationIds = @(
  "test-runtime-research-$([guid]::NewGuid().ToString())",
  "test-runtime-synthesis-$([guid]::NewGuid().ToString())",
  "test-runtime-analysis-$([guid]::NewGuid().ToString())",
  "test-runtime-fallback-$([guid]::NewGuid().ToString())"
)

$research = Invoke-DryRoute -RootPath $rootPath -Query "cherche les sources du runtime" -CorrelationId $correlationIds[0]
Assert-True ($research.status -eq "dry_run") "research route did not stay dry-run"
Assert-True ($research.agent -eq "research") "research keyword did not route to research"

$synthesis = Invoke-DryRoute -RootPath $rootPath -Query "resume le runtime local" -CorrelationId $correlationIds[1]
Assert-True ($synthesis.status -eq "dry_run") "synthesis route did not stay dry-run"
Assert-True ($synthesis.agent -eq "synthesis") "synthesis keyword did not route to synthesis"

$analysis = Invoke-DryRoute -RootPath $rootPath -Query "analyse le runtime local" -CorrelationId $correlationIds[2]
Assert-True ($analysis.status -eq "dry_run") "analysis route did not stay dry-run"
Assert-True ($analysis.agent -eq "analysis") "analysis keyword did not route to analysis"
Assert-True ($analysis.reason -eq "keyword") "analysis keyword route reason is wrong"

$fallback = Invoke-DryRoute -RootPath $rootPath -Query "requete neutre sans mot cle" -CorrelationId $correlationIds[3]
Assert-True ($fallback.status -eq "dry_run") "fallback route did not stay dry-run"
Assert-True ($fallback.agent -eq "analysis") "fallback did not route to analysis"
Assert-True ($fallback.reason -eq "default_analysis") "fallback reason is wrong"

Assert-True (-not (Test-EventCorrelationIdExists -RootPath $rootPath -CorrelationIds $correlationIds)) "dry-run routing wrote runtime events"

[pscustomobject]@{
  status = "passed"
  checks = 9
  dry_run_event_check = "no matching correlation ids"
} | ConvertTo-Json -Depth 5
