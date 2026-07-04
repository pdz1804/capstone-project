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

_job_service = IndexingJobService(config=merged_runtime_settings())


@router.get("/index/status/{job_id}")
def get_job_status(job_id: str) -> Dict[str, Any]:
    """Poll job status by job_id.

    Returns:
        Current job metadata with status, progress, result, and error.
    """
    logger.debug("Polling job status: job_id=%s", job_id)
    job = _job_service.get_job(job_id)
    if not job:
        logger.warning("Job not found or expired: job_id=%s", job_id)
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found or expired")
    logger.debug("Job status: job_id=%s status=%s", job_id, job.get("status"))
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
    """Background task for document processing.

    Logs entry, completion, timing, and any errors.
    """
    import time

    start_time = time.time()
    logger.info(
        "Starting processing job: job_id=%s user=%s force=%s mode=%s paths=%d",
        job_id,
        user_id,
        force,
        mode,
        len(selected_paths),
    )

    try:
        _job_service.update_job(job_id, status="running")
        stats = run_processing(user_id=user_id, force=force, selected_paths=selected_paths, mode=mode)
        if isinstance(stats, dict):
            if stats.get("status") == "failed":
                error_msg = stats.get("error", "Processing failed")
                logger.error("Processing job failed: job_id=%s error=%s", job_id, error_msg)
                _job_service.mark_job_failed(job_id, error_msg)
                return
            doc_stage = (stats.get("stages") or {}).get("document_processing") or {}
            if int(doc_stage.get("failed_files", 0) or 0) > 0:
                error_msg = f"Document processing failed for {doc_stage.get('failed_files')} file(s)."
                logger.error("Processing job failed: job_id=%s error=%s", job_id, error_msg)
                _job_service.mark_job_failed(job_id, error_msg)
                return
        _job_service.mark_job_completed(job_id, {"status": "completed", "results": stats})
        elapsed = time.time() - start_time
        logger.info(
            "Processing job completed: job_id=%s user=%s elapsed_sec=%.1f",
            job_id,
            user_id,
            elapsed,
        )
    except Exception as e:
        elapsed = time.time() - start_time
        logger.exception(
            "Processing job failed: job_id=%s user=%s elapsed_sec=%.1f error=%s",
            job_id,
            user_id,
            elapsed,
            str(e),
        )
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
    """Start document processing job.

    Returns:
        202 Accepted with job_id for polling status.
    """
    selected_paths = body.selected_paths if body else []
    mode = (body.mode if body else "standard") or "standard"

    logger.info(
        "process request: user=%s force=%s mode=%s selected_paths=%d",
        user_id,
        force,
        mode,
        len(selected_paths),
    )

    try:
        job_id = _job_service.create_job(
            user_id=user_id,
            job_type="process",
            params={"force": force, "selected_paths": selected_paths, "mode": mode},
        )
    except Exception as e:
        logger.exception("Failed to create process job for user=%s: %s", user_id, e)
        raise HTTPException(
            status_code=503,
            detail="Job system unavailable (Redis connection failed). Please try again later.",
        )

    if not job_id:
        logger.warning("Concurrency limit hit for user=%s (max 3 concurrent jobs)", user_id)
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent jobs. Max 3 per user. Please wait for a job to complete.",
        )

    logger.info("Created process job: job_id=%s user=%s", job_id, user_id)

    background_tasks.add_task(
        _run_processing_job,
        job_id=job_id,
        user_id=user_id,
        force=force,
        selected_paths=selected_paths,
        mode=mode,
    )

    return {
        "status": "accepted",
        "job_id": job_id,
        "message": "Processing started. Poll /api/index/status/{job_id}",
    }


def _run_index_all_job(
    job_id: str,
    user_id: str,
    force: bool,
    selected_paths: list,
    selected_names: list,
    mode: str,
) -> None:
    """Background task for combined text + image indexing.

    Logs entry, completion, timing, and any errors.
    """
    import time

    start_time = time.time()
    logger.info(
        "Starting index_all job: job_id=%s user=%s force=%s mode=%s paths=%d names=%s",
        job_id,
        user_id,
        force,
        mode,
        len(selected_paths),
        selected_names,
    )

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
            error_msg = out["text"].get("error")
            logger.error("Index_all job failed (text): job_id=%s error=%s", job_id, error_msg)
            _job_service.mark_job_failed(job_id, error_msg)
            return
        if out.get("image", {}).get("status") == "failed":
            error_msg = out["image"].get("error")
            logger.error("Index_all job failed (image): job_id=%s error=%s", job_id, error_msg)
            _job_service.mark_job_failed(job_id, error_msg)
            return
        _job_service.mark_job_completed(job_id, {"status": "completed", "results": out})
        elapsed = time.time() - start_time
        logger.info(
            "Index_all job completed: job_id=%s user=%s elapsed_sec=%.1f",
            job_id,
            user_id,
            elapsed,
        )
    except Exception as e:
        elapsed = time.time() - start_time
        if is_qdrant_unreachable(e):
            logger.error(
                "Index_all job failed (Qdrant): job_id=%s user=%s elapsed_sec=%.1f error=%s",
                job_id,
                user_id,
                elapsed,
                str(e),
            )
            _job_service.mark_job_failed(job_id, f"Qdrant unreachable: {e}")
        else:
            logger.exception(
                "Index_all job failed: job_id=%s user=%s elapsed_sec=%.1f error=%s",
                job_id,
                user_id,
                elapsed,
                str(e),
            )
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
    """Start combined text + image indexing job.

    Returns:
        202 Accepted with job_id for polling status.
    """
    selected_paths = body.selected_paths if body else []
    selected_names = body.selected_names if body else []
    mode = (body.mode if body else "standard") or "standard"

    logger.info(
        "index request: user=%s mode=%s selected_paths=%d selected_names=%s",
        user_id,
        mode,
        len(selected_paths),
        selected_names,
    )

    try:
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
    except Exception as e:
        logger.exception("Failed to create index_all job for user=%s: %s", user_id, e)
        raise HTTPException(
            status_code=503,
            detail="Job system unavailable (Redis connection failed). Please try again later.",
        )

    if not job_id:
        logger.warning("Concurrency limit hit for user=%s (max 3 concurrent jobs)", user_id)
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent jobs. Max 3 per user. Please wait for a job to complete.",
        )

    logger.info("Created index_all job: job_id=%s user=%s", job_id, user_id)

    background_tasks.add_task(
        _run_index_all_job,
        job_id=job_id,
        user_id=user_id,
        force=force,
        selected_paths=selected_paths,
        selected_names=selected_names,
        mode=mode,
    )

    return {
        "status": "accepted",
        "job_id": job_id,
        "message": "Indexing started. Poll /api/index/status/{job_id}",
    }


def _run_index_text_job(
    job_id: str,
    user_id: str,
    force: bool,
    selected_paths: list,
    selected_names: list,
) -> None:
    """Background task for text-only indexing.

    Logs entry, completion, timing, and any errors.
    """
    import time

    start_time = time.time()
    logger.info(
        "Starting index_text job: job_id=%s user=%s force=%s paths=%d names=%s",
        job_id,
        user_id,
        force,
        len(selected_paths),
        selected_names,
    )

    try:
        _job_service.update_job(job_id, status="running")
        cfg = merged_runtime_settings()
        out = IndexingService(cfg, user_id=user_id).index_text(
            force=force,
            selected_paths=selected_paths,
            selected_names=selected_names,
        )
        if out.get("status") == "failed":
            error_msg = out.get("error")
            logger.error("Index_text job failed: job_id=%s error=%s", job_id, error_msg)
            _job_service.mark_job_failed(job_id, error_msg)
            return
        _job_service.mark_job_completed(job_id, {"status": "completed", "results": out})
        elapsed = time.time() - start_time
        logger.info(
            "Index_text job completed: job_id=%s user=%s elapsed_sec=%.1f",
            job_id,
            user_id,
            elapsed,
        )
    except Exception as e:
        elapsed = time.time() - start_time
        if is_qdrant_unreachable(e):
            logger.error(
                "Index_text job failed (Qdrant): job_id=%s user=%s elapsed_sec=%.1f error=%s",
                job_id,
                user_id,
                elapsed,
                str(e),
            )
            _job_service.mark_job_failed(job_id, f"Qdrant unreachable: {e}")
        else:
            logger.exception(
                "Index_text job failed: job_id=%s user=%s elapsed_sec=%.1f error=%s",
                job_id,
                user_id,
                elapsed,
                str(e),
            )
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
    """Start text-only indexing job (BM25 + Dense embeddings).

    Returns:
        202 Accepted with job_id for polling status.
    """
    selected_paths = body.selected_paths if body else []
    selected_names = body.selected_names if body else []

    logger.info(
        "index/text request: user=%s selected_paths=%d selected_names=%s",
        user_id,
        len(selected_paths),
        selected_names,
    )

    try:
        job_id = _job_service.create_job(
            user_id=user_id,
            job_type="index_text",
            params={
                "force": force,
                "selected_paths": selected_paths,
                "selected_names": selected_names,
            },
        )
    except Exception as e:
        logger.exception("Failed to create index_text job for user=%s: %s", user_id, e)
        raise HTTPException(
            status_code=503,
            detail="Job system unavailable (Redis connection failed). Please try again later.",
        )

    if not job_id:
        logger.warning("Concurrency limit hit for user=%s (max 3 concurrent jobs)", user_id)
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent jobs. Max 3 per user. Please wait for a job to complete.",
        )

    logger.info("Created index_text job: job_id=%s user=%s", job_id, user_id)

    background_tasks.add_task(
        _run_index_text_job,
        job_id=job_id,
        user_id=user_id,
        force=force,
        selected_paths=selected_paths,
        selected_names=selected_names,
    )

    return {
        "status": "accepted",
        "job_id": job_id,
        "message": "Text indexing started. Poll /api/index/status/{job_id}",
    }


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
    """Remove documents or clear indexes.

    Returns:
        202 Accepted with job_id for polling status.
    """
    logger.info(
        "index/remove request: user=%s text_source=%s image_pdf_name=%s",
        user_id,
        body.text_source,
        body.image_pdf_name,
    )

    try:
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
    except Exception as e:
        logger.exception("Failed to create remove job for user=%s: %s", user_id, e)
        raise HTTPException(
            status_code=503,
            detail="Job system unavailable (Redis connection failed). Please try again later.",
        )

    if not job_id:
        logger.warning("Concurrency limit hit for user=%s (max 3 concurrent jobs)", user_id)
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent jobs. Max 3 per user. Please wait for a job to complete.",
        )

    logger.info("Created remove job: job_id=%s user=%s", job_id, user_id)

    background_tasks.add_task(
        _run_index_remove_job,
        job_id=job_id,
        user_id=user_id,
        text_source=(body.text_source or "").strip() or None,
        image_pdf_name=(body.image_pdf_name or "").strip() or None,
        clear_image_index=body.clear_image_index,
        clear_text_index=body.clear_text_index,
    )

    return {
        "status": "accepted",
        "job_id": job_id,
        "message": "Removal started. Poll /api/index/status/{job_id}",
    }


def _run_index_images_job(
    job_id: str,
    user_id: str,
    force: bool,
    selected_paths: list,
    selected_names: list,
) -> None:
    """Background task for image-only indexing.

    Logs entry, completion, timing, and any errors.
    """
    import time

    start_time = time.time()
    logger.info(
        "Starting index_images job: job_id=%s user=%s force=%s paths=%d names=%s",
        job_id,
        user_id,
        force,
        len(selected_paths),
        selected_names,
    )

    try:
        _job_service.update_job(job_id, status="running")
        cfg = merged_runtime_settings()
        out = IndexingService(cfg, user_id=user_id).index_images(
            force=force,
            selected_paths=selected_paths,
            selected_names=selected_names,
        )
        if out.get("status") == "failed":
            error_msg = out.get("error")
            logger.error("Index_images job failed: job_id=%s error=%s", job_id, error_msg)
            _job_service.mark_job_failed(job_id, error_msg)
            return
        _job_service.mark_job_completed(job_id, {"status": "completed", "results": out})
        elapsed = time.time() - start_time
        logger.info(
            "Index_images job completed: job_id=%s user=%s elapsed_sec=%.1f",
            job_id,
            user_id,
            elapsed,
        )
    except Exception as e:
        elapsed = time.time() - start_time
        if is_qdrant_unreachable(e):
            logger.error(
                "Index_images job failed (Qdrant): job_id=%s user=%s elapsed_sec=%.1f error=%s",
                job_id,
                user_id,
                elapsed,
                str(e),
            )
            _job_service.mark_job_failed(job_id, f"Qdrant unreachable: {e}")
        else:
            logger.exception(
                "Index_images job failed: job_id=%s user=%s elapsed_sec=%.1f error=%s",
                job_id,
                user_id,
                elapsed,
                str(e),
            )
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
    """Start image-only indexing job (ColQwen visual embeddings).

    Returns:
        202 Accepted with job_id for polling status.
    """
    selected_paths = body.selected_paths if body else []
    selected_names = body.selected_names if body else []

    logger.info(
        "index/image request: user=%s selected_paths=%d selected_names=%s",
        user_id,
        len(selected_paths),
        selected_names,
    )

    try:
        job_id = _job_service.create_job(
            user_id=user_id,
            job_type="index_images",
            params={
                "force": force,
                "selected_paths": selected_paths,
                "selected_names": selected_names,
            },
        )
    except Exception as e:
        logger.exception("Failed to create index_images job for user=%s: %s", user_id, e)
        raise HTTPException(
            status_code=503,
            detail="Job system unavailable (Redis connection failed). Please try again later.",
        )

    if not job_id:
        logger.warning("Concurrency limit hit for user=%s (max 3 concurrent jobs)", user_id)
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent jobs. Max 3 per user. Please wait for a job to complete.",
        )

    logger.info("Created index_images job: job_id=%s user=%s", job_id, user_id)

    background_tasks.add_task(
        _run_index_images_job,
        job_id=job_id,
        user_id=user_id,
        force=force,
        selected_paths=selected_paths,
        selected_names=selected_names,
    )

    return {
        "status": "accepted",
        "job_id": job_id,
        "message": "Image indexing started. Poll /api/index/status/{job_id}",
    }
