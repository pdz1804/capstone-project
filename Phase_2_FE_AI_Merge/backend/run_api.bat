@echo off
REM Run API from this directory (avoids "No module named 'app'").
cd /d "%~dp0"

set "PY_BIN="
if exist "myenv\Scripts\python.exe" set "PY_BIN=myenv\Scripts\python.exe"
if "%PY_BIN%"=="" if exist ".venv\Scripts\python.exe" set "PY_BIN=.venv\Scripts\python.exe"

if "%PY_BIN%"=="" (
  echo No myenv/.venv found in backend. Create one first.
  exit /b 1
)

if "%RUN_API_WORKERS%"=="" set "RUN_API_WORKERS=1"

if "%RUN_API_WORKERS%"=="1" (
  "%PY_BIN%" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
) else (
  "%PY_BIN%" -m uvicorn app.main:app --host 0.0.0.0 --port 5000 --workers %RUN_API_WORKERS%
)
