"""
SageMaker-compatible Whisper ASR server.
"""

from __future__ import annotations

import base64
import tempfile
import time
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Response
from pydantic import BaseModel

logger = logging.getLogger("whisper-sagemaker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_model: Any = None
_model_name = "base"
_device = "cpu"
_load_time_s = 0.0


class InvocationRequest(BaseModel):
    operation: str
    filename: str = "audio.wav"
    audio_base64: str = ""
    language: str | None = None
    word_timestamps: bool = True


def _load_model() -> None:
    global _model, _model_name, _device, _load_time_s
    started = time.time()

    import torch
    import whisper

    _model_name = os.getenv("WHISPER_MODEL", "base")
    _device = "cuda" if torch.cuda.is_available() else "cpu"
    _model = whisper.load_model(_model_name, device=_device)
    _load_time_s = time.time() - started

    logger.info("Whisper loaded model=%s device=%s startup_s=%.2f", _model_name, _device, _load_time_s)


def _transcribe(req: InvocationRequest) -> dict:
    if not req.audio_base64:
        raise HTTPException(status_code=400, detail="audio_base64 is required")

    try:
        raw = base64.b64decode(req.audio_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid audio_base64: {exc}") from exc

    suffix = Path(req.filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(raw)
        audio_path = Path(tmp.name)

    try:
        started = time.time()
        result = _model.transcribe(
            str(audio_path),
            task="transcribe",
            language=req.language,
            word_timestamps=bool(req.word_timestamps),
        )
        elapsed = (time.time() - started) * 1000
        return {
            "text": result.get("text", ""),
            "language": result.get("language"),
            "duration": result.get("duration"),
            "segments": result.get("segments", []),
            "inference_time_ms": round(elapsed, 1),
        }
    finally:
        try:
            audio_path.unlink(missing_ok=True)
        except Exception:
            pass


app = FastAPI(title="Whisper SageMaker Server", version="1.0.0")


@app.on_event("startup")
def startup_event() -> None:
    _load_model()


@app.get("/ping")
async def ping():
    return Response(status_code=200 if _model is not None else 503)


@app.get("/health")
async def health():
    return {
        "status": "healthy" if _model is not None else "not_ready",
        "model": _model_name,
        "device": _device,
        "load_time_s": round(_load_time_s, 3),
    }


@app.post("/invocations")
async def invocations(req: InvocationRequest = Body(...)):
    op = req.operation.strip().lower()
    if op == "health":
        return await health()
    if op != "transcribe-audio":
        raise HTTPException(status_code=400, detail=f"Unsupported operation: {req.operation}")
    if _model is None:
        raise HTTPException(status_code=503, detail="Whisper model not loaded")
    return _transcribe(req)
