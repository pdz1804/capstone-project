# Run BK-MInD frontend from this folder (correct Vite root + port).
# Default URL: http://localhost:5173  (set PORT=3000 in .env only if you know nothing else uses it)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path "node_modules")) {
    Write-Host "Run: npm install" -ForegroundColor Yellow
    exit 1
}
npm run dev
