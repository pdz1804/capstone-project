# Phase_2_FE_AI_Merge   create backend venv, install Python + npm deps, run unit tests.
#
# Usage (PowerShell, from repo):
#   cd Phase_2_FE_AI_Merge\scripts
#   .\setup.ps1
#   .\setup.ps1 -SkipTests        # deps only
#   .\setup.ps1 -SkipFrontend     # backend + tests only
#
# If execution policy blocks scripts:
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1

param(
    [switch]$SkipTests,
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$MergeRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Backend = Join-Path $MergeRoot "backend"
$Frontend = Join-Path $MergeRoot "frontend"
$VenvDir = Join-Path $Backend ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

if (-not (Test-Path $Backend)) {
    Write-Host "Backend folder not found: $Backend" -ForegroundColor Red
    exit 1
}

Write-Step "Backend venv: $VenvDir"
if (-not (Test-Path $VenvPython)) {
    $created = $false
    foreach ($venvArgs in @(
            @("-3.12", "-m", "venv", $VenvDir),
            @("-3", "-m", "venv", $VenvDir),
            @("-m", "venv", $VenvDir)
        )) {
        try {
            Write-Host "Trying: py $($venvArgs -join ' ')"
            & py @venvArgs
            if (Test-Path $VenvPython) { $created = $true; break }
        }
        catch { }
    }
    if (-not $created) {
        try {
            Write-Host "Trying: python -m venv"
            & python -m venv $VenvDir
            if (Test-Path $VenvPython) { $created = $true }
        }
        catch { }
    }
    if (-not $created -or -not (Test-Path $VenvPython)) {
        Write-Host "Could not create venv. Install Python 3.11+ and ensure 'py' or 'python' is on PATH." -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "Venv already exists."
}

Write-Step "Upgrade pip & install backend requirements"
Push-Location $Backend
try {
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r requirements.txt
}
finally {
    Pop-Location
}

if (-not $SkipFrontend) {
    if (-not (Test-Path $Frontend)) {
        Write-Host "Frontend folder missing; skipping npm." -ForegroundColor Yellow
    }
    else {
        Write-Step "Frontend npm install"
        Push-Location $Frontend
        try {
            if (Get-Command npm -ErrorAction SilentlyContinue) {
                npm install
            }
            else {
                Write-Host "npm not found on PATH; install Node.js LTS and re-run without -SkipFrontend." -ForegroundColor Yellow
            }
        }
        finally {
            Pop-Location
        }
    }
}

if (-not $SkipTests) {
    Write-Step "Backend unit tests (pytest)"
    Push-Location $Backend
    try {
        & $VenvPython -m pytest tests -q --tb=short
        if ($LASTEXITCODE -ne 0) {
            Write-Host "pytest exited with $LASTEXITCODE" -ForegroundColor Red
            exit $LASTEXITCODE
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Done. Activate backend venv:" -ForegroundColor Green
Write-Host "  $($VenvDir)\Scripts\Activate.ps1"
Write-Host "Run API:  cd $Backend; .\run_api.ps1"
Write-Host "          (must run from Phase_2_FE_AI_Merge\backend   not Code\backend)"
Write-Host "Run UI:   cd frontend; npm run dev"
Write-Host ""
Write-Host "AWS / .env checklist (see assistant message or backend/.env.example):" -ForegroundColor DarkGray
Write-Host "  - DynamoDB table (users), S3 bucket(s) if FILE_STORAGE_BACKEND=s3, Qdrant, Bedrock/SageMaker IAM, Firebase key"
