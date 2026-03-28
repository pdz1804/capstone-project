"""Document processing stages (normalization → RAG-ready)."""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, Sequence

from app.core.paths import is_s3_storage_backend, load_yaml_config, merged_runtime_settings, workspace_paths_for_user
from app.storage import get_file_storage
from src.processor.document_processor import ProcessingConfig
from src.processor.media_processor_enhanced import MediaProcessorConfig
from src.processor.pipeline import DocumentProcessingPipeline, PipelineConfig


def _build_pipeline_config(runtime: Dict[str, Any], force: bool, mode: str = "standard") -> PipelineConfig:
    """Apply ``processing`` / ``processing.document`` from merged YAML (was ignored before)."""
    proc = runtime.get("processing") or {}
    doc = proc.get("document") or {}
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
        export_images=bool(doc.get("export_images", True)),
        export_tables=bool(doc.get("export_tables", True)),
    )

    media_config = MediaProcessorConfig(
        use_gpu=use_gpu,
        extract_audio=bool(proc.get("enable_media_processing", True)),
        enable_transcription=True,
        asr_model=str((proc.get("media") or {}).get("asr_model", "base")),
        extract_frames=True,
        frame_interval=int((proc.get("media") or {}).get("frame_interval", 100)),
        use_word_timestamps=True,
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

    return PipelineConfig(
        skip_processed=not force,
        runtime_yaml=runtime,
        use_gpu=use_gpu,
        enable_normalization=bool(proc.get("enable_normalization", True)),
        enable_media_processing=bool(proc.get("enable_media_processing", True)),
        enable_document_processing=bool(proc.get("enable_document_processing", True)),
        media_config=media_config,
        document_config=document_config,
    )


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
    storage.publish_pipeline_output(paths.processing_dir)
    return result
