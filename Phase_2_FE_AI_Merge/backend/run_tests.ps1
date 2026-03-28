# Run backend tests using, in order:
#   1) backend\.venv\Scripts\python.exe (created by ../scripts/setup.ps1)
#   2) $env:MYENV_PYTHON
#   3) Code\myenv\Scripts\python.exe (legacy layout)
#
# Usage (from this backend folder):
#   .\run_tests.ps1
#   .\run_tests.ps1 -m unit
#   .\run_tests.ps1 tests\api

$ErrorActionPreference = "Stop"
$BackendDir = $PSScriptRoot

$PythonExe = $null
$LocalVenv = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (Test-Path $LocalVenv) {
    $PythonExe = $LocalVenv
}
if (-not $PythonExe -and $env:MYENV_PYTHON -and (Test-Path $env:MYENV_PYTHON)) {
    $PythonExe = $env:MYENV_PYTHON
}
if (-not $PythonExe) {
    $CodeRoot = (Resolve-Path (Join-Path $BackendDir "..\..")).Path
    $Legacy = Join-Path $CodeRoot "myenv\Scripts\python.exe"
    if (Test-Path $Legacy) { $PythonExe = $Legacy }
}

if (-not $PythonExe -or -not (Test-Path $PythonExe)) {
    Write-Host "No Python found. Run ..\scripts\setup.ps1 first, or set MYENV_PYTHON." -ForegroundColor Red
    exit 1
}

Write-Host "Using: $PythonExe" -ForegroundColor Cyan
Push-Location $BackendDir
try {
    & $PythonExe -m pytest @args
} finally {
    Pop-Location
}
