param(
  [string]$Summary = "Session closed.",
  [string]$CorrelationId = ([guid]::NewGuid().ToString()),
  [string]$CausationId = $null,
  [string]$Root = (Resolve-Path ".").Path
)

$ErrorActionPreference = "Stop"

$now = Get-Date
$year = $now.ToString("yyyy")
$month = $now.ToString("MM")
$stamp = $now.ToString("yyyy-MM-dd-HHmm")
$sessionDir = Join-Path $Root "context/sessions/$year/$month"
New-Item -ItemType Directory -Force -Path $sessionDir | Out-Null

$sessionId = [guid]::NewGuid().ToString()
$sessionPath = Join-Path $sessionDir "$stamp.md"

if (Test-Path -LiteralPath $sessionPath) {
  $sessionPath = Join-Path $sessionDir ($now.ToString("yyyy-MM-dd-HHmmss") + ".md")
}

$expiresAt = $now.AddDays(30).ToUniversalTime().ToString("o")
$startedAt = $now.ToUniversalTime().ToString("o")

$content = @"
---
schema_version: "1.0.0"
id: $sessionId
status: closed
date: $($now.ToString("yyyy-MM-dd"))
created_at: $startedAt
expires_at: $expiresAt
ttl_days: 30
correlation_id: $CorrelationId
---

# Session $stamp

$Summary
"@

Set-Content -LiteralPath $sessionPath -Value $content -Encoding UTF8

$emitScript = Join-Path $Root "tools/scripts/emit-event.ps1"
& $emitScript `
  -Event "session.closed" `
  -Actor "save-session" `
  -Target ($sessionPath.Replace($Root + [System.IO.Path]::DirectorySeparatorChar, "")) `
  -CorrelationId $CorrelationId `
  -CausationId $CausationId `
  -MetaJson (@{ session_id = $sessionId; ttl_days = 30 } | ConvertTo-Json -Compress) `
  -Root $Root | Out-Null

Write-Output $sessionPath
