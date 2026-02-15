"""
Pipeline routes: process documents, build/rebuild indexes.
"""

import shutil
import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException

from shared import (
    INPUT_DIR, OUTPUT_DIR, CONFIG_PATH,
    load_yaml_config,
    UnifiedRAGConfig, UnifiedRAGPipeline,
    PipelineConfig, GenerationConfig,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["pipeline"])


@router.get("/processing-stats")
async def get_processing_stats() -> Dict[str, Any]:
    """Get processing pipeline statistics."""
    try:
        import json
        stats_file = OUTPUT_DIR / "processing" / "pipeline_stats.json"
        if stats_file.exists():
            with open(stats_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"error": "No processing stats found"}
    except Exception as e:
        logger.error(f"Failed to load processing stats: {e}")
        return {"error": str(e)}


@router.post("/process")
async def process_documents(force: bool = False):
    """Process uploaded documents.
    
    Args:
        force: If True, reprocess ALL files (ignore cache). Default is False
               which only processes new/changed files.
    """
    try:
        logger.info(f"Starting document processing (force={force})...")

        processing_config = PipelineConfig(skip_processed=not force)

        config = UnifiedRAGConfig(
            enable_processing=True,
            enable_retrieval=False,
            enable_generation=False,
            enable_evaluation=False,
            rag_mode="text",
            processing_config=processing_config
        )

        pipeline_instance = UnifiedRAGPipeline(
            input_dir=str(INPUT_DIR),
            output_dir=str(OUTPUT_DIR),
            config=config
        )

        results = pipeline_instance.run()
        logger.info(f"Processing completed: {results}")

        if results.get("status") == "failed":
            raise HTTPException(status_code=500, detail=results.get("error", "Processing failed"))

        return {"status": "completed", "results": results}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Processing failed with exception: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@router.post("/index")
async def build_index(force: bool = False):
    """Build/rebuild retrieval index using config file (same as CLI).
    
    Args:
        force: If True, delete existing indexes and rebuild from scratch.
               If False (default), load existing indexes if available.
    """
    try:
        logger.info(f"Starting index building (force={force})...")

        if force:
            # Clean old indexes to force rebuild
            image_retrieval_dir = OUTPUT_DIR / "image_retrieval"
            if image_retrieval_dir.exists():
                logger.info(f"Removing old image retrieval index: {image_retrieval_dir}")
                shutil.rmtree(image_retrieval_dir)

            for text_dir_name in ["retrieval", "retrieval_index"]:
                text_retrieval_dir = OUTPUT_DIR / text_dir_name
                if text_retrieval_dir.exists():
                    logger.info(f"Removing old text retrieval index: {text_retrieval_dir}")
                    shutil.rmtree(text_retrieval_dir)
        else:
            logger.info("Loading existing indexes if available (use force=true to rebuild)")

        yaml_config = load_yaml_config()

        processing_config = PipelineConfig()
        generation_config = GenerationConfig()

        yaml_colqwen = yaml_config.get('image_retrieval', {}).get('colqwen', {})
        yaml_image_retrieval_enabled = yaml_config.get('image_retrieval', {}).get('enabled', False)
        rag_mode = yaml_config.get('pipeline', {}).get('rag_mode', 'text')
        enable_image_retrieval = rag_mode in ["image", "both"] or yaml_image_retrieval_enabled

        config = UnifiedRAGConfig(
            enable_processing=False,
            enable_retrieval=True,
            enable_generation=False,
            enable_evaluation=False,
            processing_config=processing_config,
            rag_mode=rag_mode,
            retrieval_methods=yaml_config.get('pipeline', {}).get('retrievers', ['bm25', 'dense', 'hybrid']),
            enable_image_retrieval=enable_image_retrieval,
            image_retrieval_methods=yaml_config.get('image_retrieval', {}).get('methods', ['colqwen']),
            colqwen_model=yaml_colqwen.get('model', 'vidore/colqwen2-v1.0'),
            colqwen_dtype=yaml_colqwen.get('dtype', 'bfloat16'),
            colqwen_quantization=yaml_colqwen.get('quantization', None),
            colqwen_pdf_dpi=yaml_colqwen.get('pdf_dpi', 150),
            generation_config=generation_config
        )

        pipeline_instance = UnifiedRAGPipeline(
            input_dir=str(INPUT_DIR),
            output_dir=str(OUTPUT_DIR),
            config=config
        )

        results = pipeline_instance.run()
        logger.info(f"Indexing completed: {results}")

        if results.get("status") == "failed":
            raise HTTPException(status_code=500, detail=results.get("error", "Indexing failed"))

        return {"status": "completed", "results": results}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Indexing failed with exception: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Indexing error: {str(e)}")


@router.post("/index/{index_type}")
async def build_specific_index(index_type: str, force: bool = False):
    """Build/rebuild a specific index type (text or image).
    
    Args:
        index_type: 'text' or 'image'
        force: If True, delete existing index and rebuild. If False, load existing.
    """
    if index_type not in ["text", "image"]:
        raise HTTPException(status_code=400, detail="index_type must be 'text' or 'image'")

    try:
        logger.info(f"Starting {index_type} index building (force={force})...")

        yaml_config = load_yaml_config()
        processing_config = PipelineConfig()
        generation_config = GenerationConfig()

        yaml_colqwen = yaml_config.get('image_retrieval', {}).get('colqwen', {})

        if index_type == "text":
            if force:
                for dir_name in ["retrieval", "retrieval_index"]:
                    d = OUTPUT_DIR / dir_name
                    if d.exists():
                        logger.info(f"Removing old text retrieval index: {d}")
                        shutil.rmtree(d)

            config = UnifiedRAGConfig(
                enable_processing=False,
                enable_retrieval=True,
                enable_generation=False,
                enable_evaluation=False,
                enable_image_retrieval=False,
                processing_config=processing_config,
                rag_mode="text",
                retrieval_methods=yaml_config.get('pipeline', {}).get('retrievers', ['bm25', 'dense', 'hybrid']),
                generation_config=generation_config
            )
        else:
            if force:
                image_retrieval_dir = OUTPUT_DIR / "image_retrieval"
                if image_retrieval_dir.exists():
                    logger.info(f"Removing old image retrieval index: {image_retrieval_dir}")
                    shutil.rmtree(image_retrieval_dir)

            config = UnifiedRAGConfig(
                enable_processing=False,
                enable_retrieval=False,
                enable_generation=False,
                enable_evaluation=False,
                enable_image_retrieval=True,
                processing_config=processing_config,
                rag_mode="image",
                image_retrieval_methods=yaml_config.get('image_retrieval', {}).get('methods', ['colqwen']),
                colqwen_model=yaml_colqwen.get('model', 'vidore/colqwen2-v1.0'),
                colqwen_dtype=yaml_colqwen.get('dtype', 'bfloat16'),
                colqwen_quantization=yaml_colqwen.get('quantization', None),
                colqwen_pdf_dpi=yaml_colqwen.get('pdf_dpi', 150),
                generation_config=generation_config
            )

        pipeline_instance = UnifiedRAGPipeline(
            input_dir=str(INPUT_DIR),
            output_dir=str(OUTPUT_DIR),
            config=config
        )

        results = pipeline_instance.run()
        logger.info(f"{index_type.capitalize()} indexing completed: {results}")

        if results.get("status") == "failed":
            raise HTTPException(status_code=500, detail=results.get("error", f"{index_type.capitalize()} indexing failed"))

        return {"status": "completed", "index_type": index_type, "results": results}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"{index_type.capitalize()} indexing failed with exception: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"{index_type.capitalize()} indexing error: {str(e)}")
