param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("draft.created", "draft.promoted", "session.closed", "agent.invoked", "tool.called", "tool.failed", "run.started", "run.ended", "reflection.created")]
  [string]$Event,

  [Parameter(Mandatory = $true)]
  [string]$Actor,

  [Parameter(Mandatory = $true)]
  [string]$Target,

  [string]$CorrelationId = ([guid]::NewGuid().ToString()),
  [string]$CausationId = $null,
  [string]$IdempotencyKey = $null,
  [string]$MetaJson = "{}",
  [string]$ErrorJson = $null,
  [string]$Root = (Resolve-Path ".").Path
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

function ConvertTo-CompactJson {
  param([Parameter(Mandatory = $true)]$Value)
  return ($Value | ConvertTo-Json -Depth 20 -Compress)
}

$timestamp = (Get-Date).ToUniversalTime().ToString("o")
$eventDir = Join-Path $Root "runtime/events"
New-Item -ItemType Directory -Force -Path $eventDir | Out-Null
$eventFile = Join-Path $eventDir ((Get-Date).ToUniversalTime().ToString("yyyy-MM") + ".jsonl")

# Idempotency key is deterministic per (actor, event, target, correlation_id) — no timestamp.
# This ensures retries within the same correlation scope are correctly deduplicated
# regardless of minute boundaries.
if (-not $IdempotencyKey) {
  $IdempotencyKey = Get-Sha256Hex -Text "$Actor|$Event|$Target|$CorrelationId"
}

if (Test-Path -LiteralPath $eventFile) {
  $duplicate = Get-Content -LiteralPath $eventFile | Where-Object {
    $_.Trim().Length -gt 0 -and $_ -like "*$IdempotencyKey*"
  } | Select-Object -First 1

  if ($duplicate) {
    Write-Error "Duplicate event refused by idempotency_key: $IdempotencyKey"
  }
}

$prevHash = $null
if (Test-Path -LiteralPath $eventFile) {
  $lastLine = Get-Content -LiteralPath $eventFile | Where-Object { $_.Trim().Length -gt 0 } | Select-Object -Last 1
  if ($lastLine) {
    $prevHash = ($lastLine | ConvertFrom-Json).hash
  }
}

$meta = $MetaJson | ConvertFrom-Json
$errorValue = $null
if ($ErrorJson) {
  $errorValue = $ErrorJson | ConvertFrom-Json
}

$payload = [ordered]@{
  id = [guid]::NewGuid().ToString()
  event_version = "1.0.0"
  idempotency_key = $IdempotencyKey
  correlation_id = $CorrelationId
  causation_id = $CausationId
  event = $Event
  timestamp = $timestamp
  actor = $Actor
  target = $Target
  prev_hash = $prevHash
  error = $errorValue
  meta = $meta
}

$payloadJson = ConvertTo-CompactJson -Value $payload
$payload.hash = Get-Sha256Hex -Text $payloadJson
$line = ConvertTo-CompactJson -Value $payload

Add-Content -LiteralPath $eventFile -Value $line -Encoding UTF8
Write-Output $line
