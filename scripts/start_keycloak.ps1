# Start Keycloak 26.0.7 in Dev Mode with Auto-Imported Mind-Equip Realm
$ErrorActionPreference = "Stop"

$jdkPath = "C:\Program Files\Microsoft\jdk-17.0.21.21-hotspot"
if (Test-Path $jdkPath) {
    $env:JAVA_HOME = $jdkPath
    $env:PATH = "$jdkPath\bin;$env:PATH"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$kcBat = Join-Path $projectRoot "tools\keycloak-26.0.7\bin\kc.bat"
$importDir = Join-Path $projectRoot "tools\keycloak-26.0.7\data\import"

if (-not (Test-Path $importDir)) {
    New-Item -ItemType Directory -Force -Path $importDir | Out-Null
}
Copy-Item (Join-Path $projectRoot "config\keycloak-realm.json") (Join-Path $importDir "keycloak-realm.json") -Force

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting Keycloak 26.0.7 on http://0.0.0.0:8080" -ForegroundColor Green
Write-Host "  Realm:      mind-equip" -ForegroundColor White
Write-Host "  Client ID:  mind-equip-app" -ForegroundColor White
Write-Host "  Accounts:   admin / admin123" -ForegroundColor Yellow
Write-Host "              engineer / engineer123" -ForegroundColor Yellow
Write-Host "              operator / operator123" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

$env:KEYCLOAK_ADMIN = "admin"
$env:KEYCLOAK_ADMIN_PASSWORD = "admin"

& $kcBat start-dev --import-realm --http-port=8080 --http-host=0.0.0.0
