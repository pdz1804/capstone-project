"""Orchestrate text + image indexing into Qdrant and BM25 snapshot."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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

_TEXT_EMBEDDER_CACHE: Dict[str, Any] = {}
_TEXT_EMBEDDER_LOCK = threading.Lock()
_PREPARED_TEXT_COLLECTIONS: Set[str] = set()
_PREPARED_IMAGE_COLLECTIONS: Set[str] = set()


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


def _stage1_normalized_pdf_path(paths: WorkspacePaths, doc_id: str) -> Path:
    return paths.processing_dir / "stage1_normalized" / "normalized_pdfs" / f"{doc_id}.pdf"


def _doc_matches_selection(doc: Dict[str, Any], selected_name_set: Set[str], selected_stem_set: Set[str]) -> bool:
    meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    candidates = [
        str(meta.get("original_file", "")),
        str(meta.get("source", "")),
        str(doc.get("source", "")),
        str(doc.get("id", "")),
        str(doc.get("doc_id", "")),
    ]
    for c in candidates:
        c_norm = _name_from_path_or_uri(c).lower()
        if not c_norm:
            continue
        if c_norm in selected_name_set or _stem(c_norm) in selected_stem_set:
            return True
        folder_name = Path(c.replace("\\", "/")).parent.name.lower()
        if folder_name and (folder_name in selected_name_set or folder_name in selected_stem_set):
            return True
    return False


def _get_text_embedder(model_name: str):
    from sentence_transformers import SentenceTransformer

    key = (model_name or "").strip()
    if not key:
        key = "all-MiniLM-L6-v2"
    with _TEXT_EMBEDDER_LOCK:
        cached = _TEXT_EMBEDDER_CACHE.get(key)
        if cached is not None:
            return cached
        # Always load on CPU: GPU is reserved for ColQwen/Docling/Whisper on SageMaker.
        # all-MiniLM-L6-v2 is fast enough on CPU for the chunk sizes used here.
        model = SentenceTransformer(key, device="cpu")
        _TEXT_EMBEDDER_CACHE[key] = model
        return model


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

    def _sync_selected_stage4_docs_from_s3(
        self,
        selected_paths: Sequence[str] | None = None,
        selected_names: Sequence[str] | None = None,
    ) -> None:
        """
        In S3 storage mode, refresh local stage4_rag_ready from S3 for selected docs only.
        This prevents indexing stale local folders from prior runs.
        Parallelizes downloads with ThreadPoolExecutor for 5-7x speedup.
        """
        if not is_s3_storage_backend():
            return
        selected_name_set, selected_stem_set = _build_selection(selected_paths, selected_names)
        if not selected_name_set and not selected_stem_set:
            return

        st = get_file_storage(self._paths.user_id)
        if not isinstance(st, S3FileStorage):
            return

        # Rebuild local stage4 view with selected docs only.
        shutil.rmtree(self._paths.rag_ready_dir, ignore_errors=True)
        self._paths.rag_ready_dir.mkdir(parents=True, exist_ok=True)

        stage4_prefix = st._key_processing("stage4_rag_ready/")
        paginator = st._client.get_paginator("list_objects_v2")

        # Collect all files to download first
        downloads_to_do = []
        for page in paginator.paginate(Bucket=st.processed_bucket, Prefix=stage4_prefix):
            for obj in page.get("Contents") or []:
                key = str(obj.get("Key") or "")
                if not key or key.endswith("/"):
                    continue
                rel = key[len(st.processing_prefix) :].lstrip("/") if st.processing_prefix else key.lstrip("/")
                parts = rel.split("/")
                # Expect: stage4_rag_ready/<doc_id>/<file>
                if len(parts) < 3 or parts[0] != "stage4_rag_ready":
                    continue
                doc_id = parts[1].lower()
                file_name = parts[-1].lower()
                file_stem = Path(file_name).stem.lower()
                match = (
                    doc_id in selected_stem_set
                    or file_name in selected_name_set
                    or file_stem in selected_stem_set
                )
                if not match:
                    continue
                dest = self._paths.processing_dir / Path(*parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                downloads_to_do.append((key, dest))

        # Parallel download with 10 workers
        downloaded = 0
        if downloads_to_do:
            def _download_file(task: tuple) -> bool:
                key, dest = task
                try:
                    st._client.download_file(st.processed_bucket, key, str(dest))
                    return True
                except Exception as e:
                    logger.warning("S3 download failed for %s: %s", key, e)
                    return False

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(_download_file, task) for task in downloads_to_do]
                for future in as_completed(futures):
                    if future.result():
                        downloaded += 1

        logger.info(
            "S3 stage4 sync for indexing: selected_names=%s selected_stems=%s downloaded_files=%s/%s",
            sorted(selected_name_set),
            sorted(selected_stem_set),
            downloaded,
            len(downloads_to_do),
        )

    def index_text(
        self,
        force: bool = False,
        selected_paths: Sequence[str] | None = None,
        selected_names: Sequence[str] | None = None,
        _skip_s3_sync: bool = False,
    ) -> Dict[str, Any]:
        if not is_s3_storage_backend():
            self._paths.retrieval_dir.mkdir(parents=True, exist_ok=True)
        if not self._paths.rag_ready_dir.exists():
            return {
                "status": "failed",
                "error": f"RAG-ready dir missing: {self._paths.rag_ready_dir}. Run /api/process first.",
            }

        if not _skip_s3_sync:
            self._sync_selected_stage4_docs_from_s3(selected_paths=selected_paths, selected_names=selected_names)

        documents = load_documents_for_indexing(self._paths.rag_ready_dir, self.cfg)
        if not documents:
            return {"status": "failed", "error": "No text chunks produced from RAG-ready documents."}

        selected_name_set, selected_stem_set = _build_selection(selected_paths, selected_names)
        if selected_name_set or selected_stem_set:
            documents = [d for d in documents if _doc_matches_selection(d, selected_name_set, selected_stem_set)]
            if not documents:
                return {
                    "status": "ok",
                    "chunks": 0,
                    "collection": self._text_collection,
                    "embedding_model": self._embed_model,
                    "message": "No matching text chunks found for selected files in current stage4 outputs.",
                }

        enrich_chunk_documents_storage_uris(documents, user_id=self._paths.user_id)

        model = _get_text_embedder(self._embed_model)
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
        if force:
            _PREPARED_TEXT_COLLECTIONS.discard(self._text_collection)
        if force or self._text_collection not in _PREPARED_TEXT_COLLECTIONS:
            repo.ensure_collection(recreate=force)
            _PREPARED_TEXT_COLLECTIONS.add(self._text_collection)

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

        # Keep index state additive for partial (selected-file) runs:
        # replace only selected docs in sparse sidecars, preserve others.
        docs_to_save = documents
        if (selected_name_set or selected_stem_set) and not force:
            existing_docs = load_documents_snapshot(self._paths.documents_json_path, user_id=self._paths.user_id)
            kept_docs = [d for d in existing_docs if not _doc_matches_selection(d, selected_name_set, selected_stem_set)]
            docs_to_save = kept_docs + documents

        save_documents_snapshot(docs_to_save, self._paths.documents_json_path, user_id=self._paths.user_id)
        save_bm25_index(docs_to_save, self._paths.bm25_pickle_path, user_id=self._paths.user_id)

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
        _skip_s3_sync: bool = False,
    ) -> Dict[str, Any]:
        try:
            from pdf2image import convert_from_path
        except ImportError as e:
            return {"status": "failed", "error": f"pdf2image required: {e}"}

        if not self._paths.rag_ready_dir.exists():
            return {"status": "failed", "error": f"RAG-ready dir missing: {self._paths.rag_ready_dir}"}

        if not _skip_s3_sync:
            self._sync_selected_stage4_docs_from_s3(selected_paths=selected_paths, selected_names=selected_names)

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
        if force:
            _PREPARED_IMAGE_COLLECTIONS.discard(self._image_collection)
        if force or self._image_collection not in _PREPARED_IMAGE_COLLECTIONS:
            repo.ensure_collection(recreate=force)
            _PREPARED_IMAGE_COLLECTIONS.add(self._image_collection)

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

        def _resolve_pdf_for_doc(doc: Path) -> Path | None:
            """Prefer stage4 PDF; fallback to stage1 normalized PDF (download from S3 if needed)."""
            stage4_pdfs = list(doc.glob("*.pdf"))
            if stage4_pdfs:
                return stage4_pdfs[0]

            stage1_pdf = _stage1_normalized_pdf_path(self._paths, doc.name)
            if stage1_pdf.exists():
                return stage1_pdf

            if isinstance(storage, S3FileStorage):
                rel = f"stage1_normalized/normalized_pdfs/{doc.name}.pdf"
                key = storage._key_processing(rel)
                try:
                    storage._client.head_object(Bucket=storage.processed_bucket, Key=key)
                except Exception:
                    return None
                stage1_pdf.parent.mkdir(parents=True, exist_ok=True)
                try:
                    storage._client.download_file(storage.processed_bucket, key, str(stage1_pdf))
                except Exception:
                    return None
                if stage1_pdf.exists() and stage1_pdf.stat().st_size > 0:
                    logger.info("Using stage1 normalized PDF fallback for image indexing: %s", stage1_pdf.name)
                    return stage1_pdf

            return None

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
            pdf_path = _resolve_pdf_for_doc(doc)
            if pdf_path is not None:
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
                if len(batch_imgs) >= 16:
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
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Sync S3 stage4 artifacts once before spawning threads to avoid
        # concurrent writes to rag_ready_dir.
        self._sync_selected_stage4_docs_from_s3(
            selected_paths=selected_paths, selected_names=selected_names
        )

        if mode == "fast":
            text_res = self.index_text(
                force=force,
                selected_paths=selected_paths,
                selected_names=selected_names,
                _skip_s3_sync=True,
            )
            return {
                "text": text_res,
                "image": {
                    "status": "skipped_fast_mode",
                    "message": "Fast indexing mode runs text index only.",
                    "pages": 0,
                },
            }

        # Standard mode: run text and image indexing in parallel.
        text_res: Dict[str, Any] = {}
        img_res: Dict[str, Any] = {}

        def _run_text() -> Dict[str, Any]:
            return self.index_text(
                force=force,
                selected_paths=selected_paths,
                selected_names=selected_names,
                _skip_s3_sync=True,
            )

        def _run_images() -> Dict[str, Any]:
            return self.index_images(
                force=force,
                selected_paths=selected_paths,
                selected_names=selected_names,
                _skip_s3_sync=True,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_text = pool.submit(_run_text)
            fut_imgs = pool.submit(_run_images)
            for fut in as_completed([fut_text, fut_imgs]):
                if fut is fut_text:
                    text_res = fut.result()
                else:
                    img_res = fut.result()

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
