# SmartAPI Autonomous AI Agent for AO Intergas Central Asia
# Direct connection via SmartAPI gateway: https://smartapi.pro/v1
# Pure ASCII script - 100% compatible with PowerShell 5.1, 7+, AppLocker

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
Write-Host ' AI-ENGINEER // AO INTERGAS CENTRAL ASIA // SMARTAPI PRO' -ForegroundColor Cyan
Write-Host ' Gateway: https://smartapi.pro/v1 | Model: gemini-3.8-flash' -ForegroundColor DarkGray
Write-Host ' Mode: Native Windows PowerShell (No Python or external .exe needed)' -ForegroundColor Green
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

# 2. Base system prompt (ASCII) + dynamic UTF-8 GEMINI.md
$systemPrompt = 'You are the leading Russian-speaking AI engineer for AO Intergas Central Asia (QazaqGaz).' + "`n" +
'Organization: AO Intergas Central Asia, facilities: LPU, GRS, KS.' + "`n" +
'CORE PRINCIPLE: TOTAL ABSENCE OF PRICES AND CURRENCIES. No tenge, no rubles. Only maintenance schedules, spare parts units, and defect counts.' + "`n" +
'Active Directory configuration file on this PC: ' + $EnvFilePath + "`n" +
'Project workspace folder: ' + $TargetDir + "`n`n" +
'RULES:' + "`n" +
'1. Always answer in clear, professional Russian.' + "`n" +
'2. NEVER output internal DSML tags, bash calls, or pwd/ls.' + "`n" +
'3. The user is in Windows PowerShell on a corporate computer with AppLocker (no external .exe or Python installation permitted).' + "`n" +
'4. When the user asks where to write login/password for Active Directory, give them the exact path: ' + $EnvFilePath + "`n" +
'5. If you need to perform an action on the PC (check AD network port 636, read a file, inspect directory), provide a ```powershell ... ``` block.' + "`n"

$geminiMdPath = Join-Path $TargetDir 'GEMINI.md'
if (Test-Path $geminiMdPath) {
    try {
        $bytes = [System.IO.File]::ReadAllBytes($geminiMdPath)
        $systemPrompt = $systemPrompt + "`n`n" + [System.Text.Encoding]::UTF8.GetString($bytes)
        Write-Host '[+] Knowledge base (GEMINI.md) loaded into memory!' -ForegroundColor Green
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
        temperature = 0.3
    }
    $bodyJson = $bodyObj | ConvertTo-Json -Depth 6
    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyJson)

    $headers = @{
        'Authorization' = ('Bearer ' + $ApiKey)
        'Content-Type'  = 'application/json; charset=utf-8'
    }

    try {
        $res = Invoke-RestMethod -Uri ($BaseUrl + '/chat/completions') -Method Post -Headers $headers -Body $bodyBytes -TimeoutSec 60
        return $res.choices[0].message.content
    } catch {
        return ('[SmartAPI Error]: ' + $_.Exception.Message)
    }
}

# 4. Agent tool execution handler
function Execute-AgentTurn {
    param (
        [ref]$HistoryRef,
        [string]$ModelName = $CurrentModel
    )

    $maxSteps = 4
    $step = 0

    while ($step -lt $maxSteps) {
        $step++
        $reply = Invoke-SmartApiChat -Messages ($HistoryRef.Value) -ModelName $ModelName

        # Strip accidental DSML tags
        $cleanReply = [regex]::Replace($reply, '(?s)<\|\s*DSML.*?\|>', '')

        $psMatch = [regex]::Match($cleanReply, '(?s)```powershell\s*(.*?)\s*```')

        if ($psMatch.Success) {
            $cmd = $psMatch.Groups[1].Value.Trim()
            Write-Host ''
            Write-Host ('[AI executes PowerShell]: ' + $cmd) -ForegroundColor Yellow
            try {
                Push-Location $TargetDir
                $cmdOut = (Invoke-Expression $cmd 2>&1 | Out-String)
                Pop-Location
            } catch {
                $cmdOut = $_.Exception.Message
            }

            if (-not $cmdOut.Trim()) { $cmdOut = '(Command executed, output is empty)' }

            Write-Host ('[PC Output]: ' + $cmdOut.Trim()) -ForegroundColor DarkGray

            $HistoryRef.Value += @{ role = 'assistant'; content = $cleanReply }
            $HistoryRef.Value += @{ role = 'user'; content = ('[PowerShell result]:`n' + $cmdOut) }
        } else {
            return $cleanReply
        }
    }
    return $cleanReply
}

# 5. Check connection
Write-Host ('[*] Testing connection to ' + $CurrentModel + ' via SmartAPI...') -ForegroundColor Yellow
$testMsgs = @(
    @{ role = 'user'; content = 'Confirm readiness in one sentence in Russian.' }
)
$testResp = Invoke-SmartApiChat -Messages $testMsgs -ModelName $CurrentModel
Write-Host ('[+] Status: ' + $testResp.Trim()) -ForegroundColor Green

Write-Host ''
Write-Host '========================================================================' -ForegroundColor Green
Write-Host ' AI ASSISTANT READY // AO INTERGAS CENTRAL ASIA' -ForegroundColor Green
Write-Host (' Project folder: ' + $TargetDir) -ForegroundColor White
Write-Host (' Config .env:    ' + $EnvFilePath) -ForegroundColor Cyan
Write-Host '========================================================================' -ForegroundColor Green
Write-Host 'Quick commands:' -ForegroundColor Yellow
Write-Host '  /env      - open .env in Notepad to edit Active Directory credentials' -ForegroundColor Gray
Write-Host '  /test-ad  - test connection to Active Directory domain controller (port 636)' -ForegroundColor Gray
Write-Host '  /clear    - clear conversation history' -ForegroundColor Gray
Write-Host '  exit      - exit' -ForegroundColor Gray
Write-Host ''

$history = @(
    @{ role = 'system'; content = $systemPrompt }
)

while ($true) {
    Write-Host 'You > ' -NoNewline -ForegroundColor Cyan
    $userInput = Read-Host

    if (-not $userInput -or -not $userInput.Trim()) { continue }

    if ($userInput -in @('exit', 'quit', 'q', '/exit', '/quit')) {
        Write-Host 'Session ended.' -ForegroundColor Yellow
        break
    }

    if ($userInput -eq '/clear') {
        $history = @( @{ role = 'system'; content = $systemPrompt } )
        Write-Host '[+] History cleared.' -ForegroundColor Green
        continue
    }

    if ($userInput -eq '/env') {
        Write-Host ('[*] Opening ' + $EnvFilePath + ' in Notepad...') -ForegroundColor Yellow
        notepad $EnvFilePath
        Write-Host '[+] Save file in Notepad (Ctrl+S) and close it.' -ForegroundColor Green
        continue
    }

    if ($userInput -eq '/test-ad') {
        Write-Host '[*] Testing Active Directory connection on LDAPS port 636...' -ForegroundColor Yellow
        $server = 'dc01.intergas.kz'
        if (Test-Path $EnvFilePath) {
            $lines = Get-Content $EnvFilePath
            foreach ($line in $lines) {
                if ($line -match '^AD_SERVER\s*=\s*(?:ldaps?://)?([^:/]+)') {
                    $server = $matches[1]
                }
            }
        }
        Write-Host ('[>] Testing host: ' + $server + ':636...') -ForegroundColor Gray
        try {
            $t = Test-NetConnection -ComputerName $server -Port 636 -WarningAction SilentlyContinue
            if ($t.TcpTestSucceeded) {
                Write-Host ('[+] CONNECTION SUCCESS! Port 636 on ' + $server + ' is open.') -ForegroundColor Green
            } else {
                Write-Host ('[!] PORT CLOSED or host unreachable: ' + $server + ':636') -ForegroundColor Red
                Write-Host '    Verify server hostname or IP in .env' -ForegroundColor Yellow
            }
        } catch {
            Write-Host ('[!] Network test error: ' + $_.Exception.Message) -ForegroundColor Red
        }
        continue
    }

    $history += @{ role = 'user'; content = $userInput }
    Write-Host 'Thinking...' -ForegroundColor DarkMagenta

    $finalAnswer = Execute-AgentTurn -HistoryRef ([ref]$history) -ModelName $CurrentModel
    Write-Host ''
    Write-Host 'Engineer:' -ForegroundColor Green
    Write-Host $finalAnswer -ForegroundColor White
    Write-Host ''

    $history += @{ role = 'assistant'; content = $finalAnswer }
}
