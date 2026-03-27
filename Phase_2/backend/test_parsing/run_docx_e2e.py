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


def main():
    parser = argparse.ArgumentParser(description="DOCX → RAG-ready E2E test")
    parser.add_argument(
        "--json",
        type=str,
        default=str(DEFAULT_JSON),
        help="Path to parsed DOCX JSON (from docx_reader_v2)",
    )
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

    json_path = Path(args.json)
    if not json_path.exists():
        log.error(f"JSON file not found: {json_path}")
        sys.exit(1)

    log.info(f"Input JSON : {json_path}")
    log.info(f"Output dir : {args.output}")

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

    # Quick sanity checks
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

    # Print first 3 chunk previews
    for i, c in enumerate(chunks_data["chunks"][:3]):
        preview = c["text"][:120].replace("\n", "\\n")
        breadcrumb = c["metadata"].get("heading_breadcrumb", [])
        log.info(f"  Chunk[{i}] breadcrumb={breadcrumb}")
        log.info(f"           text={preview}...")

    log.info("✅ DOCX E2E pipeline completed successfully!")


if __name__ == "__main__":
    main()
