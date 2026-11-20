# 
# Скрипт создания фирменных ярлыков Mind CLI на Рабочем столе
# 
$ErrorActionPreference = "SilentlyContinue"

$desktop = [Environment]::GetFolderPath('Desktop')
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir

# ==============================================================================
# 1. MIND CLI — ГЛАВНЫЙ АВТОНОМНЫЙ ТЕРМИНАЛ
# ==============================================================================
$mindCmdPath = Join-Path $desktop "Mind CLI.cmd"
$mindCmdContent = @"
@echo off
title MIND // CLI — Autonomous Executive Terminal
chcp 65001 >nul
cd /d "$projectDir"
if exist "$projectDir\venv\Scripts\python.exe" (
    "$projectDir\venv\Scripts\python.exe" "$projectDir\scripts\mind_cli.py" %*
) else if exist "C:\Program Files\Python311\python.exe" (
    "C:\Program Files\Python311\python.exe" "$projectDir\scripts\mind_cli.py" %*
) else (
    py "$projectDir\scripts\mind_cli.py" %*
)
pause
"@
Set-Content -Path $mindCmdPath -Value $mindCmdContent -Encoding ASCII

# Графический ярлык .lnk для Mind CLI
$lnkMindPath = Join-Path $desktop "Mind CLI.lnk"
$wsh = New-Object -ComObject WScript.Shell
$scMind = $wsh.CreateShortcut($lnkMindPath)
$scMind.TargetPath = (Join-Path $projectDir "mind.cmd")
$scMind.WorkingDirectory = $projectDir
$scMind.WindowStyle = 1
$scMind.Description = "MIND // CLI — Autonomous Executive Terminal // Tagir Iskaliev"

if (Test-Path "C:\Windows\System32\imageres.dll") {
    $scMind.IconLocation = "C:\Windows\System32\imageres.dll,109"
} else {
    $scMind.IconLocation = "C:\Windows\System32\shell32.dll,220"
}
$scMind.Save()

# ==============================================================================
# 2. MIND PC ASSISTANT (Универсальный помощник)
# ==============================================================================
$pcCmdPath = Join-Path $desktop "Mind_AI_Desktop.cmd"
$pcCmdContent = @"
@echo off
title Mind Universal AI Assistant
chcp 65001 >nul
cd /d "$projectDir"
if exist "$projectDir\venv\Scripts\python.exe" (
    "$projectDir\venv\Scripts\python.exe" "$projectDir\scripts\mind_desktop_agent.py" %*
) else if exist "C:\Program Files\Python311\python.exe" (
    "C:\Program Files\Python311\python.exe" "$projectDir\scripts\mind_desktop_agent.py" %*
) else (
    py "$projectDir\scripts\mind_desktop_agent.py" %*
)
pause
"@
Set-Content -Path $pcCmdPath -Value $pcCmdContent -Encoding ASCII

$lnkPcPath = Join-Path $desktop "Mind Universal AI.lnk"
$scPc = $wsh.CreateShortcut($lnkPcPath)
$scPc.TargetPath = (Join-Path $projectDir "run_desktop_agent.cmd")
$scPc.WorkingDirectory = $projectDir
$scPc.WindowStyle = 1
$scPc.Description = "Mind Universal AI Assistant // Автоматизация Windows"
$scPc.IconLocation = "C:\Windows\System32\shell32.dll,220"
$scPc.Save()

Write-Host "`n[+] Фирменные ярлыки Mind успешно размещены на Рабочем столе:" -ForegroundColor Green
Write-Host "    1. Mind CLI (Графический ярлык): $lnkMindPath" -ForegroundColor Cyan
Write-Host "    2. Mind CLI (Прямой лаунчер):    $mindCmdPath" -ForegroundColor Cyan
Write-Host "    3. Mind Universal AI:            $lnkPcPath" -ForegroundColor DarkGray
