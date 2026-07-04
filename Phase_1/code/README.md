# Phase 1 Code

Phase 1 code is grouped by research area instead of weekly delivery folders. The week labels are preserved here as project-progress notes, while the code lives under the domain where it belongs.

## Structure

| Area | Path | What it contains |
| --- | --- | --- |
| ASR/OCR | `asr_ocr/` | Audio/video transcription, slide OCR, and OCR/ASR model comparisons |
| Retrieval | `retrieval/` | Sparse, dense, hybrid, reranking, ColBERT/ColPali, and multimodal retrieval experiments |
| Processing + RAG pipeline | `processing_rag_pipeline/` | Document processing, RAG framework comparisons, and the integrated Phase 1 pipeline |

## ASR/OCR Progress

| Project period | Current path | Summary |
| --- | --- | --- |
| Week 03-04 | `asr_ocr/baseline_ocr_asr/` | First OCR/ASR baseline for extracting slide text and lecture transcripts from media. |
| Week 05-06 | `asr_ocr/multi_model_benchmark/` | Model-comparison work for Whisper, Gemini, and DeepSeek-style OCR/ASR outputs. |

Related local data is under `Phase_1/data/asr_ocr/`.

## Retrieval Progress

| Project period | Current path | Summary |
| --- | --- | --- |
| Week 03-04 | `retrieval/baseline_bm25_dense_hybrid/` | Baseline BM25, dense retrieval, weighted hybrid, and RRF comparisons on MS MARCO-style data. |
| Week 05-06 | `retrieval/production_retrieval/` | Broader retrieval study with MiniLM/BGE, rerankers, ColBERT, ColQwen/ColPali, and Milvus/Pyserini-oriented production notes. |
| Week 07-09 | `retrieval/colpali_modal_retrieval/` | PDF/image retrieval work using ColPali/Modal deployment patterns and lecture PDF corpus experiments. |

Related local data is under `Phase_1/data/retrieval/`.

## Processing And RAG Pipeline Progress

| Project period | Current path | Summary |
| --- | --- | --- |
| Week 03-04 | `processing_rag_pipeline/rag_framework_comparison/` | Early comparison of LangChain, LlamaIndex, and manual RAG pipeline approaches. |
| Week 05-06 | `processing_rag_pipeline/docling_processor/` | Docling-based document conversion and processor exploration. |
| Week 07-09 | `processing_rag_pipeline/unified_processor/` | Unified staged processor: normalization, media handling, document parsing, and consolidation. |
| Week 09-11 | `processing_rag_pipeline/integrated_app/` | Integrated app/pipeline combining document processing, retrieval, evaluation, and API/frontend pieces. |

Related local data is under `Phase_1/data/processing_rag_pipeline/`.

## Data Policy

Do not commit raw inputs, generated outputs, evaluation artifacts, local indexes, or model files. Put them under `Phase_1/data/`, which is intentionally ignored by Git and should be restored from Drive when needed.
