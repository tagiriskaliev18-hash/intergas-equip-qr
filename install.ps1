# ==============================================================================
# M I N D // C L I  —  ONE-LINE UNIVERSAL INSTALLER
# ==============================================================================
# Использование: 
#   irm https://raw.githubusercontent.com/tagiriskaliev18-hash/intergas-equip-qr/main/install.ps1 | iex
# ==============================================================================

$ErrorActionPreference = "Stop"

# Включение современных TLS протоколов и обход корпоративных прокси
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
[System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }

# ANSI цвета
$ESC = [char]27
$CYAN = "$ESC[38;2;0;245;255m"
$VIOLET = "$ESC[38;2;123;47;247m"
$GREEN = "$ESC[38;2;0;230;153m"
$MUTED = "$ESC[38;2;145;155;180m"
$RESET = "$ESC[0m"

Write-Host ""
Write-Host "$VIOLET━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$RESET"
Write-Host "  $CYAN◆ M I N D // C L I$RESET  $MUTED•  УНИВЕРСАЛЬНЫЙ АВТОНОМНЫЙ УСТАНОВЩИК$RESET"
Write-Host "  $MUTEDТагир Искалиев // Развёртывание интеллекта в 1 команду$RESET"
Write-Host "$VIOLET━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$RESET"
Write-Host ""

# 1. Определение рабочей папки установки
$mindDir = Join-Path $HOME ".mind"
$binDir = Join-Path $mindDir "bin"
$scriptsDir = Join-Path $mindDir "scripts"

New-Item -ItemType Directory -Path $binDir -Force | Out-Null
New-Item -ItemType Directory -Path $scriptsDir -Force | Out-Null

# 2. Скачивание главного ядра Mind CLI
Write-Host "$MUTED[*] Загрузка ядра Mind CLI с GitHub...$RESET"
$rawUrl = "https://raw.githubusercontent.com/tagiriskaliev18-hash/intergas-equip-qr/main/scripts/mind_cli.py"
$targetScript = Join-Path $scriptsDir "mind_cli.py"

Invoke-WebRequest -Uri $rawUrl -OutFile $targetScript -UseBasicParsing

# 3. Создание глобального исполняемого файла mind.cmd
$cmdLauncher = Join-Path $binDir "mind.cmd"
$cmdScript = @"
@echo off
title MIND CLI
chcp 65001 >nul

if exist "C:\Program Files\Python311\python.exe" (
    "C:\Program Files\Python311\python.exe" "$targetScript" %*
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
Set-Content -Path $cmdLauncher -Value $cmdScript -Encoding ASCII

# 4. Добавление в системный PATH пользователя (чтобы команда 'mind' работала везде)
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$binDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$binDir;$userPath", "User")
    $env:Path = "$binDir;$env:Path"
}

# 5. Создание ярлыков на Рабочем столе
$desktop = [Environment]::GetFolderPath('Desktop')
if (Test-Path $desktop) {
    # Графический .lnk ярлык
    $lnkPath = Join-Path $desktop "Mind CLI.lnk"
    $wsh = New-Object -ComObject WScript.Shell
    $shortcut = $wsh.CreateShortcut($lnkPath)
    $shortcut.TargetPath = $cmdLauncher
    $shortcut.WorkingDirectory = $mindDir
    $shortcut.WindowStyle = 1
    $shortcut.Description = "MIND // CLI — Autonomous Executive Terminal"
    if (Test-Path "C:\Windows\System32\imageres.dll") {
        $shortcut.IconLocation = "C:\Windows\System32\imageres.dll,109"
    } else {
        $shortcut.IconLocation = "C:\Windows\System32\shell32.dll,220"
    }
    $shortcut.Save()

    # Прямой .cmd лаунчер
    Copy-Item -Path $cmdLauncher -Destination (Join-Path $desktop "Mind CLI.cmd") -Force
}

Write-Host "$GREEN[✔] Установка завершена успешно!$RESET"
Write-Host "$MUTED    - Папка:   $mindDir$RESET"
Write-Host "$MUTED    - Команда: теперь в любом терминале просто напишите: $CYAN mind $RESET"
Write-Host "$MUTED    - Ярлык:   создан на вашем Рабочем столе$RESET"
Write-Host ""
Write-Host "$CYAN[*] Запуск Mind CLI прямо сейчас...$RESET"
Write-Host ""

# 6. Мгновенный запуск Mind CLI прямо в текущей консоли
& $cmdLauncher
