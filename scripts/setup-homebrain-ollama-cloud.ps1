$ErrorActionPreference = 'Stop'

Write-Host 'HomeBrain Ollama Cloud hybrid setup' -ForegroundColor Cyan

$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaCommand) {
    throw 'Ollama is not installed or is not available in PATH.'
}
$ollamaExe = $ollamaCommand.Source

Write-Host 'Checking the local Ollama service...'
try {
    $installedText = (& $ollamaExe list | Out-String)
} catch {
    throw 'Ollama is installed but the service is not responding. Start Ollama and run this script again.'
}

$localModel = 'qwen3.5:4b'
$cloudModel = 'gemma4:31b-cloud'

if ($installedText -notmatch [regex]::Escape($localModel)) {
    Write-Host "Local fallback $localModel is missing; downloading it now..." -ForegroundColor Yellow
    & $ollamaExe pull $localModel
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to pull the local fallback model $localModel."
    }
} else {
    Write-Host "Local fallback present: $localModel" -ForegroundColor Green
}

Write-Host "Registering Ollama Cloud model $cloudModel..." -ForegroundColor Yellow
& $ollamaExe pull $cloudModel
if ($LASTEXITCODE -ne 0) {
    throw @"
Could not register $cloudModel.
Sign in to the Ollama Windows app, or run: ollama signin
Then run this script again. Do not paste an Ollama API key into Home Assistant.
"@
}

Write-Host 'Running a short Cloud response test...' -ForegroundColor Yellow
$body = @{
    model = $cloudModel
    stream = $false
    think = $false
    messages = @(
        @{
            role = 'user'
            content = 'Reply with exactly: HOMEBRAIN CLOUD READY'
        }
    )
    options = @{
        num_ctx = 1024
        num_predict = 24
        temperature = 0
    }
} | ConvertTo-Json -Depth 8

try {
    $response = Invoke-RestMethod `
        -Uri 'http://localhost:11434/api/chat' `
        -Method Post `
        -ContentType 'application/json' `
        -Body $body `
        -TimeoutSec 60
} catch {
    throw @"
The cloud model was registered but its test request failed: $($_.Exception.Message)
Confirm the PC has internet access and Ollama is signed in. Free-plan usage limits may also temporarily block Cloud; HomeBrain will still use $localModel locally.
"@
}

$content = [string]$response.message.content
$thinking = [string]$response.message.thinking
Write-Host "Cloud response: $content"

if ($thinking.Trim()) {
    Write-Warning 'Ollama returned a thinking trace even though think=false was requested.'
} else {
    Write-Host 'Thinking disabled: confirmed.' -ForegroundColor Green
}

if ($content -notmatch 'HOMEBRAIN CLOUD READY') {
    Write-Warning 'The Cloud model responded, but its test wording was not exact. HomeBrain can still use it.'
}

Write-Host ''
Write-Host 'Installed and registered models:' -ForegroundColor Cyan
& $ollamaExe list
Write-Host ''
Write-Host 'Agent-First Control is ready:' -ForegroundColor Green
Write-Host "  Fast exact controls: deterministic Python + Hubitat MCP"
Write-Host "  Natural control interpretation: $localModel"
Write-Host "  Subjective lighting goals and strong fallback: $cloudModel"
Write-Host 'Update and restart Hubitat MCP AI 0.10.17.'
