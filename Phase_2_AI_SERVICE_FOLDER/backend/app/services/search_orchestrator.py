"""Compose text + image retrieval and LLM generation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from app.core.paths import BACKEND_ROOT, DOCUMENTS_JSON_PATH
from app.services.image_search_service import ImageSearchService
from app.services.text_search_service import TextSearchService, _load_doc_map

logger = logging.getLogger(__name__)


def _generation_enabled(cfg: Dict[str, Any]) -> bool:
    return bool((cfg.get("generation", {}) or {}).get("enabled", True))


def _image_enabled(cfg: Dict[str, Any]) -> bool:
    pipe = cfg.get("pipeline", {}) or {}
    rag_mode = (pipe.get("rag_mode") or "text").lower()
    if rag_mode in ("image", "both"):
        return True
    return bool((cfg.get("image_retrieval", {}) or {}).get("enabled", False))


def _expand_text_for_generation(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    doc_map = _load_doc_map(DOCUMENTS_JSON_PATH)
    out: List[Dict[str, Any]] = []
    for r in rows:
        cid = str(r.get("id", ""))
        full = doc_map.get(cid, {})
        text = full.get("text") or r.get("text", "")
        item = dict(r)
        item["text"] = text
        if full.get("source"):
            item["source"] = full["source"]
        if full.get("metadata"):
            item["metadata"] = full["metadata"]
        out.append(item)
    return out


class SearchOrchestrator:
    def __init__(self, yaml_config: Dict[str, Any]):
        self.cfg = yaml_config

    def run(
        self,
        query: str,
        top_k: int = 10,
        retriever_type: str = "hybrid",
        include_images: bool = True,
        images_for_generation: int = 5,
    ) -> Dict[str, Any]:
        text_svc = TextSearchService(self.cfg)
        text_rows = text_svc.search(query, retriever_type, top_k)

        image_rows: List[Dict[str, Any]] = []
        if include_images and _image_enabled(self.cfg):
            try:
                image_rows = ImageSearchService(self.cfg).search(query, top_k)
            except Exception as e:
                logger.exception("Image search failed: %s", e)

        result: Dict[str, Any] = {
            "query": query,
            "text_results": text_rows,
            "image_results": image_rows,
            "answer": None,
        }

        if not _generation_enabled(self.cfg):
            return result

        if not text_rows and not image_rows:
            return result

        try:
            from src.generation.generator import GenerationConfig, RAGGenerator

            gyaml = self.cfg.get("generation", {}) or {}
            gc = GenerationConfig(
                provider=str(gyaml.get("provider", "openai")),
                model_name=str(gyaml.get("model", "gpt-4o-mini")),
                api_key=gyaml.get("api_key"),
                base_url=gyaml.get("base_url"),
                temperature=float(gyaml.get("temperature", 0.0)),
                max_tokens=int(gyaml.get("max_tokens", 2000)),
                enable_citations=bool(gyaml.get("enable_citations", True)),
                citation_style=str(gyaml.get("citation_style", "numbered")),
                base_dir=str(BACKEND_ROOT),
            )
            gen = RAGGenerator(gc)
            text_for_gen = _expand_text_for_generation(text_rows)
            imgs = image_rows[:images_for_generation]
            merged = text_for_gen + imgs
            gen_out = gen.generate(query, merged)
            result["answer"] = gen_out.get("answer")
            if "contents" in gen_out:
                result["contents"] = gen_out["contents"]
            result["image_results"] = imgs
        except Exception as e:
            logger.exception("Generation failed: %s", e)

        return result
