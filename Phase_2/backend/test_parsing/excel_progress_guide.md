# Excel Content Understanding: Current Progress & Future Work

This guide outlines the current state of the Excel RAG (Retrieval-Augmented Generation) pipeline, detailing the parser implementations, chunking strategies, LLM integration, and areas identified for future development.

---

## 1. Excel Parser ([xlsx_reader_v2.py](file:///home/khoinn12/Documents/cap/capstone-project/Phase_2/backend/test_parsing/xlsx_reader_v2.py))
The parser is built to aggressively interpret the underlying XML of Document objects without relying on bloated generic libraries. It translates raw Excel files into highly structured JSON representations optimized for LLM processing.

### **Completed Features:**
- **Zero-Dependency Native Parsing (`.xlsx`)**: Unzips raw Excel streams and directly builds DOMs from the underlying XML (`xl/worksheets/sheet*.xml`).
- **Comprehensive Cell Data Types**: Robust resolution of shared strings (`sharedStrings.xml`), numbers, inline strings, booleans, and evaluated formula strings.
- **Merged Cell Value Propagation**: Automatically identifies `<mergeCells>` and dynamically propagates the value of the top-left cell across all spanned sub-cells. This ensures that when the table is eventually chunked, no cells are left "empty" due to structural merging.
- **Styling and Render Semantics**: Extracts `styles.xml` data including fonts (bold, italic), fills/backgrounds, and specific `numFmt` codes (dates, currencies, percentages). This is attached to cells as a compact styling summary to give the LLM visual context cues.
- **Formal Excel Tables (`xl/tables/`)**: Explicit extraction of designated XML tables, identifying defined column headers independently of the cell grid.
- **Hyperlink Extraction**: Captures `xl/_rels/` logic to properly link URLs back to standard cell references (e.g., `= HYPERLINK(...)`).
- **Multimodal Artifacts (Drawings)**: Parses `xl/drawings/` structures. Media items are embedded into the layout utilizing positional markers such as `[START_IMAGE]path/to/media[END_IMAGE]` and `[START_SHAPE]text[END_SHAPE]` accurately mapped by reading their internal `<xdr:from>` properties.

---

## 2. Table-Aware Chunker ([excel_chunker.py](file:///home/khoinn12/Documents/cap/capstone-project/Phase_2/backend/src/chunking/excel_chunker.py))
Because naive text splitting destroys tabular arrangements, the pipeline uses a custom [ExcelTableChunker](file:///home/khoinn12/Documents/cap/capstone-project/Phase_2/backend/src/chunking/excel_chunker.py#301-781) that acts intelligently on the parser's structured JSON.

### **Completed Features:**
- **Markdown-to-Entity Structural Parsing**: Converts parsed markdown grids into explicit [TableBlock](file:///home/khoinn12/Documents/cap/capstone-project/Phase_2/backend/src/chunking/excel_chunker.py#66-81), [Row](file:///home/khoinn12/Documents/cap/capstone-project/Phase_2/backend/src/chunking/excel_chunker.py#60-64), and [Cell](file:///home/khoinn12/Documents/cap/capstone-project/Phase_2/backend/src/chunking/excel_chunker.py#53-58) datatypes. 
- **Key-Value Serialization (Embedding Optimized)**: Reconstructs standard tables into localized Key-Value paragraphs instead of markdown. 
  *Example:* `Sheet: ĐẠI CƯƠNG. Section: TOÁN. Course: MT1003. Title: Giải tích 1. Lecturer: Võ Trần An.`
  This radically improves dense vector embeddings which often fail to interpret pipe-delimited `|` text grids.
- **Granular "Row Entity" Documents**: Generates atomic micro-documents for each row (`type: row_entity`). This guarantees high precision for lookup questions based around specific identifiers (e.g. searching a specific course code).
- **Header Repetition on Large Tables**: Enforces strict row limits per chunk (`max_rows_per_chunk`). When tables exceed limits, they are split horizontally, but the column headers and `[Sheet/Section]` contexts are repeated on every chunk.
- **Image Artifact Passthrough**: Explicitly identifies `[START_IMAGE]` blocks and attaches the image paths directly to chunk metadata (`metadata.image_paths`) ensuring compatibility with Multimodal embedding paths.

---

## 3. LLM Integration & Retrieval ([run_excel_e2e.py](file:///home/khoinn12/Documents/cap/capstone-project/Phase_2/backend/test_parsing/run_excel_e2e.py))
The retrieval phase operates on the JSON outputs from the chunker, feeding targeted semantic chunks directly to language models to answer user queries.

### **Completed Features:**
- **End-to-End Search Pipeline**: Scripted processes run seamlessly from raw `.xlsx` → Parse → Chunk → Search → Generate (via [run_excel_e2e.py](file:///home/khoinn12/Documents/cap/capstone-project/Phase_2/backend/test_parsing/run_excel_e2e.py)).
- **BM25 & Keyword Pre-Retrieval**: Integrated BM25 implementation for hard keyword matching. Structured spreadsheet data often demands strict terminology lookup (e.g. course codes, explicit names) rather than fuzzy semantic concepts.
- **RAG Generation Layer ([src/generation/generator.py](file:///home/khoinn12/Documents/cap/capstone-project/Phase_2/backend/src/generation/generator.py))**: Hands the LLM deeply contextualized text snippets (with Sheet Names and Table Header contexts attached to each snippet). Supports multiple LLM providers seamlessly (`OpenAI`, `AWS Bedrock`).
- **Built-in Source Citation**: Final generation explicitly outputs provenance traces (`[1.2]`) allowing users to track the origin of any returned data directly back to its worksheet name and row ID.
- **Full Web UI Capability**: Fully integrated end-to-end via the FastAPI backend and Vite frontend (Upload → Process → Index → Query).

---

## 4. Future Work & Next Steps
- **Reliable `.xls` & `.xlsm` Handling**: Currently relies on LibreOffice conversions for legacy formats which may introduce formatting bugs or data loss. Exploring native binary readers (like `xlrd`) or python converters to eliminate dependencies on headless office suites.
- **Hybrid Retrieval Fine-Tuning**: Finding the optimum weighting ratio between Dense Embedding searches (semantic reasoning) and Sparse Vectors / BM25 (exact text/code lookups), which is critical for highly distinct table data.
- **Complex Multi-level Headers**: Expand [ExcelTableChunker](file:///home/khoinn12/Documents/cap/capstone-project/Phase_2/backend/src/chunking/excel_chunker.py#301-781) to handle deeply nested and multi-tiered hierarchical headers intelligently, likely utilizing more advanced semantic tagging.
- **Full Multimodal RAG Queries**: Upgrade the final LLM step to accept the embedded `[START_IMAGE]` charts directly as base64 images into `GPT-4o` rather than limiting retrieval to textual data only.
