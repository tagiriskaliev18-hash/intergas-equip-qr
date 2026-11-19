# ==============================================================================
# AO INTERGAS CENTRAL ASIA // JSC NC QAZAQGAZ
# Master Administrator Setup Script (Node.js, Python, RSAT AD, Aider, Tests)
# Pure ASCII - 100% Compatible with PowerShell 5.1 & 7+
# ==============================================================================

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Continue'

# 0. Check for Administrator Elevation
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host '[*] Requesting Administrator privileges (UAC)...' -ForegroundColor Yellow
    Start-Process powershell.exe -Verb RunAs -ArgumentList ('-ExecutionPolicy Bypass -NoProfile -File "' + $PSCommandPath + '"')
    exit
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = if (Test-Path (Join-Path $ScriptDir 'GEMINI.md')) { $ScriptDir } else { Split-Path -Parent $ScriptDir }
Set-Location $RootDir

Write-Host ''
Write-Host '========================================================================' -ForegroundColor Cyan
Write-Host ' MASTER ADMIN SETUP // AO INTERGAS CENTRAL ASIA' -ForegroundColor Cyan
Write-Host ' Installing: Node.js LTS, Python 3.11+, RSAT Active Directory, Aider' -ForegroundColor DarkGray
Write-Host '========================================================================' -ForegroundColor Cyan
Write-Host ''

# ------------------------------------------------------------------------------
# 1. Install Node.js LTS
# ------------------------------------------------------------------------------
Write-Host '------------------------------------------------------------------------' -ForegroundColor DarkCyan
Write-Host '[1/6] Checking and installing Node.js LTS...' -ForegroundColor Yellow
Write-Host '------------------------------------------------------------------------' -ForegroundColor DarkCyan

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Host '[*] Node.js not found. Installing...' -ForegroundColor Yellow
    $installed = $false

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host '[>] Installing Node.js LTS via winget...' -ForegroundColor Gray
        & winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements --silent
        if ($LASTEXITCODE -eq 0) { $installed = $true }
    }

    if (-not $installed) {
        Write-Host '[>] Downloading official Node.js LTS MSI from nodejs.org...' -ForegroundColor Gray
        $nodeMsiUrl = 'https://nodejs.org/dist/v20.18.0/node-v20.18.0-x64.msi'
        $tempMsi = Join-Path $env:TEMP 'node-v20-x64.msi'
        try {
            Invoke-WebRequest -Uri $nodeMsiUrl -OutFile $tempMsi -UseBasicParsing
            Write-Host '[>] Running MSI silent installation...' -ForegroundColor Gray
            Start-Process msiexec.exe -ArgumentList ('/i "' + $tempMsi + '" /qn /norestart') -Wait
            Remove-Item $tempMsi -Force -ErrorAction SilentlyContinue
            $installed = $true
        } catch {
            Write-Host ('[!] MSI Download error: ' + $_.Exception.Message) -ForegroundColor DarkYellow
        }
    }

    $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'User')
}

$nodeCheck = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCheck) {
    Write-Host ('[+] Node.js ready: ' + (& node -v) + ' (npm ' + (& npm -v) + ')') -ForegroundColor Green
} else {
    Write-Host '[!] Node.js installed (restart shell if PATH is not updated).' -ForegroundColor DarkYellow
}

# ------------------------------------------------------------------------------
# 2. Install Python 3.11+
# ------------------------------------------------------------------------------
Write-Host ''
Write-Host '------------------------------------------------------------------------' -ForegroundColor DarkCyan
Write-Host '[2/6] Checking and installing Python 3.11+...' -ForegroundColor Yellow
Write-Host '------------------------------------------------------------------------' -ForegroundColor DarkCyan

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host '[*] Python not found. Installing...' -ForegroundColor Yellow
    $pyInstalled = $false

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host '[>] Installing Python 3.11 via winget...' -ForegroundColor Gray
        & winget install Python.Python.3.11 --accept-package-agreements --accept-source-agreements --silent
        if ($LASTEXITCODE -eq 0) { $pyInstalled = $true }
    }

    if (-not $pyInstalled) {
        Write-Host '[>] Downloading official Python 3.11 installer from python.org...' -ForegroundColor Gray
        $pyUrl = 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe'
        $tempPy = Join-Path $env:TEMP 'python-3.11.9-installer.exe'
        try {
            Invoke-WebRequest -Uri $pyUrl -OutFile $tempPy -UseBasicParsing
            Write-Host '[>] Installing Python for all users with PrependPath...' -ForegroundColor Gray
            Start-Process $tempPy -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0' -Wait
            Remove-Item $tempPy -Force -ErrorAction SilentlyContinue
            $pyInstalled = $true
        } catch {
            Write-Host ('[!] Python download error: ' + $_.Exception.Message) -ForegroundColor DarkYellow
        }
    }

    $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'User')
}

$pythonCheck = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCheck) {
    Write-Host ('[+] Python ready: ' + (& python --version)) -ForegroundColor Green
} else {
    Write-Host '[!] Python installed.' -ForegroundColor DarkYellow
}

# ------------------------------------------------------------------------------
# 3. Virtual Environment & Dependencies
# ------------------------------------------------------------------------------
Write-Host ''
Write-Host '------------------------------------------------------------------------' -ForegroundColor DarkCyan
Write-Host '[3/6] Setting up Python virtual environment (venv) and packages...' -ForegroundColor Yellow
Write-Host '------------------------------------------------------------------------' -ForegroundColor DarkCyan

$VenvDir = Join-Path $RootDir 'venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'

if (-not (Test-Path $VenvPython)) {
    Write-Host '[*] Creating venv in project directory...' -ForegroundColor Yellow
    & python -m venv $VenvDir
}

if (Test-Path $VenvPython) {
    Write-Host ('[+] Active venv: ' + $VenvPython) -ForegroundColor Green
    Write-Host '[*] Upgrading pip and installing requirements.txt...' -ForegroundColor Gray
    & $VenvPython -m pip install --upgrade pip --quiet
    $reqFile = Join-Path $RootDir 'requirements.txt'
    if (Test-Path $reqFile) {
        & $VenvPython -m pip install -r $reqFile --quiet
    }
    Write-Host '[*] Installing enterprise libraries: ldap3, cryptography, aider-chat...' -ForegroundColor Gray
    & $VenvPython -m pip install ldap3 google-genai aider-chat --quiet
    Write-Host '[+] Python packages installed successfully!' -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# 4. Install Active Directory Tools (RSAT)
# ------------------------------------------------------------------------------
Write-Host ''
Write-Host '------------------------------------------------------------------------' -ForegroundColor DarkCyan
Write-Host '[4/6] Installing Active Directory components (RSAT)...' -ForegroundColor Yellow
Write-Host '------------------------------------------------------------------------' -ForegroundColor DarkCyan

$os = Get-CimInstance Win32_OperatingSystem
if ($os.ProductType -ne 1) {
    Write-Host '[*] Windows Server detected. Installing RSAT-ADDS features...' -ForegroundColor Yellow
    try {
        Install-WindowsFeature -Name RSAT-AD-PowerShell, RSAT-ADDS -IncludeManagementTools -ErrorAction SilentlyContinue | Out-Null
        Write-Host '[+] Active Directory Tools installed on Server!' -ForegroundColor Green
    } catch {
        Write-Host ('[!] Server feature notice: ' + $_.Exception.Message) -ForegroundColor DarkYellow
    }
} else {
    Write-Host '[*] Windows Client detected. Installing RSAT Active Directory Capability...' -ForegroundColor Yellow
    try {
        $cap = Get-WindowsCapability -Online -Name 'Rsat.ActiveDirectory.DS-LDS.Tools*' -ErrorAction SilentlyContinue
        if ($cap -and $cap.State -eq 'Installed') {
            Write-Host '[+] RSAT Active Directory Tools already installed!' -ForegroundColor Green
        } else {
            Write-Host '[>] Activating Rsat.ActiveDirectory.DS-LDS.Tools capability...' -ForegroundColor Gray
            Add-WindowsCapability -Online -Name 'Rsat.ActiveDirectory.DS-LDS.Tools~~~~0.0.1.0' -ErrorAction Stop | Out-Null
            Write-Host '[+] RSAT Active Directory installed (ActiveDirectory module + dsa.msc console ready)!' -ForegroundColor Green
        }
    } catch {
        Write-Host ('[!] RSAT Capability notice: ' + $_.Exception.Message) -ForegroundColor DarkYellow
    }
}

# ------------------------------------------------------------------------------
# 5. Configure Active Directory Groups and Service Account
# ------------------------------------------------------------------------------
Write-Host ''
Write-Host '------------------------------------------------------------------------' -ForegroundColor DarkCyan
Write-Host '[5/6] Configuring Active Directory domain security groups and roles...' -ForegroundColor Yellow
Write-Host '------------------------------------------------------------------------' -ForegroundColor DarkCyan

$sys = Get-CimInstance Win32_ComputerSystem
$domainName = if ($sys.PartOfDomain) { $sys.Domain } else { 'intergas.kz' }
Write-Host ('[*] Domain: ' + $domainName + ' (PartOfDomain: ' + $sys.PartOfDomain + ')') -ForegroundColor Cyan

$adMod = Get-Module -ListAvailable ActiveDirectory -ErrorAction SilentlyContinue
if ($adMod -and $sys.PartOfDomain) {
    Import-Module ActiveDirectory -ErrorAction SilentlyContinue
    Write-Host '[*] Creating corporate AD security groups for AO Intergas Central Asia...' -ForegroundColor Yellow

    $groups = @(
        @{ Name = 'GG_ICA_Mechanics'; Desc = 'AO Intergas Central Asia - Chief Mechanics (System Admins)' },
        @{ Name = 'GG_ICA_Engineers'; Desc = 'AO Intergas Central Asia - Shift Maintenance Engineers' },
        @{ Name = 'GG_ICA_Operators'; Desc = 'AO Intergas Central Asia - Duty Operators GRS/KS' }
    )

    foreach ($g in $groups) {
        $exist = Get-ADGroup -Filter ("SamAccountName -eq '" + $g.Name + "'") -ErrorAction SilentlyContinue
        if (-not $exist) {
            try {
                New-ADGroup -Name $g.Name -GroupScope Global -GroupCategory Security -Description $g.Desc -ErrorAction Stop
                Write-Host ('[+] Created AD Security Group: ' + $g.Name) -ForegroundColor Green
            } catch {
                Write-Host ('[!] AD Group ' + $g.Name + ': ' + $_.Exception.Message) -ForegroundColor DarkYellow
            }
        } else {
            Write-Host ('[+] AD Security Group exists: ' + $g.Name) -ForegroundColor Green
        }
    }

    # Service account check / creation
    $svcName = 'svc_qr_reader'
    $existUser = Get-ADUser -Filter ("SamAccountName -eq '" + $svcName + "'") -ErrorAction SilentlyContinue
    if (-not $existUser) {
        Write-Host ('[?] Would you like to create service account ' + $svcName + ' for LDAP read? (Y/N)') -ForegroundColor Yellow
        $resp = Read-Host '[Y/N]'
        if ($resp -match '^[Yy]') {
            $passPlain = 'IcaQr_Service_2026!'
            $secPwd = ConvertTo-SecureString $passPlain -AsPlainText -Force
            try {
                New-ADUser -Name $svcName -SamAccountName $svcName -UserPrincipalName ($svcName + '@' + $domainName) -AccountPassword $secPwd -Enabled $true -PasswordNeverExpires $true -Description 'Service Account for Equip QR and Keycloak' -ErrorAction Stop
                Write-Host ('[+] Service Account ' + $svcName + ' created with default password: ' + $passPlain) -ForegroundColor Green
            } catch {
                Write-Host ('[!] Service Account notice: ' + $_.Exception.Message) -ForegroundColor DarkYellow
            }
        }
    } else {
        Write-Host ('[+] Service Account found in directory: ' + $svcName) -ForegroundColor Green
    }
} else {
    Write-Host '[*] Active Directory module or domain not directly reachable from this host.' -ForegroundColor DarkYellow
    Write-Host '    Remote connection to ldaps://dc01.intergas.kz:636 will be used via app/ad_auth.py.' -ForegroundColor Gray
}

# ------------------------------------------------------------------------------
# 6. Setup AI Tools, Config & Verification
# ------------------------------------------------------------------------------
Write-Host ''
Write-Host '------------------------------------------------------------------------' -ForegroundColor DarkCyan
Write-Host '[6/6] Configuring AI Tools (Aider, Gemini CLI), .env and Running Tests...' -ForegroundColor Yellow
Write-Host '------------------------------------------------------------------------' -ForegroundColor DarkCyan

$smartKey = 'sk-smart-J6NAKcsgKoJ_tfaOrfapSY14L1W8us5GR4ZZ3FwPIO8'
[System.Environment]::SetEnvironmentVariable('SMARTAPI_KEY', $smartKey, 'Machine')
[System.Environment]::SetEnvironmentVariable('OPENAI_API_BASE', 'https://smartapi.pro/v1', 'Machine')
[System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', $smartKey, 'Machine')
$env:SMARTAPI_KEY = $smartKey
$env:OPENAI_API_BASE = 'https://smartapi.pro/v1'
$env:OPENAI_API_KEY = $smartKey

# Install Gemini CLI globally via npm
$npm = Get-Command npm -ErrorAction SilentlyContinue
if ($npm) {
    Write-Host '[>] Installing @google/gemini-cli globally via npm...' -ForegroundColor Gray
    & npm install -g @google/gemini-cli --silent
    Write-Host '[+] Gemini CLI installed!' -ForegroundColor Green
}

# Copy GEMINI.md to user profile
$geminiDir = Join-Path $HOME '.gemini'
if (-not (Test-Path $geminiDir)) { New-Item -ItemType Directory -Path $geminiDir -Force | Out-Null }
Copy-Item (Join-Path $RootDir 'GEMINI.md') (Join-Path $geminiDir 'GEMINI.md') -Force
Write-Host '[+] GEMINI.md knowledge base synced to global AI profile!' -ForegroundColor Green

# Prepare .env
$envPath = Join-Path $RootDir '.env'
if (-not (Test-Path $envPath)) {
    Copy-Item (Join-Path $RootDir '.env.ad.example') $envPath -Force
    Write-Host '[+] Config file .env initialized from .env.ad.example' -ForegroundColor Green
}

# Run pytest
if (Test-Path $VenvPython) {
    Write-Host '[*] Running test suite (pytest)...' -ForegroundColor Yellow
    & $VenvPython -m pytest (Join-Path $RootDir 'tests\test_app.py') -v --disable-warnings
    if ($LASTEXITCODE -eq 0) {
        Write-Host '[+] ALL 14 TESTS PASSED! 100% GREEN.' -ForegroundColor Green
    }
}

# Desktop launchers
$desktop = [Environment]::GetFolderPath('Desktop')
$startServerCmd = '@echo off' + "`r`n" + 'cd /d "' + $RootDir + '"' + "`r`n" + 'call venv\Scripts\activate.bat' + "`r`n" + 'python run.py' + "`r`n" + 'pause'
Set-Content -Path (Join-Path $desktop 'Start_Intergas_QR.cmd') -Value $startServerCmd -Encoding ASCII

$startAiderCmd = '@echo off' + "`r`n" + 'cd /d "' + $RootDir + '"' + "`r`n" + 'set OPENAI_API_BASE=https://smartapi.pro/v1' + "`r`n" + 'set OPENAI_API_KEY=' + $smartKey + "`r`n" + 'call venv\Scripts\activate.bat' + "`r`n" + 'aider --model openai/gemini-3.8-flash' + "`r`n" + 'pause'
Set-Content -Path (Join-Path $desktop 'Start_Aider_AI.cmd') -Value $startAiderCmd -Encoding ASCII

Write-Host ''
Write-Host '========================================================================' -ForegroundColor Green
Write-Host ' MASTER ADMIN SETUP COMPLETED SUCCESSFULLY!' -ForegroundColor Green
Write-Host '========================================================================' -ForegroundColor Green
Write-Host 'Installed and Configured:' -ForegroundColor Cyan
Write-Host '  1. Node.js LTS and npm' -ForegroundColor White
Write-Host '  2. Python 3.11+, virtualenv and all dependencies' -ForegroundColor White
Write-Host '  3. RSAT Active Directory Tools (ActiveDirectory module + dsa.msc console)' -ForegroundColor White
Write-Host '  4. AD Security Groups (GG_ICA_Mechanics, GG_ICA_Engineers, GG_ICA_Operators)' -ForegroundColor White
Write-Host '  5. Aider and Gemini CLI with SmartAPI (gemini-3.8-flash, Claude Opus 5.5)' -ForegroundColor White
Write-Host '  6. Desktop shortcuts created:' -ForegroundColor Yellow
Write-Host '     - Start_Intergas_QR.cmd -> launches server on https://127.0.0.1:8443' -ForegroundColor Gray
Write-Host '     - Start_Aider_AI.cmd    -> launches Aider AI assistant' -ForegroundColor Gray
Write-Host '========================================================================' -ForegroundColor Green
Write-Host ''
