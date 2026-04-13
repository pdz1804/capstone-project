"""BM25 + Qdrant dense + hybrid text search."""

from __future__ import annotations

import logging
from pathlib import Path
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from app.core.paths import qdrant_collection_names_for_user, workspace_paths_for_user
from app.repositories import (
    TextIndexRepository,
    bm25_search,
    build_qdrant_client,
    load_bm25_index,
    load_documents_snapshot,
)
from app.storage import get_file_storage
from app.storage.service import S3FileStorage
from app.services.citation_uris import canonical_document_source, sanitize_metadata_for_api
from app.services.search_cache import get_search_cache_client

logger = logging.getLogger(__name__)


def _min_max_normalize(scores: Dict[str, float]) -> Dict[str, float]:
    if not scores:
        return {}
    vals = list(scores.values())
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return {k: 1.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


def _coerce_time_seconds(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _format_time_mmss(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _extract_time_window_fields(meta: Dict[str, Any]) -> tuple[float | None, float | None, str]:
    start = _coerce_time_seconds(meta.get("start_time"))
    end = _coerce_time_seconds(meta.get("end_time"))
    if start is None and end is None:
        return None, None, ""
    if start is not None and end is not None:
        return start, end, f"{_format_time_mmss(start)} - {_format_time_mmss(end)}"
    if start is not None:
        return start, None, f"from {_format_time_mmss(start)}"
    return None, end, f"until {_format_time_mmss(end)}"


def _basename_from_any_path(value: str) -> str:
    """Extract basename from Linux/Windows-like path strings regardless of runtime OS."""
    raw = str(value or "").strip().strip('"').strip("'")
    if not raw:
        return ""
    # Normalize separators then split; this handles C:\\... and /... styles.
    normalized = raw.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]
    return parts[-1] if parts else ""


def _attach_original_media_storage_uri(meta: Dict[str, Any], user_id: str | None) -> None:
    """Best-effort hydration for deployed media preview when historical indexes lack original_storage_uri."""
    if not isinstance(meta, dict):
        return
    if str(meta.get("document_type") or "").lower() != "media":
        return
    if str(meta.get("original_storage_uri") or "").strip():
        return

    candidate = str(meta.get("original_file") or meta.get("preview_source_path") or "").strip()

    try:
        storage = get_file_storage(user_id)
    except Exception:
        return

    if not isinstance(storage, S3FileStorage):
        return

    uri = None

    # 1) Direct mapping from known local path when available
    if candidate:
        p = Path(candidate)
        uri = storage.uri_for_local_under_input(p) or storage.uri_for_local_under_processing(p)

    # 2) Deployed fallback for historical metadata with machine-local absolute paths
    # Build a virtual input path from filename/doc_id and convert it to tenant input S3 URI.
    if not uri:
        name = ""
        if candidate:
            name = _basename_from_any_path(candidate)
        if not name:
            doc_id = str(meta.get("doc_id") or "").strip()
            ext = str(meta.get("original_file_format") or "").strip().lstrip(".")
            if doc_id and ext:
                name = f"{doc_id}.{ext}"
            elif doc_id:
                name = doc_id
        if name:
            virtual_input = storage.local_input_dir / name
            uri = storage.uri_for_local_under_input(virtual_input)

    if uri:
        meta["original_storage_uri"] = uri


def _load_doc_map_for_user(path: Path, user_id: str | None) -> Dict[str, Dict[str, Any]]:
    docs = load_documents_snapshot(path, user_id=user_id)
    out: Dict[str, Dict[str, Any]] = {}
    for d in docs:
        cid = str(d.get("id", ""))
        if cid:
            out[cid] = d
    return out


class TextSearchService:
    _embedder_lock = threading.Lock()
    _embedder_cache: Dict[str, Any] = {}
    _reranker_lock = threading.Lock()
    _reranker_cache: Dict[str, Any] = {}
    _reranker_inference_lock = threading.Lock()
    _prepared_collections_lock = threading.Lock()
    _prepared_collections: set[str] = set()
    _doc_map_lock = threading.Lock()
    _doc_map_cache: Dict[str, tuple[float, int, Dict[str, Dict[str, Any]]]] = {}
    _bm25_lock = threading.Lock()
    _bm25_cache: Dict[str, tuple[float, int, Any]] = {}

    def __init__(self, yaml_config: Dict[str, Any], user_id: str | None = None):
        self.cfg = yaml_config
        self._paths = workspace_paths_for_user(user_id)
        self._user_id = self._paths.user_id
        self._client = build_qdrant_client(yaml_config)
        q = yaml_config.get("qdrant", {}) or {}
        tr = yaml_config.get("text_retrieval", {}) or {}
        inf = yaml_config.get("inference", {}) or {}
        base_txt = q.get("text_collection", "edu_text_chunks")
        base_img = q.get("image_collection", "edu_image_pages")
        self._collection, _ = qdrant_collection_names_for_user(
            base_txt, base_img, self._paths.user_id
        )
        self._vec_name = q.get("text_vector_name", "text")
        self._text_quant = q.get("text_storage_quantization", "scalar")
        self._embed_model = tr.get("embedding_model", "all-MiniLM-L6-v2")
        self._alpha = float(inf.get("hybrid_alpha", 0.5))
        # NOTE: Reranker is intentionally disabled globally to cut retrieval latency.
        # Keep reranker implementation in codebase for fast rollback if needed.
        self._reranker_model = None

    def _repo(self, dim: int) -> TextIndexRepository:
        return TextIndexRepository(
            self._client,
            collection_name=self._collection,
            vector_name=self._vec_name,
            vector_size=dim,
            storage_quantization=self._text_quant,
            on_disk_vectors=True,
        )

    def _ensure_collection_once(self, repo: TextIndexRepository) -> None:
        key = str(self._collection)
        with TextSearchService._prepared_collections_lock:
            if key in TextSearchService._prepared_collections:
                return

        cache = get_search_cache_client()
        marker_key = f"text:{key}"
        if cache.marker_exists(marker_key):
            with TextSearchService._prepared_collections_lock:
                TextSearchService._prepared_collections.add(key)
            return

        repo.ensure_collection(recreate=False, search_only_indexes=True)
        with TextSearchService._prepared_collections_lock:
            TextSearchService._prepared_collections.add(key)
        cache.set_marker(marker_key)

    def _get_embedder(self):
        from sentence_transformers import SentenceTransformer

        with TextSearchService._embedder_lock:
            cached = TextSearchService._embedder_cache.get(self._embed_model)
            if cached is not None:
                return cached
            model = SentenceTransformer(self._embed_model)
            TextSearchService._embedder_cache[self._embed_model] = model
            return model

    def _get_reranker(self):
        model_name = str(self._reranker_model or "").strip()
        if not model_name:
            return None
        with TextSearchService._reranker_lock:
            cached = TextSearchService._reranker_cache.get(model_name)
            if cached is not None:
                return cached
            from src.retrieval.rag_retrievers import CrossEncoderReranker

            cached = CrossEncoderReranker(model_name)
            TextSearchService._reranker_cache[model_name] = cached
            return cached

    def _encode_query(self, query: str) -> tuple:
        model = self._get_embedder()
        dim = model.get_sentence_embedding_dimension()
        vec = model.encode([query], show_progress_bar=False)[0].tolist()
        return vec, dim

    @staticmethod
    def _stat_signature(path: Path) -> tuple[float, int]:
        try:
            st = path.stat()
            return float(st.st_mtime), int(st.st_size)
        except Exception:
            return 0.0, 0

    def _get_doc_map_cached(self) -> Dict[str, Dict[str, Any]]:
        cache_key = f"{self._paths.user_id}:{self._paths.documents_json_path.as_posix()}"
        mtime, size = self._stat_signature(self._paths.documents_json_path)
        with TextSearchService._doc_map_lock:
            cached = TextSearchService._doc_map_cache.get(cache_key)
            if cached and cached[0] == mtime and cached[1] == size:
                return cached[2]
        doc_map = _load_doc_map_for_user(self._paths.documents_json_path, self._user_id)
        with TextSearchService._doc_map_lock:
            TextSearchService._doc_map_cache[cache_key] = (mtime, size, doc_map)
        return doc_map

    def _get_bm25_cached(self):
        cache_key = f"{self._paths.user_id}:{self._paths.bm25_pickle_path.as_posix()}"
        mtime, size = self._stat_signature(self._paths.bm25_pickle_path)
        with TextSearchService._bm25_lock:
            cached = TextSearchService._bm25_cache.get(cache_key)
            if cached and cached[0] == mtime and cached[1] == size:
                return cached[2]
        data = load_bm25_index(self._paths.bm25_pickle_path, user_id=self._user_id)
        with TextSearchService._bm25_lock:
            TextSearchService._bm25_cache[cache_key] = (mtime, size, data)
        return data

    def search_dense(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        vec, dim = self._encode_query(query)
        repo = self._repo(dim)
        # Ensure payload indexes (notably user_id) exist on pre-migration collections.
        self._ensure_collection_once(repo)
        raw = repo.search(vec, limit=top_k, user_id=self._user_id)
        doc_map = self._get_doc_map_cached()
        results: List[Dict[str, Any]] = []
        for rank, hit in enumerate(raw, start=1):
            pl = hit.get("payload") or {}
            cid = str(pl.get("chunk_id", hit.get("id", "")))
            base = doc_map.get(cid, {})
            full_text = base.get("text") or pl.get("text_preview") or ""
            meta_raw = dict(base.get("metadata") or {})
            _attach_original_media_storage_uri(meta_raw, self._user_id)
            if pl.get("storage_uri"):
                meta_raw["storage_uri"] = pl["storage_uri"]
                meta_raw["storage_backend"] = pl.get("storage_backend", "s3")
            meta = sanitize_metadata_for_api(meta_raw)
            src = canonical_document_source(meta, str(base.get("source", pl.get("source", ""))))
            start_t, end_t, time_label = _extract_time_window_fields(meta)
            results.append(
                {
                    "id": cid,
                    "text": full_text[:500] + ("..." if len(full_text) > 500 else ""),
                    "full_text": full_text,
                    "source": src,
                    "score": float(hit.get("score", 0.0)),
                    "rank": rank,
                    "metadata": meta,
                    "retrieval_type": "dense_qdrant",
                    "start_time": start_t,
                    "end_time": end_t,
                    "time_range_label": time_label,
                }
            )
        return results

    def search_bm25(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        data = self._get_bm25_cached()
        if not data:
            return []
        rows = bm25_search(data, query, top_k)
        for r in rows:
            full_text = str(r.get("text", "") or "")
            r["full_text"] = full_text
            r["text"] = full_text[:500] + ("..." if len(full_text) > 500 else "")
            r["retrieval_type"] = "bm25"
            m = dict(r.get("metadata") or {})
            _attach_original_media_storage_uri(m, self._user_id)
            r["metadata"] = sanitize_metadata_for_api(m)
            r["source"] = canonical_document_source(r["metadata"], str(r.get("source", "")))
            start_t, end_t, time_label = _extract_time_window_fields(r["metadata"])
            r["start_time"] = start_t
            r["end_time"] = end_t
            r["time_range_label"] = time_label
        return rows

    def search_hybrid(self, query: str, top_k: int, skip_reranker: bool = False) -> List[Dict[str, Any]]:
        # Reranker is globally disabled for performance. Ignore caller/config flag.
        skip_reranker = True
        expand = max(top_k, int(top_k * 1.15))
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_bm = pool.submit(self.search_bm25, query, expand)
            fut_dn = pool.submit(self.search_dense, query, expand)
            bm = fut_bm.result()
            dn = fut_dn.result()
        bm_scores = {str(r["id"]): float(r.get("score", 0.0)) for r in bm}
        dn_scores = {str(r["id"]): float(r.get("score", 0.0)) for r in dn}
        bm_norm = _min_max_normalize(bm_scores)
        all_ids = set(bm_scores) | set(dn_scores)
        combined: Dict[str, float] = {}
        for cid in all_ids:
            combined[cid] = (1.0 - self._alpha) * bm_norm.get(cid, 0.0) + self._alpha * dn_scores.get(
                cid, 0.0
            )
        sorted_ids = sorted(combined.keys(), key=lambda x: combined[x], reverse=True)[:top_k]
        doc_map = self._get_doc_map_cached()
        out: List[Dict[str, Any]] = []
        for rank, cid in enumerate(sorted_ids, start=1):
            base = doc_map.get(cid, {})
            full_text = base.get("text", "")
            meta_raw = dict(base.get("metadata") or {})
            _attach_original_media_storage_uri(meta_raw, self._user_id)
            meta = sanitize_metadata_for_api(meta_raw)
            src = canonical_document_source(meta, str(base.get("source", "")))
            start_t, end_t, time_label = _extract_time_window_fields(meta)
            out.append(
                {
                    "id": cid,
                    "text": full_text[:500] + ("..." if len(full_text) > 500 else ""),
                    "full_text": full_text,
                    "source": src,
                    "score": float(combined[cid]),
                    "rank": rank,
                    "metadata": meta,
                    "retrieval_type": "hybrid_qdrant_bm25",
                    "retrieval_info": {
                        "bm25_score": bm_scores.get(cid),
                        "dense_score": dn_scores.get(cid),
                    },
                    "start_time": start_t,
                    "end_time": end_t,
                    "time_range_label": time_label,
                }
            )
        if self._reranker_model and out and not skip_reranker:
            ce = self._get_reranker()
            if ce is None:
                return out
            # pass fuller text for rerank
            full_docs = []
            for r in out:
                full = doc_map.get(str(r["id"]), {})
                full_docs.append(
                    {
                        "id": r["id"],
                        "text": full.get("text", r["text"]),
                        "source": r.get("source", ""),
                        "metadata": r.get("metadata", {}),
                        "score": r["score"],
                    }
                )
            with TextSearchService._reranker_inference_lock:
                reranked = ce.rerank(query, full_docs, top_k)
            for x in reranked:
                x["retrieval_type"] = "hybrid_qdrant_bm25_reranked"
                xm = dict(x.get("metadata") or {})
                _attach_original_media_storage_uri(xm, self._user_id)
                x["metadata"] = sanitize_metadata_for_api(xm)
                x["source"] = canonical_document_source(x["metadata"], str(x.get("source", "")))
                start_t, end_t, time_label = _extract_time_window_fields(x["metadata"])
                x["start_time"] = start_t
                x["end_time"] = end_t
                x["time_range_label"] = time_label
            return reranked
        return out

    def search(
        self,
        query: str,
        retriever_type: str,
        top_k: int,
        skip_reranker: bool = False,
    ) -> List[Dict[str, Any]]:
        rt = (retriever_type or "hybrid").lower()
        if rt == "bm25":
            return self.search_bm25(query, top_k)
        if rt == "dense":
            return self.search_dense(query, top_k)
        return self.search_hybrid(query, top_k, skip_reranker=skip_reranker)
