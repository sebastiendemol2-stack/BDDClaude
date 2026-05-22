param(
  [string]$Root = (Resolve-Path ".").Path,
  [switch]$Strict
)

# Verifies BDDClaude Cognitive Runtime integrity:
#   (a) Event bus hash chain
#   (b) Run state machine status validity
#   (c) Knowledge/Execution boundary (no .md/.json directly under runtime/)
#   (d) Registry agent path consistency
#
# Cross-month continuity: each YYYY-MM.jsonl is an independent chain.
# First event of a new month has prev_hash: null by design.

$ErrorActionPreference = "Stop"

function Get-Sha256Hex {
  param([string]$Text)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    return (($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString("x2") }) -join "")
  }
  finally { $sha.Dispose() }
}

function ConvertTo-CompactJson {
  param($Value)
  return ($Value | ConvertTo-Json -Depth 20 -Compress)
}

$pass = 0; $fail = 0; $warn = 0

function Check-OK   { param($msg) Write-Host "[OK]   $msg"; $script:pass++ }
function Check-FAIL { param($msg) Write-Host "[FAIL] $msg"; $script:fail++ }
function Check-WARN { param($msg) Write-Host "[WARN] $msg"; $script:warn++ }

# ── 1. Event bus hash chain ──────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Event bus ==="
$eventsDir = Join-Path $Root "runtime\events"
$eventFiles = Get-ChildItem $eventsDir -Filter "*.jsonl" -ErrorAction SilentlyContinue | Sort-Object Name

if (-not $eventFiles) {
  Check-WARN "No event files found in runtime/events/"
} else {
  foreach ($file in $eventFiles) {
    $lines = Get-Content -LiteralPath $file.FullName | Where-Object { $_.Trim().Length -gt 0 }
    if (-not $lines) { Check-WARN "$($file.Name): empty"; continue }

    $prevHash = $null
    $lineNum = 0
    $chainOk = $true

    foreach ($line in $lines) {
      $lineNum++
      try {
        $ev = $line | ConvertFrom-Json
      } catch {
        Check-FAIL "$($file.Name) line $($lineNum): invalid JSON"
        $chainOk = $false; continue
      }

      # Recompute hash from payload minus the hash field
      $payload = [ordered]@{}
      foreach ($prop in $ev.PSObject.Properties) {
        if ($prop.Name -ne "hash") { $payload[$prop.Name] = $prop.Value }
      }
      $expectedHash = Get-Sha256Hex -Text (ConvertTo-CompactJson $payload)

      if ($ev.hash -ne $expectedHash) {
        Check-FAIL "$($file.Name) line $($lineNum) id=$($ev.id): hash mismatch"
        $chainOk = $false
      }

      if ($lineNum -gt 1 -and $ev.prev_hash -ne $prevHash) {
        Check-FAIL "$($file.Name) line $($lineNum) id=$($ev.id): prev_hash chain break"
        $chainOk = $false
      }

      $prevHash = $ev.hash
    }

    if ($chainOk) {
      Check-OK "$($file.Name): $($lineNum) events, hash chain intact"
    }
  }
}

# ── 2. Run state machine ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Runs ==="
$validStatuses = @("pending","running","completed","failed","timeout","cancelled","retried","routed")
$runsDir = Join-Path $Root "runtime\runs"
$runFiles = Get-ChildItem $runsDir -Filter "*.yaml" -ErrorAction SilentlyContinue

if (-not $runFiles) {
  Check-WARN "No run files in runtime/runs/"
} else {
  $runOk = $true
  foreach ($file in $runFiles) {
    $content = Get-Content -LiteralPath $file.FullName -Raw
    if ($content -match "status:\s*(\S+)") {
      $status = $Matches[1]
      if ($validStatuses -contains $status) {
        $script:pass++
      } else {
        Check-FAIL "$($file.Name): invalid status '$($status)'"
        $runOk = $false
      }
    } else {
      Check-WARN "$($file.Name): no status field"
    }
  }
  if ($runOk) { Check-OK "runtime/runs/: $($runFiles.Count) runs, all status values valid" }
}

# ── 3. Knowledge/Execution boundary ──────────────────────────────────────────
Write-Host ""
Write-Host "=== Boundary ==="
$runtimeRoot = Join-Path $Root "runtime"
# Only direct children (no recursion) — filter by parent path
$runtimeChildren = Get-ChildItem $runtimeRoot -File -ErrorAction SilentlyContinue |
  Where-Object { $_.DirectoryName -eq $runtimeRoot }
$boundary_violations = @($runtimeChildren | Where-Object { $_.Extension -in @(".md", ".json") })

if ($boundary_violations.Count -gt 0) {
  foreach ($v in $boundary_violations) {
    Check-FAIL "Boundary violation: $($v.Name) under runtime/ root"
  }
} else {
  Check-OK "runtime/ root: no knowledge files present"
}

# ── 4. Registry consistency ───────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Registry ==="
$regPath = Join-Path $Root "agents\registry.json"
if (Test-Path $regPath) {
  $registry = Get-Content -LiteralPath $regPath | ConvertFrom-Json
  foreach ($name in $registry.agents.PSObject.Properties.Name) {
    $agentPath = Join-Path $Root $registry.agents.$name.path
    if (Test-Path $agentPath) {
      Check-OK "agent '$($name)' path exists"
    } else {
      Check-FAIL "agent '$($name)' path missing: $($registry.agents.$name.path)"
    }
  }
} else {
  Check-FAIL "agents/registry.json not found"
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== RESULTS: $($pass) passed, $($warn) warnings, $($fail) failed ==="
if ($fail -gt 0 -and $Strict) { exit 1 }
