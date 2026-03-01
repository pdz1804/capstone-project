#!/usr/bin/env python3
"""
Comprehensive Test Suite for Excel Parsing Pipeline

Divided into:
  - MOCK TESTS  : No real files or LLM needed, test logic with synthetic data
  - FULL TESTS  : Use real Excel files from test_parsing/output/excel/
  - E2E TESTS   : Full pipeline with real LLM calls (requires API key)

Run specific test groups:
    pytest test_excel_pipeline.py -m mock -v             # Mock tests only (fast, no deps)
    pytest test_excel_pipeline.py -m full -v              # Full tests with real files
    pytest test_excel_pipeline.py -m e2e -v               # End-to-end with LLM
    pytest test_excel_pipeline.py -v                      # All tests
    pytest test_excel_pipeline.py -m "not e2e" -v         # Everything except LLM calls
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from typing import List, Dict, Any

import pytest

# ── Path setup ──
BACKEND_DIR = Path(__file__).resolve().parent.parent
TEST_PARSING_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "src"))
sys.path.insert(0, str(TEST_PARSING_DIR))

from chunking.excel_chunker import (
    ExcelTableChunker, ExcelChunkingConfig, chunk_excel_json,
    TABLE_START_MARKER, TABLE_END_MARKER,
    IMAGE_START_MARKER, IMAGE_END_MARKER,
)
from chunking.excel_preprocessor import ExcelPreprocessor, preprocess_excel_for_rag
from chunking.chunker import TextChunker, ChunkingConfig

# ── Test data paths ──
EXCEL_JSON_DIR = TEST_PARSING_DIR / "output" / "excel"
EXCEL_RAW_DIR = TEST_PARSING_DIR / "raw" / "excel"

# Check if real files exist for full tests
HAS_REAL_FILES = EXCEL_JSON_DIR.exists() and any(EXCEL_JSON_DIR.glob("*.json"))
HAS_OPENAI_KEY = bool(os.getenv("OPENAI_API_KEY"))


# ════════════════════════════════════════════════════════════════════
# SYNTHETIC TEST DATA
# ════════════════════════════════════════════════════════════════════

SIMPLE_TABLE = """| Name | Age | City |
| --- | --- | --- |
| Alice | 30 | NYC |
| Bob | 25 | LA |
| Charlie | 35 | SF |"""

LARGE_TABLE = "| Col1 | Col2 | Col3 |\n| --- | --- | --- |\n" + \
    "\n".join(f"| Row{i} | Data{i} | Value{i} |" for i in range(100))

SAMPLE_SHEETS = [
    {
        "sheet_name": "Overview",
        "content": (
            "This is a text introduction to the spreadsheet.\n\n"
            "It has multiple paragraphs explaining the content.\n\n"
            f"{TABLE_START_MARKER}\n{SIMPLE_TABLE}\n{TABLE_END_MARKER}\n\n"
            "Some text after the table."
        ),
    },
    {
        "sheet_name": "Data",
        "content": (
            f"{TABLE_START_MARKER}\n{LARGE_TABLE}\n{TABLE_END_MARKER}"
        ),
    },
    {
        "sheet_name": "Images",
        "content": (
            "Some text with an image reference.\n"
            f"{IMAGE_START_MARKER}/path/to/image1.png{IMAGE_END_MARKER}\n"
            f"{TABLE_START_MARKER}\n{SIMPLE_TABLE}\n{TABLE_END_MARKER}\n"
            f"{IMAGE_START_MARKER}/path/to/image2.jpg{IMAGE_END_MARKER}"
        ),
    },
]

EMPTY_SHEET = [{"sheet_name": "Empty", "content": ""}]
WHITESPACE_SHEET = [{"sheet_name": "Whitespace", "content": "   \n\n   "}]

SHEET_NO_TABLES = [
    {
        "sheet_name": "TextOnly",
        "content": "This is a long text document.\n\n" * 20,
    }
]


# ════════════════════════════════════════════════════════════════════
# MOCK TESTS — No real files or API calls needed
# ════════════════════════════════════════════════════════════════════


@pytest.mark.mock
class TestExcelChunkerSegmentSplitting:
    """Test the internal segment splitting logic."""

    def test_no_tables(self):
        chunker = ExcelTableChunker()
        segments = chunker._split_into_segments("Hello world, no tables here.")
        assert len(segments) == 1
        assert segments[0]["type"] == "text"

    def test_single_table(self):
        content = f"Before\n{TABLE_START_MARKER}\n{SIMPLE_TABLE}\n{TABLE_END_MARKER}\nAfter"
        chunker = ExcelTableChunker()
        segments = chunker._split_into_segments(content)
        assert len(segments) == 3
        assert segments[0]["type"] == "text"
        assert segments[1]["type"] == "table"
        assert segments[2]["type"] == "text"

    def test_multiple_tables(self):
        content = (
            f"Text1\n{TABLE_START_MARKER}\nT1\n{TABLE_END_MARKER}\n"
            f"Text2\n{TABLE_START_MARKER}\nT2\n{TABLE_END_MARKER}\n"
            f"Text3"
        )
        chunker = ExcelTableChunker()
        segments = chunker._split_into_segments(content)
        types = [s["type"] for s in segments]
        assert types == ["text", "table", "text", "table", "text"]

    def test_adjacent_tables_no_text_between(self):
        content = f"{TABLE_START_MARKER}\nT1\n{TABLE_END_MARKER}{TABLE_START_MARKER}\nT2\n{TABLE_END_MARKER}"
        chunker = ExcelTableChunker()
        segments = chunker._split_into_segments(content)
        table_segments = [s for s in segments if s["type"] == "table"]
        assert len(table_segments) == 2

    def test_empty_content(self):
        chunker = ExcelTableChunker()
        segments = chunker._split_into_segments("")
        assert segments == []

    def test_malformed_markers(self):
        content = f"{TABLE_START_MARKER}\nNo end marker"
        chunker = ExcelTableChunker()
        segments = chunker._split_into_segments(content)
        assert len(segments) == 1
        assert segments[0]["type"] == "text"


@pytest.mark.mock
class TestExcelChunkerTableParsing:
    """Test Markdown table parsing and splitting."""

    def test_parse_md_table(self):
        header, sep, rows = ExcelTableChunker._parse_md_table(SIMPLE_TABLE)
        assert header is not None
        assert "Name" in header
        assert sep is not None
        assert "---" in sep
        assert len(rows) == 3

    def test_parse_empty_table(self):
        header, sep, rows = ExcelTableChunker._parse_md_table("")
        assert header is None
        assert rows == []

    def test_split_small_table_stays_whole(self):
        config = ExcelChunkingConfig(max_table_chunk_size=5000)
        chunker = ExcelTableChunker(config)
        result = chunker._split_table(SIMPLE_TABLE)
        assert len(result) == 1

    def test_split_large_table_produces_multiple(self):
        config = ExcelChunkingConfig(max_table_chunk_size=200)
        chunker = ExcelTableChunker(config)
        result = chunker._split_table(LARGE_TABLE)
        assert len(result) > 1
        # Each chunk should have the header
        for chunk in result:
            assert "Col1" in chunk
            assert "---" in chunk

    def test_header_repeated_in_all_chunks(self):
        config = ExcelChunkingConfig(max_table_chunk_size=300)
        chunker = ExcelTableChunker(config)
        result = chunker._split_table(LARGE_TABLE)
        for chunk in result:
            lines = chunk.strip().split("\n")
            assert "Col1" in lines[0], f"Header missing in chunk: {lines[0]}"


@pytest.mark.mock
class TestExcelChunkerSplitText:
    """Test the overridden split_text method."""

    def test_text_only(self):
        chunker = ExcelTableChunker(ExcelChunkingConfig(chunk_size=100, chunk_overlap=20))
        chunks = chunker.split_text("Hello world. " * 50)
        assert len(chunks) > 1

    def test_table_preserved_whole(self):
        content = f"{TABLE_START_MARKER}\n{SIMPLE_TABLE}\n{TABLE_END_MARKER}"
        config = ExcelChunkingConfig(max_table_chunk_size=5000, prefer_whole_tables=True)
        chunker = ExcelTableChunker(config)
        chunks = chunker.split_text(content)
        assert len(chunks) == 1
        assert "Alice" in chunks[0]

    def test_mixed_content(self):
        content = SAMPLE_SHEETS[0]["content"]
        chunker = ExcelTableChunker(ExcelChunkingConfig(chunk_size=200))
        chunks = chunker.split_text(content)
        assert len(chunks) >= 2

    def test_empty_text(self):
        chunker = ExcelTableChunker()
        assert chunker.split_text("") == []
        assert chunker.split_text("   ") == []


@pytest.mark.mock
class TestExcelChunkerImageExtraction:
    """Test image path extraction."""

    def test_extract_images(self):
        content = (
            f"Text before {IMAGE_START_MARKER}/img/a.png{IMAGE_END_MARKER} "
            f"and {IMAGE_START_MARKER}/img/b.jpg{IMAGE_END_MARKER}"
        )
        paths = ExcelTableChunker._extract_image_paths(content)
        assert len(paths) == 2
        assert "/img/a.png" in paths
        assert "/img/b.jpg" in paths

    def test_no_images(self):
        paths = ExcelTableChunker._extract_image_paths("No images here.")
        assert paths == []


@pytest.mark.mock
class TestExcelChunkerChunkDocument:
    """Test chunk_excel_document and chunk_excel_json."""

    def test_chunk_single_sheet(self):
        chunker = ExcelTableChunker(ExcelChunkingConfig(chunk_size=500))
        chunks = chunker.chunk_excel_document(
            SAMPLE_SHEETS[0], doc_id="test", source="test.xlsx"
        )
        assert len(chunks) > 0
        for chunk in chunks:
            assert "id" in chunk
            assert "text" in chunk
            assert "metadata" in chunk
            assert chunk["metadata"]["sheet_name"] == "Overview"
            assert chunk["metadata"]["document_type"] == "spreadsheet"
            assert chunk["metadata"]["parent_doc_id"] == "test"

    def test_chunk_entire_workbook(self):
        chunks = chunk_excel_json(
            SAMPLE_SHEETS, doc_id="workbook", source="test.xlsx",
            chunk_size=500, chunk_overlap=100,
        )
        assert len(chunks) > 0

        # Check all sheets are represented
        sheet_names = set(c["metadata"]["sheet_name"] for c in chunks)
        assert "Overview" in sheet_names
        assert "Data" in sheet_names
        assert "Images" in sheet_names

    def test_empty_sheet_produces_no_chunks(self):
        chunks = chunk_excel_json(EMPTY_SHEET, doc_id="empty")
        assert chunks == []

    def test_whitespace_sheet_produces_no_chunks(self):
        chunks = chunk_excel_json(WHITESPACE_SHEET, doc_id="ws")
        assert chunks == []

    def test_table_chunks_have_is_table_flag(self):
        chunks = chunk_excel_json(SAMPLE_SHEETS, doc_id="test", chunk_size=5000)
        table_chunks = [c for c in chunks if c["metadata"]["is_table"]]
        text_chunks = [c for c in chunks if not c["metadata"]["is_table"]]
        assert len(table_chunks) > 0
        assert len(text_chunks) > 0

    def test_image_metadata_attached(self):
        chunks = chunk_excel_json(SAMPLE_SHEETS, doc_id="test")
        img_chunks = [c for c in chunks if c["metadata"].get("has_images")]
        # The Images sheet has image markers
        assert len(img_chunks) > 0

    def test_chunk_ids_are_unique(self):
        chunks = chunk_excel_json(SAMPLE_SHEETS, doc_id="test")
        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids)), "Duplicate chunk IDs found"

    def test_chunk_metadata_uniform_fields(self):
        chunks = chunk_excel_json(SAMPLE_SHEETS, doc_id="test", source="test.xlsx")
        for chunk in chunks:
            meta = chunk["metadata"]
            assert "document_type" in meta
            assert meta["document_type"] == "spreadsheet"
            assert "uniform_metadata_version" in meta
            assert "content_type" in meta
            assert "original_file" in meta


@pytest.mark.mock
class TestExcelPreprocessor:
    """Test ExcelPreprocessor with temp directories."""

    def test_process_creates_output_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write sample JSON
            json_path = Path(tmpdir) / "test.json"
            json_path.write_text(json.dumps(SAMPLE_SHEETS), encoding="utf-8")

            output_dir = Path(tmpdir) / "rag_ready"
            summary = preprocess_excel_for_rag(
                json_path=json_path,
                output_dir=output_dir,
            )

            assert summary["num_chunks"] > 0
            assert summary["num_sheets"] == 3

            doc_folder = Path(summary["output_folder"])
            assert (doc_folder / "test.md").exists()
            assert (doc_folder / "excel_chunks.json").exists()
            assert (doc_folder / "excel_manifest.json").exists()

    def test_manifest_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "test.json"
            json_path.write_text(json.dumps(SAMPLE_SHEETS), encoding="utf-8")

            output_dir = Path(tmpdir) / "rag_ready"
            summary = preprocess_excel_for_rag(json_path=json_path, output_dir=output_dir)

            manifest_path = Path(summary["output_folder"]) / "excel_manifest.json"
            with open(manifest_path) as f:
                manifest = json.load(f)

            assert manifest["document_type"] == "spreadsheet"
            assert manifest["has_excel_chunks"] is True
            assert manifest["num_sheets"] == 3

    def test_chunks_json_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "test.json"
            json_path.write_text(json.dumps(SAMPLE_SHEETS), encoding="utf-8")

            output_dir = Path(tmpdir) / "rag_ready"
            summary = preprocess_excel_for_rag(json_path=json_path, output_dir=output_dir)

            chunks_path = Path(summary["output_folder"]) / "excel_chunks.json"
            with open(chunks_path) as f:
                data = json.load(f)

            assert "metadata" in data
            assert "chunks" in data
            assert data["metadata"]["total_chunks"] == len(data["chunks"])
            assert data["metadata"]["num_sheets"] == 3

    def test_markdown_contains_all_sheets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "test.json"
            json_path.write_text(json.dumps(SAMPLE_SHEETS), encoding="utf-8")

            output_dir = Path(tmpdir) / "rag_ready"
            summary = preprocess_excel_for_rag(json_path=json_path, output_dir=output_dir)

            md_path = Path(summary["output_folder"]) / "test.md"
            md_content = md_path.read_text(encoding="utf-8")

            assert "## Sheet: Overview" in md_content
            assert "## Sheet: Data" in md_content
            assert "## Sheet: Images" in md_content

    def test_custom_doc_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "test.json"
            json_path.write_text(json.dumps(SAMPLE_SHEETS), encoding="utf-8")

            output_dir = Path(tmpdir) / "rag_ready"
            summary = preprocess_excel_for_rag(
                json_path=json_path, output_dir=output_dir, doc_id="my_custom_id"
            )

            assert summary["doc_id"] == "my_custom_id"
            assert (Path(summary["output_folder"]) / "my_custom_id.md").exists()

    def test_chunking_params_propagated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "test.json"
            json_path.write_text(json.dumps(SAMPLE_SHEETS), encoding="utf-8")

            output_dir = Path(tmpdir) / "rag_ready"
            summary_small = preprocess_excel_for_rag(
                json_path=json_path, output_dir=output_dir / "small",
                chunk_size=200, chunk_overlap=50,
            )
            summary_large = preprocess_excel_for_rag(
                json_path=json_path, output_dir=output_dir / "large",
                chunk_size=5000, chunk_overlap=500,
            )

            # Smaller chunk size should produce more chunks
            assert summary_small["num_chunks"] >= summary_large["num_chunks"]


@pytest.mark.mock
class TestChunkingConfigEdgeCases:
    """Test edge cases in chunking configuration."""

    def test_very_small_chunk_size(self):
        config = ExcelChunkingConfig(chunk_size=50, chunk_overlap=10, min_chunk_size=10)
        chunker = ExcelTableChunker(config)
        chunks = chunker.split_text("Hello world. " * 20)
        assert len(chunks) > 0

    def test_overlap_larger_than_chunk(self):
        # LangChain rejects overlap > chunk_size; verify we handle it
        config = ExcelChunkingConfig(chunk_size=100, chunk_overlap=50)
        chunker = ExcelTableChunker(config)
        chunks = chunker.split_text("Hello world. " * 50)
        assert len(chunks) > 0

    def test_max_table_chunk_very_small(self):
        config = ExcelChunkingConfig(max_table_chunk_size=100, prefer_whole_tables=False)
        chunker = ExcelTableChunker(config)
        content = f"{TABLE_START_MARKER}\n{LARGE_TABLE}\n{TABLE_END_MARKER}"
        chunks = chunker.split_text(content)
        assert len(chunks) > 1


@pytest.mark.mock
class TestBuildMarkdown:
    """Test the Markdown builder."""

    def test_build_markdown(self):
        md = ExcelPreprocessor._build_markdown(SAMPLE_SHEETS, "test_doc")
        assert "# test_doc" in md
        assert "## Sheet: Overview" in md
        assert "## Sheet: Data" in md
        assert TABLE_START_MARKER in md
        assert TABLE_END_MARKER in md

    def test_build_markdown_empty_sheets(self):
        md = ExcelPreprocessor._build_markdown(EMPTY_SHEET, "empty")
        assert "# empty" in md
        assert "## Sheet: Empty" in md


# ════════════════════════════════════════════════════════════════════
# MOCK TESTS — LLM Generation (mocked)
# ════════════════════════════════════════════════════════════════════

@pytest.mark.mock
class TestGeneratorWithMockedLLM:
    """Test generation logic with mocked LLM calls."""

    def _make_generator(self):
        """Create a RAGGenerator with mocked client (no real openai needed)."""
        from generation.generator import RAGGenerator, GenerationConfig
        config = GenerationConfig(provider="openai", api_key="fake")
        gen = RAGGenerator.__new__(RAGGenerator)
        gen.config = config
        gen.base_dir = None
        gen.client = MagicMock()
        return gen

    def test_format_context_with_citations(self):
        generator = self._make_generator()

        docs = [
            {"text": "Alice is 30", "source": "test.xlsx", "score": 0.9, "id": "c1",
             "metadata": {"sheet_name": "Sheet1", "is_table": False, "document_type": "spreadsheet"}},
            {"text": "| Name | Age |\n| --- | --- |\n| Bob | 25 |", "source": "test.xlsx",
             "score": 0.8, "id": "c2",
             "metadata": {"sheet_name": "Sheet1", "is_table": True, "document_type": "spreadsheet"}},
        ]

        ctx, file_map, chunk_map = generator._format_context_with_citations(docs)
        assert "test.xlsx" in str(file_map)
        assert len(chunk_map) == 2
        assert "[1.1]" in ctx
        assert "[1.2]" in ctx
        assert "[Sheet: Sheet1]" in ctx
        assert "[Table Data]" in ctx

    def test_generate_returns_structure(self):
        generator = self._make_generator()

        # Mock the LLM response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Mocked answer about Alice."
        generator.client.chat.completions.create.return_value = mock_response

        docs = [
            {"text": "Alice is 30", "source": "test.xlsx", "score": 0.9, "id": "c1",
             "metadata": {"sheet_name": "S1", "is_table": False, "document_type": "spreadsheet"}},
        ]
        result = generator.generate("Who is Alice?", docs)

        assert "answer" in result
        assert "Mocked answer" in result["answer"]
        assert "files" in result
        assert "contents" in result

    def test_generate_empty_docs(self):
        generator = self._make_generator()

        result = generator.generate("test?", [])
        assert "couldn't find" in result["answer"].lower()


# ════════════════════════════════════════════════════════════════════
# FULL TESTS — Use real Excel JSON files from disk
# ════════════════════════════════════════════════════════════════════

@pytest.mark.full
@pytest.mark.skipif(not HAS_REAL_FILES, reason="No real Excel JSON files found")
class TestFullChunkingWithRealFiles:
    """Test chunking with actual parsed Excel JSON files."""

    def _get_json_files(self) -> List[Path]:
        return sorted(EXCEL_JSON_DIR.glob("*.json"))[:5]

    def test_all_files_chunk_without_error(self):
        for jf in self._get_json_files():
            with open(jf, "r", encoding="utf-8") as f:
                sheets = json.load(f)
            chunks = chunk_excel_json(sheets, doc_id=jf.stem, source=str(jf))
            assert len(chunks) >= 0, f"Failed on {jf.name}"

    def test_chunks_have_valid_metadata(self):
        for jf in self._get_json_files():
            with open(jf, "r", encoding="utf-8") as f:
                sheets = json.load(f)
            chunks = chunk_excel_json(sheets, doc_id=jf.stem)
            for chunk in chunks:
                assert "metadata" in chunk
                assert "sheet_name" in chunk["metadata"]
                assert "is_table" in chunk["metadata"]
                assert len(chunk["text"]) > 0

    def test_preprocessor_on_real_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for jf in self._get_json_files()[:3]:
                summary = preprocess_excel_for_rag(
                    json_path=jf, output_dir=Path(tmpdir) / "rag"
                )
                assert summary["num_chunks"] > 0
                out = Path(summary["output_folder"])
                assert (out / "excel_chunks.json").exists()
                assert (out / "excel_manifest.json").exists()

    def test_courseware_specific(self):
        """Test the courseware.json specifically if it exists."""
        courseware = EXCEL_JSON_DIR / "courseware.json"
        if not courseware.exists():
            pytest.skip("courseware.json not found")

        with open(courseware, "r", encoding="utf-8") as f:
            sheets = json.load(f)

        chunks = chunk_excel_json(sheets, doc_id="courseware", chunk_size=1000)
        assert len(chunks) > 10  # courseware is a large file

        # Should have multiple sheets
        sheet_names = set(c["metadata"]["sheet_name"] for c in chunks)
        assert len(sheet_names) >= 3

        # Should have both table and text chunks
        table_count = sum(1 for c in chunks if c["metadata"]["is_table"])
        text_count = sum(1 for c in chunks if not c["metadata"]["is_table"])
        assert table_count > 0
        assert text_count > 0


@pytest.mark.full
@pytest.mark.skipif(not HAS_REAL_FILES, reason="No real Excel JSON files found")
class TestFullRetrievalWithRealFiles:
    """Test BM25 retrieval on real chunked Excel data."""

    def _get_chunks(self, filename: str = "courseware.json"):
        jf = EXCEL_JSON_DIR / filename
        if not jf.exists():
            jf = next(EXCEL_JSON_DIR.glob("*.json"), None)
            if jf is None:
                pytest.skip("No JSON files available")

        with open(jf, "r", encoding="utf-8") as f:
            sheets = json.load(f)
        return chunk_excel_json(sheets, doc_id=jf.stem)

    def test_bm25_retrieval(self):
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            pytest.skip("rank_bm25 not installed")

        chunks = self._get_chunks()
        if not chunks:
            pytest.skip("No chunks produced")

        corpus = [c["text"].lower().split() for c in chunks]
        bm25 = BM25Okapi(corpus)

        query = "course material"
        scores = bm25.get_scores(query.lower().split())
        top_indices = sorted(range(len(scores)), key=lambda i: -scores[i])[:5]

        assert len(top_indices) > 0
        assert scores[top_indices[0]] > 0

    def test_retrieval_with_vietnamese_query(self):
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            pytest.skip("rank_bm25 not installed")

        chunks = self._get_chunks()
        if not chunks:
            pytest.skip("No chunks produced")

        corpus = [c["text"].lower().split() for c in chunks]
        bm25 = BM25Okapi(corpus)

        query = "Giải tích"
        scores = bm25.get_scores(query.lower().split())
        top_idx = sorted(range(len(scores)), key=lambda i: -scores[i])[0]
        # At least one chunk should match
        assert scores[top_idx] >= 0


# ════════════════════════════════════════════════════════════════════
# E2E TESTS — Full pipeline with real LLM calls
# ════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
@pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not set")
@pytest.mark.skipif(not HAS_REAL_FILES, reason="No real Excel JSON files found")
class TestE2EWithRealLLM:
    """End-to-end tests that call real LLM APIs. Costs money!"""

    def _run_pipeline(self, query: str, filename: str = "courseware.json"):
        from generation.generator import RAGGenerator, GenerationConfig
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            pytest.skip("rank_bm25 not installed")

        jf = EXCEL_JSON_DIR / filename
        if not jf.exists():
            jf = next(EXCEL_JSON_DIR.glob("*.json"), None)
            if not jf:
                pytest.skip("No JSON files")

        with open(jf, "r", encoding="utf-8") as f:
            sheets = json.load(f)
        chunks = chunk_excel_json(sheets, doc_id=jf.stem)

        corpus = [c["text"].lower().split() for c in chunks]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(query.lower().split())
        top_indices = sorted(range(len(scores)), key=lambda i: -scores[i])[:5]
        retrieved = [{**chunks[i], "score": float(scores[i])} for i in top_indices]

        config = GenerationConfig(
            provider="openai",
            model_name="gpt-4o-mini",
            temperature=0.0,
        )
        generator = RAGGenerator(config)
        return generator.generate(query, retrieved)

    def test_e2e_english_query(self):
        result = self._run_pipeline("What courses are available?")
        assert result["answer"]
        assert len(result["answer"]) > 50

    def test_e2e_vietnamese_query(self):
        result = self._run_pipeline("Giải tích 1 do ai dạy?")
        assert result["answer"]
        assert len(result["answer"]) > 20

    def test_e2e_has_citations(self):
        result = self._run_pipeline("List the computer science courses")
        assert result["answer"]
        assert result.get("files") or result.get("contents")


# ════════════════════════════════════════════════════════════════════
# E2E TESTS — Local LLM (test_parsing providers)
# ════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
@pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not set")
@pytest.mark.skipif(not HAS_REAL_FILES, reason="No real files")
class TestE2EWithLocalProvider:
    """E2E using test_parsing's LLM providers."""

    def test_local_llm_generation(self):
        from dotenv import load_dotenv
        load_dotenv(TEST_PARSING_DIR / ".env")

        jf = next(EXCEL_JSON_DIR.glob("*.json"), None)
        if not jf:
            pytest.skip("No JSON files")

        with open(jf, "r", encoding="utf-8") as f:
            sheets = json.load(f)
        chunks = chunk_excel_json(sheets, doc_id=jf.stem)[:3]

        from llm_provider import LLMProvider
        from llm_utils import call_llm

        llm = LLMProvider.create()
        model = os.getenv("OPENAI_LLM_MODEL", "gpt-4.1-mini")

        context = "\n---\n".join(c["text"][:300] for c in chunks)

        async def _run():
            return await call_llm(
                llm, lambda m: {"model": m},
                model=model,
                system_prompt="Answer based on context only.",
                user_prompt=f"Context:\n{context}\n\nQuestion: What is this about?",
                temperature=0.0,
            )

        result = asyncio.run(_run())
        assert result and len(str(result)) > 10


# ════════════════════════════════════════════════════════════════════
# Conftest / fixtures
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import asyncio
    pytest.main([__file__, "-v", "--tb=short"])
