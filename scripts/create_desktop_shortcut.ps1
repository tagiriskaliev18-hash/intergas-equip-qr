# 
# Скрипт создания ярлыка запуска Mind Universal AI Assistant на Рабочем столе
# 
$ErrorActionPreference = "SilentlyContinue"

$desktop = [Environment]::GetFolderPath('Desktop')
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir

$targetCmd = Join-Path $projectDir "run_desktop_agent.cmd"

# 1. Создание прямого .cmd лаунчера на Рабочем столе
$desktopCmdPath = Join-Path $desktop "Mind_AI_Desktop.cmd"
$cmdContent = @"
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
Set-Content -Path $desktopCmdPath -Value $cmdContent -Encoding ASCII

# 2. Создание полноценного графического ярлыка .lnk с иконкой
$lnkPath = Join-Path $desktop "Mind Universal AI.lnk"
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($lnkPath)
$shortcut.TargetPath = $targetCmd
$shortcut.WorkingDirectory = $projectDir
$shortcut.WindowStyle = 1
$shortcut.Description = "Mind Universal AI Assistant // Автоматизация Windows и ПК"

# Подбор красивой иконки (шестерёнка / терминал / процессор)
$iconCandidate = "C:\Windows\System32\imageres.dll,109"
if (Test-Path "C:\Windows\System32\imageres.dll") {
    $shortcut.IconLocation = $iconCandidate
} else {
    $shortcut.IconLocation = "C:\Windows\System32\shell32.dll,220"
}

$shortcut.Save()

Write-Host "`n[+] Ярлыки успешно созданы на Рабочем столе:" -ForegroundColor Green
Write-Host "    1. Графический ярлык: $lnkPath" -ForegroundColor Cyan
Write-Host "    2. Прямой лаунчер:    $desktopCmdPath" -ForegroundColor Cyan
