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
    config_routes,
    files_routes,
    health_routes,
    images_routes,
    insights_routes,
    pipeline_routes,
    search_routes,
    status_routes,
    system_routes,
)
from app.core.paths import ensure_data_dirs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    ensure_data_dirs("default")
    logger.info("AI service startup")
    yield
    logger.info("AI service shutdown")


app = FastAPI(
    title="Educational RAG AI Service",
    description="Multimodal RAG with Qdrant + optional AWS SageMaker ColQwen inference.",
    version="2.0.0",
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


@app.get("/api")
async def api_root():
    return {
        "service": "phase2-ai-service",
        "version": "2.0.0",
        "docs": "/docs",
        "timestamp": datetime.now().isoformat(),
    }
