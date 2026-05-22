param(
  [Parameter(Mandatory = $true)]
  [string]$Path,

  [string]$CorrelationId = ([guid]::NewGuid().ToString()),
  [string]$CausationId = $null,
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

function Get-RelativePath {
  param(
    [Parameter(Mandatory = $true)][string]$Base,
    [Parameter(Mandatory = $true)][string]$FullPath
  )
  $baseUri = [System.Uri]((Resolve-Path -LiteralPath $Base).Path.TrimEnd('\') + '\')
  $pathUri = [System.Uri]((Resolve-Path -LiteralPath $FullPath).Path)
  return [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($pathUri).ToString()).Replace('/', '\')
}

function Test-IdempotencyKey {
  param(
    [Parameter(Mandatory = $true)][string]$EventsDir,
    [Parameter(Mandatory = $true)][string]$Key
  )
  if (-not (Test-Path -LiteralPath $EventsDir)) {
    return $false
  }
  $match = Get-ChildItem -LiteralPath $EventsDir -Filter "*.jsonl" -File -ErrorAction SilentlyContinue |
    ForEach-Object {
      Get-Content -LiteralPath $_.FullName | Where-Object { $_ -like "*$Key*" } | Select-Object -First 1
    } |
    Select-Object -First 1
  return [bool]$match
}

function Test-PromotionTargetAlreadyEmitted {
  param(
    [Parameter(Mandatory = $true)][string]$EventsDir,
    [Parameter(Mandatory = $true)][string]$Target
  )
  if (-not (Test-Path -LiteralPath $EventsDir)) {
    return $false
  }

  foreach ($file in Get-ChildItem -LiteralPath $EventsDir -Filter "*.jsonl" -File -ErrorAction SilentlyContinue) {
    foreach ($line in Get-Content -LiteralPath $file.FullName) {
      if (-not $line.Trim()) {
        continue
      }
      try {
        $event = $line | ConvertFrom-Json
        if ($event.event -eq "draft.promoted" -and $event.target -eq $Target) {
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

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$sourcePath = (Resolve-Path -LiteralPath $Path).Path
$draftRoot = (Resolve-Path -LiteralPath (Join-Path $rootPath "context/_drafts")).Path

if (-not $sourcePath.StartsWith($draftRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Promote refused: source must be under context/_drafts/"
}

$policyPath = Join-Path $rootPath "agents/_policy.yaml"
if (-not (Test-Path -LiteralPath $policyPath)) {
  throw "Promote refused: missing agents/_policy.yaml"
}

$policyText = Get-Content -LiteralPath $policyPath -Raw
if ($policyText -notmatch "draft:\s*\r?\n\s*allowed_transitions:\s*\[review,\s*archived\]") {
  throw "Promote refused: policy does not allow draft -> review"
}
if ($policyText -notmatch "runtime_direct_write_forbidden:\s*true") {
  throw "Promote refused: runtime_direct_write_forbidden is not true"
}

$relativePath = Get-RelativePath -Base $rootPath -FullPath $sourcePath
$eventsDir = Join-Path $rootPath "runtime/events"

if (Test-PromotionTargetAlreadyEmitted -EventsDir $eventsDir -Target $relativePath) {
  throw "Promote refused: idempotency_key already exists"
}

$content = Get-Content -LiteralPath $sourcePath -Raw
if ($content -notmatch "(?s)^---\r?\n(.*?)\r?\n---") {
  throw "Promote refused: missing frontmatter"
}
if ($content -notmatch "(?m)^status:\s*draft\s*$") {
  throw "Promote refused: source status is not draft"
}

$draftHash = Get-Sha256Hex -Text $content
$idempotencyKey = Get-Sha256Hex -Text "promote_draft|$relativePath|$draftHash"

if (Test-IdempotencyKey -EventsDir $eventsDir -Key $idempotencyKey) {
  throw "Promote refused: idempotency_key already exists"
}

$lockDir = Join-Path $rootPath "runtime/locks"
New-Item -ItemType Directory -Force -Path $lockDir | Out-Null
$lockPath = Join-Path $lockDir "promote.lock"
$lockAcquired = $false

try {
  New-Item -ItemType File -Path $lockPath -Value "pid=$PID`npath=$relativePath`ncreated_at=$((Get-Date).ToUniversalTime().ToString("o"))`n" -ErrorAction Stop | Out-Null
  $lockAcquired = $true

  $updated = $content -replace "(?m)^status:\s*draft\s*$", "status: review"
  Set-Content -LiteralPath $sourcePath -Value $updated -Encoding UTF8

  $emitScript = Join-Path $rootPath "tools/scripts/emit-event.ps1"
  $eventJson = & $emitScript `
    -Event "draft.promoted" `
    -Actor "promote-skill" `
    -Target $relativePath `
    -CorrelationId $CorrelationId `
    -CausationId $CausationId `
    -IdempotencyKey $idempotencyKey `
    -MetaJson (@{ transition = "draft->review"; draft_hash = $draftHash } | ConvertTo-Json -Compress) `
    -Root $rootPath

  $event = $eventJson | ConvertFrom-Json
  $runId = [guid]::NewGuid().ToString()
  $startedAt = (Get-Date).ToUniversalTime().ToString("o")
  $runStamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
  $runPath = Join-Path (Join-Path $rootPath "runtime/runs") "$runStamp-promote-$runId.yaml"
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $runPath) | Out-Null

  $runContent = @"
---
schema_version: "1.0.0"
id: $runId
idempotency_key: $idempotencyKey
run_type: single_agent
correlation_id: $CorrelationId
parent_run_id: null
agent: promote
status: completed
started_at: $startedAt
ended_at: $((Get-Date).ToUniversalTime().ToString("o"))
retry_count: 0
limits_applied: { max_tokens: 0, max_duration_ms: 10000 }
tools_used: [emit_event]
events: [$($event.id)]
output_path: $relativePath
error: null
---
"@

  Set-Content -LiteralPath $runPath -Value $runContent -Encoding UTF8

  [pscustomobject]@{
    status = "completed"
    path = $relativePath
    event_id = $event.id
    run_path = (Get-RelativePath -Base $rootPath -FullPath $runPath)
    idempotency_key = $idempotencyKey
  } | ConvertTo-Json -Depth 10
}
finally {
  if ($lockAcquired -and (Test-Path -LiteralPath $lockPath)) {
    Remove-Item -LiteralPath $lockPath -Force
  }
}
