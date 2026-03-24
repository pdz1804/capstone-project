"""Document processing stages (normalization → RAG-ready)."""

from __future__ import annotations

from typing import Any, Dict

from app.core.paths import INPUT_DIR, PROCESSING_DIR
from src.processor.pipeline import DocumentProcessingPipeline, PipelineConfig


def run_processing(force: bool = False) -> Dict[str, Any]:
    pc = PipelineConfig(skip_processed=not force)
    pipe = DocumentProcessingPipeline(
        input_dir=INPUT_DIR,
        output_dir=PROCESSING_DIR,
        config=pc,
    )
    return pipe.run()
