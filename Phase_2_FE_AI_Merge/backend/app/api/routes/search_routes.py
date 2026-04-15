import logging
import mimetypes
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.api.deps import storage_user_id
from app.api.schemas import SearchRequest
from app.core.paths import merged_runtime_settings
from app.core.qdrant_errors import is_qdrant_unreachable, qdrant_setup_hint
from app.services.search_orchestrator import SearchOrchestrator
from app.storage import get_file_storage
from app.storage.service import S3FileStorage, parse_s3_uri

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search")
def search(
    req: SearchRequest,
    user_id: str = Depends(storage_user_id),
):
    cfg = merged_runtime_settings()
    try:
        orch = SearchOrchestrator(cfg, user_id=user_id)
        return orch.run(
            query=req.query,
            top_k=req.top_k,
            retriever_type=req.retriever_type,
            include_images=req.include_images,
            images_for_generation=req.images_for_generation,
            mode=req.mode,
            search_scope=req.search_scope,
            generation_model=req.generation_model,
            skip_reranker=req.skip_reranker,
        )
    except Exception as e:
        if is_qdrant_unreachable(e):
            logger.warning("search: Qdrant unreachable: %s", e)
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Cannot connect to Qdrant. {qdrant_setup_hint(cfg)} "
                    f"Underlying: {type(e).__name__}: {e}"
                ),
            ) from e
        logger.exception("search")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/search/generation-models")
def list_generation_models() -> Dict[str, Any]:
    cfg = merged_runtime_settings()
    gyaml = cfg.get("generation", {}) or {}
    provider = str(gyaml.get("provider", "") or "").lower()
    configured_model = str(gyaml.get("model", "") or "").strip()
    out: Dict[str, Any] = {"provider": provider, "configured_model": configured_model, "models": []}

    if provider != "bedrock":
        if configured_model:
            out["models"] = [configured_model]
        return out

    try:
        import boto3

        region = (gyaml.get("bedrock_region") or None) or "us-east-1"
        bedrock = boto3.client("bedrock", region_name=region)
        resp = bedrock.list_foundation_models(byOutputModality="TEXT")
        model_ids: List[str] = []
        for item in resp.get("modelSummaries") or []:
            mid = str(item.get("modelId") or "").strip()
            if mid:
                model_ids.append(mid)
        model_ids = sorted(set(model_ids))
        if configured_model and configured_model not in model_ids:
            model_ids.insert(0, configured_model)
        out.update({"region": region, "models": model_ids})
        return out
    except Exception as e:
        logger.warning("list generation models failed: %s", e)
        if configured_model:
            out["models"] = [configured_model]
        out["error"] = str(e)
        return out


@router.get("/search/image-preview")
def search_image_preview(
    storage_uri: str | None = Query(None, description="s3:// URI for indexed image/pdf page source."),
    source_path: str | None = Query(None, description="Absolute local source path fallback for local backend."),
    page: int = Query(1, ge=1, description="1-based page to render when source is a PDF."),
    user_id: str = Depends(storage_user_id),
):
    storage = get_file_storage(user_id)
    body: bytes
    media_type: str | None = None
    filename = "image"

    if storage_uri:
        decoded = unquote(storage_uri).strip()
        parsed = parse_s3_uri(decoded)
        if not parsed:
            raise HTTPException(status_code=400, detail="Invalid storage_uri")
        bucket, key = parsed
        if not isinstance(storage, S3FileStorage):
            raise HTTPException(status_code=400, detail="storage_uri preview requires S3 backend")
        if not storage.can_read_object(bucket, key):
            raise HTTPException(status_code=403, detail="Access denied for this storage_uri")
        body, media_type = storage.read_object(bucket, key)
        filename = Path(key).name or "image"
    elif source_path:
        p = Path(unquote(source_path)).expanduser()
        root = storage.processing_dir.resolve()
        try:
            rp = p.resolve()
            rp.relative_to(root)
        except Exception:
            raise HTTPException(status_code=403, detail="source_path is outside processing workspace")
        if not rp.exists() or not rp.is_file():
            raise HTTPException(status_code=404, detail="source_path not found")
        body = rp.read_bytes()
        filename = rp.name
    else:
        raise HTTPException(status_code=400, detail="Provide storage_uri or source_path")

    guessed, _ = mimetypes.guess_type(filename)
    media_type = media_type or guessed or "application/octet-stream"

    # If source is PDF, render requested page to PNG so frontend <img> can display it.
    if (filename or "").lower().endswith(".pdf") or media_type == "application/pdf":
        try:
            from pdf2image import convert_from_bytes

            images = convert_from_bytes(
                body,
                first_page=page,
                last_page=page,
                dpi=150,
            )
            if images:
                import io

                out = io.BytesIO()
                images[0].save(out, format="PNG")
                body = out.getvalue()
                media_type = "image/png"
                filename = f"{Path(filename).stem}_p{page}.png"
        except Exception as e:
            logger.warning("search/image-preview pdf render failed (page=%s): %s", page, e)

    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{filename}"},
    )
