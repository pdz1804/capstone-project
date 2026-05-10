"""Document processing stages (normalization → RAG-ready)."""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, Sequence

from app.core.paths import is_s3_storage_backend, load_yaml_config, merged_runtime_settings, workspace_paths_for_user
from app.storage import get_file_storage
from src.processor.document_processor import ProcessingConfig
from src.processor.document_processor_v2 import ProcessingConfigV2
from src.processor.media_processor_enhanced import MediaProcessorConfig
from src.processor.pipeline import DocumentProcessingPipeline, PipelineConfig


def _build_pipeline_config(runtime: Dict[str, Any], force: bool, mode: str = "standard") -> PipelineConfig:
    """Apply ``processing`` / ``processing.document`` from merged YAML (was ignored before)."""
    def _as_bool(v: Any, default: bool = False) -> bool:
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("1", "true", "yes"):
                return True
            if s in ("0", "false", "no"):
                return False
            return default
        return bool(v)

    proc = runtime.get("processing") or {}
    media = proc.get("media") or {}
    doc = proc.get("document") or {}
    inf = runtime.get("inference") or {}
    use_gpu = bool(proc.get("use_gpu", True))

    ocr_langs = doc.get("ocr_languages")
    if ocr_langs is not None and not isinstance(ocr_langs, list):
        ocr_langs = None

    document_config = ProcessingConfig(
        use_gpu=use_gpu,
        enable_ocr=bool(doc.get("enable_ocr", True)),
        enable_vlm=bool(doc.get("enable_vlm", False)),
        enable_asr=bool(doc.get("enable_asr", True)),
        ocr_engine=str(doc.get("ocr_engine", "rapidocr")),
        ocr_languages=ocr_langs,
        vlm_model=str(doc.get("vlm_model", "smolvlm")),
        export_markdown=bool(doc.get("export_markdown", True)),
        export_images=bool(doc.get("export_images", False)),
        export_tables=bool(doc.get("export_tables", False)),
    )

    media_config = MediaProcessorConfig(
        use_gpu=use_gpu,
        extract_audio=_as_bool(proc.get("enable_media_processing", True), default=True),
        enable_transcription=_as_bool(media.get("enable_transcription", True), default=True),
        asr_model=str(media.get("asr_model", "base")),
        asr_language=media.get("asr_language"),
        extract_frames=_as_bool(media.get("extract_frames", False), default=False),
        frame_interval=int(media.get("frame_interval", 100)),
        use_word_timestamps=_as_bool(media.get("use_word_timestamps", True), default=True),
        use_aws_sagemaker_whisper=_as_bool(inf.get("use_aws_sagemaker_whisper", False), default=False),
        sagemaker_whisper_endpoint_name=str(inf.get("sagemaker_whisper_endpoint_name", "")),
        aws_region=str(inf.get("aws_region", "us-west-2")),
    )

    if mode == "fast":
        # Fast mode: prioritize throughput over rich multimodal artifacts.
        document_config.enable_vlm = False
        document_config.export_images = False
        document_config.export_tables = False
        media_config.asr_model = "tiny"
        media_config.use_word_timestamps = False
        media_config.frame_interval = max(media_config.frame_interval, 180)
        media_config.remove_duplicate_frames = False
        media_config.temperature_schedule = (0.0,)

    document_v2 = doc.get("v2") or {}
    excel_reader_mode = str(document_v2.get("excel_reader_mode", "xml")).strip().lower() or "xml"
    if excel_reader_mode not in {"xml", "docling"}:
        excel_reader_mode = "xml"

    document_config_v2 = ProcessingConfigV2(
        prefer_custom_readers=_as_bool(document_v2.get("prefer_custom_readers", True), default=True),
        excel_reader_mode=excel_reader_mode,
        pptx_llm_validate_headers=_as_bool(
            document_v2.get("pptx_llm_validate_headers", False),
            default=False,
        ),
        pdf_content_source=str(document_v2.get("pdf_content_source", "hybrid")).strip().lower() or "hybrid",
        docling_config=document_config,
        runtime_yaml=runtime,
    )

    cache_enabled = _as_bool(proc.get("enable_processing_cache", False), default=False)
    return PipelineConfig(
        skip_processed=(not force) and cache_enabled,
        runtime_yaml=runtime,
        use_gpu=use_gpu,
        enable_normalization=bool(proc.get("enable_normalization", True)),
        enable_media_processing=bool(proc.get("enable_media_processing", True)),
        enable_document_processing=bool(proc.get("enable_document_processing", True)),
        media_config=media_config,
        document_config=document_config,
        document_config_v2=document_config_v2,
    )


def _clear_pipeline_stage_dirs(processing_dir: "Path") -> None:
    """Remove stage1-3 subdirectories so stale normalized/media/docling
    artifacts from previous runs don't bleed into the current run.
    Stage 4 (rag_ready) is intentionally kept   it is cumulative and
    uploaded to S3; it will be rebuilt only for the files being processed."""
    import shutil as _shutil

    for stage in ("stage1_normalized", "stage2_media_processed", "stage3_document_processed"):
        d = processing_dir / stage
        if d.exists():
            _shutil.rmtree(d, ignore_errors=True)


def run_processing(
    user_id: str | None = None,
    force: bool = False,
    selected_paths: Sequence[str] | None = None,
    mode: str = "standard",
) -> Dict[str, Any]:
    # Hub default read timeout is 10s; large ONNX shards from HF often need longer (retries still slow).
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")
    if is_s3_storage_backend():
        # In S3 mode, keep backend logs concise and avoid noisy local temp-path traces.
        for logger_name in (
            "src.processor.media_processor_enhanced",
            "src.processor.document_processor",
            "docling",
            "RapidOCR",
        ):
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    paths = workspace_paths_for_user(user_id)
    storage = get_file_storage(user_id)

    # In S3 mode the local workspace is purely ephemeral. Clear stage1-3 before
    # each run so stale normalized/docling artifacts from previous runs don't get
    # re-processed alongside the current selection.
    if is_s3_storage_backend():
        _clear_pipeline_stage_dirs(paths.processing_dir)

    storage.prepare_pipeline_input(paths.input_dir, selected_paths=selected_paths)
    runtime = merged_runtime_settings(load_yaml_config())
    pc = _build_pipeline_config(runtime, force, mode=mode)
    # Selected processing should not erase previously processed stage outputs
    # for other files. Keep Stage 4 cumulative across runs.
    if selected_paths:
        pc.prune_outputs_not_in_input = False
    pipe = DocumentProcessingPipeline(
        input_dir=paths.input_dir,
        output_dir=paths.processing_dir,
        config=pc,
    )
    result = pipe.run()
    # Cached runs have no new artifacts; avoid redundant S3 upload scan.
    if not (isinstance(result, dict) and result.get("cached") is True):
        storage.publish_pipeline_output(paths.processing_dir)
    return result
