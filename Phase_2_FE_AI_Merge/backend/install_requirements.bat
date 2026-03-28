@echo off
REM Same as install_requirements.ps1 — uses Code\myenv\Scripts\python.exe
setlocal
set "BACKEND=%~dp0"
set "CODE=%BACKEND%..\.."
for %%I in ("%CODE%") do set "CODE=%%~fI"
set "PY=%CODE%\myenv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: Not found: %PY%
  echo Set MYENV_PYTHON to your venv python.exe, or create myenv under: %CODE%
  exit /b 1
)
echo Using: %PY%
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r "%BACKEND%requirements.txt"
echo Done.
