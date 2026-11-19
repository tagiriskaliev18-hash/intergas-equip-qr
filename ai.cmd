@echo off
if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" "%~dp0scripts\ai_chat.py" %*
) else (
    python "%~dp0scripts\ai_chat.py" %*
)
