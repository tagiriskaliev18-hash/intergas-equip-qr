# Bootstrap installer for Intergas Central Asia Equipment QR & Maintenance
# Zero-dependency setup for Windows PowerShell 5.1 and 7+
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ErrorActionPreference = 'Continue'

Write-Host ''
Write-Host '========================================================================' -ForegroundColor Cyan
Write-Host ' AUTOMATED BOOTSTRAP // AO INTERGAS CENTRAL ASIA' -ForegroundColor Cyan
Write-Host ' Equipment Passports, Maintenance & Gemini CLI' -ForegroundColor DarkGray
Write-Host '========================================================================' -ForegroundColor Cyan
Write-Host ''

$DesktopDir = [Environment]::GetFolderPath('Desktop')
$TargetDir = Join-Path $DesktopDir 'QRcode'

Write-Host ('[*] Target project folder: ' + $TargetDir) -ForegroundColor Yellow

if (-not (Test-Path $TargetDir)) {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}

$RepoUrl = 'https://github.com/tagiriskaliev18-hash/intergas-equip-qr'
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
$downloadSuccess = $false

if ($gitCmd) {
    Write-Host '[*] Git found. Cloning repository...' -ForegroundColor Yellow
    if (Test-Path (Join-Path $TargetDir '.git')) {
        Push-Location $TargetDir
        & git pull origin main
        Pop-Location
        $downloadSuccess = $true
    } else {
        & git clone ($RepoUrl + '.git') $TargetDir
        if ($LASTEXITCODE -eq 0) { $downloadSuccess = $true }
    }
}

if (-not $downloadSuccess) {
    Write-Host '[*] Downloading project ZIP archive from GitHub...' -ForegroundColor Yellow
    $zipUrl = $RepoUrl + '/archive/refs/heads/main.zip'
    $tempZip = Join-Path $env:TEMP 'intergas-equip-main.zip'
    $tempExtract = Join-Path $env:TEMP 'intergas-equip-extract'

    try {
        Invoke-WebRequest -Uri $zipUrl -OutFile $tempZip -UseBasicParsing
        if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
        Expand-Archive -Path $tempZip -DestinationPath $tempExtract -Force

        $innerFolder = Join-Path $tempExtract 'intergas-equip-qr-main'
        if (Test-Path $innerFolder) {
            Copy-Item -Path ($innerFolder + '\*') -Destination $TargetDir -Recurse -Force
        }
        Remove-Item $tempZip -Force -ErrorAction SilentlyContinue
        Remove-Item $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
        $downloadSuccess = $true
        Write-Host ('[+] Project successfully extracted into ' + $TargetDir) -ForegroundColor Green
    } catch {
        Write-Error ('[-] Download error from GitHub: ' + $_)
        exit 1
    }
}

Set-Location $TargetDir
$SetupScript = Join-Path $TargetDir 'setup.ps1'

if (Test-Path $SetupScript) {
    Write-Host '[*] Launching project setup (setup.ps1)...' -ForegroundColor Cyan
    & powershell.exe -ExecutionPolicy Bypass -File $SetupScript
} else {
    Write-Error ('[-] Error: setup.ps1 not found in ' + $TargetDir)
    exit 1
}
