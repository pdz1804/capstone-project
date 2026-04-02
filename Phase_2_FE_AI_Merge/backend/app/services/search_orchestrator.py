"""Compose text + image retrieval and LLM generation."""

from __future__ import annotations

import logging
from time import perf_counter
from pathlib import Path
from typing import Any, Dict, List

from app.core.paths import BACKEND_ROOT, workspace_paths_for_user
from app.services.citation_uris import canonical_document_source, sanitize_metadata_for_api
from app.repositories import load_documents_snapshot
from app.services.image_search_service import ImageSearchService
from app.services.text_search_service import TextSearchService

logger = logging.getLogger(__name__)


def _generation_enabled(cfg: Dict[str, Any]) -> bool:
    return bool((cfg.get("generation", {}) or {}).get("enabled", True))


def _image_enabled(cfg: Dict[str, Any]) -> bool:
    pipe = cfg.get("pipeline", {}) or {}
    rag_mode = (pipe.get("rag_mode") or "text").lower()
    if rag_mode in ("image", "both"):
        return True
    return bool((cfg.get("image_retrieval", {}) or {}).get("enabled", False))


def _estimate_tokens(text: str) -> int:
    # Lightweight approximation for telemetry when provider token usage is unavailable.
    return max(1, int(len((text or "").strip()) / 4))


def _expand_text_for_generation(rows: List[Dict[str, Any]], user_id: str | None) -> List[Dict[str, Any]]:
    paths = workspace_paths_for_user(user_id)
    doc_map = {}
    for d in load_documents_snapshot(paths.documents_json_path, user_id=paths.user_id):
        cid = str(d.get("id", ""))
        if cid:
            doc_map[cid] = d
    out: List[Dict[str, Any]] = []
    for r in rows:
        cid = str(r.get("id", ""))
        full = doc_map.get(cid, {})
        text = full.get("text") or r.get("text", "")
        item = dict(r)
        item["text"] = text
        meta = dict(full.get("metadata") or {})
        if item.get("metadata"):
            meta.update(dict(item["metadata"]))
        item["metadata"] = sanitize_metadata_for_api(meta)
        item["source"] = canonical_document_source(item["metadata"], str(item.get("source") or full.get("source", "")))
        out.append(item)
    return out


class SearchOrchestrator:
    def __init__(self, yaml_config: Dict[str, Any], user_id: str | None = None):
        self.cfg = yaml_config
        self._user_id = user_id

    def run(
        self,
        query: str,
        top_k: int = 10,
        retriever_type: str = "hybrid",
        include_images: bool = True,
        images_for_generation: int = 5,
        mode: str = "retrieval_generation",
        search_scope: str = "both",
        generation_model: str | None = None,
        skip_reranker: bool = False,
    ) -> Dict[str, Any]:
        t0 = perf_counter()
        step_ms: Dict[str, int] = {}
        scope = (search_scope or "both").strip().lower()
        run_generation = (mode or "retrieval_generation").strip().lower() == "retrieval_generation"

        text_rows: List[Dict[str, Any]] = []
        if scope in ("text", "both"):
            t_text = perf_counter()
            text_svc = TextSearchService(self.cfg, user_id=self._user_id)
            text_rows = text_svc.search(query, retriever_type, top_k, skip_reranker=skip_reranker)
            step_ms["text_retrieval"] = int((perf_counter() - t_text) * 1000)
        else:
            step_ms["text_retrieval"] = 0

        image_rows: List[Dict[str, Any]] = []
        can_run_image = scope in ("image", "both") and include_images and _image_enabled(self.cfg)
        if can_run_image:
            t_image = perf_counter()
            try:
                image_rows = ImageSearchService(self.cfg, user_id=self._user_id).search(query, top_k)
            except Exception as e:
                logger.exception("Image search failed: %s", e)
            finally:
                step_ms["image_retrieval"] = int((perf_counter() - t_image) * 1000)
        else:
            step_ms["image_retrieval"] = 0

        result: Dict[str, Any] = {
            "query": query,
            "text_results": text_rows,
            "image_results": image_rows,
            "answer": None,
            "mode": "retrieval_generation" if run_generation else "retrieval_only",
            "search_scope": scope if scope in ("text", "image", "both") else "both",
            "telemetry": {
                "steps_ms": step_ms,
                "tokens": {"input_total": 0, "output_total": 0, "provider_reported": False},
            },
            "retrieval_config": {
                "retriever_type": retriever_type,
                "top_k": top_k,
                "skip_reranker": bool(skip_reranker),
            },
        }

        if not run_generation or not _generation_enabled(self.cfg):
            step_ms["total"] = int((perf_counter() - t0) * 1000)
            return result

        if not text_rows and not image_rows:
            step_ms["generation"] = 0
            step_ms["total"] = int((perf_counter() - t0) * 1000)
            return result

        try:
            from src.generation.generator import GenerationConfig, RAGGenerator

            gyaml = self.cfg.get("generation", {}) or {}
            effective_model = (generation_model or "").strip() or str(gyaml.get("model", "gpt-4o-mini"))
            gc = GenerationConfig(
                provider=str(gyaml.get("provider", "openai")),
                model_name=effective_model,
                api_key=gyaml.get("api_key"),
                base_url=gyaml.get("base_url"),
                bedrock_region=(gyaml.get("bedrock_region") or None),
                temperature=float(gyaml.get("temperature", 0.0)),
                max_tokens=int(gyaml.get("max_tokens", 2000)),
                enable_citations=bool(gyaml.get("enable_citations", True)),
                citation_style=str(gyaml.get("citation_style", "numbered")),
                base_dir=str(BACKEND_ROOT),
            )
            gen = RAGGenerator(gc)
            text_for_gen = _expand_text_for_generation(text_rows, self._user_id)
            imgs = image_rows[:images_for_generation]
            merged = text_for_gen + imgs
            t_gen = perf_counter()
            gen_out = gen.generate(query, merged, storage_user_id=self._user_id)
            step_ms["generation"] = int((perf_counter() - t_gen) * 1000)
            result["answer"] = gen_out.get("answer")
            if "contents" in gen_out:
                result["contents"] = gen_out["contents"]
            result["image_results"] = imgs
            result["generation"] = {
                "provider": gc.provider,
                "model": gc.model_name,
                "images_used": len(imgs),
            }
            context_text = "".join(str((d or {}).get("text") or "") for d in text_for_gen)
            answer_text = str(result.get("answer") or "")
            result["telemetry"]["tokens"] = {
                "input_total": _estimate_tokens(query) + _estimate_tokens(context_text),
                "output_total": _estimate_tokens(answer_text),
                "provider_reported": False,
            }
        except Exception as e:
            logger.exception("Generation failed: %s", e)
            step_ms["generation"] = step_ms.get("generation", 0)

        step_ms["total"] = int((perf_counter() - t0) * 1000)
        return result
