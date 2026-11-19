<#
.SYNOPSIS
    Bootstrap-скрипт нулевого развёртывания для АО «Интергаз Центральная Азия».
    Скачивает проект с GitHub, ставит зависимости, настраивает Active Directory
    и обучает Gemini CLI полному контексту проекта.

.DESCRIPTION
    Запуск в чистом PowerShell (без предварительной установки Git):
    irm https://raw.githubusercontent.com/tagiriskaliev18-hash/intergas-equip-qr/main/bootstrap.ps1 | iex
#>

$ErrorActionPreference = "Continue"

Write-Host "`n========================================================================" -ForegroundColor Cyan
Write-Host " АВТОМАТИЧЕСКИЙ ЗАГРУЗЧИК // АО «ИНТЕРГАЗ ЦЕНТРАЛЬНАЯ АЗИЯ»" -ForegroundColor Cyan
Write-Host " Комплекс паспортизации оборудования ЛПУ, ГРС, КС и Gemini CLI" -ForegroundColor DarkGray
Write-Host "========================================================================`n" -ForegroundColor Cyan

# 1. Определение целевой папки на Рабочем столе
$DesktopDir = [Environment]::GetFolderPath("Desktop")
$TargetDir = Join-Path $DesktopDir "QRcode"

Write-Host "[*] Целевая папка проекта: $TargetDir" -ForegroundColor Yellow

if (Test-Path $TargetDir) {
    Write-Host "[!] Папка $TargetDir уже существует. Обновление файлов..." -ForegroundColor DarkYellow
} else {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}

# 2. Получение исходных файлов с GitHub (через Git или ZIP)
$RepoUrl = "https://github.com/tagiriskaliev18-hash/intergas-equip-qr"
$gitCmd = Get-Command git -ErrorAction SilentlyContinue

$downloadSuccess = $false

if ($gitCmd) {
    Write-Host "[*] Обнаружен Git. Клонирование репозитория..." -ForegroundColor Yellow
    if (Test-Path (Join-Path $TargetDir ".git")) {
        Push-Location $TargetDir
        & git pull origin main
        Pop-Location
        $downloadSuccess = $true
    } else {
        & git clone "$RepoUrl.git" $TargetDir
        if ($LASTEXITCODE -eq 0) { $downloadSuccess = $true }
    }
}

if (-not $downloadSuccess) {
    Write-Host "[*] Скачивание архива проекта с GitHub..." -ForegroundColor Yellow
    $zipUrl = "$RepoUrl/archive/refs/heads/main.zip"
    $tempZip = Join-Path $env:TEMP "intergas-equip-main.zip"
    $tempExtract = Join-Path $env:TEMP "intergas-equip-extract"

    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $zipUrl -OutFile $tempZip -UseBasicParsing
        if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
        Expand-Archive -Path $tempZip -DestinationPath $tempExtract -Force
        
        $innerFolder = Join-Path $tempExtract "intergas-equip-qr-main"
        if (Test-Path $innerFolder) {
            Copy-Item -Path "$innerFolder\*" -Destination $TargetDir -Recurse -Force
        }
        Remove-Item $tempZip -Force -ErrorAction SilentlyContinue
        Remove-Item $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
        $downloadSuccess = $true
        Write-Host "[+] Проект успешно распакован в $TargetDir!" -ForegroundColor Green
    } catch {
        Write-Error "[-] Ошибка скачивания с GitHub: $_"
        exit 1
    }
}

# 3. Переход в папку проекта и запуск комплексного мастера установки
Set-Location $TargetDir
$SetupScript = Join-Path $TargetDir "setup.ps1"

if (Test-Path $SetupScript) {
    Write-Host "`n[*] Запуск встроенного мастера настройки (setup.ps1)..." -ForegroundColor Cyan
    & $SetupScript
} else {
    Write-Error "[-] Ошибка: Файл setup.ps1 не найден в $TargetDir."
    exit 1
}
