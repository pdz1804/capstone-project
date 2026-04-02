"""Orchestrate text + image indexing into Qdrant and BM25 snapshot."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple

from PIL import Image

from app.core.paths import (
    WorkspacePaths,
    is_s3_storage_backend,
    qdrant_collection_names_for_user,
    workspace_paths_for_user,
)
from app.repositories import (
    ImageIndexRepository,
    TextIndexRepository,
    build_qdrant_client,
    load_documents_snapshot,
    save_bm25_index,
    save_documents_snapshot,
)
from app.services.citation_uris import enrich_chunk_documents_storage_uris
from app.services.colqwen_inference import ColQwenInferenceService
from app.services.document_chunks import load_documents_for_indexing
from app.storage import get_file_storage
from app.storage.service import S3FileStorage

logger = logging.getLogger(__name__)


def _drop_legacy_user_collections(client: Any, base_name: str) -> int:
    """
    Delete historical per-user collections named ``<base_name>_<suffix>``.
    """
    try:
        cols = [c.name for c in client.get_collections().collections]
    except Exception as e:
        logger.warning("List collections failed: %s", e)
        return 0
    prefix = f"{base_name}_"
    dropped = 0
    for name in cols:
        if name == base_name or not name.startswith(prefix):
            continue
        try:
            client.delete_collection(name)
            dropped += 1
        except Exception as e:
            logger.warning("Delete legacy collection %s failed: %s", name, e)
    return dropped


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


def _name_from_path_or_uri(raw: str) -> str:
    s = (raw or "").strip().replace("\\", "/")
    if not s:
        return ""
    return s.rsplit("/", 1)[-1]


def _stem(name: str) -> str:
    p = Path((name or "").strip())
    return p.stem.lower() if p.suffix else p.name.lower()


def _normalizer_safe_stem(stem: str, max_length: int = 50) -> str:
    s = (stem or "").strip()
    if not s:
        return "untitled"
    if len(s) <= max_length:
        return s.lower()
    hash_suffix = hashlib.md5(s.encode("utf-8", errors="ignore")).hexdigest()[:8]
    truncated = s[: max_length - 9]
    return f"{truncated}_{hash_suffix}".lower()


def _build_selection(selected_paths: Sequence[str] | None, selected_names: Sequence[str] | None) -> Tuple[Set[str], Set[str]]:
    names: Set[str] = set()
    stems: Set[str] = set()
    for raw in (selected_paths or []):
        n = _name_from_path_or_uri(raw).lower()
        if n:
            names.add(n)
            stems.add(_stem(n))
            stems.add(_normalizer_safe_stem(_stem(n)))
    for raw in (selected_names or []):
        n = _name_from_path_or_uri(raw).lower()
        if n:
            names.add(n)
            stems.add(_stem(n))
            stems.add(_normalizer_safe_stem(_stem(n)))
    return names, stems


def _is_image_file_name(name: str) -> bool:
    n = (name or "").lower()
    return n.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"))


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
        self._text_quant = q.get("text_storage_quantization", "scalar")
        self._embed_model = tr.get("embedding_model", "all-MiniLM-L6-v2")
        self._colqwen = ColQwenInferenceService(yaml_config)

    def index_text(
        self,
        force: bool = False,
        selected_paths: Sequence[str] | None = None,
        selected_names: Sequence[str] | None = None,
    ) -> Dict[str, Any]:
        if not is_s3_storage_backend():
            self._paths.retrieval_dir.mkdir(parents=True, exist_ok=True)
        if not self._paths.rag_ready_dir.exists():
            return {
                "status": "failed",
                "error": f"RAG-ready dir missing: {self._paths.rag_ready_dir}. Run /api/process first.",
            }

        documents = load_documents_for_indexing(self._paths.rag_ready_dir, self.cfg)
        if not documents:
            return {"status": "failed", "error": "No text chunks produced from RAG-ready documents."}

        selected_name_set, selected_stem_set = _build_selection(selected_paths, selected_names)
        if selected_name_set or selected_stem_set:
            filtered: List[Dict[str, Any]] = []
            for d in documents:
                meta = d.get("metadata") if isinstance(d.get("metadata"), dict) else {}
                candidates = [
                    str(meta.get("original_file", "")),
                    str(meta.get("source", "")),
                    str(d.get("source", "")),
                    str(d.get("id", "")),
                    str(d.get("doc_id", "")),
                ]
                matched = False
                for c in candidates:
                    c_norm = _name_from_path_or_uri(c).lower()
                    if not c_norm:
                        continue
                    if c_norm in selected_name_set or _stem(c_norm) in selected_stem_set:
                        matched = True
                        break
                    # Parent folder name in source is often the document id.
                    folder_name = Path(c.replace("\\", "/")).parent.name.lower()
                    if folder_name and (folder_name in selected_name_set or folder_name in selected_stem_set):
                        matched = True
                        break
                if matched:
                    filtered.append(d)
            documents = filtered
            if not documents:
                return {
                    "status": "ok",
                    "chunks": 0,
                    "collection": self._text_collection,
                    "embedding_model": self._embed_model,
                    "message": "No matching text chunks found for selected files in current stage4 outputs.",
                }

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
            storage_quantization=self._text_quant,
            on_disk_vectors=True,
        )
        dropped_text = _drop_legacy_user_collections(self._client, self._text_collection)
        if dropped_text:
            logger.info("Dropped %s legacy text collections", dropped_text)
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
                "user_id": self._paths.user_id,
                "source": d.get("source", ""),
                "text_preview": (d.get("text", "") or "")[:4000],
            }
            su = meta.get("storage_uri")
            if su:
                pl["storage_uri"] = su
                pl["storage_backend"] = meta.get("storage_backend", "s3")
            payloads.append(pl)

        repo.upsert_chunks(ids, embeddings, payloads)

        save_documents_snapshot(documents, self._paths.documents_json_path, user_id=self._paths.user_id)
        save_bm25_index(documents, self._paths.bm25_pickle_path, user_id=self._paths.user_id)

        return {
            "status": "ok",
            "chunks": len(documents),
            "collection": self._text_collection,
            "embedding_model": self._embed_model,
        }

    def index_images(
        self,
        force: bool = False,
        selected_paths: Sequence[str] | None = None,
        selected_names: Sequence[str] | None = None,
    ) -> Dict[str, Any]:
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
        dropped_image = _drop_legacy_user_collections(self._client, self._image_collection)
        if dropped_image:
            logger.info("Dropped %s legacy image collections", dropped_image)
        repo.ensure_collection(recreate=force)

        doc_folders = [d for d in self._paths.rag_ready_dir.iterdir() if d.is_dir()]
        selected_name_set, selected_stem_set = _build_selection(selected_paths, selected_names)
        if selected_name_set or selected_stem_set:
            filtered_docs: List[Path] = []
            for doc in doc_folders:
                dname = doc.name.lower()
                if dname in selected_stem_set or dname in selected_name_set:
                    filtered_docs.append(doc)
                    continue
                matched = False
                for f in doc.rglob("*"):
                    if not f.is_file():
                        continue
                    fname = f.name.lower()
                    stem = f.stem.lower()
                    if fname in selected_name_set or stem in selected_stem_set:
                        matched = True
                        break
                if matched:
                    filtered_docs.append(doc)
            doc_folders = filtered_docs

        if not doc_folders:
            _write_image_sidecar(self._paths, 0)
            return {"status": "ok", "pages": 0, "message": "No Stage 4 document folders for image indexing."}

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
        for doc in doc_folders:
            pdf_files = list(doc.glob("*.pdf"))
            if pdf_files:
                pdf_path = pdf_files[0]
                try:
                    pages = convert_from_path(str(pdf_path), dpi=dpi)
                except Exception as e:
                    logger.warning("Skipping PDF %s: %s", pdf_path, e)
                    pages = []
                pdf_storage_uri = (
                    storage.uri_for_local_under_processing(pdf_path)
                    if isinstance(storage, S3FileStorage)
                    else None
                )
                for page_num, page_image in enumerate(pages, start=1):
                    im = page_image if isinstance(page_image, Image.Image) else page_image
                    hid = hashlib.md5(str(pdf_path).encode("utf-8", errors="ignore")).hexdigest()[:10]
                    point_id = f"{doc.name}_{hid}_p{page_num}"
                    payload: Dict[str, Any] = {
                        "user_id": self._paths.user_id,
                        "source": doc.name,
                        "source_path": str(pdf_path),
                        "page": page_num,
                        "total_pages": len(pages),
                        "image_width": getattr(im, "width", None),
                        "image_height": getattr(im, "height", None),
                    }
                    if pdf_storage_uri:
                        payload["storage_uri"] = pdf_storage_uri
                        payload["storage_backend"] = "s3"
                    meta = {"point_id": point_id, "payload": payload}
                    batch_imgs.append(im)
                    batch_meta.append(meta)
                    if len(batch_imgs) >= 2:
                        flush_batch()
                continue

            # Non-PDF docs: index stage4 images directly (docling images, full pages, media frames).
            stage4_images = [
                p for p in doc.rglob("*")
                if p.is_file() and _is_image_file_name(p.name)
            ]
            for idx, image_path in enumerate(stage4_images, start=1):
                try:
                    im = Image.open(image_path).convert("RGB")
                except Exception as e:
                    logger.warning("Skipping image %s: %s", image_path, e)
                    continue
                hid = hashlib.md5(str(image_path).encode("utf-8", errors="ignore")).hexdigest()[:10]
                point_id = f"{doc.name}_{hid}_i{idx}"
                payload = {
                    "user_id": self._paths.user_id,
                    "source": doc.name,
                    "source_path": str(image_path),
                    "page": idx,
                    "total_pages": len(stage4_images),
                    "image_width": getattr(im, "width", None),
                    "image_height": getattr(im, "height", None),
                }
                if isinstance(storage, S3FileStorage):
                    try:
                        payload["storage_uri"] = storage.uri_for_local_under_processing(image_path)
                        payload["storage_backend"] = "s3"
                    except Exception:
                        pass
                batch_imgs.append(im)
                batch_meta.append({"point_id": point_id, "payload": payload})
                if len(batch_imgs) >= 2:
                    flush_batch()
        flush_batch()

        if all_ids:
            repo.upsert_pages(all_ids, all_vecs, all_payloads, batch_size=8)

        _write_image_sidecar(self._paths, len(all_ids))
        return {"status": "ok", "pages": len(all_ids), "collection": self._image_collection}

    def index_all(
        self,
        force: bool = False,
        selected_paths: Sequence[str] | None = None,
        selected_names: Sequence[str] | None = None,
        mode: str = "standard",
    ) -> Dict[str, Any]:
        text_res = self.index_text(force=force, selected_paths=selected_paths, selected_names=selected_names)
        if mode == "fast":
            img_res = {
                "status": "skipped_fast_mode",
                "message": "Fast indexing mode runs text index only.",
                "pages": 0,
            }
        else:
            img_res = self.index_images(force=force, selected_paths=selected_paths, selected_names=selected_names)
        return {"text": text_res, "image": img_res}

    def remove_from_index(
        self,
        text_source: str | None = None,
        image_pdf_name: str | None = None,
        clear_image_index: bool = False,
        clear_text_index: bool = False,
    ) -> Dict[str, Any]:
        """Remove text chunks by ``source``, image pages by PDF basename, and/or wipe the image collection."""
        if not clear_image_index and not clear_text_index and not text_source and not image_pdf_name:
            return {
                "status": "failed",
                "error": "Provide text_source and/or image_pdf_name, or set clear_image_index=true / clear_text_index=true.",
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

        if clear_text_index:
            t_repo = TextIndexRepository(
                self._client,
                collection_name=self._text_collection,
                vector_name=self._text_vec,
                vector_size=dim,
                storage_quantization=self._text_quant,
                on_disk_vectors=True,
            )
            removed = t_repo.delete_by_user(self._paths.user_id)
            save_documents_snapshot([], self._paths.documents_json_path, user_id=self._paths.user_id)
            save_bm25_index([], self._paths.bm25_pickle_path, user_id=self._paths.user_id)
            dropped_legacy = _drop_legacy_user_collections(self._client, self._text_collection)
            out["text"] = {
                "cleared_user_points": True,
                "removed_qdrant_points": removed,
                "dropped_legacy_collections": dropped_legacy,
            }
        elif text_source:
            ts = text_source.strip()
            if not ts:
                out["text"] = {"error": "text_source is empty"}
            else:
                t_repo = TextIndexRepository(
                    self._client,
                    collection_name=self._text_collection,
                    vector_name=self._text_vec,
                    vector_size=dim,
                    storage_quantization=self._text_quant,
                    on_disk_vectors=True,
                )
                removed_q = t_repo.delete_by_source(ts, user_id=self._paths.user_id)
                removed_json = 0
                kept: List[Dict[str, Any]] = []
                docs = load_documents_snapshot(self._paths.documents_json_path, user_id=self._paths.user_id)
                for d in docs:
                    if (d.get("source") or "") == ts:
                        removed_json += 1
                    else:
                        kept.append(d)
                save_documents_snapshot(kept, self._paths.documents_json_path, user_id=self._paths.user_id)
                save_bm25_index(kept, self._paths.bm25_pickle_path, user_id=self._paths.user_id)
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
            removed = i_repo.delete_by_user(self._paths.user_id)
            _write_image_sidecar(self._paths, 0)
            dropped_legacy = _drop_legacy_user_collections(self._client, self._image_collection)
            out["image"] = {
                "cleared_user_points": True,
                "removed_qdrant_points": removed,
                "dropped_legacy_collections": dropped_legacy,
            }
        elif image_pdf_name:
            name = image_pdf_name.strip()
            if not name.lower().endswith(".pdf"):
                name = f"{name}.pdf"
            removed_img = i_repo.delete_by_pdf_name(name, user_id=self._paths.user_id)
            out["image"] = {"removed_qdrant_points": removed_img, "pdf": name}

        return out
