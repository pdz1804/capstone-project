"""
Search route: query indexed documents with text + image retrieval and generation.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException

from shared import (
    INPUT_DIR, OUTPUT_DIR,
    load_yaml_config, build_runtime_config,
    SearchRequest, UnifiedRAGPipeline,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search")
async def search(request: SearchRequest) -> Dict[str, Any]:
    """Search the indexed documents."""
    try:
        yaml_config = load_yaml_config()
        runtime_config = build_runtime_config(yaml_config, enable_generation=True)
        pipe = UnifiedRAGPipeline(
            input_dir=INPUT_DIR,
            output_dir=OUTPUT_DIR,
            config=runtime_config
        )
        pipe.setup_retrievers(load_existing=True)
        pipe.setup_image_retrievers(load_existing=True)

        results: Dict[str, Any] = {
            "query": request.query,
            "text_results": [],
            "image_results": [],
            "answer": None
        }

        # Text search
        if pipe.retriever_manager:
            try:
                text_results = pipe.retriever_manager.search(
                    request.query,
                    request.retriever_type,
                    top_k=request.top_k
                )
                results["text_results"] = text_results
            except Exception as e:
                logger.error(f"Text search failed: {e}")

        # Image search
        if request.include_images and pipe.image_retriever_manager:
            try:
                image_results = pipe.search_images(request.query, "colqwen", top_k=request.top_k)
                results["image_results"] = image_results
            except Exception as e:
                logger.error(f"Image search failed: {e}")

        # Generate answer
        if pipe.generator and (results["text_results"] or results["image_results"]):
            try:
                images_for_gen = results["image_results"][:request.images_for_generation]
                logger.info(f"Sending {len(images_for_gen)} images to generator")

                all_results = results["text_results"] + images_for_gen
                gen_result = pipe.generator.generate(request.query, all_results)
                results["answer"] = gen_result.get("answer", "")

                if "contents" in gen_result:
                    results["contents"] = gen_result["contents"]

                results["image_results"] = images_for_gen
            except Exception as e:
                logger.error(f"Generation failed: {e}")
                import traceback
                traceback.print_exc()

        return results

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
