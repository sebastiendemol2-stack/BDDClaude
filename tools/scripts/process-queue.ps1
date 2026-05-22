param(
  [int]$Limit = 5,
  [string]$QueueId = $null,
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

function Add-OrSetProperty {
  param(
    [Parameter(Mandatory = $true)]$Object,
    [Parameter(Mandatory = $true)][string]$Name,
    [AllowNull()]$Value
  )
  $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value -Force
}

function Read-QueueItem {
  param([Parameter(Mandatory = $true)][string]$Path)
  $item = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
  return [pscustomobject]@{
    path = $Path
    item = $item
    due_at = [datetime]$item.due_at
  }
}

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$manifestPath = Join-Path $rootPath "runtime.manifest.json"
$registryPath = Join-Path $rootPath "tools/registry.json"
$emitScript = Join-Path $rootPath "tools/scripts/emit-event.ps1"
$invokeScript = Join-Path $rootPath "tools/scripts/invoke-agent.ps1"

if ($Limit -lt 1 -or $Limit -gt 100) {
  throw "Process refused: Limit must be between 1 and 100"
}
foreach ($requiredPath in @($manifestPath, $registryPath, $emitScript, $invokeScript)) {
  if (-not (Test-Path -LiteralPath $requiredPath)) {
    throw "Process refused: missing $requiredPath"
  }
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$registry = Get-Content -LiteralPath $registryPath -Raw | ConvertFrom-Json

if ($manifest.features.scheduler -ne "phase_2_local_queue") {
  throw "Process refused: scheduler feature is not phase_2_local_queue"
}
if (-not $registry.tools.process_queue -or $registry.tools.process_queue.trust_level -ne "safe_write") {
  throw "Process refused: process_queue must be registered as safe_write"
}

$pendingDir = Join-Path $rootPath "runtime/queue/pending"
$processingDir = Join-Path $rootPath "runtime/queue/processing"
$doneDir = Join-Path $rootPath "runtime/queue/done"
$deadDir = Join-Path $rootPath "runtime/queue/dead-letter"
foreach ($dir in @($pendingDir, $processingDir, $doneDir, $deadDir)) {
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

$nowUtc = (Get-Date).ToUniversalTime()
$pending = @()
foreach ($file in Get-ChildItem -LiteralPath $pendingDir -Filter "*.json" -File -ErrorAction SilentlyContinue) {
  try {
    $candidate = Read-QueueItem -Path $file.FullName
    if ($QueueId -and $candidate.item.id -ne $QueueId) {
      continue
    }
    if ($candidate.due_at.ToUniversalTime() -le $nowUtc) {
      $pending += $candidate
    }
  }
  catch {
    continue
  }
}

$selected = @($pending | Sort-Object -Property due_at, path | Select-Object -First $Limit)

if ($DryRun) {
  [pscustomobject]@{
    status = "dry_run"
    due_count = $selected.Count
    queue_ids = @($selected | ForEach-Object { $_.item.id })
    paths = @($selected | ForEach-Object { Get-RelativePath -Base $rootPath -FullPath $_.path })
  } | ConvertTo-Json -Depth 10
  exit 0
}

$lockDir = Join-Path $rootPath "runtime/locks"
New-Item -ItemType Directory -Force -Path $lockDir | Out-Null
$lockPath = Join-Path $lockDir "queue.lock"
$lockAcquired = $false
$results = @()

try {
  New-Item -ItemType File -Path $lockPath -Value "pid=$PID`ncreated_at=$($nowUtc.ToString("o"))`n" -ErrorAction Stop | Out-Null
  $lockAcquired = $true

  foreach ($candidate in $selected) {
    $item = $candidate.item
    $sourcePath = $candidate.path
    $processingPath = Join-Path $processingDir (Split-Path -Leaf $sourcePath)
    $finalPath = $null

    try {
      Move-Item -LiteralPath $sourcePath -Destination $processingPath -Force
      Add-OrSetProperty -Object $item -Name "status" -Value "processing"
      Add-OrSetProperty -Object $item -Name "started_at" -Value ((Get-Date).ToUniversalTime().ToString("o"))
      Add-OrSetProperty -Object $item -Name "attempts" -Value ([int]$item.attempts + 1)
      Set-Content -LiteralPath $processingPath -Value ($item | ConvertTo-Json -Depth 20) -Encoding UTF8

      $processEventJson = & $emitScript `
        -Event "tool.called" `
        -Actor "scheduler" `
        -Target (Get-RelativePath -Base $rootPath -FullPath $processingPath) `
        -CorrelationId $item.correlation_id `
        -CausationId $item.causation_id `
        -IdempotencyKey (Get-Sha256Hex -Text "$($item.idempotency_key)|tool.called|process|$($item.attempts)") `
        -MetaJson (@{ tool = "process_queue"; queue_id = $item.id; attempt = $item.attempts } | ConvertTo-Json -Compress) `
        -Root $rootPath
      $processEvent = $processEventJson | ConvertFrom-Json

      $invokeJson = & $invokeScript `
        -Root $rootPath `
        -Query $item.query `
        -CorrelationId $item.correlation_id `
        -CausationId $processEvent.id
      $invoke = $invokeJson | ConvertFrom-Json

      Add-OrSetProperty -Object $item -Name "status" -Value "completed"
      Add-OrSetProperty -Object $item -Name "completed_at" -Value ((Get-Date).ToUniversalTime().ToString("o"))
      Add-OrSetProperty -Object $item -Name "run_path" -Value $invoke.run_path
      $eventIds = @($processEvent.id) + @($invoke.events)
      Add-OrSetProperty -Object $item -Name "events" -Value $eventIds
      Add-OrSetProperty -Object $item -Name "error" -Value $null
      Set-Content -LiteralPath $processingPath -Value ($item | ConvertTo-Json -Depth 20) -Encoding UTF8

      $finalPath = Join-Path $doneDir (Split-Path -Leaf $processingPath)
      Move-Item -LiteralPath $processingPath -Destination $finalPath -Force
      $results += [pscustomobject]@{
        id = $item.id
        status = "completed"
        path = (Get-RelativePath -Base $rootPath -FullPath $finalPath)
        run_path = $invoke.run_path
      }
    }
    catch {
      $message = $_.Exception.Message
      Add-OrSetProperty -Object $item -Name "error" -Value @{ message = $message; at = (Get-Date).ToUniversalTime().ToString("o") }
      $shouldDeadLetter = [int]$item.attempts -ge [int]$item.max_attempts
      Add-OrSetProperty -Object $item -Name "status" -Value ($(if ($shouldDeadLetter) { "dead_letter" } else { "queued" }))

      if (Test-Path -LiteralPath $processingPath) {
        Set-Content -LiteralPath $processingPath -Value ($item | ConvertTo-Json -Depth 20) -Encoding UTF8
        $finalPath = if ($shouldDeadLetter) {
          Join-Path $deadDir (Split-Path -Leaf $processingPath)
        }
        else {
          Join-Path $pendingDir (Split-Path -Leaf $processingPath)
        }
        Move-Item -LiteralPath $processingPath -Destination $finalPath -Force
      }

      $results += [pscustomobject]@{
        id = $item.id
        status = $item.status
        path = $(if ($finalPath) { Get-RelativePath -Base $rootPath -FullPath $finalPath } else { $null })
        error = $message
      }
    }
  }
}
finally {
  if ($lockAcquired -and (Test-Path -LiteralPath $lockPath)) {
    Remove-Item -LiteralPath $lockPath -Force
  }
}

[pscustomobject]@{
  status = "processed"
  processed_count = $results.Count
  results = $results
} | ConvertTo-Json -Depth 20
