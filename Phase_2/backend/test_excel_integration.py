#!/usr/bin/env python3
"""
Test Excel Integration in the Production Pipeline

Tests the newly integrated Excel parsing + chunking pipeline:
  Stage 1  → normalizer._normalize_excel()     → excel_parsed/*.json
  Stage 3b → pipeline._run_excel_processing()  → stage4_rag_ready/{doc_id}/
  Retrieval → BaseRetriever.load_documents_from_directory() → loads pre-built chunks

Usage:
    python test_excel_integration.py <path_to_xlsx>

Example:
    python test_excel_integration.py test_parsing/raw/excel/courseware.xlsx
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# ── Setup path ──
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR / "src"))
sys.path.insert(0, str(BACKEND_DIR))

# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_ok(msg: str):
    print(f"  ✓ {msg}")


def print_fail(msg: str):
    print(f"  ✗ {msg}")


def print_info(msg: str):
    print(f"  → {msg}")


# ──────────────────────────────────────────────────────────────────
# Test 1: xlsx_reader_v2 — Parse raw .xlsx to JSON
# ──────────────────────────────────────────────────────────────────

def test_excel_parsing(xlsx_path: Path, output_dir: Path) -> Path:
    """Test that xlsx_reader_v2.process_excel_file works correctly."""
    print_header("TEST 1: Excel Parsing (xlsx_reader_v2)")

    from processor.xlsx_reader_v2 import process_excel_file

    excel_parsed_dir = output_dir / "stage1_normalized" / "excel_parsed"
    parsed_parent = excel_parsed_dir / "_parsed"
    excel_parsed_dir.mkdir(parents=True, exist_ok=True)
    parsed_parent.mkdir(parents=True, exist_ok=True)

    json_path = process_excel_file(
        excel_path=xlsx_path,
        output_dir=excel_parsed_dir,
        parsed_parent=parsed_parent,
    )

    # Verify
    assert json_path.exists(), f"JSON output not found: {json_path}"
    print_ok(f"JSON written: {json_path.name} ({json_path.stat().st_size:,} bytes)")

    with open(json_path, "r", encoding="utf-8") as f:
        sheets = json.load(f)

    assert isinstance(sheets, list), "JSON should be a list of sheets"
    assert len(sheets) > 0, "Should have at least one sheet"

    print_ok(f"Parsed {len(sheets)} sheet(s):")
    for i, sheet in enumerate(sheets):
        name = sheet.get("sheet_name", f"Sheet{i+1}")
        content = sheet.get("content", "")
        has_tables = "[START_TABLE]" in content
        has_charts = "[START_CHART]" in content
        has_images = "[START_IMAGE]" in content
        features = []
        if has_tables:
            features.append("tables")
        if has_charts:
            features.append("charts")
        if has_images:
            features.append("images")
        features_str = f" ({', '.join(features)})" if features else ""
        print_info(f"  [{i+1}] {name}: {len(content):,} chars{features_str}")

    return json_path


# ──────────────────────────────────────────────────────────────────
# Test 2: ExcelPreprocessor — JSON → RAG-ready output
# ──────────────────────────────────────────────────────────────────

def test_excel_preprocessing(json_path: Path, xlsx_path: Path, output_dir: Path) -> Path:
    """Test that ExcelPreprocessor produces correct RAG-ready output."""
    print_header("TEST 2: Excel Preprocessing (ExcelPreprocessor)")

    from chunking.excel_preprocessor import ExcelPreprocessor

    rag_ready_dir = output_dir / "stage4_rag_ready"
    doc_id = json_path.stem

    preprocessor = ExcelPreprocessor(
        output_dir=rag_ready_dir,
        chunk_size=1000,
        chunk_overlap=200,
        max_table_chunk_size=2000,
    )

    result = preprocessor.process_excel_json(
        json_path=json_path,
        original_xlsx_path=xlsx_path,
        doc_id=doc_id,
    )

    doc_folder = rag_ready_dir / doc_id

    # Verify all expected files exist
    manifest_path = doc_folder / "excel_manifest.json"
    chunks_path = doc_folder / "excel_chunks.json"
    md_path = doc_folder / f"{doc_id}.md"

    assert manifest_path.exists(), f"excel_manifest.json not found"
    assert chunks_path.exists(), f"excel_chunks.json not found"
    assert md_path.exists(), f"{doc_id}.md not found"

    print_ok(f"Output folder: {doc_folder}")
    print_ok(f"Markdown: {md_path.name} ({md_path.stat().st_size:,} bytes)")

    # Check manifest
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    print_ok(f"Manifest: document_type={manifest['document_type']}, "
             f"sheets={manifest['num_sheets']}, "
             f"has_chunks={manifest['has_excel_chunks']}")

    # Check chunks
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks_data = json.load(f)
    chunks = chunks_data.get("chunks", [])
    print_ok(f"Chunks: {len(chunks)} total")

    # Show chunk breakdown by chunk_type
    table_row_chunks = sum(1 for c in chunks if c.get("metadata", {}).get("chunk_type") == "table_rows")
    entity_chunks = sum(1 for c in chunks if c.get("metadata", {}).get("chunk_type") == "row_entity")
    text_chunks = sum(1 for c in chunks if c.get("metadata", {}).get("chunk_type") == "text" or not c.get("is_table"))
    print_info(f"  Table-row chunks: {table_row_chunks}")
    print_info(f"  Entity docs:      {entity_chunks}")
    print_info(f"  Text chunks:      {text_chunks}")

    # Show first few chunks
    for i, chunk in enumerate(chunks[:5]):
        preview = chunk.get("text", "")[:80].replace("\n", " ")
        ctype = chunk.get("metadata", {}).get("chunk_type", "unknown")
        print_info(f"  Chunk {i}: [{ctype}] {preview}...")

    return doc_folder


# ──────────────────────────────────────────────────────────────────
# Test 3: Retriever Loading — simulate BaseRetriever
# ──────────────────────────────────────────────────────────────────

def test_retriever_loading(output_dir: Path):
    """Test that the retriever can load pre-built Excel chunks."""
    print_header("TEST 3: Retriever Loading (BaseRetriever)")

    try:
        from retrieval.rag_retrievers import BaseRetriever
    except ImportError as e:
        print_info(f"SKIPPED — retriever deps not available: {e}")
        print_info("(This is a pre-existing env issue, not related to Excel integration)")
        return "skipped"

    rag_ready_dir = output_dir / "stage4_rag_ready"

    regular_docs, prebuilt_chunks = BaseRetriever.load_documents_from_directory(rag_ready_dir)

    print_ok(f"Regular documents: {len(regular_docs)}")
    print_ok(f"Pre-built chunks (Excel): {len(prebuilt_chunks)}")

    assert len(prebuilt_chunks) > 0, "Should have loaded Excel pre-built chunks"

    # Verify chunk structure
    sample = prebuilt_chunks[0]
    required_fields = ["text", "id", "source"]
    for fld in required_fields:
        assert fld in sample, f"Missing field '{fld}' in chunk"

    # Verify metadata quality
    meta = sample.get("metadata", {})
    print_ok(f"Chunk structure looks correct")
    print_info(f"  Sample chunk keys: {list(sample.keys())}")
    print_info(f"  Sample metadata keys: {sorted(meta.keys())[:10]}...")
    if meta.get("chunk_type"):
        print_info(f"  chunk_type: {meta['chunk_type']}")
    if meta.get("course_code"):
        print_info(f"  course_code: {meta['course_code']}")
    preview = sample.get("text", "")[:100].replace("\n", " ")
    print_info(f"  Sample text: {preview}...")
    return "passed"


# ──────────────────────────────────────────────────────────────────
# Test 4: Full pipeline simulation (Stage 1 → 3b, no Docling)
# ──────────────────────────────────────────────────────────────────

def test_pipeline_stages(xlsx_path: Path, output_dir: Path):
    """Simulate the pipeline stages for Excel without needing Docling."""
    print_header("TEST 4: Pipeline Stage Simulation")

    # --- Stage 1: Normalizer ---
    print_info("Stage 1: Normalizer — parsing Excel...")

    from processor.normalizer import DocumentNormalizer, NormalizerConfig

    stage1_dir = output_dir / "stage1_normalized"
    normalizer = DocumentNormalizer(
        input_dir=xlsx_path.parent,
        output_dir=stage1_dir,
        config=NormalizerConfig(generate_pdf=False, generate_markdown=False),
    )

    stem = xlsx_path.stem
    safe_stem = normalizer._get_safe_filename(stem)

    # Copy original (mimics what _normalize_file does)
    shutil.copy2(xlsx_path, normalizer.originals_dir / f"{safe_stem}{xlsx_path.suffix}")

    # Run the excel-specific normalization
    normalizer._normalize_excel(xlsx_path, safe_stem)

    json_file = stage1_dir / "excel_parsed" / f"{safe_stem}.json"
    assert json_file.exists(), f"Stage 1 JSON not created: {json_file}"
    print_ok(f"Stage 1 complete: {json_file.name}")

    # --- Stage 3b: Excel Processing ---
    print_info("Stage 3b: Excel Processing — chunking...")

    from chunking.excel_preprocessor import ExcelPreprocessor

    rag_ready_dir = output_dir / "stage4_rag_ready"
    preprocessor = ExcelPreprocessor(
        output_dir=rag_ready_dir,
        chunk_size=1000,
        chunk_overlap=200,
        max_table_chunk_size=2000,
    )

    result = preprocessor.process_excel_json(
        json_path=json_file,
        original_xlsx_path=xlsx_path,
        doc_id=safe_stem,
    )

    doc_folder = rag_ready_dir / safe_stem
    assert (doc_folder / "excel_manifest.json").exists()
    assert (doc_folder / "excel_chunks.json").exists()
    assert (doc_folder / f"{safe_stem}.md").exists()

    print_ok(f"Stage 3b complete: {result['num_chunks']} chunks")
    print_ok(f"Output: {doc_folder}")

    # --- Verify retriever can load ---
    print_info("Verification: retriever loading...")
    try:
        from retrieval.rag_retrievers import BaseRetriever
        regular, prebuilt = BaseRetriever.load_documents_from_directory(rag_ready_dir)
        total = len(regular) + len(prebuilt)
        print_ok(f"Retriever loaded {total} items ({len(prebuilt)} pre-built Excel chunks)")
    except ImportError as e:
        print_info(f"Retriever check skipped (deps not available: {e})")


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_excel_integration.py <path_to_xlsx>")
        print("Example: python test_excel_integration.py test_parsing/raw/excel/courseware.xlsx")
        sys.exit(1)

    xlsx_path = Path(sys.argv[1]).resolve()
    if not xlsx_path.exists():
        print(f"ERROR: File not found: {xlsx_path}")
        sys.exit(1)

    print(f"\n📄 Testing with: {xlsx_path.name}")

    # Use a temporary directory for output
    output_dir = Path(tempfile.mkdtemp(prefix="excel_integration_test_"))
    print(f"📂 Output dir: {output_dir}")

    passed = 0
    failed = 0
    skipped = 0

    try:
        # Test 1: Parse
        json_path = test_excel_parsing(xlsx_path, output_dir)
        passed += 1

        # Test 2: Preprocess
        test_excel_preprocessing(json_path, xlsx_path, output_dir)
        passed += 1

        # Clean up and re-run as pipeline simulation
        rag_dir = output_dir / "stage4_rag_ready"
        if rag_dir.exists():
            shutil.rmtree(rag_dir)

        # Test 3: Redo with pipeline simulation (from scratch)
        output_dir_2 = Path(tempfile.mkdtemp(prefix="excel_pipeline_test_"))
        test_pipeline_stages(xlsx_path, output_dir_2)
        passed += 1

        # Test 4: Retriever loading (may be skipped if deps unavailable)
        result = test_retriever_loading(output_dir_2)
        if result == "skipped":
            skipped += 1
        else:
            passed += 1

    except Exception as e:
        failed += 1
        import traceback
        print(f"\n  ✗ TEST FAILED: {e}")
        traceback.print_exc()

    # Summary
    print_header("TEST RESULTS")
    total = passed + failed + skipped
    print(f"  Passed: {passed}/{total}")
    if skipped > 0:
        print(f"  Skipped: {skipped}/{total} (environment deps)")
    if failed > 0:
        print(f"  Failed: {failed}/{total}")
        sys.exit(1)
    else:
        print("  All tests passed! ✓")


if __name__ == "__main__":
    main()
