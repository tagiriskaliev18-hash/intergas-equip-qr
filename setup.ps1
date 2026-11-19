# Master setup for AO Intergas Central Asia (Admin Mode)
param([Parameter(ValueFromRemainingArguments = $true)]$allArgs)
$ScriptPath = Join-Path $PSScriptRoot "scripts\setup_admin.ps1"
& powershell.exe -ExecutionPolicy Bypass -NoProfile -File $ScriptPath @allArgs
