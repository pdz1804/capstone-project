import json
import logging
import threading
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import storage_user_id
from app.api.schemas import IndexRequest, ProcessRequest, RemoveFromIndexRequest
from app.core.paths import merged_runtime_settings, workspace_paths_for_user
from app.core.qdrant_errors import is_qdrant_unreachable, qdrant_setup_hint
from app.services.indexing_service import IndexingService
from app.services.processing_service import run_processing

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["pipeline"])

_user_pipeline_locks: Dict[str, threading.Lock] = {}
_user_pipeline_locks_guard = threading.Lock()


def _pipeline_lock_for_user(user_id: str) -> threading.Lock:
    with _user_pipeline_locks_guard:
        if user_id not in _user_pipeline_locks:
            _user_pipeline_locks[user_id] = threading.Lock()
        return _user_pipeline_locks[user_id]


@router.get("/processing-stats")
def processing_stats(user_id: str = Depends(storage_user_id)) -> Dict[str, Any]:
    p = workspace_paths_for_user(user_id).processing_dir / "pipeline_stats.json"
    if not p.exists():
        return {"error": "No processing stats found"}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}


@router.post("/process")
def process(
    force: bool = False,
    body: ProcessRequest | None = None,
    user_id: str = Depends(storage_user_id),
) -> Dict[str, Any]:
    lock = _pipeline_lock_for_user(user_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A pipeline process/index job is already running for this user.")
    try:
        selected_paths = body.selected_paths if body else []
        mode = (body.mode if body else "standard") or "standard"
        stats = run_processing(user_id=user_id, force=force, selected_paths=selected_paths, mode=mode)
        if isinstance(stats, dict):
            if stats.get("status") == "failed":
                raise HTTPException(status_code=500, detail=stats.get("error", "Processing failed"))
            doc_stage = (stats.get("stages") or {}).get("document_processing") or {}
            if int(doc_stage.get("failed_files", 0) or 0) > 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"Document processing failed for {doc_stage.get('failed_files')} file(s).",
                )
        return {"status": "completed", "results": stats}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("process")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        lock.release()


@router.post("/index")
def index_all(
    force: bool = False,
    body: IndexRequest | None = None,
    user_id: str = Depends(storage_user_id),
) -> Dict[str, Any]:
    lock = _pipeline_lock_for_user(user_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A pipeline process/index job is already running for this user.")
    cfg = merged_runtime_settings()
    try:
        svc = IndexingService(cfg, user_id=user_id)
        selected_paths = body.selected_paths if body else []
        selected_names = body.selected_names if body else []
        mode = (body.mode if body else "standard") or "standard"
        out = svc.index_all(force=force, selected_paths=selected_paths, selected_names=selected_names, mode=mode)
        if out.get("text", {}).get("status") == "failed":
            raise HTTPException(status_code=500, detail=out["text"].get("error"))
        if out.get("image", {}).get("status") == "failed":
            raise HTTPException(status_code=500, detail=out["image"].get("error"))
        return {"status": "completed", "results": out}
    except HTTPException:
        raise
    except Exception as e:
        if is_qdrant_unreachable(e):
            logger.warning("index: Qdrant unreachable: %s", e)
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Cannot connect to Qdrant. {qdrant_setup_hint(cfg)} "
                    f"Underlying: {type(e).__name__}: {e}"
                ),
            ) from e
        logger.exception("index")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        lock.release()


@router.post("/index/text")
def index_text(
    force: bool = False,
    body: IndexRequest | None = None,
    user_id: str = Depends(storage_user_id),
) -> Dict[str, Any]:
    lock = _pipeline_lock_for_user(user_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A pipeline process/index job is already running for this user.")
    cfg = merged_runtime_settings()
    try:
        selected_paths = body.selected_paths if body else []
        selected_names = body.selected_names if body else []
        out = IndexingService(cfg, user_id=user_id).index_text(
            force=force,
            selected_paths=selected_paths,
            selected_names=selected_names,
        )
        if out.get("status") == "failed":
            raise HTTPException(status_code=500, detail=out.get("error"))
        return {"status": "completed", "results": out}
    except HTTPException:
        raise
    except Exception as e:
        if is_qdrant_unreachable(e):
            logger.warning("index/text: Qdrant unreachable: %s", e)
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Cannot connect to Qdrant. {qdrant_setup_hint(cfg)} "
                    f"Underlying: {type(e).__name__}: {e}"
                ),
            ) from e
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        lock.release()


@router.post("/index/remove")
def index_remove(
    body: RemoveFromIndexRequest,
    user_id: str = Depends(storage_user_id),
) -> Dict[str, Any]:
    lock = _pipeline_lock_for_user(user_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A pipeline process/index job is already running for this user.")
    cfg = merged_runtime_settings()
    try:
        svc = IndexingService(cfg, user_id=user_id)
        out = svc.remove_from_index(
            text_source=(body.text_source or "").strip() or None,
            image_pdf_name=(body.image_pdf_name or "").strip() or None,
            clear_image_index=body.clear_image_index,
            clear_text_index=body.clear_text_index,
        )
        if out.get("status") == "failed":
            raise HTTPException(status_code=400, detail=out.get("error", "Invalid request"))
        return {"status": "completed", "results": out}
    except HTTPException:
        raise
    except Exception as e:
        if is_qdrant_unreachable(e):
            logger.warning("index/remove: Qdrant unreachable: %s", e)
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Cannot connect to Qdrant. {qdrant_setup_hint(cfg)} "
                    f"Underlying: {type(e).__name__}: {e}"
                ),
            ) from e
        logger.exception("index/remove")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        lock.release()


@router.post("/index/image")
def index_image(
    force: bool = False,
    body: IndexRequest | None = None,
    user_id: str = Depends(storage_user_id),
) -> Dict[str, Any]:
    lock = _pipeline_lock_for_user(user_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A pipeline process/index job is already running for this user.")
    cfg = merged_runtime_settings()
    try:
        selected_paths = body.selected_paths if body else []
        selected_names = body.selected_names if body else []
        out = IndexingService(cfg, user_id=user_id).index_images(
            force=force,
            selected_paths=selected_paths,
            selected_names=selected_names,
        )
        if out.get("status") == "failed":
            raise HTTPException(status_code=500, detail=out.get("error"))
        return {"status": "completed", "results": out}
    except HTTPException:
        raise
    except Exception as e:
        if is_qdrant_unreachable(e):
            logger.warning("index/image: Qdrant unreachable: %s", e)
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Cannot connect to Qdrant. {qdrant_setup_hint(cfg)} "
                    f"Underlying: {type(e).__name__}: {e}"
                ),
            ) from e
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        lock.release()
