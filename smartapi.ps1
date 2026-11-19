# SmartAPI AI Assistant for AO Intergas Central Asia
# Direct connection via SmartAPI gateway: https://smartapi.pro/v1
# Pure ASCII script - 100% compatible with PowerShell 5.1 and 7+

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Continue'

$ApiKey = 'sk-smart-J6NAKcsgKoJ_tfaOrfapSY14L1W8us5GR4ZZ3FwPIO8'
$BaseUrl = 'https://smartapi.pro/v1'
$CurrentModel = 'gemini-3.8-flash'

[System.Environment]::SetEnvironmentVariable('SMARTAPI_KEY', $ApiKey, 'User')
$env:SMARTAPI_KEY = $ApiKey

Write-Host ''
Write-Host '========================================================================' -ForegroundColor Cyan
Write-Host ' CONNECTED TO SMARTAPI // AO INTERGAS CENTRAL ASIA' -ForegroundColor Cyan
Write-Host ' Gateway: https://smartapi.pro/v1 | Model: gemini-3.8-flash' -ForegroundColor DarkGray
Write-Host '========================================================================' -ForegroundColor Cyan
Write-Host ''

# 1. Target directory
$DesktopDir = [Environment]::GetFolderPath('Desktop')
$TargetDir = Join-Path $DesktopDir 'QRcode'
$EnvFilePath = Join-Path $TargetDir '.env'

if (-not (Test-Path $TargetDir)) {
    Write-Host '[*] Downloading project from GitHub to Desktop\QRcode...' -ForegroundColor Yellow
    $zipUrl = 'https://github.com/tagiriskaliev18-hash/intergas-equip-qr/archive/refs/heads/main.zip'
    $tempZip = Join-Path $env:TEMP 'intergas-smart.zip'
    $tempExtract = Join-Path $env:TEMP 'intergas-smart-extract'

    try {
        Invoke-WebRequest -Uri $zipUrl -OutFile $tempZip -UseBasicParsing
        if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
        Expand-Archive -Path $tempZip -DestinationPath $tempExtract -Force
        $inner = Join-Path $tempExtract 'intergas-equip-qr-main'
        New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
        Copy-Item -Path ($inner + '\*') -Destination $TargetDir -Recurse -Force
        Remove-Item $tempZip -Force -ErrorAction SilentlyContinue
        Remove-Item $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host ('[+] Project successfully loaded into ' + $TargetDir) -ForegroundColor Green
    } catch {
        Write-Host ('[!] Download warning: ' + $_.Exception.Message) -ForegroundColor DarkYellow
    }
}

if (-not (Test-Path $EnvFilePath)) {
    $exampleEnv = Join-Path $TargetDir '.env.ad.example'
    if (Test-Path $exampleEnv) {
        Copy-Item $exampleEnv $EnvFilePath -Force
    }
}

# 2. Load system context
$systemPrompt = 'You are the leading AI engineer for AO Intergas Central Asia. Always answer in Russian. Configuration file path on this computer: ' + $EnvFilePath + '. User can open and edit it via command: notepad ' + $EnvFilePath + '. In that file user configures AD_BIND_DN and AD_BIND_PASSWORD. NEVER output pseudo-tools, bash calls, or XML/DSML tags. Answer strictly in clean Russian text.'

$geminiMdPath = Join-Path $TargetDir 'GEMINI.md'
if (Test-Path $geminiMdPath) {
    try {
        $bytes = [System.IO.File]::ReadAllBytes($geminiMdPath)
        $systemPrompt = $systemPrompt + '

' + [System.Text.Encoding]::UTF8.GetString($bytes)
        Write-Host '[+] Knowledge base (GEMINI.md) successfully loaded into memory!' -ForegroundColor Green
    } catch {}
}

# 3. SmartAPI call function
function Invoke-SmartApiChat {
    param (
        [array]$Messages,
        [string]$ModelName = $CurrentModel
    )

    $bodyObj = @{
        model = $ModelName
        messages = $Messages
        max_tokens = 2048
        temperature = 0.5
    }
    $bodyJson = $bodyObj | ConvertTo-Json -Depth 6
    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyJson)

    $headers = @{
        'Authorization' = ('Bearer ' + $ApiKey)
        'Content-Type'  = 'application/json; charset=utf-8'
    }

    try {
        $res = Invoke-RestMethod -Uri ($BaseUrl + '/chat/completions') -Method Post -Headers $headers -Body $bodyBytes -TimeoutSec 60
        $rawText = $res.choices[0].message.content
        if ($rawText -like '*DSML*' -or $rawText -like '*<|*') {
            return ('Config file path: ' + $EnvFilePath + '. Run command: notepad ' + $EnvFilePath)
        }
        return $rawText
    } catch {
        return ('[SmartAPI Error]: ' + $_.Exception.Message)
    }
}

# 4. Check connection
Write-Host ('[*] Testing connection to ' + $CurrentModel + ' via SmartAPI...') -ForegroundColor Yellow
$testMsgs = @(
    @{ role = 'user'; content = 'Confirm connection and state readiness in Russian in one sentence.' }
)
$testResp = Invoke-SmartApiChat -Messages $testMsgs -ModelName $CurrentModel
Write-Host ('[+] AI Status: ' + $testResp.Trim()) -ForegroundColor Green

Write-Host ''
Write-Host '========================================================================' -ForegroundColor Green
Write-Host ' INTERACTIVE AI ASSISTANT READY // AO INTERGAS CENTRAL ASIA' -ForegroundColor Green
Write-Host (' Project folder: ' + $TargetDir) -ForegroundColor White
Write-Host (' Env config:     ' + $EnvFilePath) -ForegroundColor Cyan
Write-Host '========================================================================' -ForegroundColor Green
Write-Host 'Commands: /env (open .env in notepad) | /model name | /clear | exit' -ForegroundColor DarkGray
Write-Host ''

$history = @(
    @{ role = 'system'; content = $systemPrompt }
)

while ($true) {
    Write-Host 'You > ' -NoNewline -ForegroundColor Cyan
    $userInput = Read-Host

    if (-not $userInput -or -not $userInput.Trim()) { continue }

    if ($userInput -in @('exit', 'quit', 'q', '/exit', '/quit')) {
        Write-Host 'Session closed.' -ForegroundColor Yellow
        break
    }

    if ($userInput -eq '/clear') {
        $history = @( @{ role = 'system'; content = $systemPrompt } )
        Write-Host '[+] Dialog history cleared.' -ForegroundColor Green
        continue
    }

    if ($userInput -eq '/env') {
        Write-Host ('[*] Opening ' + $EnvFilePath + ' in Notepad...') -ForegroundColor Yellow
        notepad $EnvFilePath
        continue
    }

    if ($userInput.StartsWith('/model')) {
        $parts = $userInput.Split(' ', 2)
        if ($parts.Length -gt 1 -and $parts[1].Trim()) {
            $CurrentModel = $parts[1].Trim()
            Write-Host ('[+] Switched model to: ' + $CurrentModel) -ForegroundColor Green
        } else {
            Write-Host ('Current model: ' + $CurrentModel) -ForegroundColor DarkYellow
            Write-Host 'Models: gemini-3.8-flash, claude-opus-5-5, deepseek-v4-pro' -ForegroundColor DarkGray
        }
        continue
    }

    $history += @{ role = 'user'; content = $userInput }
    Write-Host 'Thinking...' -ForegroundColor DarkMagenta

    $reply = Invoke-SmartApiChat -Messages $history -ModelName $CurrentModel
    Write-Host ''
    Write-Host 'Engineer:' -ForegroundColor Green
    Write-Host $reply -ForegroundColor White
    Write-Host ''

    $history += @{ role = 'assistant'; content = $reply }
}
