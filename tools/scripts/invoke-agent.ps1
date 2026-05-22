param(
  [Parameter(Mandatory = $true)]
  [string]$Query,

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

function ConvertTo-CompactJson {
  param([Parameter(Mandatory = $true)]$Value)
  return ($Value | ConvertTo-Json -Depth 20 -Compress)
}

function ConvertTo-YamlScalar {
  param([AllowNull()][string]$Value)
  if ($null -eq $Value) {
    return "null"
  }
  return '"' + ($Value -replace '\\', '\\' -replace '"', '\"') + '"'
}

function Get-AgentPayload {
  param(
    [Parameter(Mandatory = $true)]$Agent,
    [Parameter(Mandatory = $true)][string]$AgentName,
    [Parameter(Mandatory = $true)][string]$Query,
    [Parameter(Mandatory = $true)][string]$CorrelationId
  )

  switch ($AgentName) {
    "research" {
      return [ordered]@{
        schema_version = "1.0.0"
        query = $Query
        correlation_id = $CorrelationId
        sources = @()
        constraints = @()
        max_results = 8
      }
    }
    "synthesis" {
      return [ordered]@{
        schema_version = "1.0.0"
        task = $Query
        correlation_id = $CorrelationId
        inputs = @()
        target_status = "draft"
        requires_review = [bool]($Agent.requires_review)
      }
    }
    "analysis" {
      return [ordered]@{
        schema_version = "1.0.0"
        subject = $Query
        correlation_id = $CorrelationId
        scope = @()
        risk_focus = @()
      }
    }
    default {
      throw "Unsupported agent payload mapping: $AgentName"
    }
  }
}

function Find-AgentRoute {
  param(
    [Parameter(Mandatory = $true)]$Index,
    [Parameter(Mandatory = $true)][string]$Query
  )

  $queryLower = $Query.ToLowerInvariant()
  $candidates = @()

  foreach ($property in $Index.agents.PSObject.Properties) {
    $agentName = $property.Name
    $agent = $property.Value
    $matches = @()

    foreach ($keyword in @($agent.keywords)) {
      if ($queryLower.Contains($keyword.ToString().ToLowerInvariant())) {
        $matches += $keyword.ToString()
      }
    }

    if ($matches.Count -gt 0) {
      $candidates += [pscustomobject]@{
        name = $agentName
        agent = $agent
        priority = [int]$agent.priority
        matches = $matches
        reason = "keyword"
      }
    }
  }

  if ($candidates.Count -gt 0) {
    return $candidates | Sort-Object -Property @{ Expression = "priority"; Descending = $true }, @{ Expression = "name"; Descending = $false } | Select-Object -First 1
  }

  if ($Index.agents.analysis) {
    return [pscustomobject]@{
      name = "analysis"
      agent = $Index.agents.analysis
      priority = [int]$Index.agents.analysis.priority
      matches = @()
      reason = "default_analysis"
    }
  }

  throw "No agent matched and no analysis fallback is configured"
}

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$indexPath = Join-Path $rootPath "index.json"
$registryPath = Join-Path $rootPath "tools/registry.json"
$emitScript = Join-Path $rootPath "tools/scripts/emit-event.ps1"

if (-not (Test-Path -LiteralPath $indexPath)) {
  throw "Invoke refused: missing index.json"
}
if (-not (Test-Path -LiteralPath $registryPath)) {
  throw "Invoke refused: missing tools/registry.json"
}
if (-not (Test-Path -LiteralPath $emitScript)) {
  throw "Invoke refused: missing tools/scripts/emit-event.ps1"
}

$index = Get-Content -LiteralPath $indexPath -Raw | ConvertFrom-Json
$registry = Get-Content -LiteralPath $registryPath -Raw | ConvertFrom-Json

if ($index.routing.strategy -ne "keyword" -or [int]$index.routing.phase -ne 1) {
  throw "Invoke refused: only routing strategy keyword phase 1 is supported"
}

if (-not $registry.tools.emit_event -or $registry.tools.emit_event.trust_level -ne "safe_write") {
  throw "Invoke refused: emit_event must be registered as safe_write"
}

$route = Find-AgentRoute -Index $index -Query $Query
$agent = $route.agent
$agentName = $route.name
$agentPath = Join-Path $rootPath ($agent.path.ToString().Replace('/', [System.IO.Path]::DirectorySeparatorChar))

if (-not (Test-Path -LiteralPath $agentPath)) {
  throw "Invoke refused: agent file is missing: $($agent.path)"
}

$runId = [guid]::NewGuid().ToString()
$runStamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$runPath = Join-Path (Join-Path $rootPath "runtime/runs") "$runStamp-invoke-$runId.yaml"
$payload = Get-AgentPayload -Agent $agent -AgentName $agentName -Query $Query -CorrelationId $CorrelationId
$payloadJson = ConvertTo-CompactJson -Value $payload
$queryHash = Get-Sha256Hex -Text $Query
$idempotencySeed = "invoke_agent|$agentName|$queryHash|$CorrelationId"
$idempotencyKey = Get-Sha256Hex -Text $idempotencySeed

if ($DryRun) {
  [pscustomobject]@{
    status = "dry_run"
    agent = $agentName
    reason = $route.reason
    matches = @($route.matches)
    input_schema = $agent.input_schema
    output_schema = $agent.output_schema
    payload = $payload
    run_path = (Get-RelativePath -Base $rootPath -FullPath $runPath)
    correlation_id = $CorrelationId
    idempotency_key = $idempotencyKey
  } | ConvertTo-Json -Depth 20
  exit 0
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $runPath) | Out-Null

$startedAt = (Get-Date).ToUniversalTime().ToString("o")
$startedJson = & $emitScript `
  -Event "run.started" `
  -Actor "runtime-router" `
  -Target (Get-RelativePath -Base $rootPath -FullPath $runPath) `
  -CorrelationId $CorrelationId `
  -CausationId $CausationId `
  -IdempotencyKey (Get-Sha256Hex -Text "$idempotencyKey|run.started") `
  -MetaJson (@{ run_id = $runId; agent = $agentName; routing_reason = $route.reason } | ConvertTo-Json -Compress) `
  -Root $rootPath
$startedEvent = $startedJson | ConvertFrom-Json

$agentJson = & $emitScript `
  -Event "agent.invoked" `
  -Actor "runtime-router" `
  -Target $agentName `
  -CorrelationId $CorrelationId `
  -CausationId $startedEvent.id `
  -IdempotencyKey (Get-Sha256Hex -Text "$idempotencyKey|agent.invoked") `
  -MetaJson (@{ run_id = $runId; agent_path = $agent.path; matches = @($route.matches); input_schema = $agent.input_schema; payload = $payload } | ConvertTo-Json -Depth 20 -Compress) `
  -Root $rootPath
$agentEvent = $agentJson | ConvertFrom-Json

$endedAt = (Get-Date).ToUniversalTime().ToString("o")
$endedJson = & $emitScript `
  -Event "run.ended" `
  -Actor "runtime-router" `
  -Target (Get-RelativePath -Base $rootPath -FullPath $runPath) `
  -CorrelationId $CorrelationId `
  -CausationId $agentEvent.id `
  -IdempotencyKey (Get-Sha256Hex -Text "$idempotencyKey|run.ended") `
  -MetaJson (@{ run_id = $runId; agent = $agentName; status = "routed"; output_schema = $agent.output_schema } | ConvertTo-Json -Compress) `
  -Root $rootPath
$endedEvent = $endedJson | ConvertFrom-Json

$runContent = @"
---
schema_version: "1.0.0"
id: $runId
idempotency_key: $idempotencyKey
run_type: single_agent
correlation_id: $CorrelationId
parent_run_id: null
agent: $agentName
status: routed
routing_strategy: keyword
routing_reason: $($route.reason)
routing_matches: [$((@($route.matches) | ForEach-Object { ConvertTo-YamlScalar $_ }) -join ", ")]
started_at: $startedAt
ended_at: $endedAt
retry_count: 0
limits_applied: { max_tokens: $($agent.limits.max_tokens), max_duration_ms: $($agent.limits.max_duration_ms), max_tool_calls: $($agent.limits.max_tool_calls) }
tools_used: [emit_event]
events: [$($startedEvent.id), $($agentEvent.id), $($endedEvent.id)]
input_schema: $($agent.input_schema)
output_schema: $($agent.output_schema)
input_hash: $queryHash
payload_json: $(ConvertTo-YamlScalar $payloadJson)
output_path: null
error: null
---
"@

Set-Content -LiteralPath $runPath -Value $runContent -Encoding UTF8

[pscustomobject]@{
  status = "routed"
  agent = $agentName
  reason = $route.reason
  matches = @($route.matches)
  run_path = (Get-RelativePath -Base $rootPath -FullPath $runPath)
  events = @($startedEvent.id, $agentEvent.id, $endedEvent.id)
  correlation_id = $CorrelationId
  idempotency_key = $idempotencyKey
  payload = $payload
} | ConvertTo-Json -Depth 20
