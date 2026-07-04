# Phase 1 Data

`Phase_1/data/` is intentionally ignored by Git. It keeps raw inputs, generated outputs, benchmark artifacts, and intermediate pipeline data needed to reproduce Phase 1 work locally. Upload this folder to Drive before deleting local copies.

## Structure

| Area | Path | Used by | Notes |
| --- | --- | --- | --- |
| ASR/OCR | `asr_ocr/shared_ocr_outputs/` | Week 03-04 and Week 05-06 | Exact-duplicate OCR page outputs consolidated into one shared copy. |
| ASR/OCR | `asr_ocr/shared_exact_duplicates/` | Week 03-04 and Week 05-06 | Exact-duplicate transcript/output files consolidated by hash. |
| ASR/OCR | `asr_ocr/week0304_baseline_outputs/` | Week 03-04 ASR/OCR baseline | Kept as the week marker; exact duplicates were moved into shared ASR/OCR folders. |
| ASR/OCR | `asr_ocr/week0506_model_benchmark_outputs/` | Week 05-06 ASR/OCR benchmark | Week-specific Whisper/Gemini/OCR benchmark outputs that were not exact duplicates. |
| Retrieval | `retrieval/week0304_baseline_results/` | Week 03-04 retrieval baseline | BM25, dense, hybrid, and RRF result files. |
| Retrieval | `retrieval/week0506_production_results/` | Week 05-06 retrieval study | Extended retrieval and reranking benchmark outputs. |
| Retrieval | `retrieval/week070809_pdf_corpus/` | Week 07-09 multimodal retrieval | Lecture PDF corpus for ColPali/image-based retrieval. |
| Processing + RAG | `processing_rag_pipeline/shared_inputs/` | Week 05-06, Week 07-09, and Week 09-11 | Exact-duplicate processor sample inputs consolidated into one shared copy. |
| Processing + RAG | `processing_rag_pipeline/shared_exact_duplicates/` | Multiple processing weeks | Exact duplicates consolidated by hash when they did not fit a simpler shared-input name. |
| Processing + RAG | `processing_rag_pipeline/week0304_framework_outputs/` | Week 03-04 RAG comparison | Framework-comparison outputs. |
| Processing + RAG | `processing_rag_pipeline/week0506_docling_inputs/` | Week 05-06 Docling processor | Week-specific processor inputs; shared exact duplicates moved to shared folders. |
| Processing + RAG | `processing_rag_pipeline/week070809_unified_inputs/` | Week 07-09 unified processor | Week-specific staged-pipeline inputs; shared exact duplicates moved to shared folders. |
| Processing + RAG | `processing_rag_pipeline/week091011_integrated_inputs/` | Week 09-11 integrated app | Week-specific integrated-pipeline inputs; shared exact duplicates moved to shared folders. |

## Duplicate Notes

During cleanup, Phase 1 data was checked for exact SHA-256 duplicates. The cleanup found 603 exact duplicate groups, created 603 canonical shared files, and removed 609 duplicate copies.

The largest duplicate class was ASR/OCR output repeated between Week 03-04 and Week 05-06. Those shared OCR outputs now live in `asr_ocr/shared_ocr_outputs/`, while duplicate transcripts and other exact duplicate ASR/OCR artifacts live in `asr_ocr/shared_exact_duplicates/`.

Shared processor inputs reused across Week 05-06, Week 07-09, and Week 09-11 now live in `processing_rag_pipeline/shared_inputs/` or `processing_rag_pipeline/shared_exact_duplicates/`.

Some files may still share the same basename across weeks. Matching names alone are not treated as duplicates unless SHA-256 also matches.

## Restore From Drive

Restore Drive data into the same relative location:

```text
Drive/capstone-project/Phase_1/data/ -> Phase_1/data/
```

After restore, code should refer to local files through the ignored `Phase_1/data/` tree instead of committing data back into Git.
