@echo off
setlocal
REM Prefer backend\.venv (see ..\scripts\setup.ps1), then MYENV_PYTHON, then Code\myenv.

set "BACKEND_DIR=%~dp0"
set "PY=%BACKEND_DIR%.venv\Scripts\python.exe"

if not exist "%PY%" (
  if defined MYENV_PYTHON (
    set "PY=%MYENV_PYTHON%"
  ) else (
    for %%I in ("%BACKEND_DIR%..\..") do set "CODE_ROOT=%%~fI"
    set "PY=%CODE_ROOT%\myenv\Scripts\python.exe"
  )
)

if not exist "%PY%" (
  echo No Python found. Run ..\scripts\setup.ps1 or set MYENV_PYTHON.
  exit /b 1
)

echo Using: %PY%
pushd "%BACKEND_DIR%"
"%PY%" -m pytest %*
set "EC=%ERRORLEVEL%"
popd
exit /b %EC%
