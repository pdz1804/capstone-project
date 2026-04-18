"""
Unified SageMaker endpoint server for Docling + Whisper + ColQwen.

This server is intentionally aligned with backend local implementations by reusing:
- app.services.colqwen_inference.ColQwenInferenceService
- src.processor.document_processor.MultimodalDocumentProcessor / ProcessingConfig
- src.processor.media_processor_enhanced.AudioTranscriber / MediaProcessorConfig
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import shutil
import sys
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List

from fastapi import Body, FastAPI, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from PIL import Image
from pydantic import BaseModel, Field

# Ensure backend imports resolve in both local dev and SageMaker container.
_backend_candidates = [
    Path(__file__).resolve().parents[2] / "backend",  # local repo layout
    Path("/opt/program/backend"),  # SageMaker image layout
]
for _backend_root in _backend_candidates:
    if _backend_root.exists():
        if str(_backend_root) not in sys.path:
            sys.path.insert(0, str(_backend_root))
        _backend_src = _backend_root / "src"
        if _backend_src.exists() and str(_backend_src) not in sys.path:
            sys.path.insert(0, str(_backend_src))

from app.services.colqwen_inference import ColQwenInferenceService  # type: ignore[import-not-found]
from processor.document_processor import (  # type: ignore[import-not-found]
    MultimodalDocumentProcessor,
    ProcessingConfig,
)
from processor.media_processor_enhanced import (  # type: ignore[import-not-found]
    AudioTranscriber,
    MediaProcessorConfig,
)

logger = logging.getLogger("phase2-unified-sagemaker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_colqwen: ColQwenInferenceService | None = None
_docling_processor: MultimodalDocumentProcessor | None = None
_whisper_transcriber: AudioTranscriber | None = None
_docling_cfg: ProcessingConfig | None = None
_whisper_cfg: MediaProcessorConfig | None = None
_docling_lock = asyncio.Lock()
_whisper_lock = asyncio.Lock()


class InvocationRequest(BaseModel):
    operation: str

    # Common/ColQwen
    query: str = ""
    images_base64: List[str] = Field(default_factory=list)
    query_embedding: List[List[float]] = Field(default_factory=list)
    doc_embeddings: List[List[List[float]]] = Field(default_factory=list)

    # Docling
    filename: str = ""
    content_base64: str = ""

    # Whisper
    audio_base64: str = ""
    language: str | None = None
    word_timestamps: bool | None = None


def _truthy_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes"):
        return True
    if raw in ("0", "false", "no"):
        return False
    return default


def _parse_float_tuple(raw: str, fallback: tuple[float, ...]) -> tuple[float, ...]:
    values = []
    for part in (raw or "").split(","):
        p = part.strip()
        if not p:
            continue
        try:
            values.append(float(p))
        except ValueError:
            return fallback
    return tuple(values) if values else fallback


def _decode_images_base64(values: List[str]) -> List[Image.Image]:
    out: List[Image.Image] = []
    for idx, encoded in enumerate(values):
        try:
            if "," in encoded and "base64" in encoded.split(",", 1)[0]:
                encoded = encoded.split(",", 1)[1]
            data = base64.b64decode(encoded)
            out.append(Image.open(io.BytesIO(data)).convert("RGB"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid images_base64[{idx}]: {exc}") from exc
    return out


def _score_sync(query_embedding: List[List[float]], doc_embeddings: List[List[List[float]]]) -> List[float]:
    import torch

    q = torch.tensor(query_embedding, dtype=torch.float32)
    scores: List[float] = []
    for doc in doc_embeddings:
        d = torch.tensor(doc, dtype=torch.float32)
        sim = torch.matmul(q, d.T)
        scores.append(float(sim.max(dim=1).values.sum().item()))
    return scores


def _build_colqwen_cfg() -> Dict[str, Any]:
    quant = os.getenv("COLQWEN_QUANTIZATION", "").strip().lower()
    load_4 = _truthy_env("COLQWEN_LOAD_IN_4BIT", default=quant == "4bit")
    load_8 = _truthy_env("COLQWEN_LOAD_IN_8BIT", default=(quant == "8bit" or not load_4))

    return {
        "inference": {
            "use_aws_sagemaker": False,
            "aws_region": os.getenv("AWS_REGION", "us-west-2").strip() or "us-west-2",
            "sagemaker_endpoint_name": "",
        },
        "image_retrieval": {
            "colqwen": {
                "model": os.getenv("COLQWEN_MODEL", "vidore/colqwen2-v1.0"),
                "dtype": os.getenv("COLQWEN_DTYPE", "bfloat16"),
                "load_in_4bit": load_4,
                "load_in_8bit": load_8,
            }
        },
    }


def _build_docling_cfg() -> ProcessingConfig:
    # Defaults aligned with backend default.yaml: VLM, image-export and table-export are
    # OFF by default for lower latency. Enable explicitly via container env when needed.
    return ProcessingConfig(
        use_gpu=_truthy_env("DOCLING_USE_GPU", default=True),
        enable_ocr=_truthy_env("DOCLING_ENABLE_OCR", default=True),
        enable_vlm=_truthy_env("DOCLING_ENABLE_VLM", default=False),
        enable_asr=_truthy_env("DOCLING_ENABLE_ASR", default=True),
        ocr_engine=os.getenv("DOCLING_OCR_ENGINE", "rapidocr"),
        vlm_model=os.getenv("DOCLING_VLM_MODEL", "granite_docling"),
        asr_model=os.getenv("DOCLING_ASR_MODEL", "whisper"),
        export_markdown=True,
        export_images=_truthy_env("DOCLING_EXPORT_IMAGES", default=False),
        export_tables=_truthy_env("DOCLING_EXPORT_TABLES", default=False),
        export_metadata=_truthy_env("DOCLING_EXPORT_METADATA", default=True),
    )


def _build_whisper_cfg() -> MediaProcessorConfig:
    return MediaProcessorConfig(
        use_gpu=_truthy_env("WHISPER_USE_GPU", default=True),
        enable_transcription=True,
        asr_model=os.getenv("WHISPER_MODEL", "base"),
        asr_language=(os.getenv("WHISPER_LANGUAGE") or None),
        use_word_timestamps=_truthy_env("WHISPER_WORD_TIMESTAMPS", default=True),
        temperature_schedule=_parse_float_tuple(
            os.getenv("WHISPER_TEMPERATURE_SCHEDULE", "0.0,0.2,0.4,0.6,0.8,1.0"),
            fallback=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
        ),
        # Ensure this service always uses local model loading inside endpoint.
        use_aws_sagemaker_whisper=False,
        aws_region=os.getenv("AWS_REGION", "us-west-2").strip() or "us-west-2",
    )


def _iter_exported_paths(value: Any) -> Iterable[Path]:
    if isinstance(value, str):
        p = Path(value)
        if p.exists():
            yield p
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_exported_paths(item)
        return
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(v, str) and (
                k in {"markdown", "saved_path", "metadata_path", "csv_path", "markdown_path", "image_path"}
                or k.endswith("_path")
            ):
                p = Path(v)
                if p.exists():
                    yield p
            else:
                yield from _iter_exported_paths(v)


def _docling_process_sync(req: InvocationRequest) -> Dict[str, Any]:
    if _docling_processor is None:
        raise RuntimeError("Docling processor is not initialized")
    if not req.content_base64:
        raise ValueError("content_base64 is required for process-document")

    filename = req.filename.strip() or "document.bin"
    raw = base64.b64decode(req.content_base64)

    workspace = Path(tempfile.gettempdir()) / "phase2_sm_unified" / f"doc_{uuid.uuid4().hex}"
    workspace.mkdir(parents=True, exist_ok=True)
    source = workspace / filename
    source.write_bytes(raw)

    try:
        info = _docling_processor.process_single_file(source)
        if not info.get("success"):
            raise RuntimeError(info.get("error", "Docling conversion failed"))
        exported = _docling_processor.export_processed_document(info)
        md_path = Path(exported.get("markdown", ""))
        if not md_path.exists():
            raise RuntimeError("Docling export produced no markdown file")
        markdown = md_path.read_text(encoding="utf-8")

        additional_files: Dict[str, str] = {}
        md_parent = md_path.parent
        for p in _iter_exported_paths(exported):
            if p == md_path or not p.is_file():
                continue
            rel = p.relative_to(md_parent).as_posix() if p.is_relative_to(md_parent) else p.name
            additional_files[rel] = base64.b64encode(p.read_bytes()).decode("ascii")

        return {"markdown": markdown, "additional_files": additional_files}
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
        # Remove docling export folder to keep endpoint disk usage bounded.
        try:
            if "md_path" in locals() and md_path.exists():
                shutil.rmtree(md_path.parent, ignore_errors=True)
        except Exception:
            pass


def _whisper_transcribe_sync(req: InvocationRequest) -> Dict[str, Any]:
    if _whisper_transcriber is None:
        raise RuntimeError("Whisper transcriber is not initialized")
    if not req.audio_base64:
        raise ValueError("audio_base64 is required for transcribe-audio")

    filename = req.filename.strip() or "audio.wav"
    audio_raw = base64.b64decode(req.audio_base64)
    suffix = Path(filename).suffix or ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio_raw)
        audio_path = Path(tmp.name)

    try:
        old_lang = _whisper_transcriber.config.asr_language
        old_words = _whisper_transcriber.config.use_word_timestamps
        if req.language is not None:
            _whisper_transcriber.config.asr_language = req.language
        if req.word_timestamps is not None:
            _whisper_transcriber.config.use_word_timestamps = bool(req.word_timestamps)

        result = _whisper_transcriber.transcribe(audio_path)
        if not result:
            raise RuntimeError("Whisper transcription returned empty result")
        return result
    finally:
        try:
            _whisper_transcriber.config.asr_language = old_lang
            _whisper_transcriber.config.use_word_timestamps = old_words
        except Exception:
            pass
        audio_path.unlink(missing_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _colqwen, _docling_processor, _whisper_transcriber, _docling_cfg, _whisper_cfg

    started = time.time()

    _colqwen = ColQwenInferenceService(_build_colqwen_cfg())

    doc_root = Path(tempfile.gettempdir()) / "phase2_sm_unified_docling"
    doc_root.mkdir(parents=True, exist_ok=True)
    _docling_cfg = _build_docling_cfg()
    _docling_processor = MultimodalDocumentProcessor(
        input_dir=doc_root / "input",
        output_dir=doc_root / "output",
        config=_docling_cfg,
    )

    _whisper_cfg = _build_whisper_cfg()
    _whisper_transcriber = AudioTranscriber(_whisper_cfg)

    logger.info("Unified endpoint ready in %.2fs", time.time() - started)
    yield


app = FastAPI(title="Phase2 Unified SageMaker Endpoint", version="1.0.0", lifespan=lifespan)


@app.get("/ping")
async def ping():
    ok = _colqwen is not None and _docling_processor is not None and _whisper_transcriber is not None
    return Response(status_code=200 if ok else 503)


@app.get("/health")
async def health():
    col_cfg = _build_colqwen_cfg()
    return {
        "status": "healthy" if (_colqwen and _docling_processor and _whisper_transcriber) else "not_ready",
        "services": {
            "colqwen": {
                "model": ((col_cfg.get("image_retrieval") or {}).get("colqwen") or {}).get("model"),
                "quant_4bit": ((col_cfg.get("image_retrieval") or {}).get("colqwen") or {}).get("load_in_4bit"),
                "quant_8bit": ((col_cfg.get("image_retrieval") or {}).get("colqwen") or {}).get("load_in_8bit"),
            },
            "docling": {
                "ocr_engine": getattr(_docling_cfg, "ocr_engine", None),
                "enable_vlm": getattr(_docling_cfg, "enable_vlm", None),
                "vlm_model": getattr(_docling_cfg, "vlm_model", None),
                "export_images": getattr(_docling_cfg, "export_images", None),
                "export_tables": getattr(_docling_cfg, "export_tables", None),
            },
            "whisper": {
                "model": getattr(_whisper_cfg, "asr_model", None),
                "language": getattr(_whisper_cfg, "asr_language", None),
                "word_timestamps": getattr(_whisper_cfg, "use_word_timestamps", None),
            },
        },
        "aws_region": os.getenv("AWS_REGION", "us-west-2"),
    }


@app.post("/invocations")
async def invocations(req: InvocationRequest = Body(...)):
    op = req.operation.strip().lower()
    started = time.time()

    if op == "health":
        return await health()

    if op == "embed-query":
        if _colqwen is None:
            raise HTTPException(status_code=503, detail="ColQwen service not initialized")
        if not req.query.strip():
            raise HTTPException(status_code=400, detail="query is required for embed-query")
        embedding = await run_in_threadpool(_colqwen.embed_query, req.query)
        return {
            "operation": op,
            "embedding": embedding,
            "n_tokens": len(embedding),
            "embed_dim": len(embedding[0]) if embedding else 0,
            "inference_time_ms": round((time.time() - started) * 1000, 1),
        }

    if op == "embed-images":
        if _colqwen is None:
            raise HTTPException(status_code=503, detail="ColQwen service not initialized")
        if not req.images_base64:
            raise HTTPException(status_code=400, detail="images_base64 is required for embed-images")
        images = _decode_images_base64(req.images_base64)
        embeddings, n_patches = await run_in_threadpool(_colqwen.embed_images, images)
        return {
            "operation": op,
            "embeddings": embeddings,
            "n_patches_per_image": n_patches,
            "num_images": len(embeddings),
            "embed_dim": len(embeddings[0][0]) if embeddings and embeddings[0] else 0,
            "inference_time_ms": round((time.time() - started) * 1000, 1),
        }

    if op == "score":
        if not req.query_embedding or not req.doc_embeddings:
            raise HTTPException(status_code=400, detail="query_embedding and doc_embeddings are required for score")
        scores = await run_in_threadpool(_score_sync, req.query_embedding, req.doc_embeddings)
        return {
            "operation": op,
            "scores": scores,
            "inference_time_ms": round((time.time() - started) * 1000, 1),
        }

    if op == "process-document":
        async with _docling_lock:
            try:
                data = await run_in_threadpool(_docling_process_sync, req)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Docling processing failed: {exc}") from exc
        data["operation"] = op
        data["inference_time_ms"] = round((time.time() - started) * 1000, 1)
        return data

    if op == "transcribe-audio":
        async with _whisper_lock:
            try:
                data = await run_in_threadpool(_whisper_transcribe_sync, req)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Whisper transcription failed: {exc}") from exc
        data["operation"] = op
        data["inference_time_ms"] = round((time.time() - started) * 1000, 1)
        return data

    raise HTTPException(status_code=400, detail=f"Unsupported operation: {req.operation}")

