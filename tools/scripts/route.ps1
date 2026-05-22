param(
  [Parameter(Mandatory = $true)]
  [string]$Input,

  [string]$Root = (Resolve-Path ".").Path,
  [switch]$Emit
)

# P0 routing: keyword-based, reads agents/registry.json.
# Returns the matched agent name and path, emits a run.started event if -Emit.
# Phase 2 will add embedding scoring; phase 3 will add a meta-agent orchestrator.

$ErrorActionPreference = "Stop"

$registryPath = Join-Path $Root "agents/registry.json"
if (-not (Test-Path $registryPath)) {
  Write-Error "Registry not found: $registryPath"
}

$registry = Get-Content -LiteralPath $registryPath | ConvertFrom-Json
$normalised = $Input.ToLower()

$matched = $null
$matchedKeyword = $null

# Score each agent by number of keyword hits; highest score (then priority) wins.
$scores = @()
foreach ($name in $registry.agents.PSObject.Properties.Name) {
  $agent = $registry.agents.$name
  $hits = @($agent.keywords | Where-Object { $normalised -match [regex]::Escape($_) })
  $scores += [PSCustomObject]@{
    Name     = $name
    Agent    = $agent
    Hits     = $hits.Count
    Keyword  = if ($hits.Count -gt 0) { $hits[0] } else { $null }
    Priority = $agent.priority
  }
}

$winner = $scores |
  Where-Object { $_.Hits -gt 0 } |
  Sort-Object -Property @{ E = 'Hits'; D = $true }, @{ E = 'Priority'; D = $true } |
  Select-Object -First 1

if (-not $winner) {
  # No keyword match — fall through to highest-priority agent as catch-all.
  $winner = $scores | Sort-Object -Property @{ E = 'Priority'; D = $true } | Select-Object -First 1
  $reason = "no_match_default"
} else {
  $reason = "keyword"
  $matchedKeyword = $winner.Keyword
}

$agentName = $winner.Name
$agentPath = Join-Path $Root $winner.Agent.path

$result = [PSCustomObject]@{
  agent         = $agentName
  path          = $winner.Agent.path
  routing_reason = $reason
  matched_keyword = $matchedKeyword
  score         = $winner.Hits
}

Write-Output ($result | ConvertTo-Json -Compress)

if ($Emit) {
  $correlationId = [guid]::NewGuid().ToString()
  $emitScript = Join-Path $Root "tools/scripts/emit-event.ps1"
  & $emitScript `
    -Event "agent.invoked" `
    -Actor "route.ps1" `
    -Target $agentName `
    -CorrelationId $correlationId `
    -MetaJson (@{
      routing_reason  = $reason
      matched_keyword = $matchedKeyword
      input_preview   = ($Input.Substring(0, [Math]::Min(80, $Input.Length)))
    } | ConvertTo-Json -Compress) `
    -Root $Root | Out-Null
}
