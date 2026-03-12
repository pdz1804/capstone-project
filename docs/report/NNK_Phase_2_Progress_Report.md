# Excel Content Understanding: Use Cases, Current Progress & Future Work

This document combines the stakeholder-oriented use cases for the Excel parsing feature with the technical progress guide outlining the current state of the Excel RAG (Retrieval-Augmented Generation) pipeline.

---

## Part 1: Stakeholder-Oriented Use Cases for Excel Parsing

### 1. Scope Clarification

This section describes the stakeholder-oriented use cases for an Excel parsing feature using a cleaner taxonomy. The target stakeholder groups are **Business Analyst (BA), Data Analyst (DA), Project Manager (PM), Human Resources (HR), Accountant**, and a more cautious **Computer Science (CS) / technical student** category. In this version, **UAT/QA is not treated as a primary stakeholder group**, because it was not part of the original user list. UAT- and QA-related spreadsheets may still appear in practice, but they should be considered adjacent artifacts rather than a replacement for BA-oriented work.

### 2. Role of the Excel Parsing Feature

The purpose of the Excel parsing feature is to convert spreadsheet workbooks into structured, machine-readable representations while preserving the information that gives the workbook meaning: sheet boundaries, logical tables, formulas, headers, merged cells, comments, visual summaries, and cross-sheet relationships. This matters because Excel is often used not just as a raw data container but also as a lightweight planning, reporting, and decision-support environment. Microsoft’s own guidance on PivotTables, PivotCharts, and dashboard construction makes that point rather loudly in spreadsheet dialect.

### 3. Stakeholder-Specific Use Cases and Corresponding Excel File Features

#### 3.1 Business Analyst (BA)

**Use case.**
A business analyst uses Excel to organize and communicate business analysis artifacts such as stakeholder lists, prioritization matrices, requirement mappings, process-related inventories, RACI-style responsibility views, and traceability-oriented records. IIBA defines business analysis as enabling change by defining needs and recommending solutions that deliver value, and its materials emphasize stakeholder lists, requirement traceability, prioritization, and maintaining relationships between business needs and solution elements.

**Typical Excel file features.**
BA-oriented workbooks are usually **text-heavy rather than number-heavy**. They often contain multiple worksheets, structured identifiers such as requirement IDs or stakeholder IDs, ownership columns, priority/status columns, business-rule notes, dependency references, and sectioned matrices. Compared with analyst or finance files, BA workbooks usually rely less on dense numeric computation and more on **semi-structured tables**, categorization fields, and mapping relationships across sheets. A professional parser for BA files should therefore be strong at detecting logical tables, multi-column text records, cross-references, and layout cues that separate sections of analysis rather than just reading plain rectangular data.

#### 3.2 Data Analyst (DA)

**Use case.**
A data analyst uses Excel to clean data, inspect distributions, summarize business performance, build dashboards, and communicate insights through aggregated views. This is closely aligned with the spreadsheet’s strengths in summarization and visual analysis: Microsoft explicitly positions PivotTables and PivotCharts as tools to summarize, analyze, explore, and present data, and to build interactive dashboards with slicers, timelines, and linked views. IBM’s data analyst training materials also continue to treat Excel spreadsheets as a practical tool in the analyst workflow.

**Typical Excel file features.**
DA-oriented workbooks usually have a **raw-data sheet plus one or more summary or dashboard sheets**. Typical signals include long row-based datasets, typed columns, calculated fields, PivotTables, PivotCharts, KPI blocks, slicers, timelines, filters, conditional formatting, and chart-heavy summary pages. These workbooks are usually more quantitative than BA files and more presentation-oriented than accounting ledgers. A parser for DA files should preserve worksheet roles, detect large tabular regions, retain formula columns, and capture dashboard-linked objects and summary structures without flattening the workbook into CSV mush.

#### 3.3 Project Manager (PM)

**Use case.**
A project manager uses Excel to coordinate schedules, milestones, budgets, resource assignments, risks, issue logs, and progress reporting. PMI and BLS both describe project management work in terms of coordinating budget, schedule, staffing, and other project details, while PMI materials repeatedly refer to work breakdown structures, schedules, Gantt-style planning, and risk-oriented tracking artifacts.

**Typical Excel file features.**
PM workbooks often contain **task tables**, owner columns, start and end dates, milestone flags, dependency references, percent-complete fields, cost columns, issue logs, and risk registers. Visually, they may include Gantt-like timeline layouts, milestone charts, or schedule summary sheets. They are often multi-sheet workbooks, with one sheet for the work plan, another for risks or issues, and another for status reporting. A parser for PM files should therefore handle date-rich structures, hierarchical task plans, progress metrics, and logs/registers that are operational rather than purely financial or analytical.

#### 3.4 Human Resources (HR)

**Use case.**
HR teams use Excel for employee records, attendance monitoring, workforce planning, performance-cycle support, recruitment tracking, training matrices, and HR information management. SHRM highlights attendance management, HRIS design, record-keeping, and performance management as core HR operational areas, while BLS describes HR specialists as working across recruiting, screening, interviewing, placement, and related HR activities.

**Typical Excel file features.**
HR workbooks typically contain **entity-record tables**: one row per employee, applicant, department member, attendance entry, training record, or review cycle entry. Common patterns include date-heavy columns, status categories, department/team fields, note columns, compliance-related fields, and moderate use of conditional formatting to highlight absences, overdue reviews, or candidate stages. Compared with finance workbooks, HR files are less formula-dense; compared with BA files, they are more record-oriented and operational. A parser for HR spreadsheets should prioritize stable row-level extraction, date normalization, category handling, and preservation of comments or notes.

#### 3.5 Accountant

**Use case.**
Accountants use Excel to prepare and examine financial records, reconcile accounts, assemble statements, review balances, track payroll-related entries, and support reporting. The U.S. Bureau of Labor Statistics describes accountants and auditors as preparing and examining financial records, while AICPA/CIMA job postings emphasize reconciliations, general ledger work, sub-ledger checks, payroll-related entries, and financial reporting.

**Typical Excel file features.**
Accounting workbooks are usually the most **regular and ledger-like** of the stakeholder groups. Common signals include transaction tables, account codes, debit/credit columns, posting dates, reference numbers, subtotal and total rows, roll-up formulas, reconciliation sections, and statement-style sheets. They often use strong border formatting and carefully positioned totals because the workbook is part calculation engine, part report. A parser for accountant files should be good at detecting repeated financial row schemas, subtotal logic, formula-based rollups, and relationships between detailed transaction sheets and summary statement sheets.

#### 3.6 Computer Science (CS) / Technical Student

**Use case.**
This category is less standardized than the others. CS students and technical users may use Excel for benchmark tracking, experiment logging, grade calculations, bug or issue summaries, lightweight dataset inspection, resource planning, or project status tracking. There is no single canonical “CS spreadsheet” artifact in the way there is for a ledger or attendance table. Research on spreadsheet benchmarks emphasizes that real-world spreadsheet use cases are highly diverse rather than neatly uniform, and Microsoft’s student-oriented spreadsheet pages also lean toward planning, assignment tracking, and lightweight organization rather than one fixed technical format.

**Typical Excel file features.**
CS-oriented workbooks are therefore best described as **heterogeneous**. They may contain experiment tables, runtime or accuracy comparisons, grading matrices, issue trackers, task lists, or mixed technical logs. Typical patterns include metric columns, scenario/run identifiers, comparison tables, date/version fields, and occasional charts used to compare results across algorithms or iterations. A parser should not overfit to one structure here. Instead, it should be robust to semi-structured technical tables, sparse metadata, multiple small worksheets, and ad hoc layouts created by students or engineering teams in a hurry—which is a wonderfully chaotic human tradition.

---

## Part 2: Technical Progress & Future Work

This section outlines the current state of the Excel RAG pipeline, detailing the parser implementations, chunking strategies, LLM integration, and areas identified for future development.

### 1. Excel Parser (`xlsx_reader_v2.py`)

The parser is built to aggressively interpret the underlying XML of Document objects without relying on bloated generic libraries. It translates raw Excel files into highly structured JSON representations optimized for LLM processing.

**Completed Features:**

- **Zero-Dependency Native Parsing (`.xlsx`)**: Unzips raw Excel streams and directly builds DOMs from the underlying XML (`xl/worksheets/sheet*.xml`).
- **Comprehensive Cell Data Types**: Robust resolution of shared strings (`sharedStrings.xml`), numbers, inline strings, booleans, and evaluated formula strings.
- **Merged Cell Value Propagation**: Automatically identifies `<mergeCells>` and dynamically propagates the value of the top-left cell across all spanned sub-cells. This ensures that when the table is eventually chunked, no cells are left "empty" due to structural merging.
- **Styling and Render Semantics**: Extracts `styles.xml` data including fonts (bold, italic), fills/backgrounds, and specific `numFmt` codes (dates, currencies, percentages). This is attached to cells as a compact styling summary to give the LLM visual context cues.
- **Formal Excel Tables (`xl/tables/`)**: Explicit extraction of designated XML tables, identifying defined column headers independently of the cell grid.
- **Hyperlink Extraction**: Captures `xl/_rels/` logic to properly link URLs back to standard cell references (e.g., `= HYPERLINK(...)`).
- **Multimodal Artifacts (Drawings)**: Parses `xl/drawings/` structures. Media items are embedded into the layout utilizing positional markers such as `[START_IMAGE]path/to/media[END_IMAGE]` and `[START_SHAPE]text[END_SHAPE]` accurately mapped by reading their internal `<xdr:from>` properties.

### 2. Table-Aware Chunker (`excel_chunker.py`)

Because naive text splitting destroys tabular arrangements, the pipeline uses a custom `ExcelTableChunker` that acts intelligently on the parser's structured JSON.

**Completed Features:**

- **Markdown-to-Entity Structural Parsing**: Converts parsed markdown grids into explicit `TableBlock`, `Row`, and `Cell` datatypes.
- **Key-Value Serialization (Embedding Optimized)**: Reconstructs standard tables into localized Key-Value paragraphs instead of markdown.
  *Example:* `Sheet: ĐẠI CƯƠNG. Section: TOÁN. Course: MT1003. Title: Giải tích 1. Lecturer: Võ Trần An.`
  This radically improves dense vector embeddings which often fail to interpret pipe-delimited `|` text grids.
- **Granular "Row Entity" Documents**: Generates atomic micro-documents for each row (`type: row_entity`). This guarantees high precision for lookup questions based around specific identifiers (e.g. searching a specific course code).
- **Header Repetition on Large Tables**: Enforces strict row limits per chunk (`max_rows_per_chunk`). When tables exceed limits, they are split horizontally, but the column headers and `[Sheet/Section]` contexts are repeated on every chunk.
- **Image Artifact Passthrough**: Explicitly identifies `[START_IMAGE]` blocks and attaches the image paths directly to chunk metadata (`metadata.image_paths`) ensuring compatibility with Multimodal embedding paths.

### 3. LLM Integration & Retrieval (`run_excel_e2e.py`)

The retrieval phase operates on the JSON outputs from the chunker, feeding targeted semantic chunks directly to language models to answer user queries.

**Completed Features:**

- **End-to-End Search Pipeline**: Scripted processes run seamlessly from raw `.xlsx` → Parse → Chunk → Search → Generate (via `run_excel_e2e.py`).
- **BM25 & Keyword Pre-Retrieval**: Integrated BM25 implementation for hard keyword matching. Structured spreadsheet data often demands strict terminology lookup (e.g. course codes, explicit names) rather than fuzzy semantic concepts.
- **RAG Generation Layer (`src/generation/generator.py`)**: Hands the LLM deeply contextualized text snippets (with Sheet Names and Table Header contexts attached to each snippet). Supports multiple LLM providers seamlessly (`OpenAI`, `AWS Bedrock`).
- **Built-in Source Citation**: Final generation explicitly outputs provenance traces (`[1.2]`) allowing users to track the origin of any returned data directly back to its worksheet name and row ID.
- **Full Web UI Capability**: Fully integrated end-to-end via the FastAPI backend and Vite frontend (Upload → Process → Index → Query).

### 4. Future Work & Next Steps

- **Reliable `.xls` & `.xlsm` Handling**: Currently relies on LibreOffice conversions for legacy formats which may introduce formatting bugs or data loss. Exploring native binary readers (like `xlrd`) or python converters to eliminate dependencies on headless office suites.
- **Hybrid Retrieval Fine-Tuning**: Finding the optimum weighting ratio between Dense Embedding searches (semantic reasoning) and Sparse Vectors / BM25 (exact text/code lookups), which is critical for highly distinct table data.
- **Complex Multi-level Headers**: Expand `ExcelTableChunker` to handle deeply nested and multi-tiered hierarchical headers intelligently, likely utilizing more advanced semantic tagging.
- **Full Multimodal RAG Queries**: Upgrade the final LLM step to accept the embedded `[START_IMAGE]` charts directly as base64 images into `GPT-4o` rather than limiting retrieval to textual data only.
- **Format Extension (Docx & Born-Digital PDFs)**: Extend content understanding to docx and born-digital pdfs without relying on Docling. Keep Docling strictly for scanned pdfs (not born-digital) to reduce API calls and improve speed and performance.
- **Advanced Chunking and Retrieval Strategies**: Develop and research more methods of chunking for each type of format (text, tables, charts, diagrams...) and corresponding retrieval strategies.
