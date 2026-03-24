@echo off
setlocal
REM Run backend unit tests with Code\myenv\Scripts\python.exe (or MYENV_PYTHON).
REM Usage (from backend folder): run_tests.bat
REM   run_tests.bat
REM   run_tests.bat tests\api

set "BACKEND_DIR=%~dp0"
for %%I in ("%BACKEND_DIR%..\..") do set "CODE_ROOT=%%~fI"

if defined MYENV_PYTHON (
  set "PY=%MYENV_PYTHON%"
) else (
  set "PY=%CODE_ROOT%\myenv\Scripts\python.exe"
)

if not exist "%PY%" (
  echo Could not find Python: %PY%
  echo Set MYENV_PYTHON to your venv's python.exe.
  exit /b 1
)

echo Using: %PY%
pushd "%BACKEND_DIR%"
"%PY%" -m pytest %*
set "EC=%ERRORLEVEL%"
popd
exit /b %EC%
