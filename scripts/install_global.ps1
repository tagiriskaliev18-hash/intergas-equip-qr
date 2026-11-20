# 
# Установка Mind CLI глобально в Windows (доступно из ЛЮБОЙ папки)
# 
$ErrorActionPreference = "SilentlyContinue"

$mindHome = Join-Path $HOME ".mind"
$mindBin = Join-Path $mindHome "bin"
$mindScripts = Join-Path $mindHome "scripts"

New-Item -ItemType Directory -Path $mindBin -Force | Out-Null
New-Item -ItemType Directory -Path $mindScripts -Force | Out-Null

# 1. Копируем ядро mind_cli.py
$sourceScript = Join-Path $PSScriptRoot "mind_cli.py"
$targetScript = Join-Path $mindScripts "mind_cli.py"
Copy-Item -Path $sourceScript -Destination $targetScript -Force

# 2. Создаем универсальный лаунчер mind.cmd
$cmdLauncher = Join-Path $mindBin "mind.cmd"
$cmdContent = @"
@echo off
title MIND // CLI
chcp 65001 >nul

if exist "%USERPROFILE%\Desktop\QRcode\venv\Scripts\python.exe" (
    "%USERPROFILE%\Desktop\QRcode\venv\Scripts\python.exe" "$targetScript" %*
    goto :done
)
if exist "C:\QRcode\venv\Scripts\python.exe" (
    "C:\QRcode\venv\Scripts\python.exe" "$targetScript" %*
    goto :done
)
if exist "C:\Program Files\Python311\python.exe" (
    "C:\Program Files\Python311\python.exe" "$targetScript" %*
    goto :done
)
if exist "%USERPROFILE%\.mind\python\python.exe" (
    "%USERPROFILE%\.mind\python\python.exe" "$targetScript" %*
    goto :done
)
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    py "$targetScript" %*
    goto :done
)
python "$targetScript" %*

:done
"@
Set-Content -Path $cmdLauncher -Value $cmdContent -Encoding ASCII

# 3. Создаем лаунчер для PowerShell mind.ps1
$ps1Launcher = Join-Path $mindBin "mind.ps1"
$ps1Content = @"
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = `$true)]
    `$ArgsList
)
`$py = `$null
`$candidates = @(
    "`$HOME\Desktop\QRcode\venv\Scripts\python.exe",
    "C:\QRcode\venv\Scripts\python.exe",
    "C:\Program Files\Python311\python.exe",
    "`$HOME\.mind\python\python.exe"
)
foreach (`$c in `$candidates) {
    if (Test-Path `$c) { `$py = `$c; break }
}
if (-not `$py) {
    if (Get-Command py -ErrorAction SilentlyContinue) { `$py = "py" }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { `$py = "python" }
}
if (`$py) {
    & `$py "$targetScript" @ArgsList
} else {
    Write-Host "[!] Python не найден." -ForegroundColor Red
}
"@
Set-Content -Path $ps1Launcher -Value $ps1Content -Encoding ASCII

# 4. Раскладываем в системные папки, которые гарантированно есть в PATH:
# C:\Users\user\.local\bin
$localBin = Join-Path $HOME ".local\bin"
if (Test-Path $localBin) {
    Copy-Item -Path $cmdLauncher -Destination (Join-Path $localBin "mind.cmd") -Force
    Copy-Item -Path $ps1Launcher -Destination (Join-Path $localBin "mind.ps1") -Force
}

# C:\Users\user\AppData\Local\Microsoft\WindowsApps
$winApps = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
if (Test-Path $winApps) {
    Copy-Item -Path $cmdLauncher -Destination (Join-Path $winApps "mind.cmd") -Force
    Copy-Item -Path $ps1Launcher -Destination (Join-Path $winApps "mind.ps1") -Force
}

# 5. Добавляем $mindBin в переменную среды PATH пользователя
$curUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($curUserPath -notlike "*$mindBin*") {
    [Environment]::SetEnvironmentVariable("Path", "$mindBin;$curUserPath", "User")
}

# 6. Создаем ярлык на Рабочем столе
$desktop = [Environment]::GetFolderPath('Desktop')
if (Test-Path $desktop) {
    $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop "Mind CLI.lnk"))
    $lnk.TargetPath = $cmdLauncher
    $lnk.WorkingDirectory = $HOME
    if (Test-Path "C:\Windows\System32\imageres.dll") {
        $lnk.IconLocation = "C:\Windows\System32\imageres.dll,109"
    } else {
        $lnk.IconLocation = "C:\Windows\System32\shell32.dll,220"
    }
    $lnk.Save()

    Copy-Item -Path $cmdLauncher -Destination (Join-Path $desktop "Mind CLI.cmd") -Force
}

Write-Host "[SUCCESS] Mind CLI успешно установлен глобально в систему!" -ForegroundColor Green
Write-Host "Теперь команда 'mind' доступна из абсолютно любой папки (cmd, powershell, терминал)!" -ForegroundColor Cyan
