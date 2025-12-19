#!/bin/bash

# LaTeX Compilation Script
# Compiles main.tex with proper bibliography handling

# Change to script directory
cd "$(dirname "$0")"

echo "=========================================="
echo "Compiling LaTeX document..."
echo "=========================================="

# Step 1: First pdflatex pass
echo ""
echo "[1/4] Running pdflatex (first pass)..."
if ! pdflatex -interaction=nonstopmode main.tex > /tmp/pdflatex1.log 2>&1; then
    echo "❌ Error: pdflatex failed"
    if [ -f main.log ]; then
        echo "Last 30 lines of main.log:"
        tail -30 main.log
    else
        echo "Last 30 lines of output:"
        tail -30 /tmp/pdflatex1.log
    fi
    exit 1
fi
echo "✓ First pass complete"

# Step 2: Run biber for bibliography
echo ""
echo "[2/4] Running biber for bibliography..."
if ! biber main > /tmp/biber.log 2>&1; then
    echo "⚠ Warning: biber had issues (this might be okay if no citations changed)"
    echo "Check /tmp/biber.log for details"
else
    echo "✓ Bibliography processed"
fi

# Step 3: Second pdflatex pass
echo ""
echo "[3/4] Running pdflatex (second pass)..."
if ! pdflatex -interaction=nonstopmode main.tex > /tmp/pdflatex2.log 2>&1; then
    echo "❌ Error: pdflatex failed"
    if [ -f main.log ]; then
        echo "Last 30 lines of main.log:"
        tail -30 main.log
    else
        echo "Last 30 lines of output:"
        tail -30 /tmp/pdflatex2.log
    fi
    exit 1
fi
echo "✓ Second pass complete"

# Step 4: Third pdflatex pass (to resolve all references)
echo ""
echo "[4/4] Running pdflatex (final pass)..."
if ! pdflatex -interaction=nonstopmode main.tex > /tmp/pdflatex3.log 2>&1; then
    echo "❌ Error: pdflatex failed"
    if [ -f main.log ]; then
        echo "Last 30 lines of main.log:"
        tail -30 main.log
    else
        echo "Last 30 lines of output:"
        tail -30 /tmp/pdflatex3.log
    fi
    exit 1
fi
echo "✓ Final pass complete"

echo ""
echo "=========================================="
echo "✓ Compilation complete!"
echo "Output: main.pdf"
echo "=========================================="
