@echo off
title AI Agent // AO Intergas Central Asia
chcp 65001 >nul
cd /d "%~dp0"
if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" "%~dp0scripts\ai_agent.py" %*
) else (
    python "%~dp0scripts\ai_agent.py" %*
)
pause
