# Data Manifest

Generated: 2026-07-04 10:37:59 +07

This repository now separates code/docs from local data. Data folders are intentionally ignored by Git and should be uploaded to Drive before local deletion.

## Restore Convention

Copy Drive data back into the same relative paths:

```text
Drive/capstone-project/Phase_1/data/ -> Phase_1/data/
Drive/capstone-project/Phase_2/data/ -> Phase_2/data/
```

Code and report folders remain in Git. Final report PDFs are intentionally kept tracked.

## Phase 1 Data

| Local path | Size | Purpose | Drive target |
| --- | ---: | --- | --- |
| `Phase_1/data/` | ~61 MB | All Phase 1 raw inputs and generated outputs after exact-duplicate consolidation | `Drive/capstone-project/Phase_1/data/` |
| `Phase_1/data/processing_rag_pipeline/` | ~30 MB | RAG framework outputs, Docling inputs, unified processor inputs, integrated pipeline inputs, and shared processor inputs | `Drive/capstone-project/Phase_1/data/processing_rag_pipeline/` |
| `Phase_1/data/retrieval/` | ~29 MB | Retrieval benchmark outputs and lecture PDF corpus | `Drive/capstone-project/Phase_1/data/retrieval/` |
| `Phase_1/data/asr_ocr/` | ~2.8 MB | ASR/OCR shared baseline outputs and week-specific model-benchmark outputs | `Drive/capstone-project/Phase_1/data/asr_ocr/` |
| `Phase_1/data/processing_rag_pipeline/week0506_docling_inputs/` | ~16 MB | Week 05-06 Docling processor input files after shared duplicates were moved out | `Drive/capstone-project/Phase_1/data/processing_rag_pipeline/week0506_docling_inputs/` |
| `Phase_1/data/retrieval/week0304_baseline_results/` | ~15 MB | Week 03-04 retrieval benchmark result files | `Drive/capstone-project/Phase_1/data/retrieval/week0304_baseline_results/` |
| `Phase_1/data/processing_rag_pipeline/shared_exact_duplicates/` | ~6.7 MB | Exact duplicate processor artifacts consolidated by hash | `Drive/capstone-project/Phase_1/data/processing_rag_pipeline/shared_exact_duplicates/` |
| `Phase_1/data/processing_rag_pipeline/shared_inputs/` | ~6.2 MB | Shared processor inputs reused across multiple weeks | `Drive/capstone-project/Phase_1/data/processing_rag_pipeline/shared_inputs/` |
| `Phase_1/data/retrieval/week0506_production_results/` | ~7.6 MB | Week 05-06 retrieval benchmark result files | `Drive/capstone-project/Phase_1/data/retrieval/week0506_production_results/` |
| `Phase_1/data/retrieval/week070809_pdf_corpus/` | ~5.6 MB | Week 07-09 retrieval PDF corpus | `Drive/capstone-project/Phase_1/data/retrieval/week070809_pdf_corpus/` |
| `Phase_1/data/asr_ocr/shared_ocr_outputs/` | ~2.3 MB | Exact duplicate OCR page outputs shared by Week 03-04 and Week 05-06 | `Drive/capstone-project/Phase_1/data/asr_ocr/shared_ocr_outputs/` |
| `Phase_1/data/asr_ocr/week0506_model_benchmark_outputs/` | ~356 KB | Week 05-06 ASR/OCR generated outputs that are not exact duplicates | `Drive/capstone-project/Phase_1/data/asr_ocr/week0506_model_benchmark_outputs/` |

## Phase 2 Data

| Local path | Size | Purpose | Drive target |
| --- | ---: | --- | --- |
| `Phase_2/data/` | ~2.7 GB | All Phase 2 raw inputs, generated artifacts, eval data, and third-party local checkouts | `Drive/capstone-project/Phase_2/data/` |
| `Phase_2/data/backend/input/` | ~1.2 GB | Backend raw/document/eval input data | `Drive/capstone-project/Phase_2/data/backend/input/` |
| `Phase_2/data/backend/evals/` | ~822 MB | Evaluation datasets, workdirs, and generated eval outputs | `Drive/capstone-project/Phase_2/data/backend/evals/` |
| `Phase_2/data/backend/output/` | ~351 MB | Pipeline outputs and parsed/generated artifacts | `Drive/capstone-project/Phase_2/data/backend/output/` |
| `Phase_2/data/backend/src/processor/` | ~175 MB | Generated parser scratch artifacts formerly under source tree | `Drive/capstone-project/Phase_2/data/backend/src/processor/` |
| `Phase_2/data/third_party/` | ~173 MB | External benchmark/tool checkouts kept out of Git | `Drive/capstone-project/Phase_2/data/third_party/` |
| `Phase_2/data/frontend/dist/` | ~17 MB | Frontend build output | `Drive/capstone-project/Phase_2/data/frontend/dist/` |
| `Phase_2/data/docs/jmeter-capacity-tests/` | small | Generated JMeter run data and sample upload data | `Drive/capstone-project/Phase_2/data/docs/jmeter-capacity-tests/` |
| `Phase_2/data/sagemaker/` | small | Generated SageMaker endpoint logs and deployment scratch data | `Drive/capstone-project/Phase_2/data/sagemaker/` |

## Tracked Report Artifacts

These remain in Git by design:

- `Phase_1/Report/HK251-DAGD1-244_2252378_2252377_2252621.pdf`
- `Phase_2/Report/HK252_180_DATN_Finish_2252377_2252378_2252621.pdf`
- `Phase_2/Manuscript/main.pdf`
- report and manuscript LaTeX/BibTeX sources

## Notes

- `Phase_1/data/` and `Phase_2/data/` are ignored. Git will not show their contents after the cleanup is staged.
- Phase 1 data was checked for exact SHA-256 duplicates during cleanup. 603 duplicate groups were consolidated into shared data folders, removing 609 duplicate copies. Same-name files are only treated as duplicates when SHA-256 also matches.
- Do not delete local data until the Drive upload has been verified.
- `git filter-repo` is required to remove older committed copies from Git history; it is not installed in this environment at the time of this cleanup.
