# Start FastAPI from this folder (fixes ModuleNotFoundError: No module named 'app' when cwd is wrong).
# Usage: .\run_api.ps1
# Optional: .\run_api.ps1 --port 8001

param(
    [string]$Host = "0.0.0.0",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "No .venv found. Run ..\scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}

& $py -m uvicorn app.main:app --reload --host $Host --port $Port
