"""Orchestrate text + image indexing into Qdrant and BM25 snapshot."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image

from app.core.paths import (
    WorkspacePaths,
    qdrant_collection_names_for_user,
    workspace_paths_for_user,
)
from app.repositories import (
    ImageIndexRepository,
    TextIndexRepository,
    build_qdrant_client,
    save_bm25_index,
)
from app.services.citation_uris import enrich_chunk_documents_storage_uris
from app.services.colqwen_inference import ColQwenInferenceService
from app.services.document_chunks import load_documents_for_indexing
from app.storage import get_file_storage
from app.storage.service import S3FileStorage

logger = logging.getLogger(__name__)


def _embedding_dim_from_model_name(model_name: str) -> int:
    m = (model_name or "").lower()
    if "minilm-l6" in m:
        return 384
    if "large" in m:
        return 1024
    return 384


def _write_image_sidecar(paths: WorkspacePaths, num_pages: int) -> None:
    img_root = paths.image_retrieval_root
    col_dir = img_root / "colqwen"
    col_dir.mkdir(parents=True, exist_ok=True)
    with open(paths.image_meta_path, "w", encoding="utf-8") as f:
        json.dump({"retrievers": ["colqwen"], "vector_store": "qdrant"}, f, indent=2)
    with open(col_dir / "colqwen_meta.json", "w", encoding="utf-8") as f:
        json.dump({"num_pages": num_pages, "model": "colqwen"}, f, indent=2)


class IndexingService:
    def __init__(self, yaml_config: Dict[str, Any], user_id: str | None = None):
        self.cfg = yaml_config
        self._paths = workspace_paths_for_user(user_id)
        self._client = build_qdrant_client(yaml_config)
        q = yaml_config.get("qdrant", {}) or {}
        tr = yaml_config.get("text_retrieval", {}) or {}
        base_text = q.get("text_collection", "edu_text_chunks")
        base_image = q.get("image_collection", "edu_image_pages")
        self._text_collection, self._image_collection = qdrant_collection_names_for_user(
            base_text, base_image, self._paths.user_id
        )
        self._text_vec = q.get("text_vector_name", "text")
        self._image_vec = q.get("image_vector_name", "colpali_multivec")
        self._embed_model = tr.get("embedding_model", "all-MiniLM-L6-v2")
        self._colqwen = ColQwenInferenceService(yaml_config)

    def index_text(self, force: bool = False) -> Dict[str, Any]:
        self._paths.retrieval_dir.mkdir(parents=True, exist_ok=True)
        if not self._paths.rag_ready_dir.exists():
            return {
                "status": "failed",
                "error": f"RAG-ready dir missing: {self._paths.rag_ready_dir}. Run /api/process first.",
            }

        documents = load_documents_for_indexing(self._paths.rag_ready_dir, self.cfg)
        if not documents:
            return {"status": "failed", "error": "No text chunks produced from RAG-ready documents."}

        enrich_chunk_documents_storage_uris(documents, user_id=self._paths.user_id)

        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(self._embed_model)
        dim = model.get_sentence_embedding_dimension()
        texts = [d.get("text", "") for d in documents]
        embeddings = model.encode(texts, show_progress_bar=False)

        repo = TextIndexRepository(
            self._client,
            collection_name=self._text_collection,
            vector_name=self._text_vec,
            vector_size=dim,
        )
        repo.ensure_collection(recreate=force)

        ids: List[str] = []
        payloads: List[Dict[str, Any]] = []
        for d in documents:
            cid = str(d.get("id", "") or "").strip()
            if not cid:
                raw = (str(d.get("source", "")) + "\n" + (d.get("text", "") or "")[:800]).encode(
                    "utf-8", errors="ignore"
                )
                cid = "h_" + hashlib.sha256(raw).hexdigest()[:32]
            ids.append(cid)
            meta = d.get("metadata") if isinstance(d.get("metadata"), dict) else {}
            pl: Dict[str, Any] = {
                "chunk_id": cid,
                "source": d.get("source", ""),
                "text_preview": (d.get("text", "") or "")[:4000],
            }
            su = meta.get("storage_uri")
            if su:
                pl["storage_uri"] = su
                pl["storage_backend"] = meta.get("storage_backend", "s3")
            payloads.append(pl)

        repo.upsert_chunks(ids, embeddings, payloads)

        with open(self._paths.documents_json_path, "w", encoding="utf-8") as f:
            json.dump(documents, f, ensure_ascii=False, indent=2)
        save_bm25_index(documents, self._paths.bm25_pickle_path)

        return {
            "status": "ok",
            "chunks": len(documents),
            "collection": self._text_collection,
            "embedding_model": self._embed_model,
        }

    def index_images(self, force: bool = False) -> Dict[str, Any]:
        try:
            from pdf2image import convert_from_path
        except ImportError as e:
            return {"status": "failed", "error": f"pdf2image required: {e}"}

        if not self._paths.rag_ready_dir.exists():
            return {"status": "failed", "error": f"RAG-ready dir missing: {self._paths.rag_ready_dir}"}

        cq = (self.cfg.get("image_retrieval", {}) or {}).get("colqwen", {}) or {}
        dpi = int(cq.get("pdf_dpi", 150))
        quant = (self.cfg.get("qdrant", {}) or {}).get("image_storage_quantization", "scalar")

        repo = ImageIndexRepository(
            self._client,
            collection_name=self._image_collection,
            vector_name=self._image_vec,
            embedding_dim=128,
            storage_quantization=quant,
        )
        repo.ensure_collection(recreate=force)

        pdf_files = list(self._paths.rag_ready_dir.rglob("*.pdf"))
        if not pdf_files:
            _write_image_sidecar(self._paths, 0)
            return {"status": "ok", "pages": 0, "message": "No PDFs under RAG-ready tree."}

        all_ids: List[str] = []
        all_vecs: List[List[List[float]]] = []
        all_payloads: List[Dict[str, Any]] = []
        batch_imgs: List[Any] = []
        batch_meta: List[Dict[str, Any]] = []

        def flush_batch():
            nonlocal batch_imgs, batch_meta
            if not batch_imgs:
                return
            vecs, _ = self._colqwen.embed_images(batch_imgs)
            for meta, mv in zip(batch_meta, vecs):
                all_ids.append(meta["point_id"])
                all_vecs.append(mv)
                all_payloads.append(meta["payload"])
            batch_imgs = []
            batch_meta = []

        storage = get_file_storage(self._paths.user_id)
        for pdf_path in pdf_files:
            try:
                pages = convert_from_path(str(pdf_path), dpi=dpi)
            except Exception as e:
                logger.warning("Skipping PDF %s: %s", pdf_path, e)
                continue
            pdf_storage_uri = (
                storage.uri_for_local_under_processing(pdf_path)
                if isinstance(storage, S3FileStorage)
                else None
            )
            for page_num, page_image in enumerate(pages, start=1):
                im = page_image if isinstance(page_image, Image.Image) else page_image
                hid = hashlib.md5(str(pdf_path).encode("utf-8", errors="ignore")).hexdigest()[:10]
                point_id = f"{pdf_path.stem}_{hid}_p{page_num}"
                payload: Dict[str, Any] = {
                    "source": pdf_path.name,
                    "source_path": str(pdf_path),
                    "page": page_num,
                    "total_pages": len(pages),
                    "image_width": getattr(im, "width", None),
                    "image_height": getattr(im, "height", None),
                }
                if pdf_storage_uri:
                    payload["storage_uri"] = pdf_storage_uri
                    payload["storage_backend"] = "s3"
                meta = {
                    "point_id": point_id,
                    "payload": payload,
                }
                batch_imgs.append(im)
                batch_meta.append(meta)
                if len(batch_imgs) >= 2:
                    flush_batch()
        flush_batch()

        if all_ids:
            repo.upsert_pages(all_ids, all_vecs, all_payloads, batch_size=8)

        _write_image_sidecar(self._paths, len(all_ids))
        return {"status": "ok", "pages": len(all_ids), "collection": self._image_collection}

    def index_all(self, force: bool = False) -> Dict[str, Any]:
        text_res = self.index_text(force=force)
        img_res = self.index_images(force=force)
        return {"text": text_res, "image": img_res}

    def remove_from_index(
        self,
        text_source: str | None = None,
        image_pdf_name: str | None = None,
        clear_image_index: bool = False,
    ) -> Dict[str, Any]:
        """Remove text chunks by ``source``, image pages by PDF basename, and/or wipe the image collection."""
        if not clear_image_index and not text_source and not image_pdf_name:
            return {
                "status": "failed",
                "error": "Provide text_source and/or image_pdf_name, or set clear_image_index=true.",
            }

        out: Dict[str, Any] = {"status": "ok", "text": None, "image": None}

        tr = self.cfg.get("text_retrieval", {}) or {}
        embed_model = tr.get("embedding_model", "all-MiniLM-L6-v2")
        if "minilm-l6" in embed_model.lower():
            dim = 384
        elif "large" in embed_model.lower():
            dim = 1024
        else:
            dim = 384

        if text_source:
            ts = text_source.strip()
            if not ts:
                out["text"] = {"error": "text_source is empty"}
            else:
                t_repo = TextIndexRepository(
                    self._client,
                    collection_name=self._text_collection,
                    vector_name=self._text_vec,
                    vector_size=dim,
                )
                removed_q = t_repo.delete_by_source(ts)
                removed_json = 0
                kept: List[Dict[str, Any]] = []
                if self._paths.documents_json_path.exists():
                    try:
                        with open(self._paths.documents_json_path, "r", encoding="utf-8") as f:
                            docs = json.load(f)
                        if isinstance(docs, list):
                            for d in docs:
                                if (d.get("source") or "") == ts:
                                    removed_json += 1
                                else:
                                    kept.append(d)
                        with open(self._paths.documents_json_path, "w", encoding="utf-8") as f:
                            json.dump(kept, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        logger.warning("documents.json update after remove: %s", e)
                save_bm25_index(kept, self._paths.bm25_pickle_path)
                out["text"] = {
                    "removed_qdrant_points": removed_q,
                    "removed_documents_json_chunks": removed_json,
                }

        quant = (self.cfg.get("qdrant", {}) or {}).get("image_storage_quantization", "scalar")
        i_repo = ImageIndexRepository(
            self._client,
            collection_name=self._image_collection,
            vector_name=self._image_vec,
            embedding_dim=128,
            storage_quantization=quant,
        )

        if clear_image_index:
            prev_count = i_repo.count_points()
            i_repo.clear_all_points()
            _write_image_sidecar(self._paths, 0)
            out["image"] = {"cleared_collection": True, "previous_point_count": prev_count}
        elif image_pdf_name:
            name = image_pdf_name.strip()
            if not name.lower().endswith(".pdf"):
                name = f"{name}.pdf"
            removed_img = i_repo.delete_by_pdf_name(name)
            out["image"] = {"removed_qdrant_points": removed_img, "pdf": name}

        return out
