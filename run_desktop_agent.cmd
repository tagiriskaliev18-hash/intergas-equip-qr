@echo off
title Mind Universal AI Assistant // Windows Automation
cd /d "%~dp0"

if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" "%~dp0scripts\mind_desktop_agent.py" %*
    goto :done
)

if exist "C:\Program Files\Python311\python.exe" (
    "C:\Program Files\Python311\python.exe" "%~dp0scripts\mind_desktop_agent.py" %*
    goto :done
)

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    py "%~dp0scripts\mind_desktop_agent.py" %*
    goto :done
)

python "%~dp0scripts\mind_desktop_agent.py" %*

:done
if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Process exited with code %ERRORLEVEL%. Press any key to close...
    pause >nul
)
