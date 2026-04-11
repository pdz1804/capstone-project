# Document Content Understanding: Excel & DOCX - Progress & Use Cases

This document outlines the current state of the intelligent document processing pipeline, covering stakeholder-oriented use cases, technical implementations for Excel and DOCX formats, and advanced RAG features like multimodal citations.

---

## Part 1: Stakeholder-Oriented Use Cases for Excel Parsing

### 1. Scope Clarification

This section describes the stakeholder-oriented use cases for an Excel parsing feature using a cleaner taxonomy. The target stakeholder groups are **Business Analyst (BA), Data Analyst (DA), Project Manager (PM), Human Resources (HR), Accountant**, and a more cautious **Computer Science (CS) / technical student** category. In this version, **UAT/QA is not treated as a primary stakeholder group**, because it was not part of the original user list. UAT- and QA-related spreadsheets may still appear in practice, but they should be considered adjacent artifacts rather than a replacement for BA-oriented work.

### 2. Role of the Excel Parsing Feature

The purpose of the Excel parsing feature is to convert spreadsheet workbooks into structured, machine-readable representations while preserving the information that gives the workbook meaning: sheet boundaries, logical tables, formulas, headers, merged cells, comments, visual summaries, and cross-sheet relationships. This matters because Excel is often used not just as a raw data container but also as a lightweight planning, reporting, and decision-support environment. Microsoft’s own guidance on PivotTables, PivotCharts, and dashboard construction makes that point rather loudly in spreadsheet dialect.

### 3. Stakeholder-Specific Use Cases and Corresponding Excel File Features

#### 3.1 Business Analyst (BA)
**Use case.**  
A business analyst uses Excel to organize and communicate business analysis artifacts such as stakeholder lists, prioritization matrices, requirement mappings, process-related inventories, RACI-style responsibility views, and traceability-oriented records. 

**Typical Excel file features.**  
BA-oriented workbooks are usually **text-heavy rather than number-heavy**. They often contain semi-structured tables, categorization fields, and mapping relationships across sheets.

#### 3.2 Data Analyst (DA)
**Use case.**  
A data analyst uses Excel to clean data, inspect distributions, summarize business performance, build dashboards, and communicate insights through aggregated views. 

**Typical Excel file features.**  
DA-oriented workbooks usually have a **raw-data sheet plus one or more summary or dashboard sheets**. Typical signals include long row-based datasets, PivotTables, PivotCharts, KPI blocks, and chart-heavy summary pages.

#### 3.3 Project Manager (PM)
**Use case.**  
A project manager uses Excel to coordinate schedules, milestones, budgets, resource assignments, risks, issue logs, and progress reporting. 

**Typical Excel file features.**  
PM workbooks often contain **task tables**, owner columns, start/end dates, milestone flags, dependency references, and risk registers.

#### 3.4 Human Resources (HR)
**Use case.**  
HR teams use Excel for employee records, attendance monitoring, workforce planning, recruitment tracking, training matrices, and HR information management. 

**Typical Excel file features.**  
HR workbooks typically contain **entity-record tables**: one row per employee, applicant, or training record. They are record-oriented and operational with moderate use of conditional formatting.

#### 3.5 Accountant
**Use case.**  
Accountants use Excel to prepare and examine financial records, reconcile accounts, assemble statements, review balances, and track payroll. 

**Typical Excel file features.**  
Accounting workbooks are usually **regular and ledger-like**, containing transaction tables, account codes, debit/credit columns, subtotal/total rows, and formula-based rollups.

#### 3.6 Computer Science (CS) / Technical Student
**Use case.**  
CS students use Excel for benchmark tracking, experiment logging, grade calculations, bug summaries, and lightweight dataset inspection. 

**Typical Excel file features.**  
These workbooks are **heterogeneous**. They may contain experiment tables, runtime or accuracy comparisons, metric columns, and scenario identifiers.

---

## Part 2: Stakeholder-Oriented Use Cases for DOCX Parsing

### 1. Role of the DOCX Parsing Feature

The DOCX parsing feature extracts structured text, hierarchical headings, nested lists, and embedded tables/images from Microsoft Word documents. Unlike raw text extraction, it preserves the document's logical hierarchy, which is critical for context-aware RAG systems.

### 2. Stakeholder-Specific Use Cases

#### 2.1 Business Analyst (BA)
**Use case.**  
BAs create Requirements Documents (PRDs), Business Cases, and Market Research reports. These documents define project scope and justification.

**Typical DOCX features.**  
Hierarchical headings (H1-H6), nested bullet/numbered lists, tables for requirement tracking, and embedded charts or research images.

#### 2.2 Legal & Compliance
**Use case.**  
Legal teams manage Contracts, TOS, and Regulatory Filings. Precision in clause numbering and section hierarchy is critical.

**Typical DOCX features.**  
Numbered clauses (e.g., 1.1, 1.2.1), cross-references between sections, complex formatting in tables (e.g., definitions), and headers/footers with versioning info.

#### 2.3 Technical Writer / Engineer
**Use case.**  
Engineers author Technical Specifications, API Documentation, and Design Docs. These often mix prose with structured data.

**Typical DOCX features.**  
Code blocks (mono-spaced styling), diagrams (embedded shapes/images), complex tables for parameters, and version history tables.

#### 2.4 Human Resources (HR)
**Use case.**  
HR uses Word for Employee Handbooks, Job Descriptions, and Performance Review templates.

**Typical DOCX features.**  
Standardized templates, long lists of responsibilities, tables for competency matrices, and comment-heavy review sections.

#### 2.5 Project Manager (PM)
**Use case.**  
PMs create Project Charters, Risk Management Plans, and Status Reports to track progress and accountability.

**Typical DOCX features.**  
Status tables, milestone lists, and embedded Gantt charts (usually as images).

#### 2.6 CS / Technical Student
**Use case.**  
Students write Research Papers, Lab Reports, and Lecture Notes where technical accuracy is essential.

**Typical DOCX features.**  
Mathematical equations (OMML), citations, bibliographies, multi-column layouts, and figures with detailed captions.

---

## Part 3: Technical Progress - Excel Pipeline (`xlsx_reader_v2.py`, `excel_chunker.py`)

**Completed Features:**
- **Zero-Dependency Native Parsing**: Directly builds DOMs from underlying XML (`xl/worksheets/sheet*.xml`).
- **Merged Cell Value Propagation**: Automatically propagates top-left values across spanned sub-cells.
- **Styling and Render Semantics**: Extracts fonts, fills, and numeric formats (dates, currencies) as context cues.
- **Formal Excel Tables**: Explicit extraction of designated XML tables and column headers.
- **Image Artifact Passthrough**: Maps images/shapes to positional markers (`[START_IMAGE]`) for multimodal support.
- **Key-Value Serialization**: Reconstructs tables into localized paragraphs (e.g., `Sheet: A. Section: B. Key: Value`) to improve vector embeddings.
- **Granular Row Entity Documents**: Generates atomic documents for each row (`type: row_entity`) for high-precision retrieval.

---

## Part 4: Technical Progress - DOCX Pipeline (`docx_reader_v2.py`, `docx_chunker.py`)

**Completed Features:**
- **Zero-Dependency XML-to-Markdown Parsing**: Direct extraction of `word/document.xml`, bypassing heavy libraries for speed and accuracy.
- **Hierarchical Heading Extraction**: Intelligent detection of Word styles (Heading 1-9) to reconstruct the document's logical tree.
- **Table-to-Markdown Conversion**: Preserves tabular structure, cell merging, and formatting while converting to RAG-friendly Markdown.
- **Complex List & Numbering Support**: Resolves nested bullet points and multi-level numbering (`1.1.a`, `(i)`, etc.) into correct textual markers.
- **Multimodal Artifact Extraction**: Identifies embedded images and shapes, mapping them to specific locations using `[START_IMAGE_PATH]` markers.
- **Table-Aware Chunking**: Splits content while keeping tables whole (where possible) and repeating headers for large tables.
- **Breadcrumb Metadata**: Each chunk carries its full heading hierarchy (e.g., `Part 2 > Section 3.1`), providing structural context to the LLM.

---

## Part 5: UI & Retrieval Enhancements

**Completed Features:**
- **Image-Enabled Citations**: The frontend (`CitationCard.jsx`) now renders embedded images directly within citation previews. Users see visual context immediately upon retrieval.
- **Rich Citation Metadata**: Displays detailed provenance including source filename, score, and processing timestamps.
- **BM25 & Keyword Pre-Retrieval**: Integrated BM25 for hard keyword matching, critical for technical terms and course codes.
- **Source Citation Provenance**: Final LLM generations include interactive markers (`[1.2]`) that link back to the exact section or table row origin.

---

## Part 6: Future Work & Next Steps

- **Reliable `.xls` & `.xlsm` Handling**: Exploring native binary readers (like `xlrd`) to eliminate dependency on headless office suites.
- **Hybrid Retrieval Fine-Tuning**: Finding the optimum weighting ratio between Dense Embedding (semantic) and Sparse Vectors / BM25 (exact lookups).
- **Complex Multi-level Headers**: Expand `ExcelTableChunker` to handle deeply nested hierarchical headers.
- **Full Multimodal RAG Queries**: Upgrade the final LLM step to accept extracted images directly (e.g., charts into GPT-4o).
- **Format Extension (Born-Digital PDFs)**: Extend the custom parsing logic to digital PDFs to reduce Docling API reliance for increased performance.
- **Advanced Chunking Strategies**: Research specialized chunking for charts, diagrams, and complex mathematical notation.

