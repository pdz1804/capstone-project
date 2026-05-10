"""
Phase 2 AI Service   FastAPI entrypoint.

Layering: api (this app) → services → repositories → Qdrant / files.
"""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    chat_history_routes,
    chat_routes,
    config_routes,
    feedback_routes,
    files_routes,
    health_routes,
    images_routes,
    insights_routes,
    pipeline_routes,
    quiz_routes,
    retrieval_eval_routes,
    search_routes,
    status_routes,
    system_routes,
)
from app.admin.routes import router as admin_router
from app.identity.routes import auth_router as identity_auth_router
from app.identity.routes import users_router as identity_users_router
from app.core.paths import ensure_data_dirs, sanitize_storage_user_id
from app.identity.user_repository_factory import get_user_repository_from_env
from app.identity.user_service import UserService
from app.services.app_usage_service import AppUsageService

_log_level_name = (os.getenv("LOG_LEVEL") or "INFO").upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)
logging.basicConfig(level=_log_level)
# Silence very chatty third-party loggers unless explicitly raised.
logging.getLogger("botocore.credentials").setLevel(max(logging.WARNING, _log_level))
logging.getLogger("boto3").setLevel(max(logging.WARNING, _log_level))
logging.getLogger("botocore").setLevel(max(logging.WARNING, _log_level))
logging.getLogger("urllib3").setLevel(max(logging.WARNING, _log_level))
logger = logging.getLogger(__name__)
USAGE_SERVICE: AppUsageService | None = None


def _resolve_usage_user_id(request: Request) -> str | None:
    raw = str(request.headers.get("X-User-Id") or "").strip()
    if not raw:
        return None

    sanitized = sanitize_storage_user_id(raw)
    # Do not record telemetry entries that collapse to fallback/default IDs.
    if not sanitized or sanitized == "default":
        return None

    return sanitized


async def _record_usage_safely(
    svc: AppUsageService,
    *,
    method: str,
    path: str,
    status_code: int,
    duration_ms: int,
    user_id: str,
    model_id: str | None,
    token_in: int,
    token_out: int,
    feature: str | None,
    request_id: str | None,
) -> None:
    try:
        recorded = await asyncio.to_thread(
            svc.record_invocation,
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            user_id=user_id,
            model_id=model_id,
            token_in=token_in,
            token_out=token_out,
            feature=feature,
            request_id=request_id,
        )
        table_name = (os.getenv("DYNAMODB_APP_USAGE_TABLE") or "<unknown>").strip() or "<unknown>"
        usage_id = str((recorded or {}).get("usage_id") or "")
        saved_feature = str((recorded or {}).get("feature") or feature or "")
        saved_user_id = str((recorded or {}).get("user_id") or user_id)
        logger.info(
            "Usage record saved to %s: usage_id=%s feature=%s user_id=%s method=%s path=%s status=%s",
            table_name,
            usage_id,
            saved_feature,
            saved_user_id,
            method,
            path,
            status_code,
        )
    except Exception:
        logger.exception("Usage tracking write failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global USAGE_SERVICE

    logger.info("🚀 AI service startup initiated")

    try:
        # In containers, runtime env vars from `docker run --env-file` should win over
        # the baked-in `.env` copied into the image.
        load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
        logger.info("✓ Environment variables loaded")
    except Exception as env_err:
        logger.exception("❌ Failed to load environment variables: %s", env_err)
        raise

    try:
        ensure_data_dirs("default")
        logger.info("✓ Data directories ensured")
    except Exception as dir_err:
        logger.exception("❌ Failed to ensure data directories: %s", dir_err)
        raise

    try:
        user_repo = get_user_repository_from_env()
        logger.info("✓ User repository initialized")
        UserService(user_repo).ensure_default_admin_account()
        logger.info("✓ Default admin bootstrap complete")
    except Exception as bootstrap_err:
        logger.warning("⚠️  Default admin bootstrap skipped: %s", bootstrap_err)

    try:
        USAGE_SERVICE = AppUsageService.from_env_optional()
        if USAGE_SERVICE is None:
            logger.warning("⚠️  App usage tracking disabled (DYNAMODB_APP_USAGE_TABLE is not configured)")
        else:
            logger.info("✓ App usage tracking enabled")
    except Exception as usage_err:
        logger.exception("❌ App usage service initialization failed: %s", usage_err)

    port = os.getenv("RUN_API_PORT", "5000")
    logger.info("✅ AI service startup complete - listening on port %s", port)
    yield
    logger.info("🛑 AI service shutdown")


app = FastAPI(
    title="Phase 2 FE + AI Merge",
    description="Multimodal RAG (Qdrant, S3, SageMaker ColQwen/Docling, Bedrock Claude) + Firebase Google auth + DynamoDB users.",
    version="2.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def usage_tracking_middleware(request: Request, call_next):
    started = perf_counter()
    response = None
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        svc = USAGE_SERVICE
        if svc is not None:
            duration_ms = int((perf_counter() - started) * 1000)
            user_id = _resolve_usage_user_id(request)
            if user_id:
                model_id = ""
                token_in = 0
                token_out = 0
                feature = ""
                request_id = ""
                if response is not None:
                    model_id = str(response.headers.get("X-Usage-Model-Id") or "").strip()
                    feature = str(response.headers.get("X-Usage-Feature") or "").strip()
                    request_id = str(response.headers.get("X-Request-Id") or "").strip()
                    try:
                        token_in = int(response.headers.get("X-Usage-Token-In") or 0)
                    except Exception:
                        token_in = 0
                    try:
                        token_out = int(response.headers.get("X-Usage-Token-Out") or 0)
                    except Exception:
                        token_out = 0

                asyncio.create_task(
                    _record_usage_safely(
                        svc,
                        method=request.method,
                        path=request.url.path,
                        status_code=status_code,
                        duration_ms=duration_ms,
                        user_id=user_id,
                        model_id=model_id or None,
                        token_in=token_in,
                        token_out=token_out,
                        feature=feature or None,
                        request_id=request_id or None,
                    )
                )

app.include_router(health_routes.router)
app.include_router(status_routes.router)
app.include_router(config_routes.router)
app.include_router(system_routes.router)
app.include_router(files_routes.router)
app.include_router(pipeline_routes.router)
app.include_router(search_routes.router)
app.include_router(images_routes.router)
app.include_router(insights_routes.router)
app.include_router(quiz_routes.router)
app.include_router(retrieval_eval_routes.router)
app.include_router(chat_routes.router)
app.include_router(chat_history_routes.router)
app.include_router(feedback_routes.router)
app.include_router(identity_auth_router, prefix="/api")
app.include_router(identity_users_router, prefix="/api")
app.include_router(admin_router)


@app.get("/api")
def api_root():
    return {
        "service": "phase2-fe-ai-merge",
        "version": "2.1.0",
        "docs": "/docs",
        "timestamp": datetime.now().isoformat(),
    }
