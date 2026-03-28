@echo off
REM Run API from this directory (avoids "No module named 'app'").
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run ..\scripts\setup.ps1 first to create .venv
  exit /b 1
)
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
