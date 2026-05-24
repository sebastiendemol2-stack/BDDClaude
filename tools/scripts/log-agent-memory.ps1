param(
  [Parameter(Mandatory = $true)][string]$RunId,
  [Parameter(Mandatory = $true)][string]$AgentName,
  [Parameter(Mandatory = $true)][string]$Query,
  [Parameter(Mandatory = $true)][string]$CorrelationId,
  [string]$Status = "routed",
  [string]$Root = (Resolve-Path ".").Path
)

$ErrorActionPreference = "Continue"

$supabaseUrl = $env:SUPABASE_URL
$supabaseKey = $env:SUPABASE_SERVICE_ROLE_KEY

if (-not $supabaseUrl -or -not $supabaseKey) {
  Write-Warning "log-agent-memory: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set. Skipping."
  exit 0
}

$memoriesUrl = "$supabaseUrl/functions/v1/memories-store"
$feedbackUrl = "$supabaseUrl/functions/v1/feedback-collect"
$headers = @{
  "Content-Type" = "application/json"
  "Authorization" = "Bearer $supabaseKey"
}

$timestamp = (Get-Date).ToUniversalTime().ToString("o")

$memoryBody = @{
  session_id = $RunId
  project_slug = "bddclaude"
  summary = "Agent [$AgentName] dispatched: $Query"
  decisions = @()
  patterns = @("agent-dispatch", "pilot-integration")
} | ConvertTo-Json -Compress

try {
  $memResult = Invoke-RestMethod -Uri $memoriesUrl -Method Post -Headers $headers -Body $memoryBody -ContentType "application/json" -TimeoutSec 10
  $memoryId = $memResult.id
  Write-Verbose "log-agent-memory: stored memory $memoryId for run $RunId"
}
catch {
  Write-Warning "log-agent-memory: memories-store failed: $_"
  $memoryId = $null
}

if ($memoryId) {
  $feedbackBody = @{
    event_id = $memoryId
    content = "Agent [$AgentName] status: $Status — $Query"
    positive = ($Status -eq "routed" -or $Status -eq "completed")
    source = "runtime"
  } | ConvertTo-Json -Compress

  try {
    $fbResult = Invoke-RestMethod -Uri $feedbackUrl -Method Post -Headers $headers -Body $feedbackBody -ContentType "application/json" -TimeoutSec 10
    Write-Verbose "log-agent-memory: stored feedback $($fbResult.id)"
  }
  catch {
    Write-Warning "log-agent-memory: feedback-collect failed: $_"
  }
}
