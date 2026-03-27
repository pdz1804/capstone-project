#!/usr/bin/env python3
"""
End-to-end test script for the DOCX RAG pipeline.

Usage
-----
    cd backend
    python test_parsing/run_docx_e2e.py                       # default sample
    python test_parsing/run_docx_e2e.py --json raw/docx/docx_output_293.json
    python test_parsing/run_docx_e2e.py --json raw/docx/docx_output_293.json --output /tmp/docx_rag
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# ── make ``src`` importable when running from repo root ──────────────
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from chunking.docx_preprocessor import preprocess_docx_for_rag  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("docx_e2e")


# ── Defaults ──────────────────────────────────────────────────────────
DEFAULT_JSON = ROOT / "test_parsing" / "raw" / "docx" / "docx_output_293.json"
DEFAULT_OUTPUT = ROOT / "test_parsing" / "output" / "docx_rag_ready"


def run_pipeline(json_path, args, log):
    if not json_path.exists():
        log.error(f"JSON file not found: {json_path}")
        return False

    log.info(f"Input JSON : {json_path}")
    summary = preprocess_docx_for_rag(
        json_path=json_path,
        output_dir=args.output,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        max_table_chunk_size=args.max_table_chunk,
    )

    log.info("=" * 60)
    log.info("  DOCX E2E SUMMARY")
    log.info("=" * 60)
    for k, v in summary.items():
        log.info(f"  {k:20s}: {v}")
    log.info("=" * 60)

    out_folder = Path(summary["output_folder"])
    md_file = list(out_folder.glob("*.md"))
    chunks_file = out_folder / "docx_chunks.json"
    manifest_file = out_folder / "docx_manifest.json"

    assert md_file, "❌ No .md file generated"
    assert chunks_file.exists(), "❌ docx_chunks.json not generated"
    assert manifest_file.exists(), "❌ docx_manifest.json not generated"

    with open(chunks_file, "r", encoding="utf-8") as f:
        chunks_data = json.load(f)
    total = chunks_data["metadata"]["total_chunks"]
    log.info(f"✅ Generated {total} chunks")

    for i, c in enumerate(chunks_data["chunks"][:3]):
        preview = c["text"][:120].replace("\n", "\\n")
        breadcrumb = c["metadata"].get("heading_breadcrumb", [])
        log.info(f"  Chunk[{i}] breadcrumb={breadcrumb}")
        log.info(f"           text={preview}...")

    log.info(f"✅ Pipeline completed successfully for {json_path.name}")
    return True


def parse_raw_docx(docx_path: Path, output_dir: Path, log) -> Path:
    sys.path.insert(0, str(ROOT / "test_parsing"))
    from docx_reader_v2 import DocxParser

    log.info(f"Parsing raw DOCX: {docx_path}")
    parser = DocxParser()
    tree = parser.extract_docx_text(str(docx_path))
    
    json_out = output_dir / f"{docx_path.stem}.json"
    json_out.parent.mkdir(parents=True, exist_ok=True)
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=2)
        
    log.info(f"Parsed JSON saved to: {json_out}")
    return json_out


def main():
    parser = argparse.ArgumentParser(description="DOCX → RAG-ready E2E test")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--json", type=str, help="Path to parsed DOCX JSON")
    group.add_argument("--raw", type=str, help="Path to a single raw .docx file")
    group.add_argument("--raw-dir", type=str, help="Directory containing .docx files")

    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT),
        help="Output directory for RAG-ready structure",
    )
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--max-table-chunk", type=int, default=2000)
    args = parser.parse_args()

    parsed_json_dir = ROOT / "test_parsing" / "output" / "docx"

    if args.json:
        run_pipeline(Path(args.json), args, log)

    elif args.raw:
        raw_path = Path(args.raw)
        if not raw_path.exists():
            log.error(f"Raw DOCX not found: {raw_path}")
            sys.exit(1)
            
        json_path = parse_raw_docx(raw_path, parsed_json_dir, log)
        run_pipeline(json_path, args, log)

    elif args.raw_dir:
        raw_dir = Path(args.raw_dir)
        docx_files = list(raw_dir.glob("*.docx"))
        
        # Filter out temporary word files like ~$*.docx
        docx_files = [f for f in docx_files if not f.name.startswith("~$")]
        
        if not docx_files:
            log.error(f"No valid .docx files found in {raw_dir}")
            sys.exit(1)
            
        log.info(f"Found {len(docx_files)} DOCX files in {raw_dir}")
        for docx_file in docx_files:
            try:
                log.info(f"--- Processing {docx_file.name} ---")
                json_path = parse_raw_docx(docx_file, parsed_json_dir, log)
                run_pipeline(json_path, args, log)
            except Exception as e:
                log.error(f"Failed processing {docx_file.name}: {e}")

if __name__ == "__main__":
    main()
