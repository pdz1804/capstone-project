# DOCX RAG Pipeline Guide

This guide details the end-to-end processing pipeline for Microsoft Word (`.docx`) documents, built to preserve the structural and temporal context of business specifications, reports, and manuals.

## Pipeline Architecture

The DOCX pipeline is designed to perfectly mirror the Excel pipeline (`EXCEL_PIPELINE_GUIDE.md`), meaning the downstream Retrieval Augmented Generation (RAG) modules can seamlessly consume DOCX text, tables, and images.

The pipeline consists of three main stages:

### Stage 1: Parser (`docx_reader_v2.py`)
- Reads raw `.docx` XML directly to avoid the performance penalties and abstraction limits of `python-docx`.
- Extracts text while preserving the native **Heading Hierarchy**.
- Converts Word tables into clean Markdown tables bracketed with `[START_TABLE_CONTENT]` and `[END_TABLE_CONTENT]`.
- Extracts drawn shape text using `[START_SHAPE_CONTENT]` and `[END_SHAPE_CONTENT]`.
- Dumps native `<w:drawing>` images to disk and leaves `[START_IMAGE_PATH]...[END_IMAGE_PATH]` tracking markers.
- **Output:** A hierarchical JSON tree where each node represents a section (`heading_text`, `heading_level`, `children`, `content`).

### Stage 2: Preprocessor (`docx_preprocessor.py`)
- Flattens the parsed JSON tree into a single, cohesive `.md` file for full-document context.
- Collects all linked images via regex and copies them into an `images/` directory.
- Creates `docx_manifest.json` telling the retrieval infrastructure that this document has pre-built chunks ready to load.
- Automatically orchestrates the execution of the chunker.

### Stage 3: Chunker (`docx_chunker.py`)
- Inherits from the base `TextChunker`.
- Understands the hierarchical heading JSON structure and constructs a `heading_breadcrumb` metadata array for every chunk (e.g. `["1. System Architecture", "1.1 Backend APIs"]`).
- **Table-Aware logic:** Recognizes markdown tables and either keeps them intact or splits them safely (row-by-row) while repeating headers, circumventing token limit issues while maintaining column context.
- Appends extracted image links into chunk metadata.

## E2E Testing

You can run the full DOCX chunking flow locally on test mock data to verify chunk sizes, table splits, and metadata correctly populate.

```bash
# General usage
python test_parsing/run_docx_e2e.py --json raw/docx/docx_output_293.json

# Using a custom output destination
python test_parsing/run_docx_e2e.py --json raw/docx/custom.json --output /tmp/docx_rag
```

**Expected Output Structure:**
```text
test_parsing/output/docx_rag_ready/docx_output_293/
├── docx_output_293.md         # Full unified markdown file
├── docx_chunks.json           # Array of standard chunks with heading metadata
├── docx_manifest.json         # Metadata indicating valid DOCX processing
└── images/                    # Extracted figures and schematics
```

## Why this Architecture?
Unlike standard Langchain RecursiveCharacterTextSplitters, this explicit hierarchy-aware approach ensures:
1. When retrieving a random paragraph halfway down page 82, the LLM still knows it belongs to "Appendix C: Security Specifications". 
2. Complex parameter tables extracted from Word don't lose their Header column when split across chunks.
3. Images are not discarded and remain linked in both the unified text and chunk-level metadata.
