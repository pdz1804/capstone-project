import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import storage_user_id
from app.api.schemas import IndexRequest, ProcessRequest, RemoveFromIndexRequest
from app.core.paths import merged_runtime_settings, workspace_paths_for_user
from app.core.qdrant_errors import is_qdrant_unreachable, qdrant_setup_hint
from app.services.indexing_job_service import IndexingJobService
from app.services.indexing_service import IndexingService
from app.services.processing_service import run_processing

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["pipeline"])

_job_service = IndexingJobService()


@router.get("/index/status/{job_id}")
def get_job_status(job_id: str) -> Dict[str, Any]:
    """Poll job status by job_id."""
    job = _job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found or expired")
    return job


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


def _run_processing_job(job_id: str, user_id: str, force: bool, selected_paths: list, mode: str) -> None:
    """Background task for processing."""
    try:
        _job_service.update_job(job_id, status="running")
        stats = run_processing(user_id=user_id, force=force, selected_paths=selected_paths, mode=mode)
        if isinstance(stats, dict):
            if stats.get("status") == "failed":
                _job_service.mark_job_failed(job_id, stats.get("error", "Processing failed"))
                return
            doc_stage = (stats.get("stages") or {}).get("document_processing") or {}
            if int(doc_stage.get("failed_files", 0) or 0) > 0:
                _job_service.mark_job_failed(
                    job_id,
                    f"Document processing failed for {doc_stage.get('failed_files')} file(s).",
                )
                return
        _job_service.mark_job_completed(job_id, {"status": "completed", "results": stats})
    except Exception as e:
        logger.exception("process job job_id=%s: %s", job_id, e)
        _job_service.mark_job_failed(job_id, str(e))
    finally:
        _job_service.cleanup_job_on_completion(job_id)


@router.post("/process")
def process(
    force: bool = False,
    body: ProcessRequest | None = None,
    user_id: str = Depends(storage_user_id),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Dict[str, Any]:
    selected_paths = body.selected_paths if body else []
    mode = (body.mode if body else "standard") or "standard"

    job_id = _job_service.create_job(
        user_id=user_id,
        job_type="process",
        params={"force": force, "selected_paths": selected_paths, "mode": mode},
    )
    if not job_id:
        raise HTTPException(
            status_code=429,
            detail=f"Too many concurrent jobs. Max {3} per user.",
        )

    background_tasks.add_task(
        _run_processing_job,
        job_id=job_id,
        user_id=user_id,
        force=force,
        selected_paths=selected_paths,
        mode=mode,
    )

    return {"status": "accepted", "job_id": job_id, "message": "Processing started. Poll /api/index/status/{job_id}"}


def _run_index_all_job(
    job_id: str,
    user_id: str,
    force: bool,
    selected_paths: list,
    selected_names: list,
    mode: str,
) -> None:
    """Background task for index_all."""
    try:
        _job_service.update_job(job_id, status="running")
        cfg = merged_runtime_settings()
        svc = IndexingService(cfg, user_id=user_id)
        out = svc.index_all(
            force=force,
            selected_paths=selected_paths,
            selected_names=selected_names,
            mode=mode,
        )
        if out.get("text", {}).get("status") == "failed":
            _job_service.mark_job_failed(job_id, out["text"].get("error"))
            return
        if out.get("image", {}).get("status") == "failed":
            _job_service.mark_job_failed(job_id, out["image"].get("error"))
            return
        _job_service.mark_job_completed(job_id, {"status": "completed", "results": out})
    except Exception as e:
        if is_qdrant_unreachable(e):
            logger.warning("index job unreachable: %s", e)
            _job_service.mark_job_failed(job_id, f"Qdrant unreachable: {e}")
        else:
            logger.exception("index job job_id=%s: %s", job_id, e)
            _job_service.mark_job_failed(job_id, str(e))
    finally:
        _job_service.cleanup_job_on_completion(job_id)


@router.post("/index")
def index_all(
    force: bool = False,
    body: IndexRequest | None = None,
    user_id: str = Depends(storage_user_id),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Dict[str, Any]:
    selected_paths = body.selected_paths if body else []
    selected_names = body.selected_names if body else []
    mode = (body.mode if body else "standard") or "standard"

    logger.info(
        "index request user=%s mode=%s selected_paths=%s selected_names=%s",
        user_id,
        mode,
        len(selected_paths),
        selected_names,
    )

    job_id = _job_service.create_job(
        user_id=user_id,
        job_type="index_all",
        params={
            "force": force,
            "selected_paths": selected_paths,
            "selected_names": selected_names,
            "mode": mode,
        },
    )
    if not job_id:
        raise HTTPException(
            status_code=429,
            detail=f"Too many concurrent jobs. Max {3} per user.",
        )

    background_tasks.add_task(
        _run_index_all_job,
        job_id=job_id,
        user_id=user_id,
        force=force,
        selected_paths=selected_paths,
        selected_names=selected_names,
        mode=mode,
    )

    return {"status": "accepted", "job_id": job_id, "message": "Indexing started. Poll /api/index/status/{job_id}"}


def _run_index_text_job(
    job_id: str,
    user_id: str,
    force: bool,
    selected_paths: list,
    selected_names: list,
) -> None:
    """Background task for index_text."""
    try:
        _job_service.update_job(job_id, status="running")
        cfg = merged_runtime_settings()
        out = IndexingService(cfg, user_id=user_id).index_text(
            force=force,
            selected_paths=selected_paths,
            selected_names=selected_names,
        )
        if out.get("status") == "failed":
            _job_service.mark_job_failed(job_id, out.get("error"))
            return
        _job_service.mark_job_completed(job_id, {"status": "completed", "results": out})
    except Exception as e:
        if is_qdrant_unreachable(e):
            logger.warning("index/text job unreachable: %s", e)
            _job_service.mark_job_failed(job_id, f"Qdrant unreachable: {e}")
        else:
            logger.exception("index/text job job_id=%s: %s", job_id, e)
            _job_service.mark_job_failed(job_id, str(e))
    finally:
        _job_service.cleanup_job_on_completion(job_id)


@router.post("/index/text")
def index_text(
    force: bool = False,
    body: IndexRequest | None = None,
    user_id: str = Depends(storage_user_id),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Dict[str, Any]:
    selected_paths = body.selected_paths if body else []
    selected_names = body.selected_names if body else []

    job_id = _job_service.create_job(
        user_id=user_id,
        job_type="index_text",
        params={
            "force": force,
            "selected_paths": selected_paths,
            "selected_names": selected_names,
        },
    )
    if not job_id:
        raise HTTPException(
            status_code=429,
            detail=f"Too many concurrent jobs. Max {3} per user.",
        )

    background_tasks.add_task(
        _run_index_text_job,
        job_id=job_id,
        user_id=user_id,
        force=force,
        selected_paths=selected_paths,
        selected_names=selected_names,
    )

    return {"status": "accepted", "job_id": job_id, "message": "Text indexing started. Poll /api/index/status/{job_id}"}


def _run_index_remove_job(
    job_id: str,
    user_id: str,
    text_source: str | None,
    image_pdf_name: str | None,
    clear_image_index: bool,
    clear_text_index: bool,
) -> None:
    """Background task for remove_from_index."""
    try:
        _job_service.update_job(job_id, status="running")
        cfg = merged_runtime_settings()
        svc = IndexingService(cfg, user_id=user_id)
        out = svc.remove_from_index(
            text_source=text_source,
            image_pdf_name=image_pdf_name,
            clear_image_index=clear_image_index,
            clear_text_index=clear_text_index,
        )
        if out.get("status") == "failed":
            _job_service.mark_job_failed(job_id, out.get("error", "Invalid request"))
            return
        _job_service.mark_job_completed(job_id, {"status": "completed", "results": out})
    except Exception as e:
        if is_qdrant_unreachable(e):
            logger.warning("index/remove job unreachable: %s", e)
            _job_service.mark_job_failed(job_id, f"Qdrant unreachable: {e}")
        else:
            logger.exception("index/remove job job_id=%s: %s", job_id, e)
            _job_service.mark_job_failed(job_id, str(e))
    finally:
        _job_service.cleanup_job_on_completion(job_id)


@router.post("/index/remove")
def index_remove(
    body: RemoveFromIndexRequest,
    user_id: str = Depends(storage_user_id),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Dict[str, Any]:
    job_id = _job_service.create_job(
        user_id=user_id,
        job_type="remove",
        params={
            "text_source": body.text_source,
            "image_pdf_name": body.image_pdf_name,
            "clear_image_index": body.clear_image_index,
            "clear_text_index": body.clear_text_index,
        },
    )
    if not job_id:
        raise HTTPException(
            status_code=429,
            detail=f"Too many concurrent jobs. Max {3} per user.",
        )

    background_tasks.add_task(
        _run_index_remove_job,
        job_id=job_id,
        user_id=user_id,
        text_source=(body.text_source or "").strip() or None,
        image_pdf_name=(body.image_pdf_name or "").strip() or None,
        clear_image_index=body.clear_image_index,
        clear_text_index=body.clear_text_index,
    )

    return {"status": "accepted", "job_id": job_id, "message": "Removal started. Poll /api/index/status/{job_id}"}


def _run_index_images_job(
    job_id: str,
    user_id: str,
    force: bool,
    selected_paths: list,
    selected_names: list,
) -> None:
    """Background task for index_images."""
    try:
        _job_service.update_job(job_id, status="running")
        cfg = merged_runtime_settings()
        out = IndexingService(cfg, user_id=user_id).index_images(
            force=force,
            selected_paths=selected_paths,
            selected_names=selected_names,
        )
        if out.get("status") == "failed":
            _job_service.mark_job_failed(job_id, out.get("error"))
            return
        _job_service.mark_job_completed(job_id, {"status": "completed", "results": out})
    except Exception as e:
        if is_qdrant_unreachable(e):
            logger.warning("index/image job unreachable: %s", e)
            _job_service.mark_job_failed(job_id, f"Qdrant unreachable: {e}")
        else:
            logger.exception("index/image job job_id=%s: %s", job_id, e)
            _job_service.mark_job_failed(job_id, str(e))
    finally:
        _job_service.cleanup_job_on_completion(job_id)


@router.post("/index/image")
def index_image(
    force: bool = False,
    body: IndexRequest | None = None,
    user_id: str = Depends(storage_user_id),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Dict[str, Any]:
    selected_paths = body.selected_paths if body else []
    selected_names = body.selected_names if body else []

    job_id = _job_service.create_job(
        user_id=user_id,
        job_type="index_images",
        params={
            "force": force,
            "selected_paths": selected_paths,
            "selected_names": selected_names,
        },
    )
    if not job_id:
        raise HTTPException(
            status_code=429,
            detail=f"Too many concurrent jobs. Max {3} per user.",
        )

    background_tasks.add_task(
        _run_index_images_job,
        job_id=job_id,
        user_id=user_id,
        force=force,
        selected_paths=selected_paths,
        selected_names=selected_names,
    )

    return {"status": "accepted", "job_id": job_id, "message": "Image indexing started. Poll /api/index/status/{job_id}"}
