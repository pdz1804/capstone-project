#!/usr/bin/env python3
"""
End-to-end test script for the PDF RAG pipeline.

Two parsers are available:

  docling (default)    Docling unified parser.
                       Born-digital → OCR disabled (fast).
                       Scanned / hybrid → OCR enabled automatically.

  pymupdf              Legacy custom PdfParser (pymupdf / font heuristics).
                       Born-digital only; no OCR support.

Usage
-----
    cd backend

    # Classify only
    python run_pdf_e2e.py --raw input/report.pdf --classify-only

    # Full pipeline with legacy pymupdf parser
    python run_pdf_e2e.py --raw input/report.pdf --parser pymupdf

    # Process a whole directory
    python run_pdf_e2e.py --raw-dir input/

    # Start from an already-parsed JSON
    python run_pdf_e2e.py --json output/pdf_parsed/report.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Add src/ sub-packages directly so imports bypass the heavyweight src/__init__
# (which pulls in sentence_transformers, retrieval stack, etc.)
for _sub in ("processor", "chunking"):
    _p = str(ROOT / "src" / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)
# Also add src/ itself for cross-package imports (e.g. chunker → chunking.chunker)
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# Import via the chunking sub-package directly
from chunking.pdf_preprocessor import preprocess_pdf_for_rag  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("pdf_e2e")

DEFAULT_OUTPUT = ROOT / "output" / "pdf_rag_ready"


# ---------------------------------------------------------------------------
# Step 1   classify
# ---------------------------------------------------------------------------

def classify_pdf(pdf_path: Path) -> dict:
    from pdf_classifier import PdfClassifier

    classifier = PdfClassifier()
    c = classifier.classify(pdf_path)

    log.info(f"Classification : {c.pdf_type.value}")
    log.info(f"  Confidence   : {c.confidence:.2f}")
    log.info(f"  PDF version  : {c.pdf_version}")
    log.info(f"  Pages        : {c.page_count}")
    log.info(f"  StructTree   : {'Tagged' if c.has_structure_tree else 'Untagged'}")
    log.info(f"  Born-digital : {c.signals.get('born_ratio', 0):.1%}")
    log.info(f"  Scanned      : {c.signals.get('scanned_ratio', 0):.1%}")
    log.info(f"  Producer     : {c.signals.get('producer', '')}")

    return {
        "pdf_type": c.pdf_type.value,
        "confidence": c.confidence,
        "pdf_version": c.pdf_version,
        "page_count": c.page_count,
        "has_structure_tree": c.has_structure_tree,
    }


# ---------------------------------------------------------------------------
# Step 2   parse
# ---------------------------------------------------------------------------
def parse_with_pymupdf(pdf_path: Path, output_dir: Path) -> Path:
    """Parse via legacy pymupdf PdfParser (born-digital only, no OCR)."""
    from pdf_reader import PdfParser

    parsed_dir = output_dir / "_parsed" / pdf_path.stem
    parsed_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"Parsing with pymupdf (legacy): {pdf_path.name}")
    parser = PdfParser()
    tree = parser.parse(str(pdf_path), output_dir=str(parsed_dir))

    json_out = output_dir / f"{pdf_path.stem}.json"
    json_out.parent.mkdir(parents=True, exist_ok=True)
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=2)

    log.info(f"Parsed JSON saved: {json_out} ({len(tree)} top-level sections)")
    return json_out


# ---------------------------------------------------------------------------
# Step 3   preprocess (chunk + manifest)
# ---------------------------------------------------------------------------

def run_pipeline(json_path: Path, args, pdf_classification: dict | None = None) -> bool:
    if not json_path.exists():
        log.error(f"JSON not found: {json_path}")
        return False

    log.info(f"Input JSON: {json_path}")
    summary = preprocess_pdf_for_rag(
        json_path=json_path,
        output_dir=args.output,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        max_table_chunk_size=args.max_table_chunk,
        pdf_classification=pdf_classification,
    )

    log.info("=" * 60)
    log.info("  PDF E2E SUMMARY")
    log.info("=" * 60)
    for k, v in summary.items():
        log.info(f"  {k:20s}: {v}")
    log.info("=" * 60)

    out_folder = Path(summary["output_folder"])
    md_files     = list(out_folder.glob("*.md"))
    chunks_file  = out_folder / "pdf_chunks.json"
    manifest_file = out_folder / "pdf_manifest.json"

    assert md_files,              "No .md file generated"
    assert chunks_file.exists(),  "pdf_chunks.json not generated"
    assert manifest_file.exists(),"pdf_manifest.json not generated"

    with open(chunks_file, encoding="utf-8") as f:
        chunks_data = json.load(f)
    total = chunks_data["metadata"]["total_chunks"]
    log.info(f"Generated {total} chunks")

    for i, c in enumerate(chunks_data["chunks"][:3]):
        preview    = c["text"][:120].replace("\n", "\\n")
        breadcrumb = c["metadata"].get("heading_breadcrumb", [])
        log.info(f"  Chunk[{i}] breadcrumb={breadcrumb}")
        log.info(f"           text={preview}...")

    log.info(f"Pipeline completed successfully for {json_path.name}")
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _process_single(pdf_path: Path, args, parsed_json_dir: Path):
    classification = classify_pdf(pdf_path)

    if args.classify_only:
        return

    if args.parser == "pymupdf":
        if classification["pdf_type"] != "born_digital":
            log.warning(
                f"PDF is '{classification['pdf_type']}'   pymupdf parser has no OCR. "
                "Use --parser docling for scanned PDFs."
            )
        json_path = parse_with_pymupdf(pdf_path, parsed_json_dir)

    run_pipeline(json_path, args, pdf_classification=classification)


def main():
    parser = argparse.ArgumentParser(description="PDF → RAG-ready E2E test")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--json",    type=str, help="Path to already-parsed PDF JSON")
    group.add_argument("--raw",     type=str, help="Path to a single raw .pdf file")
    group.add_argument("--raw-dir", type=str, help="Directory containing .pdf files")

    parser.add_argument("--output",        type=str, default=str(DEFAULT_OUTPUT))
    parser.add_argument("--chunk-size",    type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--max-table-chunk", type=int, default=2000)
    parser.add_argument(
        "--parser",
        choices=["pymupdf"],
        default="pymupdf",
    )
    parser.add_argument(
        "--classify-only",
        action="store_true",
        help="Only classify the PDF (skip parsing and chunking)",
    )
    args = parser.parse_args()

    parsed_json_dir = ROOT / "output" / "pdf_parsed"

    if args.json:
        run_pipeline(Path(args.json), args)

    elif args.raw:
        raw_path = Path(args.raw)
        if not raw_path.exists():
            log.error(f"PDF not found: {raw_path}")
            sys.exit(1)
        _process_single(raw_path, args, parsed_json_dir)

    elif args.raw_dir:
        raw_dir  = Path(args.raw_dir)
        pdf_files = list(raw_dir.glob("*.pdf"))
        if not pdf_files:
            log.error(f"No .pdf files found in {raw_dir}")
            sys.exit(1)

        log.info(f"Found {len(pdf_files)} PDF files in {raw_dir}")
        for pdf_file in pdf_files:
            try:
                log.info(f"\n--- Processing {pdf_file.name} ---")
                _process_single(pdf_file, args, parsed_json_dir)
            except Exception as e:
                log.error(f"Failed processing {pdf_file.name}: {e}")


if __name__ == "__main__":
    main()
