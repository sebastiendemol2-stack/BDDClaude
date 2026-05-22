param(
  [string]$Root = (Resolve-Path ".").Path
)

$ErrorActionPreference = "Stop"

$directories = @(
  "tools/mcp-servers",
  "tools/scripts",
  "tools/prompts",
  "tools/snippets",
  "tools/schemas/input",
  "tools/schemas/output",
  "tools/schemas/events",
  "tools/schemas/errors",
  "agents",
  "capabilities",
  "reflection/decisions",
  "reflection/patterns",
  "reflection/lessons-learned",
  "reflection/references",
  "context/projects",
  "context/sessions/2026/05",
  "context/_drafts",
  "runtime/events",
  "runtime/runs",
  "runtime/locks",
  "runtime/snapshots",
  "runtime/scheduler",
  "runtime/scheduler/dags",
  "runtime/queue/pending",
  "runtime/queue/processing",
  "runtime/queue/done",
  "runtime/queue/dead-letter",
  "runtime/context",
  "runtime/index"
)

foreach ($dir in $directories) {
  $path = Join-Path $Root $dir
  New-Item -ItemType Directory -Force -Path $path | Out-Null
}

$runtimeKeepDirs = @(
  "runtime/events",
  "runtime/runs",
  "runtime/locks",
  "runtime/snapshots",
  "runtime/scheduler",
  "runtime/scheduler/dags",
  "runtime/queue/pending",
  "runtime/queue/processing",
  "runtime/queue/done",
  "runtime/queue/dead-letter",
  "runtime/context",
  "runtime/index"
)

foreach ($dir in $runtimeKeepDirs) {
  $keep = Join-Path (Join-Path $Root $dir) ".gitkeep"
  if (-not (Test-Path -LiteralPath $keep)) {
    New-Item -ItemType File -Path $keep | Out-Null
  }
}

Write-Host "P0 scaffold ensured at $Root"
