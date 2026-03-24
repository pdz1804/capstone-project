"""Orchestrate text + image indexing into Qdrant and BM25 snapshot."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image

from app.core.paths import (
    BM25_PICKLE_PATH,
    DOCUMENTS_JSON_PATH,
    OUTPUT_DIR,
    RAG_READY_DIR,
    RETRIEVAL_DIR,
)
from app.repositories import (
    ImageIndexRepository,
    TextIndexRepository,
    build_qdrant_client,
    save_bm25_index,
)
from app.services.colqwen_inference import ColQwenInferenceService
from app.services.document_chunks import load_documents_for_indexing

logger = logging.getLogger(__name__)


def _write_image_sidecar(num_pages: int) -> None:
    img_root = OUTPUT_DIR / "image_retrieval"
    col_dir = img_root / "colqwen"
    col_dir.mkdir(parents=True, exist_ok=True)
    with open(img_root / "image_index_meta.json", "w", encoding="utf-8") as f:
        json.dump({"retrievers": ["colqwen"], "vector_store": "qdrant"}, f, indent=2)
    with open(col_dir / "colqwen_meta.json", "w", encoding="utf-8") as f:
        json.dump({"num_pages": num_pages, "model": "colqwen"}, f, indent=2)


class IndexingService:
    def __init__(self, yaml_config: Dict[str, Any]):
        self.cfg = yaml_config
        self._client = build_qdrant_client(yaml_config)
        q = yaml_config.get("qdrant", {}) or {}
        tr = yaml_config.get("text_retrieval", {}) or {}
        self._text_collection = q.get("text_collection", "edu_text_chunks")
        self._image_collection = q.get("image_collection", "edu_image_pages")
        self._text_vec = q.get("text_vector_name", "text")
        self._image_vec = q.get("image_vector_name", "colpali_multivec")
        self._embed_model = tr.get("embedding_model", "all-MiniLM-L6-v2")
        self._colqwen = ColQwenInferenceService(yaml_config)

    def index_text(self, force: bool = False) -> Dict[str, Any]:
        RETRIEVAL_DIR.mkdir(parents=True, exist_ok=True)
        if not RAG_READY_DIR.exists():
            return {"status": "failed", "error": f"RAG-ready dir missing: {RAG_READY_DIR}. Run /api/process first."}

        documents = load_documents_for_indexing(RAG_READY_DIR, self.cfg)
        if not documents:
            return {"status": "failed", "error": "No text chunks produced from RAG-ready documents."}

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
            payloads.append(
                {
                    "chunk_id": cid,
                    "source": d.get("source", ""),
                    "text_preview": (d.get("text", "") or "")[:4000],
                }
            )

        repo.upsert_chunks(ids, embeddings, payloads)

        with open(DOCUMENTS_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(documents, f, ensure_ascii=False, indent=2)
        save_bm25_index(documents, BM25_PICKLE_PATH)

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

        if not RAG_READY_DIR.exists():
            return {"status": "failed", "error": f"RAG-ready dir missing: {RAG_READY_DIR}"}

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

        pdf_files = list(RAG_READY_DIR.rglob("*.pdf"))
        if not pdf_files:
            _write_image_sidecar(0)
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

        for pdf_path in pdf_files:
            try:
                pages = convert_from_path(str(pdf_path), dpi=dpi)
            except Exception as e:
                logger.warning("Skipping PDF %s: %s", pdf_path, e)
                continue
            for page_num, page_image in enumerate(pages, start=1):
                im = page_image if isinstance(page_image, Image.Image) else page_image
                hid = hashlib.md5(str(pdf_path).encode("utf-8", errors="ignore")).hexdigest()[:10]
                point_id = f"{pdf_path.stem}_{hid}_p{page_num}"
                meta = {
                    "point_id": point_id,
                    "payload": {
                        "source": pdf_path.name,
                        "source_path": str(pdf_path),
                        "page": page_num,
                        "total_pages": len(pages),
                        "image_width": getattr(im, "width", None),
                        "image_height": getattr(im, "height", None),
                    },
                }
                batch_imgs.append(im)
                batch_meta.append(meta)
                if len(batch_imgs) >= 2:
                    flush_batch()
        flush_batch()

        if all_ids:
            repo.upsert_pages(all_ids, all_vecs, all_payloads, batch_size=8)

        _write_image_sidecar(len(all_ids))
        return {"status": "ok", "pages": len(all_ids), "collection": self._image_collection}

    def index_all(self, force: bool = False) -> Dict[str, Any]:
        text_res = self.index_text(force=force)
        img_res = self.index_images(force=force)
        return {"text": text_res, "image": img_res}
