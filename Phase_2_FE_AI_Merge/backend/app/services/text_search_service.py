"""BM25 + Qdrant dense + hybrid text search."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from app.core.qdrant_errors import is_qdrant_unreachable
from app.core.paths import qdrant_collection_names_for_user, workspace_paths_for_user
from app.repositories import (
    TextIndexRepository,
    bm25_search,
    build_qdrant_client,
    load_bm25_index,
    load_documents_snapshot,
)
from app.services.citation_uris import canonical_document_source, sanitize_metadata_for_api

logger = logging.getLogger(__name__)


def _min_max_normalize(scores: Dict[str, float]) -> Dict[str, float]:
    if not scores:
        return {}
    vals = list(scores.values())
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return {k: 1.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


def _load_doc_map_for_user(path: Path, user_id: str | None) -> Dict[str, Dict[str, Any]]:
    docs = load_documents_snapshot(path, user_id=user_id)
    out: Dict[str, Dict[str, Any]] = {}
    for d in docs:
        cid = str(d.get("id", ""))
        if cid:
            out[cid] = d
    return out


def _bm25_fallback_rows(
    rows: List[Dict[str, Any]],
    top_k: int,
    fallback_reason: str,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for rank, row in enumerate(rows[:top_k], start=1):
        item = dict(row)
        item["rank"] = rank
        item["retrieval_type"] = "hybrid_bm25_fallback_qdrant_unavailable"
        info = dict(item.get("retrieval_info") or {})
        info["bm25_score"] = float(item.get("score", 0.0))
        info["dense_score"] = None
        info["fallback_reason"] = fallback_reason
        item["retrieval_info"] = info
        out.append(item)
    return out


class TextSearchService:
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
        self._reranker_model = None
        rr = tr.get("reranker", {}) or {}
        if rr.get("enabled") and rr.get("model"):
            self._reranker_model = rr["model"]

    def _repo(self, dim: int) -> TextIndexRepository:
        return TextIndexRepository(
            self._client,
            collection_name=self._collection,
            vector_name=self._vec_name,
            vector_size=dim,
            storage_quantization=self._text_quant,
            on_disk_vectors=True,
        )

    def _encode_query(self, query: str) -> tuple:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(self._embed_model)
        dim = model.get_sentence_embedding_dimension()
        vec = model.encode([query], show_progress_bar=False)[0].tolist()
        return vec, dim

    def search_dense(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        vec, dim = self._encode_query(query)
        repo = self._repo(dim)
        # Ensure payload indexes (notably user_id) exist on pre-migration collections.
        repo.ensure_collection(recreate=False)
        raw = repo.search(vec, limit=top_k, user_id=self._user_id)
        doc_map = _load_doc_map_for_user(self._paths.documents_json_path, self._user_id)
        results: List[Dict[str, Any]] = []
        for rank, hit in enumerate(raw, start=1):
            pl = hit.get("payload") or {}
            cid = str(pl.get("chunk_id", hit.get("id", "")))
            base = doc_map.get(cid, {})
            full_text = base.get("text") or pl.get("text_preview") or ""
            meta_raw = dict(base.get("metadata") or {})
            if pl.get("storage_uri"):
                meta_raw["storage_uri"] = pl["storage_uri"]
                meta_raw["storage_backend"] = pl.get("storage_backend", "s3")
            meta = sanitize_metadata_for_api(meta_raw)
            src = canonical_document_source(meta, str(base.get("source", pl.get("source", ""))))
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
                }
            )
        return results

    def search_bm25(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        data = load_bm25_index(self._paths.bm25_pickle_path, user_id=self._user_id)
        if not data:
            return []
        rows = bm25_search(data, query, top_k)
        for r in rows:
            full_text = str(r.get("text", "") or "")
            r["full_text"] = full_text
            r["text"] = full_text[:500] + ("..." if len(full_text) > 500 else "")
            r["retrieval_type"] = "bm25"
            m = dict(r.get("metadata") or {})
            r["metadata"] = sanitize_metadata_for_api(m)
            r["source"] = canonical_document_source(r["metadata"], str(r.get("source", "")))
        return rows

    def search_hybrid(self, query: str, top_k: int, skip_reranker: bool = False) -> List[Dict[str, Any]]:
        expand = max(top_k, int(top_k * 1.3))
        bm = self.search_bm25(query, expand)
        try:
            dn = self.search_dense(query, expand)
        except Exception as e:
            if not is_qdrant_unreachable(e):
                raise
            logger.warning("Hybrid search: dense Qdrant branch unavailable, falling back to BM25: %s", e)
            return _bm25_fallback_rows(
                bm,
                top_k=top_k,
                fallback_reason=f"{type(e).__name__}: {e}",
            )
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
        doc_map = _load_doc_map_for_user(self._paths.documents_json_path, self._user_id)
        out: List[Dict[str, Any]] = []
        for rank, cid in enumerate(sorted_ids, start=1):
            base = doc_map.get(cid, {})
            full_text = base.get("text", "")
            meta = sanitize_metadata_for_api(dict(base.get("metadata") or {}))
            src = canonical_document_source(meta, str(base.get("source", "")))
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
                }
            )
        if self._reranker_model and out and not skip_reranker:
            from src.retrieval.rag_retrievers import CrossEncoderReranker

            ce = CrossEncoderReranker(self._reranker_model)
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
            reranked = ce.rerank(query, full_docs, top_k)
            for x in reranked:
                x["retrieval_type"] = "hybrid_qdrant_bm25_reranked"
                xm = dict(x.get("metadata") or {})
                x["metadata"] = sanitize_metadata_for_api(xm)
                x["source"] = canonical_document_source(x["metadata"], str(x.get("source", "")))
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
