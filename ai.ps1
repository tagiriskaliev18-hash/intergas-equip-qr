# Терминальный AI-ассистент проекта Интергаз Центральная Азия
# Подключен к SmartAPI с моделями Gemini 3.8 Flash, Claude Opus 5.5, DeepSeek
param([Parameter(ValueFromRemainingArguments = $true)]$args)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ScriptDir "venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    $PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $PythonExe) {
        Write-Error "[-] Python не найден. Запустите сначала .\setup.ps1"
        exit 1
    }
}

$ChatScript = Join-Path $ScriptDir "scripts\ai_chat.py"
& $PythonExe $ChatScript @args
