"""Compose text + image retrieval and LLM generation."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter
from pathlib import Path
from typing import Any, Dict, List

from app.core.paths import BACKEND_ROOT, workspace_paths_for_user
from app.services.citation_uris import canonical_document_source, sanitize_metadata_for_api
from app.repositories import load_documents_snapshot
from app.services.search_cache import get_search_cache_client
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


def _cache_user_key(user_id: str | None) -> str:
    return str(user_id or "anonymous")


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
        # Reranker can be controlled via config or parameter; default to enabled if not explicitly disabled
        # To skip reranking, set SKIP_RERANKER=true or pass skip_reranker=True
        config_skip_reranker = os.getenv("SKIP_RERANKER", "true").lower() in ("true", "1", "yes")
        skip_reranker = skip_reranker or config_skip_reranker
        t0 = perf_counter()
        step_ms: Dict[str, int] = {}
        scope = (search_scope or "both").strip().lower()
        run_generation = (mode or "retrieval_generation").strip().lower() == "retrieval_generation"

        def _log_timings(kind: str) -> None:
            logger.info(
                "Search orchestrator timing: user=%s mode=%s scope=%s retrieval_ms=%s generation_ms=%s total_ms=%s retrieval_cache_hit=%s kind=%s",
                self._user_id,
                "retrieval_generation" if run_generation else "retrieval_only",
                scope if scope in ("text", "image", "both") else "both",
                step_ms.get("retrieval_total", 0),
                step_ms.get("generation", 0),
                step_ms.get("total", 0),
                retrieval_cache_hit,
                kind,
            )

        run_text = scope in ("text", "both")
        can_run_image = scope in ("image", "both") and include_images and _image_enabled(self.cfg)

        retrieval_cache_payload: Dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "retriever_type": retriever_type,
            "search_scope": scope,
            "include_images": bool(include_images),
            "skip_reranker": bool(skip_reranker),
            "run_text": bool(run_text),
            "can_run_image": bool(can_run_image),
        }
        cache_client = get_search_cache_client()
        cache_user = _cache_user_key(self._user_id)
        cached_retrieval = cache_client.get(cache_user, retrieval_cache_payload, namespace="retrieval")
        retrieval_cache_hit = False
        retrieval_cache_write_ok: bool | None = None

        text_rows: List[Dict[str, Any]] = []
        image_rows: List[Dict[str, Any]] = []
        retrieval_total_ms = 0

        if isinstance(cached_retrieval, dict):
            cached_text = cached_retrieval.get("text_results")
            cached_images = cached_retrieval.get("image_results")
            if isinstance(cached_text, list) and isinstance(cached_images, list):
                text_rows = cached_text
                image_rows = cached_images
                retrieval_cache_hit = True
                step_ms["text_retrieval"] = 0
                step_ms["image_retrieval"] = 0
                retrieval_total_ms = 0

        if not retrieval_cache_hit and run_text and can_run_image:
            # Both branches active — run them in parallel.
            def _fetch_text() -> List[Dict[str, Any]]:
                return TextSearchService(self.cfg, user_id=self._user_id).search(
                    query, retriever_type, top_k, skip_reranker=skip_reranker
                )

            def _fetch_images() -> List[Dict[str, Any]]:
                return ImageSearchService(self.cfg, user_id=self._user_id).search(query, top_k)

            t_parallel = perf_counter()
            search_timeout_seconds = int(os.getenv("SEARCH_PARALLEL_TIMEOUT_SECONDS", "30"))
            with ThreadPoolExecutor(max_workers=2) as pool:
                fut_t = pool.submit(_fetch_text)
                fut_i = pool.submit(_fetch_images)
                for fut in as_completed([fut_t, fut_i], timeout=search_timeout_seconds):
                    if fut is fut_t:
                        try:
                            text_rows = fut.result(timeout=1)
                        except TimeoutError:
                            logger.warning("Text search timeout after %d seconds", search_timeout_seconds)
                        except Exception as e:
                            logger.exception("Text search failed: %s", e)
                    else:
                        try:
                            image_rows = fut.result(timeout=1)
                        except TimeoutError:
                            logger.warning("Image search timeout after %d seconds", search_timeout_seconds)
                        except Exception as e:
                            logger.exception("Image search failed: %s", e)
            elapsed = int((perf_counter() - t_parallel) * 1000)
            step_ms["text_retrieval"] = elapsed
            step_ms["image_retrieval"] = elapsed
            retrieval_total_ms = elapsed
        elif not retrieval_cache_hit:
            if run_text:
                t_text = perf_counter()
                text_rows = TextSearchService(self.cfg, user_id=self._user_id).search(
                    query, retriever_type, top_k, skip_reranker=skip_reranker
                )
                step_ms["text_retrieval"] = int((perf_counter() - t_text) * 1000)
            else:
                step_ms["text_retrieval"] = 0

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

            retrieval_total_ms = int(step_ms.get("text_retrieval", 0)) + int(step_ms.get("image_retrieval", 0))

        if not retrieval_cache_hit:
            retrieval_cache_write_ok = cache_client.set(
                cache_user,
                retrieval_cache_payload,
                {"text_results": text_rows, "image_results": image_rows},
                namespace="retrieval",
            )

        step_ms["retrieval_total"] = retrieval_total_ms

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
                "cache": {
                    "retrieval": {
                        "enabled": cache_client.is_enabled(),
                        "hit": retrieval_cache_hit,
                        "backend": "redis" if cache_client.is_enabled() else "none",
                        "ttl_seconds": cache_client.config.ttl_seconds,
                        "write_ok": retrieval_cache_write_ok,
                    }
                },
            },
            "retrieval_config": {
                "retriever_type": retriever_type,
                "top_k": top_k,
                "skip_reranker": bool(skip_reranker),
            },
        }

        if not run_generation or not _generation_enabled(self.cfg):
            step_ms["total"] = int((perf_counter() - t0) * 1000)
            _log_timings("retrieval_only_or_generation_disabled")
            return result

        if not text_rows and not image_rows:
            step_ms["generation"] = 0
            step_ms["total"] = int((perf_counter() - t0) * 1000)
            _log_timings("no_results_for_generation")
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
        _log_timings("completed")
        return result
