$ErrorActionPreference = 'Stop'

Write-Host 'HomeBrain local AI model setup' -ForegroundColor Cyan

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw 'Ollama is not installed or is not available in PATH.'
}

Write-Host 'Checking Ollama service...'
try {
    $null = ollama list 2>&1
} catch {
    throw 'Ollama is installed but the service is not responding. Start Ollama and run this script again.'
}

$model = 'qwen3.5:4b'
Write-Host "Pulling $model (approximately 3.4 GB)..." -ForegroundColor Yellow
ollama pull $model
if ($LASTEXITCODE -ne 0) {
    throw "Failed to pull $model."
}

Write-Host 'Unloading the previous 9B model to free shared GPU memory...'
ollama stop qwen3.5:9b 2>$null

Write-Host 'Running a short no-thinking response test...' -ForegroundColor Yellow
$body = @{
    model = $model
    stream = $false
    think = $false
    keep_alive = '30m'
    messages = @(
        @{
            role = 'user'
            content = 'Reply with exactly: HOMEBRAIN READY'
        }
    )
    options = @{
        num_ctx = 2048
        num_predict = 20
        temperature = 0
    }
} | ConvertTo-Json -Depth 8

$response = Invoke-RestMethod `
    -Uri 'http://localhost:11434/api/chat' `
    -Method Post `
    -ContentType 'application/json' `
    -Body $body `
    -TimeoutSec 60

$content = [string]$response.message.content
Write-Host "Model response: $content"

if ($content -notmatch 'HOMEBRAIN READY') {
    Write-Warning 'The model loaded, but its test response was not exact. HomeBrain can still use it.'
}

Write-Host ''
Write-Host 'Installed models:' -ForegroundColor Cyan
ollama list
Write-Host ''
Write-Host 'Qwen 3.5 4B is ready. Restart the Hubitat MCP AI add-on after updating to 0.4.10-alpha.' -ForegroundColor Green
Write-Host 'Keep qwen3.5:9b installed until HomeBrain has been tested. Remove it later with: ollama rm qwen3.5:9b' -ForegroundColor DarkGray
