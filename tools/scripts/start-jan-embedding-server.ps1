param(
  [string]$HostName = "127.0.0.1",
  [int]$Port = 1338,
  [string]$ModelName = "sentence-transformer-mini",
  [string]$ApiKey = $(if ($env:JAN_EMBED_API_KEY) { $env:JAN_EMBED_API_KEY } elseif ($env:JAN_API_KEY) { $env:JAN_API_KEY } else { "secret-key-123" }),
  [string]$JanDataPath = (Join-Path $env:APPDATA "Jan\data"),
  [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"

function Resolve-LlamaServer {
  param([Parameter(Mandatory = $true)][string]$DataPath)

  $backendRoot = Join-Path $DataPath "llamacpp\backends"
  if (-not (Test-Path -LiteralPath $backendRoot)) {
    throw "Jan llama.cpp backend directory not found: $backendRoot"
  }

  $server = Get-ChildItem -LiteralPath $backendRoot -Recurse -Filter "llama-server.exe" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

  if (-not $server) {
    throw "llama-server.exe not found under: $backendRoot"
  }

  return $server.FullName
}

function Resolve-EmbeddingModel {
  param(
    [Parameter(Mandatory = $true)][string]$DataPath,
    [Parameter(Mandatory = $true)][string]$Name
  )

  $modelPath = Join-Path $DataPath "llamacpp\models\$Name\model.gguf"
  if (-not (Test-Path -LiteralPath $modelPath)) {
    throw "Embedding model not found: $modelPath"
  }

  return $modelPath
}

function Test-EmbeddingEndpoint {
  param(
    [Parameter(Mandatory = $true)][string]$BaseUrl,
    [Parameter(Mandatory = $true)][string]$Token,
    [Parameter(Mandatory = $true)][string]$Name
  )

  $body = @{ model = $Name; input = "local embedding smoke test" } | ConvertTo-Json -Compress
  $response = Invoke-RestMethod `
    -Method Post `
    -Uri "$BaseUrl/v1/embeddings" `
    -Headers @{ Authorization = "Bearer $Token"; "Content-Type" = "application/json" } `
    -Body $body `
    -TimeoutSec 30

  return [int]$response.data[0].embedding.Count
}

$existing = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
  Where-Object { $_.State -eq "Listen" } |
  Select-Object -First 1

$baseUrl = "http://$HostName`:$Port"

if ($existing) {
  $dimension = if ($SkipSmoke) { $null } else {
    Test-EmbeddingEndpoint -BaseUrl $baseUrl -Token $ApiKey -Name $ModelName
  }

  [pscustomobject]@{
    status = "already_running"
    base_url = $baseUrl
    pid = $existing.OwningProcess
    model = $ModelName
    dimension = $dimension
  } | ConvertTo-Json -Depth 4
  exit 0
}

$serverPath = Resolve-LlamaServer -DataPath $JanDataPath
$modelPath = Resolve-EmbeddingModel -DataPath $JanDataPath -Name $ModelName
$outLog = Join-Path $env:TEMP "jan-embedding-server-$Port.out.log"
$errLog = Join-Path $env:TEMP "jan-embedding-server-$Port.err.log"

$args = @(
  "--embedding",
  "--host", $HostName,
  "--port", $Port.ToString(),
  "--api-key", $ApiKey,
  "--no-ui",
  "--alias", $ModelName,
  "--model", $modelPath,
  "--n-gpu-layers", "100"
)

$process = Start-Process `
  -FilePath $serverPath `
  -ArgumentList $args `
  -WindowStyle Hidden `
  -PassThru `
  -RedirectStandardOutput $outLog `
  -RedirectStandardError $errLog

$deadline = (Get-Date).AddSeconds(20)
do {
  Start-Sleep -Milliseconds 300
  $listener = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq "Listen" } |
    Select-Object -First 1
} while (-not $listener -and (Get-Date) -lt $deadline -and -not $process.HasExited)

if ($process.HasExited) {
  throw "Jan embedding server exited early. See $errLog"
}

if (-not $listener) {
  throw "Jan embedding server did not listen on $baseUrl within 20 seconds. See $errLog"
}

$dimension = if ($SkipSmoke) { $null } else {
  Test-EmbeddingEndpoint -BaseUrl $baseUrl -Token $ApiKey -Name $ModelName
}

[pscustomobject]@{
  status = "started"
  base_url = $baseUrl
  pid = $process.Id
  model = $ModelName
  dimension = $dimension
  stdout = $outLog
  stderr = $errLog
} | ConvertTo-Json -Depth 4
