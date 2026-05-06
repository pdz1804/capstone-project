# Evaluation Runners

This folder contains runnable evaluation and benchmark utilities. Importable
evaluation libraries remain under `backend/src/evaluation`.

## Layout

- `retrieval/`: real user-workspace retrieval eval and related indexing helpers.
- `e2e/`: real user-workspace and local corpus document-intelligence eval.
- `chunking/`: span-level chunking eval generation and strategy comparison.
- `parsing/pdf/`: OmniDocBench and generic PDF parsing information-loss eval.
- `parsing/office/`: OfficeDocBench and DOCX section coverage eval.
- `parsing/media/`: MITFLD/OCW media parsing and frame-alignment eval.
- `parsing/stanford/`: Stanford PDF/PPTX section-hierarchy benchmark helpers.

Do not commit local benchmark inputs, user workspace data, or generated
evaluation outputs. Those are intentionally ignored by git.
