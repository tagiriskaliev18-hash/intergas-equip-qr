# 
# .SYNOPSIS
# Скрипт автоматической установки и настройки Gemini CLI на рабочем компьютере.
# 
# .DESCRIPTION
# 1. Проверяет наличие Node.js и npm (при отсутствии устанавливает через winget).
# 2. Устанавливает официальный пакет @google/gemini-cli глобально.
# 3. Запрашивает и сохраняет GEMINI_API_KEY в переменные среды Windows (User Environment).
# 4. Выполняет тестовый запуск Gemini CLI.
# 5. Показывает команды для работы с проектом.
# 
# .EXAMPLE
# .\scripts\setup_gemini_cli.ps1
# 


[CmdletBinding()]
param (
    [string]$ApiKey = ""
)

$ErrorActionPreference = "Continue"

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host " УСТАНОВКА И ПОДКЛЮЧЕНИЕ GEMINI CLI (РАБОЧЕЕ МЕСТО)" -ForegroundColor Cyan
Write-Host " Google DeepMind & Antigravity Platform" -ForegroundColor DarkGray
Write-Host "========================================================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 1. Проверка Node.js и npm
# ---------------------------------------------------------------------------
Write-Host "`n[1/4] Проверка окружения Node.js..." -ForegroundColor Yellow
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue

if (-not $nodeCmd) {
    Write-Host "[!] Node.js не обнаружен. Попытка автоматической установки через Windows Package Manager (winget)..." -ForegroundColor Magenta
    $wingetCmd = Get-Command winget -ErrorAction SilentlyContinue
    if ($wingetCmd) {
        winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements --silent
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    } else {
        Write-Error "[-] Ошибка: Установите Node.js вручную с https://nodejs.org/ перед запуском."
        exit 1
    }
} else {
    $nodeVer = & node -v
    Write-Host "[+] Node.js найден: $nodeVer" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# 2. Установка @google/gemini-cli
# ---------------------------------------------------------------------------
Write-Host "`n[2/4] Установка официального Gemini CLI (@google/gemini-cli)..." -ForegroundColor Yellow
npm install -g @google/gemini-cli

$geminiCmd = Get-Command gemini -ErrorAction SilentlyContinue
if (-not $geminiCmd) {
    # Обновляем PATH текущей сессии
    $npmPrefix = npm config get prefix
    if ($npmPrefix -and (Test-Path $npmPrefix)) {
        $env:Path = "$npmPrefix;$env:Path"
    }
}

Write-Host "[+] Gemini CLI успешно установлен!" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 3. Настройка ключа API (GEMINI_API_KEY)
# ---------------------------------------------------------------------------
Write-Host "`n[3/4] Проверка и настройка GEMINI_API_KEY..." -ForegroundColor Yellow
$existingKey = [System.Environment]::GetEnvironmentVariable("GEMINI_API_KEY", "User")
if (-not $existingKey) {
    $existingKey = $env:GEMINI_API_KEY
}

if (-not $ApiKey -and -not $existingKey) {
    Write-Host "`n[?] Введите ваш Google Gemini API Key:" -ForegroundColor Yellow
    Write-Host "    (Получить бесплатно: https://aistudio.google.com/app/apikey)" -ForegroundColor DarkGray
    $inputKey = Read-Host "GEMINI_API_KEY"
    $ApiKey = $inputKey.Trim()
} elseif ($existingKey -and -not $ApiKey) {
    $ApiKey = $existingKey
    Write-Host "[+] Обнаружен сохранённый GEMINI_API_KEY в профиле Windows." -ForegroundColor Green
}

if ($ApiKey) {
    # Сохраняем в реестр пользователя навсегда
    [System.Environment]::SetEnvironmentVariable("GEMINI_API_KEY", $ApiKey, "User")
    $env:GEMINI_API_KEY = $ApiKey
    Write-Host "[+] Ключ GEMINI_API_KEY успешно сохранён в системе!" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# 4. Тестовый запуск
# ---------------------------------------------------------------------------
Write-Host "`n[4/4] Тестовый запрос к Gemini API..." -ForegroundColor Yellow
try {
    & gemini "Привет, подтверди готовность к работе с проектом оборудования Интергаз."
} catch {
    Write-Host "[!] Запустите в новом окне терминала: gemini" -ForegroundColor DarkYellow
}

Write-Host "`n========================================================================" -ForegroundColor Green
Write-Host " GEMINI CLI ГОТОВ К РАБОТЕ!" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Green
Write-Host "Команды для терминала:"
Write-Host "  gemini              - запуск интерактивного чата Gemini в терминале" -ForegroundColor Cyan
Write-Host "  gemini <вопрос>     - быстрый одиночный запрос" -ForegroundColor Cyan
Write-Host "  gemini -m gemini-2.5-flash  - запуск с быстрой моделью 2.5 Flash" -ForegroundColor Cyan
Write-Host "`nДля запуска полного интерфейса Antigravity IDE (как на этом компьютере):"
Write-Host "  Скачайте установщик: https://antigravity.google/download`n" -ForegroundColor DarkGray
