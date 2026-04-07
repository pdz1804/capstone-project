# Document Processing Flow (Local vs Cloud)

This document explains the actual processing flow implemented by the backend pipeline (`POST /api/process`), with two separate modes:

- Local mode
- Cloud mode

It is based on current code in:
- `app/services/processing_service.py`
- `src/processor/pipeline.py`
- `src/processor/normalizer.py`
- `src/processor/media_processor_enhanced.py`
- `src/processor/document_processor.py`
- `src/processor/docling_remote.py`
- `src/processor/whisper_remote.py`
- `src/processor/consolidator.py`
- `app/storage/service.py`

Scope boundary:
- All statements in this document are derived from `Phase_2_FE_AI_Merge/backend/*`.
- Any remote service mention (for example SageMaker endpoints) is described only through interfaces implemented in this folder.

---

## 1) Entry Point and High-Level Lifecycle

### API entry
- Request: `POST /api/process`
- Handler: `app/api/routes/pipeline_routes.py`
- Service call: `run_processing(user_id, force, selected_paths, mode)`

### Main lifecycle inside `run_processing`
1. Resolve per-user workspace paths.
2. Prepare local pipeline input directory (from local disk or S3).
3. Merge runtime config (`default.yaml` + env overrides).
4. Build `PipelineConfig` (normalization/media/docling settings, fast/standard mode).
5. Run `DocumentProcessingPipeline.run()` (Stage 1 -> Stage 2 -> Stage 3 -> Stage 3b -> Stage 4).
6. Publish processing output (local no-op, S3 uploads in cloud mode).
7. Return pipeline stats.

---

## 2) Mode Selection (Local vs Cloud)

### Local mode
Set:
- `FILE_STORAGE_BACKEND=local`

Effects:
- Input is read from `backend/input`.
- Output is written to `backend/output/processing`.
- No S3 sync for input/output.
- Docling/Whisper execution can still be local or SageMaker depending on inference flags.

### Cloud mode
Set:
- `FILE_STORAGE_BACKEND=s3`
- S3 bucket/prefix envs (`S3_ORIGINALS_BUCKET`, `S3_PROCESSED_BUCKET`, etc.)

Effects:
- Canonical input/output are in S3.
- Pipeline executes on a per-user local temp workspace (`workspace_paths_for_user`).
- Before processing: originals are downloaded from S3 into local temp input.
- After processing: full processing tree is uploaded to processed S3 prefix.

---

## 3) Stage-by-Stage Flow (Detailed)

## Stage 0: Input preparation

### Local mode
- `LocalFileStorage.prepare_pipeline_input()` is a no-op.
- Pipeline directly uses files already present in `backend/input`.

### Cloud mode
- `S3FileStorage.prepare_pipeline_input()`:
  - Clears local temp input directory.
  - Lists objects under user input prefix in S3.
  - Downloads all files, or only `selected_paths` if provided.

Note:
- `selected_paths` filtering is implemented in S3 preparation.
- In local mode, processing scope is effectively whatever files are in local input directory.

---

## Stage 1: Document normalization (`stage1_normalized`)

Executor:
- `DocumentNormalizer.normalize_batch()`

Output folders:
- `stage1_normalized/normalized_pdfs`
- `stage1_normalized/normalized_markdown`
- `stage1_normalized/original_files`
- `stage1_normalized/excel_parsed`
- `stage1_normalized/normalization_metadata`

### Per-file-type behavior

- DOCX/DOC:
  - Copy original to `original_files`.
  - Convert to PDF (LibreOffice preferred, ReportLab fallback) in `normalized_pdfs`.

- PPTX/PPT:
  - Copy original to `original_files`.
  - Convert to PDF in `normalized_pdfs`.

- HTML/HTM/MHTML/XHTML:
  - Copy original to `original_files`.
  - Convert to PDF with LibreOffice when available.

- PDF:
  - Copy to `normalized_pdfs`.
  - Also copied into `original_files`.

- TXT:
  - Copy original to `original_files`.
  - Convert to `.md` in `normalized_markdown`.

- MD:
  - Copy to `normalized_markdown`.
  - Also copied into `original_files`.

- Images (`png/jpg/jpeg/bmp/tiff/tif/webp`):
  - Copied to `original_files`.
  - Not converted to PDF (Docling handles images natively later).

- XLSX/XLSM:
  - Copied to `original_files`.
  - Parsed by custom XML parser to JSON in `excel_parsed`.

- XLS:
  - Copied to `original_files` (Docling handles it later).

- CSV / AsciiDoc / VTT:
  - Copied to `original_files` (processed by Docling later).

- Media (`mp4/avi/mov/...`, `wav/mp3/...`):
  - Excluded from Stage 1 document normalization path.
  - Processed in Stage 2.

---

## Stage 2: Media processing (`stage2_media_processed`)

Executor:
- `MediaProcessor.process_batch()`

Output folders:
- `extracted_audio/`
- `transcripts/` (`.json`, `.txt`, `.md`, `.srt`, `.vtt` depending config)
- `transcript_chunks/` (`*_chunks.json`)
- `extracted_frames/`
- `media_metadata/`

Flow per media file:
1. Detect video/audio type.
2. If video and enabled: extract audio.
3. Transcribe audio.
4. Chunk transcript with uniform metadata.
5. If video and enabled: extract frames (+ optional dedup).
6. Associate frames to transcript chunks by timestamp.
7. Save per-file metadata.

### Local ASR mode (Whisper local)
- `AudioTranscriber` loads Whisper model locally.
- Uses local inference for transcription.

### Cloud ASR mode (Whisper via SageMaker)
- Enabled by `USE_AWS_SAGEMAKER_WHISPER=true` (or config equivalent).
- Calls `invoke_sagemaker_whisper()` with operation `transcribe-audio`.
- Response is used as transcript payload for the same downstream chunk/frame flow.

---

## Stage 3: Document processing with Docling (`stage3_document_processed`)

Executor:
- `DocumentProcessingPipeline._run_document_processing()`

Input selection logic (deduplicated):
1. Process all files in `normalized_pdfs` (highest priority).
2. Process `.md` from `normalized_markdown`.
3. Process eligible files in `original_files` that were not already represented by normalized outputs.
4. Skip media transcripts here (already chunked in Stage 2).
5. Skip Excel files already parsed by custom parser.

### Local Docling mode
- Uses `MultimodalDocumentProcessor` (in-process Docling).
- For each file:
  - Convert with Docling converter (fallback pipeline if primary fails).
  - Export markdown as `<doc>/<doc>.md`.
  - Optionally export images/tables/metadata.

### Cloud Docling mode (SageMaker)
- Enabled by any of:
  - `USE_AWS_SAGEMAKER_DOCLING=true`
  - inference config flags
  - `processing.document.docling_backend: sagemaker`
- Calls `invoke_sagemaker_docling()` with operation `process-document`.
- Writes output via `write_docling_outputs_from_sagemaker()`:
  - `<doc>/<doc>.md`
  - Optional `additional_files/*` decoded from base64.

---

## Stage 3b: Excel specialized processing (direct to Stage 4)

Executor:
- `DocumentProcessingPipeline._run_excel_processing()`
- Uses `ExcelPreprocessor`

Input:
- `stage1_normalized/excel_parsed/*.json`

Output directly in `stage4_rag_ready/<doc>/`:
- `excel_manifest.json`
- `excel_chunks.json`
- `<doc>.md`
- optional image artifacts

Reason:
- Excel gets table-aware chunks without depending on Docling markdown chunking.

---

## Stage 4: Consolidation to RAG-ready (`stage4_rag_ready`)

Executor:
- `Stage4Consolidator.consolidate()`

### Regular document folders
For each Stage 3 doc folder:
- Copy main markdown to `stage4_rag_ready/<doc>/<doc>.md` (required).
- Copy normalized PDF if exists to `<doc>/<doc>.pdf` (optional).
- Build `docling_additional/` and copy metadata/tables/images/page renders.
- For image-origin docs, copy original image file as visual reference.

### Media document folders
For each Stage 2 transcript chunk file:
- Create `stage4_rag_ready/<stem>/`.
- Copy transcript markdown `<stem>.md`.
- Copy `transcript_chunks.json`.
- Copy frames to `frames/` (if any).
- Copy `media_metadata.json` (if any).
- Create `media_manifest.json` to mark document_type as media.

### Excel document folders
- Already written by Stage 3b; consolidator counts them and keeps them in place.

---

## 4) Publish step (Where processed artifacts go)

### Local mode
- `publish_pipeline_output()` is no-op.
- Final artifacts remain under:
  - `backend/output/processing/stage4_rag_ready/...`

### Cloud mode
- `S3FileStorage.publish_pipeline_output()` uploads every file under local processing tree to processed S3 prefix.
- Canonical processed artifacts end up in S3 (under user-isolated prefix when enabled).

---

## 5) Caching, Re-run Behavior, and Cleanup

- Processing cache file: `output/processing/.processing_cache.json`
- If `force=false`, unchanged files with existing Stage 4 outputs are skipped.
- If all inputs are already processed, pipeline returns cached status quickly.
- Before running stages, stale outputs can be pruned to match current input stems (`prune_outputs_not_in_input`).
- For selected-path runs, pruning is disabled to avoid deleting unrelated previously processed outputs.

---

## 6) Standard vs Fast mode

Request field:
- `ProcessRequest.mode`: `standard` or `fast`

Fast mode changes:
- Disable Docling VLM.
- Disable Docling image/table export.
- Whisper model -> `tiny`.
- Disable word timestamps.
- Increase frame interval (fewer extracted frames).
- Disable frame duplicate removal and aggressive ASR sampling schedule.

---

## 7) End-to-End Output Contract (What indexing will consume)

The next stage (`POST /api/index`) reads from Stage 4. Expected per-document folder in `stage4_rag_ready/<doc>/`:

- Required for regular docs:
  - `<doc>.md`

- Optional:
  - `<doc>.pdf`
  - `docling_additional/*`

- For media docs:
  - `media_manifest.json`
  - `transcript_chunks.json`
  - optional `frames/*`

- For Excel docs:
  - `excel_manifest.json`
  - `excel_chunks.json`
  - `<doc>.md`
