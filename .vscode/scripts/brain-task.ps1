param(
  [string]$ProjectDir,
  [ValidateSet('prime-save-full', 'prime-only')]
  [string]$Mode = 'prime-save-full',
  [string]$Summary = 'Session VS Code: prime + save full'
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ProjectDir)) {
  $ProjectDir = (Get-Location).Path
}

$OneDriveRoot = $env:OneDrive
if ([string]::IsNullOrWhiteSpace($OneDriveRoot)) {
  $OneDriveRoot = Join-Path $env:USERPROFILE 'OneDrive'
}

$Brain = Join-Path $OneDriveRoot 'Developpement\BDDClaude\_scripts\brain.py'
if (-not (Test-Path $Brain)) {
  throw "brain.py introuvable: $Brain"
}

$env:VAULT_PATH = $ProjectDir

Write-Host "[RUN] prime"
& python $Brain load --dir $ProjectDir
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

if ($Mode -eq 'prime-save-full') {
  Write-Host "[RUN] save full"
  & python $Brain save --dir $ProjectDir --mode full --summary $Summary
  exit $LASTEXITCODE
}
