param(
  [Parameter(Mandatory = $true)]
  [string]$Query,

  [datetime]$DueAt = (Get-Date).ToUniversalTime(),
  [int]$MaxAttempts = 1,
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
  $resolvedFullPath = if (Test-Path -LiteralPath $FullPath) {
    (Resolve-Path -LiteralPath $FullPath).Path
  }
  else {
    [System.IO.Path]::GetFullPath($FullPath)
  }
  $pathUri = [System.Uri]$resolvedFullPath
  return [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($pathUri).ToString()).Replace('/', '\')
}

function Test-QueueIdempotencyKey {
  param(
    [Parameter(Mandatory = $true)][string]$RootPath,
    [Parameter(Mandatory = $true)][string]$Key
  )
  $queueRoot = Join-Path $RootPath "runtime/queue"
  if (-not (Test-Path -LiteralPath $queueRoot)) {
    return $false
  }

  foreach ($file in Get-ChildItem -LiteralPath $queueRoot -Recurse -Filter "*.json" -File -ErrorAction SilentlyContinue) {
    try {
      $item = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
      if ($item.idempotency_key -eq $Key) {
        return $true
      }
    }
    catch {
      continue
    }
  }

  return $false
}

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$manifestPath = Join-Path $rootPath "runtime.manifest.json"
$registryPath = Join-Path $rootPath "tools/registry.json"
$emitScript = Join-Path $rootPath "tools/scripts/emit-event.ps1"

if (-not (Test-Path -LiteralPath $manifestPath)) {
  throw "Enqueue refused: missing runtime.manifest.json"
}
if (-not (Test-Path -LiteralPath $registryPath)) {
  throw "Enqueue refused: missing tools/registry.json"
}
if (-not (Test-Path -LiteralPath $emitScript)) {
  throw "Enqueue refused: missing tools/scripts/emit-event.ps1"
}
if ($MaxAttempts -lt 1 -or $MaxAttempts -gt 5) {
  throw "Enqueue refused: MaxAttempts must be between 1 and 5"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$registry = Get-Content -LiteralPath $registryPath -Raw | ConvertFrom-Json

if ($manifest.features.scheduler -ne "phase_2_local_queue") {
  throw "Enqueue refused: scheduler feature is not phase_2_local_queue"
}
if (-not $registry.tools.enqueue_run -or $registry.tools.enqueue_run.trust_level -ne "safe_write") {
  throw "Enqueue refused: enqueue_run must be registered as safe_write"
}

$dueUtc = $DueAt.ToUniversalTime()
$createdAt = (Get-Date).ToUniversalTime()
$queueId = [guid]::NewGuid().ToString()
$queryHash = Get-Sha256Hex -Text $Query
$idempotencyKey = Get-Sha256Hex -Text "enqueue_run|$queryHash|$($dueUtc.ToString("o"))|$CorrelationId"

if (Test-QueueIdempotencyKey -RootPath $rootPath -Key $idempotencyKey) {
  throw "Enqueue refused: idempotency_key already exists"
}

$pendingDir = Join-Path $rootPath "runtime/queue/pending"
New-Item -ItemType Directory -Force -Path $pendingDir | Out-Null

$fileStamp = $dueUtc.ToString("yyyyMMddTHHmmssZ")
$queuePath = Join-Path $pendingDir "$fileStamp-$queueId.json"
$relativePath = Get-RelativePath -Base $rootPath -FullPath $queuePath

$item = [ordered]@{
  schema_version = "1.0.0"
  id = $queueId
  status = "queued"
  query = $Query
  query_hash = $queryHash
  due_at = $dueUtc.ToString("o")
  created_at = $createdAt.ToString("o")
  started_at = $null
  completed_at = $null
  correlation_id = $CorrelationId
  causation_id = $CausationId
  attempts = 0
  max_attempts = $MaxAttempts
  processor = "invoke-agent"
  idempotency_key = $idempotencyKey
  run_path = $null
  events = @()
  error = $null
}

Set-Content -LiteralPath $queuePath -Value ($item | ConvertTo-Json -Depth 20) -Encoding UTF8

$eventJson = & $emitScript `
  -Event "tool.called" `
  -Actor "scheduler" `
  -Target $relativePath `
  -CorrelationId $CorrelationId `
  -CausationId $CausationId `
  -IdempotencyKey (Get-Sha256Hex -Text "$idempotencyKey|tool.called|enqueue") `
  -MetaJson (@{ tool = "enqueue_run"; queue_id = $queueId; due_at = $dueUtc.ToString("o") } | ConvertTo-Json -Compress) `
  -Root $rootPath
$event = $eventJson | ConvertFrom-Json

[pscustomobject]@{
  status = "queued"
  id = $queueId
  path = $relativePath
  due_at = $dueUtc.ToString("o")
  event_id = $event.id
  correlation_id = $CorrelationId
  idempotency_key = $idempotencyKey
} | ConvertTo-Json -Depth 10
