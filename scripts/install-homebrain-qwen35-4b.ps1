$ErrorActionPreference = 'Stop'

Write-Host 'HomeBrain local AI model setup' -ForegroundColor Cyan

$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaCommand) {
    throw 'Ollama is not installed or is not available in PATH.'
}
$ollamaExe = $ollamaCommand.Source

Write-Host 'Checking Ollama service...'
try {
    $null = & $ollamaExe list
} catch {
    throw 'Ollama is installed but the service is not responding. Start Ollama and run this script again.'
}

$model = 'qwen3.5:4b'
Write-Host "Pulling $model (approximately 3.4 GB)..." -ForegroundColor Yellow
& $ollamaExe pull $model
if ($LASTEXITCODE -ne 0) {
    throw "Failed to pull $model."
}

Write-Host 'Unloading the previous 9B model to free shared GPU memory...'
try {
    # Do not redirect Ollama stderr in Windows PowerShell. Some Ollama Windows
    # builds try to inspect the stderr console mode and fail when it is redirected.
    $stopProcess = Start-Process `
        -FilePath $ollamaExe `
        -ArgumentList @('stop', 'qwen3.5:9b') `
        -NoNewWindow `
        -Wait `
        -PassThru
    if ($stopProcess.ExitCode -ne 0) {
        Write-Warning 'The 9B model was not unloaded automatically. This is harmless if it was not running.'
    }
} catch {
    Write-Warning "Could not unload qwen3.5:9b automatically: $($_.Exception.Message)"
    Write-Warning 'Run this manually if needed: ollama stop qwen3.5:9b'
}

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
$thinking = [string]$response.message.thinking
Write-Host "Model response: $content"

if ($thinking.Trim()) {
    Write-Warning 'Ollama returned a thinking trace even though think=false was requested.'
} else {
    Write-Host 'Thinking disabled: confirmed.' -ForegroundColor Green
}

if ($content -notmatch 'HOMEBRAIN READY') {
    Write-Warning 'The model loaded, but its test response was not exact. HomeBrain can still use it.'
}

Write-Host ''
Write-Host 'Installed models:' -ForegroundColor Cyan
& $ollamaExe list
Write-Host ''
Write-Host 'Qwen 3.5 4B is ready. Restart the Hubitat MCP AI add-on after updating to 0.4.10-alpha.' -ForegroundColor Green
Write-Host 'Keep qwen3.5:9b installed until HomeBrain has been tested. Remove it later with: ollama rm qwen3.5:9b' -ForegroundColor DarkGray
