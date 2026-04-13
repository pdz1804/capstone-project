# Start FastAPI from this folder (fixes ModuleNotFoundError: No module named 'app' when cwd is wrong).
# Usage: .\run_api.ps1
# Optional: .\run_api.ps1 --port 5001

param(
    [string]$Host = "0.0.0.0",
    [int]$Port = 5000,
    [int]$Workers = 1,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$pyCandidates = @(
    (Join-Path $PSScriptRoot "myenv\Scripts\python.exe"),
    (Join-Path $PSScriptRoot ".venv\Scripts\python.exe")
)
$py = $pyCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $py) {
    Write-Host "No myenv/.venv found in backend. Create one before running API." -ForegroundColor Red
    exit 1
}

$workerCount = [Math]::Max(1, $Workers)
$useReload = -not $NoReload.IsPresent -and $workerCount -eq 1

if ($useReload) {
    & $py -m uvicorn app.main:app --reload --host $Host --port $Port
} else {
    if ($workerCount -gt 1 -and -not $NoReload.IsPresent) {
        Write-Host "Workers > 1 requires no reload; starting without --reload." -ForegroundColor Yellow
    }
    & $py -m uvicorn app.main:app --host $Host --port $Port --workers $workerCount
}
