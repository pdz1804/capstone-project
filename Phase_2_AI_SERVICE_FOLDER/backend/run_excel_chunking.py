#!/usr/bin/env python3
"""
Run Excel Chunking Pipeline (Parse → Chunk → Inspect)

This script tests the CHUNKING part of the Excel pipeline:
  1. Reads parsed Excel JSON from output/excel/
  2. Runs table-aware chunking (ExcelTableChunker)
  3. Runs the ExcelPreprocessor to produce RAG-ready output
  4. Prints detailed results for inspection

Usage:
    # Chunk a single file
    python run_excel_chunking.py --json output/excel/courseware.json

    # Chunk all JSON files in a directory
    python run_excel_chunking.py --json-dir output/excel/

    # Also run xlsx_reader_v2 first (parse from raw Excel)
    python run_excel_chunking.py --raw raw/excel/courseware.xlsx

    # Adjust chunking parameters
    python run_excel_chunking.py --json output/excel/courseware.json \
        --chunk-size 500 --chunk-overlap 100 --max-table-chunk 1500
"""

import argparse
import json
import logging
import sys
import textwrap
from pathlib import Path
from datetime import datetime

# ── Setup path so we can import from src/ ──
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "src"))

from chunking.excel_chunker import ExcelTableChunker, ExcelChunkingConfig, chunk_excel_json
from chunking.excel_preprocessor import ExcelPreprocessor, preprocess_excel_for_rag

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("run_excel_chunking")

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output" / "excel"
RAG_READY_DIR = BASE_DIR / "rag_ready"


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def load_json(json_path: Path) -> list:
    """Load parsed Excel JSON (list of sheet dicts)."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a list of sheet dicts, got {type(data).__name__}")
    return data


def print_separator(title: str, char: str = "═", width: int = 80):
    print(f"\n{char * width}")
    print(f"  {title}")
    print(f"{char * width}")


def print_chunk_detail(chunk: dict, index: int, verbose: bool = True):
    """Pretty-print a single chunk."""
    meta = chunk.get("metadata", {})
    text = chunk.get("text", "")
    
    is_table = meta.get("is_table", False)
    sheet = meta.get("sheet_name", "?")
    char_len = meta.get("char_length", len(text))
    
    icon = "📊" if is_table else "📝"
    print(f"\n  {icon} Chunk {index}: {chunk.get('id', '?')}")
    print(f"     Sheet: {sheet} | Type: {'TABLE' if is_table else 'TEXT'} | Chars: {char_len}")
    print(f"     Images: {meta.get('image_paths', [])}" if meta.get("has_images") else "")
    
    if verbose:
        preview = text[:300].replace("\n", "\n     │ ")
        print(f"     ┌─ Content Preview ─────────────────────────")
        print(f"     │ {preview}")
        if len(text) > 300:
            print(f"     │ ... ({len(text) - 300} more chars)")
        print(f"     └──────────────────────────────────────────")


# ──────────────────────────────────────────────────────────────────
# Chunking-only mode
# ──────────────────────────────────────────────────────────────────

def run_chunking_only(json_path: Path, chunk_size: int, chunk_overlap: int,
                      max_table_chunk: int, verbose: bool):
    """Run chunker directly on parsed JSON and print results."""
    sheets = load_json(json_path)
    doc_id = json_path.stem

    print_separator(f"CHUNKING: {json_path.name}  ({len(sheets)} sheets)")

    # Show sheet overview
    for i, sheet in enumerate(sheets):
        name = sheet.get("sheet_name", f"Sheet{i}")
        content_len = len(sheet.get("content", ""))
        print(f"  Sheet {i}: '{name}'   {content_len:,} chars")

    # Run chunker
    chunks = chunk_excel_json(
        sheets,
        doc_id=doc_id,
        source=str(json_path),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        max_table_chunk_size=max_table_chunk,
    )

    print_separator(f"RESULTS: {len(chunks)} chunks produced")

    table_chunks = [c for c in chunks if c.get("metadata", {}).get("is_table")]
    text_chunks = [c for c in chunks if not c.get("metadata", {}).get("is_table")]
    image_chunks = [c for c in chunks if c.get("metadata", {}).get("has_images")]

    print(f"  📊 Table chunks : {len(table_chunks)}")
    print(f"  📝 Text chunks  : {len(text_chunks)}")
    print(f"  🖼️  With images  : {len(image_chunks)}")
    print(f"  📏 Avg chars    : {sum(len(c['text']) for c in chunks) / max(len(chunks), 1):.0f}")

    # Print each chunk
    for i, chunk in enumerate(chunks):
        print_chunk_detail(chunk, i, verbose=verbose)

    return chunks


# ──────────────────────────────────────────────────────────────────
# Preprocessor mode (full RAG-ready output)
# ──────────────────────────────────────────────────────────────────

def run_preprocessor(json_path: Path, chunk_size: int, chunk_overlap: int,
                     max_table_chunk: int, rag_output_dir: Path, verbose: bool):
    """Run full ExcelPreprocessor (chunk + write RAG-ready dir)."""
    print_separator(f"PREPROCESSOR: {json_path.name}")

    summary = preprocess_excel_for_rag(
        json_path=json_path,
        output_dir=rag_output_dir,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        max_table_chunk_size=max_table_chunk,
    )

    print(f"  doc_id     : {summary['doc_id']}")
    print(f"  sheets     : {summary['num_sheets']}")
    print(f"  chunks     : {summary['num_chunks']}")
    print(f"  images     : {summary['num_images']}")
    print(f"  output_dir : {summary['output_folder']}")

    # Show generated files
    out = Path(summary["output_folder"])
    print(f"\n  Generated files:")
    for f in sorted(out.rglob("*")):
        if f.is_file():
            size = f.stat().st_size
            print(f"    {f.relative_to(out)}  ({size:,} bytes)")

    # Load and show chunk summary from saved JSON
    chunks_file = out / "excel_chunks.json"
    if chunks_file.exists() and verbose:
        with open(chunks_file, "r", encoding="utf-8") as f:
            chunk_data = json.load(f)
        chunks = chunk_data.get("chunks", [])
        print_separator(f"CHUNK DETAILS ({len(chunks)} chunks)")
        for i, chunk in enumerate(chunks):
            print_chunk_detail(chunk, i, verbose=verbose)

    return summary


# ──────────────────────────────────────────────────────────────────
# Parse-then-chunk mode (raw xlsx → JSON → chunks)
# ──────────────────────────────────────────────────────────────────

def run_from_raw(raw_path: Path, chunk_size: int, chunk_overlap: int,
                 max_table_chunk: int, rag_output_dir: Path, verbose: bool):
    """Parse raw .xlsx with xlsx_reader_v2, then chunk."""
    print_separator(f"PARSING RAW: {raw_path.name}")

    # Import the reader from src/processor/
    sys.path.insert(0, str(BASE_DIR / "src" / "processor"))
    from xlsx_reader_v2 import process_excel_file

    json_path = OUTPUT_DIR / f"{raw_path.stem}.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    result = process_excel_file(raw_path)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log.info(f"Parsed {raw_path.name} → {json_path}")

    # Now run preprocessor on the JSON
    return run_preprocessor(json_path, chunk_size, chunk_overlap,
                            max_table_chunk, rag_output_dir, verbose)


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Run Excel chunking pipeline (parse → chunk → inspect)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        Examples:
          # Chunk a single parsed JSON
          python run_excel_chunking.py --json output/excel/courseware.json

          # Chunk all JSONs in directory
          python run_excel_chunking.py --json-dir output/excel/

          # Parse raw Excel first, then chunk
          python run_excel_chunking.py --raw raw/excel/courseware.xlsx

          # Chunking only (no RAG-ready output)
          python run_excel_chunking.py --json output/excel/courseware.json --chunk-only

          # Quiet mode (no chunk details)
          python run_excel_chunking.py --json output/excel/courseware.json -q
        """)
    )

    # Input sources (mutually exclusive)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--json", type=str, help="Path to a parsed Excel JSON file")
    group.add_argument("--json-dir", type=str, help="Directory of parsed Excel JSON files")
    group.add_argument("--raw", type=str, help="Path to a raw .xlsx file (will parse first)")

    # Chunking params
    parser.add_argument("--chunk-size", type=int, default=1000, help="Max chars per text chunk (default: 1000)")
    parser.add_argument("--chunk-overlap", type=int, default=200, help="Overlap between text chunks (default: 200)")
    parser.add_argument("--max-table-chunk", type=int, default=2000, help="Max chars per table chunk (default: 2000)")

    # Modes
    parser.add_argument("--chunk-only", action="store_true", help="Only chunk, don't produce RAG-ready output")
    parser.add_argument("--rag-output", type=str, default=str(RAG_READY_DIR), help="RAG-ready output directory")
    parser.add_argument("-q", "--quiet", action="store_true", help="Don't print chunk details")
    parser.add_argument("-v", "--verbose", action="store_true", help="Extra verbose output")

    args = parser.parse_args()
    verbose = not args.quiet

    print_separator("EXCEL CHUNKING PIPELINE", "▓")
    print(f"  chunk_size={args.chunk_size}  overlap={args.chunk_overlap}  max_table={args.max_table_chunk}")
    print(f"  mode={'chunk-only' if args.chunk_only else 'full preprocessor'}")

    rag_output_dir = Path(args.rag_output)

    if args.raw:
        raw_path = Path(args.raw)
        if not raw_path.exists():
            log.error(f"File not found: {raw_path}")
            sys.exit(1)
        run_from_raw(raw_path, args.chunk_size, args.chunk_overlap,
                     args.max_table_chunk, rag_output_dir, verbose)

    elif args.json:
        json_path = Path(args.json)
        if not json_path.exists():
            log.error(f"File not found: {json_path}")
            sys.exit(1)
        if args.chunk_only:
            run_chunking_only(json_path, args.chunk_size, args.chunk_overlap,
                              args.max_table_chunk, verbose)
        else:
            run_preprocessor(json_path, args.chunk_size, args.chunk_overlap,
                             args.max_table_chunk, rag_output_dir, verbose)

    elif args.json_dir:
        json_dir = Path(args.json_dir)
        if not json_dir.is_dir():
            log.error(f"Not a directory: {json_dir}")
            sys.exit(1)
        json_files = sorted(json_dir.glob("*.json"))
        if not json_files:
            log.error(f"No JSON files found in {json_dir}")
            sys.exit(1)

        print(f"\n  Found {len(json_files)} JSON files")
        all_summaries = []
        for jf in json_files:
            try:
                if args.chunk_only:
                    run_chunking_only(jf, args.chunk_size, args.chunk_overlap,
                                      args.max_table_chunk, verbose)
                else:
                    summary = run_preprocessor(jf, args.chunk_size, args.chunk_overlap,
                                               args.max_table_chunk, rag_output_dir, verbose)
                    all_summaries.append(summary)
            except Exception as e:
                log.error(f"Failed on {jf.name}: {e}")

        if all_summaries:
            print_separator("BATCH SUMMARY")
            total_chunks = sum(s["num_chunks"] for s in all_summaries)
            total_sheets = sum(s["num_sheets"] for s in all_summaries)
            print(f"  Files processed : {len(all_summaries)}")
            print(f"  Total sheets    : {total_sheets}")
            print(f"  Total chunks    : {total_chunks}")

    print_separator("DONE", "▓")


if __name__ == "__main__":
    main()
