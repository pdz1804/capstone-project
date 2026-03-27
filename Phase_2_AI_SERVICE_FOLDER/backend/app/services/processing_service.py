"""Document processing stages (normalization → RAG-ready)."""

from __future__ import annotations

from typing import Any, Dict

from app.core.paths import workspace_paths_for_user
from app.storage import get_file_storage
from src.processor.pipeline import DocumentProcessingPipeline, PipelineConfig


def run_processing(user_id: str | None = None, force: bool = False) -> Dict[str, Any]:
    paths = workspace_paths_for_user(user_id)
    storage = get_file_storage(user_id)
    storage.prepare_pipeline_input(paths.input_dir)
    pc = PipelineConfig(skip_processed=not force)
    pipe = DocumentProcessingPipeline(
        input_dir=paths.input_dir,
        output_dir=paths.processing_dir,
        config=pc,
    )
    result = pipe.run()
    storage.publish_pipeline_output(paths.processing_dir)
    return result
