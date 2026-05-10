#!/bin/bash

# LaTeX Compilation Script
# Compiles main.tex with proper bibliography handling

# Change to script directory
cd "$(dirname "$0")"

show_latex_error() {
    local logfile="$1"

    if [ -f "$logfile" ]; then
        echo "Relevant errors from $logfile:"
        grep -nE "^!|^l\\.|Fatal error|Runaway argument|File ended while scanning|Text line contains an invalid character|Undefined control sequence|LaTeX Error|Package .* Error" "$logfile" | head -40
        echo ""
        echo "Last 30 lines of $logfile:"
        tail -30 "$logfile"
    else
        echo "No log file found at $logfile"
    fi
}

run_pdflatex() {
    local label="$1"
    local output_log="$2"
    local retry_log

    echo "$label"
    if ! pdflatex -interaction=nonstopmode main.tex > "$output_log" 2>&1; then
        if grep -qE "File ended while scanning use of \\\\@writefile|Text line contains an invalid character" "$output_log"; then
            echo "⚠ Auxiliary file read failed; retrying pdflatex..."
            for attempt in 1 2; do
                retry_log="${output_log%.log}-retry${attempt}.log"
                if pdflatex -interaction=nonstopmode main.tex > "$retry_log" 2>&1; then
                    echo "✓ Retry succeeded"
                    return 0
                fi
                if ! grep -qE "File ended while scanning use of \\\\@writefile|Text line contains an invalid character" "$retry_log"; then
                    output_log="$retry_log"
                    break
                fi
                output_log="$retry_log"
            done
        fi

        echo "❌ Error: pdflatex failed"
        show_latex_error "$output_log"
        exit 1
    fi
}

echo "=========================================="
echo "Compiling LaTeX document..."
echo "=========================================="

# Step 0: Clean up auxiliary files
echo ""
echo "[1/4] Cleaning up auxiliary files..."
rm -f main.aux main.bbl main.bcf main.blg main.fdb_latexmk main.fls main.lof \
      main.log main.lot main.out main.run.xml main.toc main.synctex.gz \
      main.synctex.gz\(busy\)
echo "✓ Removed main auxiliary files"
if [ -d _heading ]; then
    rm -f _heading/*.aux
    echo "✓ Removed .aux files from _heading/"
fi
echo "✓ Cleanup complete"

# Step 1: First pdflatex pass
echo ""
run_pdflatex "[2/4] Running pdflatex (first pass)..." /tmp/pdflatex1.log
echo "✓ First pass complete"

# Step 2: Run biber for bibliography
echo ""
echo "[3/4] Running biber for bibliography..."
if ! biber main > /tmp/biber.log 2>&1; then
    echo "❌ Error: biber failed"
    echo "Last 40 lines of /tmp/biber.log:"
    tail -40 /tmp/biber.log
    exit 1
fi
echo "✓ Bibliography processed"

# Step 3: Second pdflatex pass (resolves citations and cross-references)
echo ""
run_pdflatex "[4/4] Running pdflatex (final pass)..." /tmp/pdflatex2.log
echo "✓ Final pass complete"

echo ""
echo "=========================================="
echo "✓ Compilation complete!"
echo "Output: main.pdf"
echo "=========================================="
