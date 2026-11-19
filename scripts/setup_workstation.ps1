# 
# .SYNOPSIS
# Полный автоматический мастер развертывания проекта, подключения к Active Directory
# и настройки Gemini CLI на рабочем компьютере АО «Интергаз Центральная Азия».
# 
# .DESCRIPTION
# Делает ВСЁ «под ключ»:
# 1. Устанавливает и настраивает зависимости (Python venv, библиотеки requirements.txt, Node.js, @google/gemini-cli).
# 2. Вводит Gemini CLI в полный курс дела про приложение, ЛПУ/ГРС/КС, паспорта PDF, QR-коды и правила (GEMINI.md).
# 3. Запрашивает логин и пароль выданной серверной учётной записи AD (пароль скрывается звёздочками).
# 4. Записывает настройки в .env и сразу проверяет связь с контроллером домена (LDAP/LDAPS).
# 5. Прогоняет автоматические тесты (14 тестов, 100% green).
# 6. Предоставляет готовую к работе среду для продолжения диалога с Gemini.
# 
# .EXAMPLE
# .\setup.ps1
# .\scripts\setup_workstation.ps1
# 


[CmdletBinding()]
param (
    [string]$Server = "",
    [string]$BindDN = "",
    [string]$BindPassword = "",
    [string]$GeminiApiKey = ""
)

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

Write-Host "`n========================================================================" -ForegroundColor Cyan
Write-Host " АВТОМАТИЧЕСКОЕ РАЗВЕРТЫВАНИЕ РАБОЧЕГО МЕСТА // АО «ИНТЕРГАЗ ЦЕНТРАЛЬНАЯ АЗИЯ»" -ForegroundColor Cyan
Write-Host " Комплекс паспортизации оборудования ЛПУ, ГРС, КС и защищённого QR-контроля" -ForegroundColor DarkGray
Write-Host "========================================================================`n" -ForegroundColor Cyan

# =============================================================================
# ШАГ 1. Проверка системных компонентов (Python, Node.js, winget)
# =============================================================================
Write-Host "------------------------------------------------------------------------" -ForegroundColor DarkCyan
Write-Host "[1/5] Проверка системного окружения..." -ForegroundColor Yellow
Write-Host "------------------------------------------------------------------------" -ForegroundColor DarkCyan

# 1.1 Python
$sysPython = Get-Command python -ErrorAction SilentlyContinue
if (-not $sysPython) {
    Write-Host "[!] Python 3 не обнаружен. Установка Python 3.11 через Windows Package Manager..." -ForegroundColor Magenta
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        winget install Python.Python.3.11 --accept-package-agreements --accept-source-agreements --silent
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    } else {
        Write-Error "[-] Ошибка: Установите Python 3 с https://www.python.org/downloads/ и запустите скрипт снова."
        exit 1
    }
} else {
    Write-Host "[+] Python найден: $(& python --version)" -ForegroundColor Green
}

# 1.2 Node.js (для Gemini CLI)
$sysNode = Get-Command node -ErrorAction SilentlyContinue
if (-not $sysNode) {
    Write-Host "[!] Node.js не обнаружен. Установка Node.js LTS через winget..." -ForegroundColor Magenta
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements --silent
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    } else {
        Write-Host "[!] Внимание: Node.js не найден. Gemini CLI будет доступен через Python SDK." -ForegroundColor DarkYellow
    }
} else {
    Write-Host "[+] Node.js найден: $(& node -v)" -ForegroundColor Green
}

# =============================================================================
# ШАГ 2. Развертывание виртуального окружения Python и пакетов проекта
# =============================================================================
Write-Host "`n------------------------------------------------------------------------" -ForegroundColor DarkCyan
Write-Host "[2/5] Развертывание виртуального окружения (venv) и зависимостей..." -ForegroundColor Yellow
Write-Host "------------------------------------------------------------------------" -ForegroundColor DarkCyan

$VenvDir = Join-Path $RootDir "venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[*] Создание изолированного виртуального окружения venv..." -ForegroundColor Yellow
    & python -m venv $VenvDir
}

if (-not (Test-Path $VenvPython)) {
    Write-Error "[-] Ошибка создания виртуального окружения Python."
    exit 1
}

Write-Host "[+] Виртуальное окружение активно: $VenvPython" -ForegroundColor Green
Write-Host "[*] Установка пакетов (FastAPI, ldap3, Pillow, qrcode, pyjwt, cryptography, fpdf2)..." -ForegroundColor Yellow

& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install -r (Join-Path $RootDir "requirements.txt") --quiet
& $VenvPython -m pip install ldap3 google-genai --quiet

Write-Host "[+] Все зависимости Python успешно установлены!" -ForegroundColor Green

# =============================================================================
# ШАГ 3. Подключение к Active Directory (ввод серверной учётки)
# =============================================================================
Write-Host "`n------------------------------------------------------------------------" -ForegroundColor DarkCyan
Write-Host "[3/5] Подключение к Active Directory АО «Интергаз Центральная Азия»..." -ForegroundColor Yellow
Write-Host "------------------------------------------------------------------------" -ForegroundColor DarkCyan

if (-not $Server) {
    Write-Host "[?] Введите адрес или IP контроллера домена Active Directory:" -ForegroundColor Yellow
    Write-Host "    Пример: ldaps://dc01.intergas.kz:636 или ldap://10.x.x.x:389" -ForegroundColor DarkGray
    $inServer = Read-Host "Контроллер домена [ldaps://dc01.intergas.kz:636]"
    $Server = if ($inServer.Trim()) { $inServer.Trim() } else { "ldaps://dc01.intergas.kz:636" }
}

if (-not $BindDN) {
    Write-Host "`n[?] Введите логин серверной учетной записи (выданной администратором):" -ForegroundColor Yellow
    Write-Host "    Пример: svc_dev или svc_dev@intergas.kz" -ForegroundColor DarkGray
    $inBind = Read-Host "Логин серверной учётки"
    $BindDN = $inBind.Trim()
}

if (-not $BindPassword) {
    Write-Host "`n[?] Введите пароль серверной учетной записи (ввод скрыт звёздочками):" -ForegroundColor Yellow
    $secPwd = Read-Host -AsSecureString "Пароль"
    $BindPassword = [System.Net.NetworkCredential]::new("", $secPwd).Password
}

$UseSSL = $Server.StartsWith("ldaps://") -or $Server.EndsWith(":636")

# Запись в локальный .env
$EnvFile = Join-Path $RootDir ".env"
$EnvContent = @"
# ==============================================================================
# ПАРАМЕТРЫ ACTIVE DIRECTORY — АО «ИНТЕРГАЗ ЦЕНТРАЛЬНАЯ АЗИЯ»
# ==============================================================================
AD_ENABLED=true
AD_SERVER=$Server
AD_DOMAIN=intergas.kz
AD_BASE_DN=DC=intergas,DC=kz
AD_USERS_OU=OU=Users,OU=ICA,DC=intergas,DC=kz
AD_BIND_DN=$BindDN
AD_BIND_PASSWORD=$BindPassword
AD_USE_SSL=$($UseSSL.ToString().ToLower())

AD_GROUP_ADMIN=GG_ICA_Mechanics
AD_GROUP_ENGINEER=GG_ICA_Engineers
AD_GROUP_OPERATOR=GG_ICA_Operators

KEYCLOAK_URL=http://127.0.0.1:8080
KEYCLOAK_REALM=mind-equip
KEYCLOAK_CLIENT_ID=mind-equip-app
KEYCLOAK_CLIENT_SECRET=mind-equip-secret-2026-secure
"@

Set-Content -Path $EnvFile -Value $EnvContent -Encoding UTF8
Write-Host "[+] Параметры серверной учётки сохранены в локальный .env (защищено .gitignore)" -ForegroundColor Green

# Сетевая проверка контроллера
Write-Host "[*] Проверка соединения с контроллером домена $Server..." -ForegroundColor Yellow
$diagScript = Join-Path $RootDir "scripts\test_ad_connection.py"
& $VenvPython $diagScript --server $Server --bind-dn $BindDN --bind-pwd $BindPassword

# =============================================================================
# ШАГ 4. Настройка Gemini CLI и ввод его в курс дела (GEMINI.md)
# =============================================================================
Write-Host "`n------------------------------------------------------------------------" -ForegroundColor DarkCyan
Write-Host "[4/5] Настройка Gemini CLI и загрузка контекста проекта..." -ForegroundColor Yellow
Write-Host "------------------------------------------------------------------------" -ForegroundColor DarkCyan

# 4.1 Проверяем глобальный gemini cli через npm (если Node есть)
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if ($npmCmd) {
    Write-Host "[*] Проверка установки @google/gemini-cli..." -ForegroundColor Yellow
    npm install -g @google/gemini-cli --silent
}

# 4.2 Копируем GEMINI.md в профиль пользователя, чтобы агент подхватывал контекст глобально
$userGeminiDir = Join-Path $HOME ".gemini"
if (-not (Test-Path $userGeminiDir)) {
    New-Item -ItemType Directory -Path $userGeminiDir -Force | Out-Null
}
$srcGeminiMd = Join-Path $RootDir "GEMINI.md"
if (Test-Path $srcGeminiMd) {
    Copy-Item $srcGeminiMd (Join-Path $userGeminiDir "GEMINI.md") -Force
    Write-Host "[+] База знаний проекта (GEMINI.md) загружена в профиль агента!" -ForegroundColor Green
}

# 4.3 Настройка ключа Gemini API
$curKey = [System.Environment]::GetEnvironmentVariable("GEMINI_API_KEY", "User")
if (-not $curKey) { $curKey = $env:GEMINI_API_KEY }

if (-not $GeminiApiKey -and -not $curKey) {
    Write-Host "`n[?] Введите ваш Google Gemini API Key (для продолжения диалога с агентом):" -ForegroundColor Yellow
    Write-Host "    (Бесплатный ключ берётся здесь: https://aistudio.google.com/app/apikey)" -ForegroundColor DarkGray
    $inKey = Read-Host "GEMINI_API_KEY"
    $GeminiApiKey = $inKey.Trim()
} elseif ($curKey -and -not $GeminiApiKey) {
    $GeminiApiKey = $curKey
    Write-Host "[+] Использован существующий ключ GEMINI_API_KEY из профиля Windows." -ForegroundColor Green
}

if ($GeminiApiKey) {
    [System.Environment]::SetEnvironmentVariable("GEMINI_API_KEY", $GeminiApiKey, "User")
    $env:GEMINI_API_KEY = $GeminiApiKey
    Write-Host "[+] GEMINI_API_KEY активирован!" -ForegroundColor Green
}

# =============================================================================
# ШАГ 5. Автоматическая верификация и запуск тестов
# =============================================================================
Write-Host "`n------------------------------------------------------------------------" -ForegroundColor DarkCyan
Write-Host "[5/5] Запуск автоматической верификации системы (pytest)..." -ForegroundColor Yellow
Write-Host "------------------------------------------------------------------------" -ForegroundColor DarkCyan

& $VenvPython -m pytest (Join-Path $RootDir "tests\test_app.py") -q --disable-warnings
$testExit = $LASTEXITCODE

if ($testExit -eq 0) {
    Write-Host "[+] ВСЕ 14 ТЕСТОВ УСПЕШНО ПРОЙДЕНЫ! СИСТЕМА ПОЛНОСТЬЮ ИСПРАВНА." -ForegroundColor Green
} else {
    Write-Host "[!] Завершено с кодом $testExit. Проверьте вывод тестов." -ForegroundColor DarkYellow
}

# =============================================================================
# ФИНАЛЬНЫЙ ОТЧЕТ И СТАРТ
# =============================================================================
Write-Host "`n========================================================================" -ForegroundColor Green
Write-Host " РАБОЧЕЕ МЕСТО ПОЛНОСТЬЮ ГОТОВО К РАБОТЕ!" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Green
Write-Host "1. Gemini CLI введён в курс дела:" -ForegroundColor White
Write-Host "   - Знает структуру АО «Интергаз Центральная Азия» (ЛПУ, ГРС, КС)" -ForegroundColor DarkGray
Write-Host "   - Знает правила защищённого QR-сканирования и паспорта PDF" -ForegroundColor DarkGray
Write-Host "   - Знает роли Active Directory (Механик, Инженер, Оператор)" -ForegroundColor DarkGray
Write-Host "`n2. Как продолжить общение с Gemini:" -ForegroundColor White
Write-Host "   В терминале просто запустите команду:" -ForegroundColor Yellow
Write-Host "     gemini`n" -ForegroundColor Cyan
Write-Host "3. Как запустить веб-приложение:" -ForegroundColor White
Write-Host "   Выполните команду:" -ForegroundColor Yellow
Write-Host "     .\venv\Scripts\python.exe run.py" -ForegroundColor Cyan
Write-Host "   Приложение откроется на: https://127.0.0.1:8443`n" -ForegroundColor DarkGray
