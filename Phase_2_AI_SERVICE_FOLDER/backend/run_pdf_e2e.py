#!/usr/bin/env python3
"""
End-to-end test script for the born-digital PDF RAG pipeline.

Usage
-----
    cd backend
    python run_pdf_e2e.py --raw input/report.pdf
    python run_pdf_e2e.py --raw-dir input/
    python run_pdf_e2e.py --json output/pdf_parsed/report.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# ── make ``src`` importable when running from backend/ root ──────────
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

from chunking.pdf_preprocessor import preprocess_pdf_for_rag  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("pdf_e2e")

# ── Defaults ──────────────────────────────────────────────────────────
DEFAULT_OUTPUT = ROOT / "output" / "pdf_rag_ready"


def classify_pdf(pdf_path: Path, log) -> dict:
    """Classify a PDF and print results."""
    from processor.pdf_classifier import PdfClassifier

    classifier = PdfClassifier()
    classification = classifier.classify(pdf_path)

    log.info(f"Classification: {classification.pdf_type.value}")
    log.info(f"  Confidence   : {classification.confidence:.2f}")
    log.info(f"  PDF Version  : {classification.pdf_version}")
    log.info(f"  Pages        : {classification.page_count}")
    log.info(f"  Structure    : {'Tagged' if classification.has_structure_tree else 'Untagged'}")
    log.info(f"  Born-digital : {classification.signals.get('born_ratio', 0):.1%}")
    log.info(f"  Scanned      : {classification.signals.get('scanned_ratio', 0):.1%}")

    return {
        "pdf_type": classification.pdf_type.value,
        "confidence": classification.confidence,
        "pdf_version": classification.pdf_version,
        "page_count": classification.page_count,
        "has_structure_tree": classification.has_structure_tree,
    }


def parse_raw_pdf(pdf_path: Path, output_dir: Path, log) -> Path:
    """Parse a born-digital PDF into heading-tree JSON."""
    from processor.pdf_reader import PdfParser

    parsed_dir = output_dir / "_parsed" / pdf_path.stem
    parsed_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"Parsing PDF: {pdf_path}")
    parser = PdfParser()
    tree = parser.parse(str(pdf_path), output_dir=str(parsed_dir))

    json_out = output_dir / f"{pdf_path.stem}.json"
    json_out.parent.mkdir(parents=True, exist_ok=True)
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=2)

    log.info(f"Parsed JSON saved to: {json_out} ({len(tree)} top-level sections)")
    return json_out


def run_pipeline(json_path: Path, args, log, pdf_classification=None):
    """Run the preprocessing pipeline on a parsed PDF JSON."""
    if not json_path.exists():
        log.error(f"JSON file not found: {json_path}")
        return False

    log.info(f"Input JSON : {json_path}")
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
    md_file = list(out_folder.glob("*.md"))
    chunks_file = out_folder / "pdf_chunks.json"
    manifest_file = out_folder / "pdf_manifest.json"

    assert md_file, "No .md file generated"
    assert chunks_file.exists(), "pdf_chunks.json not generated"
    assert manifest_file.exists(), "pdf_manifest.json not generated"

    with open(chunks_file, "r", encoding="utf-8") as f:
        chunks_data = json.load(f)
    total = chunks_data["metadata"]["total_chunks"]
    log.info(f"Generated {total} chunks")

    for i, c in enumerate(chunks_data["chunks"][:3]):
        preview = c["text"][:120].replace("\n", "\\n")
        breadcrumb = c["metadata"].get("heading_breadcrumb", [])
        log.info(f"  Chunk[{i}] breadcrumb={breadcrumb}")
        log.info(f"           text={preview}...")

    log.info(f"Pipeline completed successfully for {json_path.name}")
    return True


def main():
    parser = argparse.ArgumentParser(description="PDF (born-digital) -> RAG-ready E2E test")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--json", type=str, help="Path to parsed PDF JSON")
    group.add_argument("--raw", type=str, help="Path to a single raw .pdf file")
    group.add_argument("--raw-dir", type=str, help="Directory containing .pdf files")

    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT),
        help="Output directory for RAG-ready structure",
    )
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--max-table-chunk", type=int, default=2000)
    parser.add_argument(
        "--classify-only",
        action="store_true",
        help="Only classify the PDF (skip parsing/chunking)",
    )
    args = parser.parse_args()

    parsed_json_dir = ROOT / "output" / "pdf_parsed"

    if args.json:
        run_pipeline(Path(args.json), args, log)

    elif args.raw:
        raw_path = Path(args.raw)
        if not raw_path.exists():
            log.error(f"PDF not found: {raw_path}")
            sys.exit(1)

        # Step 1: Classify
        classification = classify_pdf(raw_path, log)

        if args.classify_only:
            return

        if classification["pdf_type"] != "born_digital":
            log.warning(
                f"PDF classified as '{classification['pdf_type']}' — "
                f"this pipeline is designed for born-digital PDFs. "
                f"Proceeding anyway for testing."
            )

        # Step 2: Parse
        json_path = parse_raw_pdf(raw_path, parsed_json_dir, log)

        # Step 3: Preprocess
        run_pipeline(json_path, args, log, pdf_classification=classification)

    elif args.raw_dir:
        raw_dir = Path(args.raw_dir)
        pdf_files = list(raw_dir.glob("*.pdf"))

        if not pdf_files:
            log.error(f"No .pdf files found in {raw_dir}")
            sys.exit(1)

        log.info(f"Found {len(pdf_files)} PDF files in {raw_dir}")
        for pdf_file in pdf_files:
            try:
                log.info(f"\n--- Processing {pdf_file.name} ---")
                classification = classify_pdf(pdf_file, log)

                if args.classify_only:
                    continue

                json_path = parse_raw_pdf(pdf_file, parsed_json_dir, log)
                run_pipeline(json_path, args, log, pdf_classification=classification)
            except Exception as e:
                log.error(f"Failed processing {pdf_file.name}: {e}")


if __name__ == "__main__":
    main()
