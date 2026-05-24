param(
  [string]$RepoPath = (Resolve-Path ".").Path,
  [switch]$Json,
  [switch]$ReportOnly,
  [switch]$PushReport
)

$ErrorActionPreference = "Stop"
$now = Get-Date
$staleDays = 30
$lockHours = 24

function Get-WorktreeInfo {
  param([string]$Path, [string]$Branch, [string]$Head)
  $info = [ordered]@{
    path = $Path
    branch = $Branch
    head = $Head
    is_main = ($Branch -eq 'refs/heads/master' -or $Branch -eq 'refs/heads/main')
    last_commit_date = $null
    days_since_last_commit = $null
    uncommitted_files = @()
    uncommitted_count = 0
    has_uncommitted = $false
    has_lock = $false
    is_stale = $false
    lock_reason = $null
  }

  $sha = $Head
  if ($sha -and $sha.Length -ge 7) {
    $commitDate = git -C $RepoPath log -1 --format="%ct" $sha 2>$null
    if ($commitDate) {
      $epoch = [long]$commitDate
      $dt = (Get-Date "1970-01-01 00:00:00Z").AddSeconds($epoch)
      $info.last_commit_date = $dt.ToString("o")
      $info.days_since_last_commit = [math]::Floor(($now - $dt).TotalDays)
      $info.is_stale = $info.days_since_last_commit -gt $staleDays
    }
  }

  if (-not $info.is_main -and (Test-Path -LiteralPath $Path)) {
    $status = git -C $Path status --porcelain 2>$null
    if ($status) {
      $files = @($status | ForEach-Object {
        $line = $_.Trim()
        $idx = if ($line.Length -gt 3) { 3 } else { $line.Length }
        $line.Substring($idx)
      })
      $info.uncommitted_files = $files
      $info.uncommitted_count = $files.Count
      $info.has_uncommitted = $files.Count -gt 0

      if ($info.last_commit_date) {
        $hoursSinceCommit = ($now - $dt).TotalHours
        if ($files.Count -gt 0 -and $hoursSinceCommit -gt $lockHours) {
          $info.has_lock = $true
          $info.lock_reason = "$($files.Count) uncommitted file(s) for $([math]::Floor($hoursSinceCommit))h since last commit"
        }
      }
    }
  }

  return $info
}

$wtLines = git worktree list --porcelain 2>$null
$worktrees = @()
$current = @{}

foreach ($line in $wtLines) {
  if ($line -match '^worktree (.+)$') {
    if ($current.Count -gt 0) {
      $worktrees += Get-WorktreeInfo @current
    }
    $current = @{ Path = $matches[1] }
  }
  elseif ($line -match '^HEAD (.+)$') { $current.Head = $matches[1] }
  elseif ($line -match '^branch (.+)$') { $current.Branch = $matches[1] }
}
if ($current.Count -gt 0) {
  $worktrees += Get-WorktreeInfo @current
}

$report = [ordered]@{
  timestamp = $now.ToString("o")
  repo_path = $RepoPath
  total_worktrees = $worktrees.Count
  stale_count = @($worktrees | Where-Object { $_.is_stale }).Count
  lock_count = @($worktrees | Where-Object { $_.has_lock }).Count
  uncommitted_count = @($worktrees | Where-Object { $_.has_uncommitted -and -not $_.is_main }).Count
  worktrees = $worktrees
}

if ($Json) {
  $report | ConvertTo-Json -Depth 10
}
else {
  Write-Host "`n=== Worktree Inspection Report ===" -ForegroundColor Cyan
  Write-Host "Repo: $RepoPath"
  Write-Host "Scanned: $(Get-Date $now -Format 'yyyy-MM-dd HH:mm:ss UTC')`n"

  Write-Host "Summary:" -ForegroundColor Yellow
  Write-Host "  Total worktrees : $($worktrees.Count)"
  $staleColor = if ($report.stale_count -gt 0) { "Red" } else { "Green" }
  Write-Host "  Stale (>${staleDays}d) : $($report.stale_count)" -ForegroundColor $staleColor
  $lockColor = if ($report.lock_count -gt 0) { "Red" } else { "Green" }
  Write-Host "  Locked files    : $($report.lock_count)" -ForegroundColor $lockColor
  Write-Host "  Uncommitted     : $($report.uncommitted_count)`n"

  foreach ($wt in $worktrees) {
    $branchShort = $wt.branch -replace '^refs/heads/', ''
    $icon = if ($wt.is_main) { '★' } elseif ($wt.is_stale) { '⚠' } else { '✓' }
    Write-Host "$icon $branchShort" -ForegroundColor $(if ($wt.is_main) { "Green" } elseif ($wt.is_stale) { "Red" } else { "White" })
    Write-Host "    Path: $($wt.path)"
    Write-Host "    HEAD: $($wt.head.Substring(0, 7))"
    if ($wt.last_commit_date) {
      Write-Host "    Last commit: $($wt.days_since_last_commit) days ago"
    }
    if ($wt.has_uncommitted) {
      Write-Host "    Uncommitted: $($wt.uncommitted_count) file(s)" -ForegroundColor Yellow
      foreach ($f in $wt.uncommitted_files) { Write-Host "      - $f" }
    }
    if ($wt.has_lock) {
      Write-Host "    LOCKED: $($wt.lock_reason)" -ForegroundColor Red
    }
    Write-Host ""
  }
}

if (-not $ReportOnly) {
  $reportDir = Join-Path $RepoPath "runtime/reports"
  New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
  $reportFile = Join-Path $reportDir "worktree-status.json"
  $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $reportFile -Encoding UTF8
  Write-Host "Report saved to: $reportFile" -ForegroundColor Gray
}

if ($PushReport) {
  $supabaseUrl = $env:SUPABASE_URL
  $supabaseKey = $env:SUPABASE_SERVICE_ROLE_KEY
  if (-not $supabaseUrl -or -not $supabaseKey) {
    Write-Warning "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set. Skipping push."
  }
  else {
    $pushBody = @{ report = $report } | ConvertTo-Json -Depth 10
    $headers = @{
      "Content-Type" = "application/json"
      "Authorization" = "Bearer $supabaseKey"
    }
    try {
      $pushUrl = "$supabaseUrl/functions/v1/worktree-status"
      $result = Invoke-RestMethod -Uri $pushUrl -Method Post -Headers $headers -Body $pushBody -ContentType "application/json" -TimeoutSec 15
      Write-Host "Report pushed to $pushUrl (id: $($result.id))" -ForegroundColor Green
    }
    catch {
      Write-Warning "Failed to push report: $_"
    }
  }
}
