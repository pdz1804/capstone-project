"""
Phase 2 AI Service — FastAPI entrypoint.

Layering: api (this app) → services → repositories → Qdrant / files.
"""

from __future__ import annotations

import os

os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    chat_history_routes,
    chat_routes,
    config_routes,
    files_routes,
    health_routes,
    images_routes,
    insights_routes,
    pipeline_routes,
    quiz_routes,
    search_routes,
    status_routes,
    system_routes,
)
from app.identity.routes import auth_router as identity_auth_router
from app.identity.routes import users_router as identity_users_router
from app.core.paths import ensure_data_dirs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In containers, runtime env vars from `docker run --env-file` should win over
    # the baked-in `.env` copied into the image.
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
    ensure_data_dirs("default")
    logger.info("AI service startup")
    yield
    logger.info("AI service shutdown")


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
app.include_router(chat_routes.router)
app.include_router(chat_history_routes.router)
app.include_router(identity_auth_router, prefix="/api")
app.include_router(identity_users_router, prefix="/api")


@app.get("/api")
def api_root():
    return {
        "service": "phase2-fe-ai-merge",
        "version": "2.1.0",
        "docs": "/docs",
        "timestamp": datetime.now().isoformat(),
    }
