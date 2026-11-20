@echo off
title MIND CLI
cd /d "%~dp0"

if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" "%~dp0scripts\mind_cli.py" %*
    goto :done
)

if exist "C:\Program Files\Python311\python.exe" (
    "C:\Program Files\Python311\python.exe" "%~dp0scripts\mind_cli.py" %*
    goto :done
)

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    py "%~dp0scripts\mind_cli.py" %*
    goto :done
)

python "%~dp0scripts\mind_cli.py" %*

:done
if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Session exited with code %ERRORLEVEL%. Press any key...
    pause >nul
)
