# OmniDocBench Parsing Evaluation Summary

## 1. Overview

This document summarizes the methodology and evaluation framework for document parsing strategies on PDF documents within the project. The framework focuses on **Component-level Metrics**, comparing the structure extracted by our pipeline against standard benchmark annotations (OmniDocBench) to ensure no critical formatting, reading order, or component loss occurs.

## 2. Evaluation Data (Ground Truth)

The evaluation utilizes the full dataset provided by **OmniDocBench**.

- **Source Files**: Located in `data/omnidocbench/images` and evaluated as PDF/image pages.
- **Ground Truth**: JSON annotations directly from `data/omnidocbench/OmniDocBench.json`.
- **Dataset Scope**: Includes 1650 annotated pages covering equation-heavy academic literature, textbooks, presentations, and standard documents, containing complex charts, tables, and reading flow layouts.

`data/omnidocbench` and optional `third_party/OmniDocBench` metric code are local benchmark assets and are intentionally ignored by git. Restore them locally before running this evaluation; do not commit input images, benchmark JSON, or generated results.

## 3. Evaluated Parsers

1. **`DocumentProcessorV2`**: Our main internal parsing system operating in Hybrid Mode. It uses `ItemSequencer` (embedding `PyMuPDF`) for structural hierarchy combined with `Docling` (local mode, OCR enabled) for raw text and table extraction. Vision Language Models (VLMs) were disabled for this run.

## 4. Evaluation Metrics

The parsed results are scored using the official OmniDocBench evaluation configurations with weighted groups:

- **Text (F1/Jaccard)** (Weight 30%): Content-only token overlap measuring text extraction fidelity.
- **Table (TEDS / Edit Sim)** (Weight 25%): Structural and content similarity for tables using the official TEDS algorithm combined with edit distance.
- **Read Order** (Weight 15%): Tests if the extracted content follows the correct logical flow of the document (critical for multi-column layouts).
- **Figure Captioning** (Weight 15%): Ability to associate images/figures with their correct descriptive captions.
- **Section Hierarchy** (Weight 15%): Nested header structuring (Disabled in this run).

## 5. Results & Observations

**Recent Evaluation Results** (Sample Size: 1650 pages, Output: `backend/output/evaluation/parsing_info_loss_omnidocbench_full`):

| Parser Strategy | Total Pages | Skipped | Overall Score | Read Order | Table Score | Text Score | Figure Captions |
|-----------------|-------------|---------|---------------|------------|-------------|------------|------------------|
| **DocumentProcessorV2 (Hybrid)** | 1650 | 3 | 58.91% | 92.60% | 76.86% | 47.43% | N/A |

**Analysis**:

- **Exceptional Reading Order**: The pipeline excels at preserving logical text flow (`0.925`), proving robustness on multi-column and complex layouts.
- **Strong Table Extraction**: The extraction of tables (`0.768`) is very reliable. Docling's extraction engine, even without VLM aid, correctly interprets grid formations for TEDS scoring.
- **Text Extraction Bottleneck**: Text fidelity remains relatively low (`0.474`). Factors pulling this down include missing complex LaTeX/formulas, text block fragmentation, and potential OCR noise on heavily mathematical pages.
- **Figure Captioning**: Not applicable in this evaluation run (no figure captioning data available).

## 6. Commands Reference

- **Run OmniDocBench Evaluation**:
  ```bash
  python backend/evals/parsing/pdf/run_omnidocbench_parsing_eval.py \
    --config backend/config/parsing_info_loss_eval.yaml \
    --output-dir backend/output/evaluation/parsing_info_loss_omnidocbench_full
  ```
