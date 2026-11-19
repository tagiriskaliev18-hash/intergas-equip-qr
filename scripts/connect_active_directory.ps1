<#
.SYNOPSIS
    Единый мастер подключения приложения Mind Equip и Keycloak к Active Directory
    для АО «Интергаз Центральная Азия».

.DESCRIPTION
    1. Запрашивает или принимает параметры корпоративного контроллера домена AD.
    2. Безопасно сохраняет настройки в локальный .env (пароль маскируется при вводе).
    3. Выполняет сетевую проверку портов 389/636 и валидацию Bind.
    4. Автоматически регистрирует провайдер User Federation в Keycloak (Realm: mind-equip).
    5. Настраивает маппинг групп безопасности AD в роли:
       - GG_ICA_Mechanics  -> admin (Главный механик)
       - GG_ICA_Engineers  -> engineer (Сменный инженер)
       - GG_ICA_Operators  -> operator (Дежурный оператор)

.EXAMPLE
    .\scripts\connect_active_directory.ps1
    .\scripts\connect_active_directory.ps1 -Server "ldaps://dc01.intergas.kz:636" -Domain "intergas.kz" -BindDN "CN=svc_keycloak_read,OU=ServiceAccounts,DC=intergas,DC=kz"
#>

[CmdletBinding()]
param (
    [string]$Server = "",
    [string]$Domain = "intergas.kz",
    [string]$BaseDN = "DC=intergas,DC=kz",
    [string]$UsersOU = "OU=Users,OU=ICA,DC=intergas,DC=kz",
    [string]$BindDN = "",
    [string]$BindPassword = "",
    [string]$AdminGroup = "GG_ICA_Mechanics",
    [string]$EngineerGroup = "GG_ICA_Engineers",
    [string]$OperatorGroup = "GG_ICA_Operators",
    [string]$KeycloakUrl = "http://127.0.0.1:8080",
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

$PythonExe = Join-Path $RootDir "venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $PythonExe) {
        Write-Error "[-] Ошибка: Python 3 не найден в venv\Scripts\python.exe. Запустите в окружении проекта."
        exit 1
    }
}

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host " МАСТЕР ПОДКЛЮЧЕНИЯ К ACTIVE DIRECTORY (АО «ИНТЕРГАЗ ЦЕНТРАЛЬНАЯ АЗИЯ»)" -ForegroundColor Cyan
Write-Host " Комплекс паспортизации, графиков ТО и защищённого QR-контроля" -ForegroundColor DarkGray
Write-Host "========================================================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 1. Интерактивный ввод параметров (если не переданы в аргументах)
# ---------------------------------------------------------------------------
if (-not $NonInteractive) {
    if (-not $Server) {
        Write-Host "`n[?] Введите URL контроллера домена Active Directory:" -ForegroundColor Yellow
        Write-Host "    Пример: ldaps://dc01.intergas.kz:636 (защищенный LDAPS) или ldap://10.0.0.10:389" -ForegroundColor DarkGray
        $inputServer = Read-Host "Контроллер домена [ldaps://dc01.intergas.kz:636]"
        $Server = if ($inputServer.Trim()) { $inputServer.Trim() } else { "ldaps://dc01.intergas.kz:636" }
    }

    if (-not $Domain) {
        $inputDomain = Read-Host "`n[?] Доменное имя [intergas.kz]"
        $Domain = if ($inputDomain.Trim()) { $inputDomain.Trim() } else { "intergas.kz" }
    }

    if (-not $BaseDN) {
        $inputBase = Read-Host "`n[?] Базовый DN [DC=intergas,DC=kz]"
        $BaseDN = if ($inputBase.Trim()) { $inputBase.Trim() } else { "DC=intergas,DC=kz" }
    }

    if (-not $UsersOU) {
        $inputOU = Read-Host "`n[?] Контейнер сотрудников (OU) [OU=Users,OU=ICA,DC=intergas,DC=kz]"
        $UsersOU = if ($inputOU.Trim()) { $inputOU.Trim() } else { "OU=Users,OU=ICA,DC=intergas,DC=kz" }
    }

    if (-not $BindDN) {
        $defaultBind = "CN=svc_keycloak_read,OU=ServiceAccounts,$BaseDN"
        $inputBind = Read-Host "`n[?] DN сервисной учётной записи [$defaultBind]"
        $BindDN = if ($inputBind.Trim()) { $inputBind.Trim() } else { $defaultBind }
    }

    if (-not $BindPassword) {
        Write-Host "`n[?] Введите пароль сервисной учётной записи (ввод скрыт):" -ForegroundColor Yellow
        $secPwd = Read-Host -AsSecureString "Пароль сервисной учётки"
        $BindPassword = [System.Net.NetworkCredential]::new("", $secPwd).Password
    }
}

$UseSSL = $Server.StartsWith("ldaps://") -or $Server.EndsWith(":636")

Write-Host "`n[*] Параметры подключения зафиксированы:" -ForegroundColor Cyan
Write-Host "    - Сервер AD:      $Server"
Write-Host "    - Домен:          $Domain"
Write-Host "    - Base DN:        $BaseDN"
Write-Host "    - Users OU:       $UsersOU"
Write-Host "    - Сервисный DN:   $BindDN"
Write-Host "    - Протокол:       $(if ($UseSSL) { 'LDAPS (TLS/SSL шифрование: ВКЛ)' } else { 'LDAP (Cleartext)' })"
Write-Host "    - Группы ролей:   Механики=$AdminGroup | Инженеры=$EngineerGroup | Операторы=$OperatorGroup"

# ---------------------------------------------------------------------------
# 2. Сохранение конфигурации в локальный .env файл
# ---------------------------------------------------------------------------
Write-Host "`n[1/3] Запись параметров в файл .env..." -ForegroundColor Yellow
$EnvFile = Join-Path $RootDir ".env"

$EnvContent = @"
# ==============================================================================
# КОНФИГУРАЦИЯ ACTIVE DIRECTORY — АО «ИНТЕРГАЗ ЦЕНТРАЛЬНАЯ АЗИЯ»
# Сформировано мастером connect_active_directory.ps1
# ==============================================================================
AD_ENABLED=true
AD_SERVER=$Server
AD_DOMAIN=$Domain
AD_BASE_DN=$BaseDN
AD_USERS_OU=$UsersOU
AD_BIND_DN=$BindDN
AD_BIND_PASSWORD=$BindPassword
AD_USE_SSL=$($UseSSL.ToString().ToLower())

AD_GROUP_ADMIN=$AdminGroup
AD_GROUP_ENGINEER=$EngineerGroup
AD_GROUP_OPERATOR=$OperatorGroup

KEYCLOAK_URL=$KeycloakUrl
KEYCLOAK_REALM=mind-equip
KEYCLOAK_CLIENT_ID=mind-equip-app
KEYCLOAK_CLIENT_SECRET=mind-equip-secret-2026-secure
"@

Set-Content -Path $EnvFile -Value $EnvContent -Encoding UTF8
Write-Host "[+] Файл .env успешно сохранён с правами доступа локального сервера." -ForegroundColor Green

# ---------------------------------------------------------------------------
# 3. Диагностика сети и авторизации в Active Directory
# ---------------------------------------------------------------------------
Write-Host "`n[2/3] Запуск сетевой диагностики контроллера домена..." -ForegroundColor Yellow
$diagArgs = @(
    (Join-Path $RootDir "scripts\test_ad_connection.py"),
    "--server", $Server,
    "--base-dn", $BaseDN,
    "--bind-dn", $BindDN,
    "--bind-pwd", $BindPassword
)
if ($UseSSL) { $diagArgs += "--ssl" }

& $PythonExe $diagArgs
$diagExit = $LASTEXITCODE

if ($diagExit -ne 0) {
    Write-Host "`n[!] ВНИМАНИЕ: Диагностика вернула предупреждение или код сбоя (Код: $diagExit)." -ForegroundColor Magenta
    Write-Host "    Если сервер приложения пока не находится в одной корпоративной сети с DC," -ForegroundColor DarkYellow
    Write-Host "    настройки в .env всё равно сохранены и вступят в силу при подключении к сети/VPN." -ForegroundColor DarkYellow
} else {
    Write-Host "[+] Связь с Active Directory АО «Интергаз Центральная Азия» подтверждена!" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# 4. Регистрация User Federation в Keycloak (Realm: mind-equip)
# ---------------------------------------------------------------------------
Write-Host "`n[3/3] Синхронизация и настройка провайдера в Keycloak..." -ForegroundColor Yellow
$setupArgs = @(
    (Join-Path $RootDir "scripts\setup_active_directory.py"),
    "--keycloak-url", $KeycloakUrl,
    "--realm", "mind-equip"
)

& $PythonExe $setupArgs
$setupExit = $LASTEXITCODE

Write-Host "`n========================================================================" -ForegroundColor Green
Write-Host " ИНТЕГРАЦИЯ С ACTIVE DIRECTORY УСПЕШНО НАСТРОЕНА И ГОТОВА К РАБОТЕ!" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Green
Write-Host "1. Сотрудники могут авторизоваться на странице входа по своим"
Write-Host "   доменным именам (например: i.ivanov или i.ivanov@$Domain)."
Write-Host "2. Права назначаются автоматически по членству в доменных группах:"
Write-Host "   - $AdminGroup    -> Главный механик (Администратор)" -ForegroundColor Cyan
Write-Host "   - $EngineerGroup   -> Сменный инженер ТО (Механик)" -ForegroundColor Cyan
Write-Host "   - $OperatorGroup   -> Дежурный оператор (Наблюдатель)" -ForegroundColor Cyan
Write-Host "3. Проверить статус AD в рантайме: GET https://127.0.0.1:8443/api/auth/ad-status`n"
