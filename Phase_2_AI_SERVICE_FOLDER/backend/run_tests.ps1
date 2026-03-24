# Run backend unit tests with the repo's shared virtualenv "myenv".
# Layout:  Code/myenv/Scripts/python.exe
#          Code/Phase_2_AI_SERVICE_FOLDER/backend/  (this script lives here)
#
# Usage (PowerShell, from backend folder):
#   .\run_tests.ps1
#   .\run_tests.ps1 -m "unit"
#   .\run_tests.ps1 tests\api
#
# Or set a custom interpreter:
#   $env:MYENV_PYTHON = "D:\path\to\myenv\Scripts\python.exe"
#   .\run_tests.ps1

$ErrorActionPreference = "Stop"
$BackendDir = $PSScriptRoot
$CodeRoot = (Resolve-Path (Join-Path $BackendDir "..\..")).Path

$PythonExe = $env:MYENV_PYTHON
if (-not $PythonExe) {
    $Candidate = Join-Path $CodeRoot "myenv\Scripts\python.exe"
    if (Test-Path $Candidate) {
        $PythonExe = $Candidate
    }
}

if (-not $PythonExe -or -not (Test-Path $PythonExe)) {
    Write-Host "Could not find myenv Python." -ForegroundColor Red
    Write-Host "Expected: $(Join-Path $CodeRoot 'myenv\Scripts\python.exe')" -ForegroundColor Yellow
    Write-Host "Set MYENV_PYTHON to your venv's python.exe and run again." -ForegroundColor Yellow
    exit 1
}

Write-Host "Using: $PythonExe" -ForegroundColor Cyan
Push-Location $BackendDir
try {
    & $PythonExe -m pytest @args
} finally {
    Pop-Location
}
