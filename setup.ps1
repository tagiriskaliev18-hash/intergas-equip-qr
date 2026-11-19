# Мастер развертывания проекта и настройки Gemini на рабочем компьютере
# АО «Интергаз Центральная Азия»
param([Parameter(ValueFromRemainingArguments = $true)]$allArgs)
$ScriptPath = Join-Path $PSScriptRoot "scripts\setup_workstation.ps1"
& powershell.exe -ExecutionPolicy Bypass -NoProfile -File $ScriptPath @allArgs
