# LaTeX Compilation Script for Windows PowerShell
# Compiles main.tex with proper bibliography handling

$ErrorActionPreference = "Continue"

Write-Host "=========================================="
Write-Host "Compiling LaTeX document..."
Write-Host "=========================================="

# Step 0: Clean up auxiliary files
Write-Host ""
Write-Host "[1/5] Cleaning up auxiliary files..."
if (Test-Path "main.aux") {
    Remove-Item "main.aux"
    Write-Host " - Removed main.aux"
}
if (Test-Path "_heading/*.aux") {
    Remove-Item "_heading/*.aux"
    Write-Host " - Removed .aux files from _heading/"
}
Write-Host " - Cleanup complete"

# Step 1: First pdflatex pass
Write-Host ""
Write-Host "[2/5] Running pdflatex (first pass)..."
& pdflatex -interaction=nonstopmode -shell-escape main.tex
if ($LASTEXITCODE -ne 0) {
    Write-Host " ! Warning: pdflatex returned non-zero exit code"
}
Write-Host " - First pass complete"

# Step 2: Run biber for bibliography
Write-Host ""
Write-Host "[3/5] Running biber for bibliography..."
& biber main
if ($LASTEXITCODE -ne 0) {
    Write-Host " ! Warning: biber had issues (this might be okay if no citations changed)"
} else {
    Write-Host " - Bibliography processed"
}

# Step 3: Second pdflatex pass
Write-Host ""
Write-Host "[4/5] Running pdflatex (second pass)..."
& pdflatex -interaction=nonstopmode -shell-escape main.tex
Write-Host " - Second pass complete"

# Step 4: Third pdflatex pass (to resolve all references)
Write-Host ""
Write-Host "[5/5] Running pdflatex (final pass)..."
& pdflatex -interaction=nonstopmode -shell-escape main.tex
Write-Host " - Final pass complete"

Write-Host ""
Write-Host "=========================================="
Write-Host "Compilation complete!"
Write-Host "Output: main.pdf"
Write-Host "=========================================="
