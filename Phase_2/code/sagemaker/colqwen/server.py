"""
SageMaker-compatible ColQwen inference server.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import List

from fastapi import Body, FastAPI, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from PIL import Image
import torch

logger = logging.getLogger("colqwen-sagemaker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_model = None
_processor = None
_model_name = ""
_device = "cpu"
_quantization = "none"
_load_time_s = 0.0
_max_concurrent = 1
_semaphore: asyncio.Semaphore | None = None


class InvocationRequest(BaseModel):
    operation: str
    query: str = ""
    images_base64: List[str] = Field(default_factory=list)
    query_embedding: List[List[float]] = Field(default_factory=list)
    doc_embeddings: List[List[List[float]]] = Field(default_factory=list)


def _as_tensor(outputs):
    if isinstance(outputs, torch.Tensor):
        return outputs
    if hasattr(outputs, "last_hidden_state"):
        return outputs.last_hidden_state
    if isinstance(outputs, (tuple, list)) and outputs and isinstance(outputs[0], torch.Tensor):
        return outputs[0]
    raise TypeError(f"Unexpected ColQwen output type: {type(outputs)!r}")


def _decode_images(values: List[str]) -> List[Image.Image]:
    images: List[Image.Image] = []
    for idx, encoded in enumerate(values):
        try:
            if "," in encoded and "base64" in encoded.split(",", 1)[0]:
                encoded = encoded.split(",", 1)[1]
            data = base64.b64decode(encoded)
            images.append(Image.open(io.BytesIO(data)).convert("RGB"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid image at index {idx}: {exc}") from exc
    return images


def _embed_query_sync(query: str):
    with torch.no_grad():
        q_inputs = _processor.process_queries([query]).to(_model.device)
        out = _as_tensor(_model(**q_inputs)).detach().cpu()
    return out


def _embed_images_sync(images: List[Image.Image]):
    all_embeddings = []
    n_patches = []
    with torch.no_grad():
        for img in images:
            i_inputs = _processor.process_images([img]).to(_model.device)
            out = _as_tensor(_model(**i_inputs)).detach().cpu().numpy()
            all_embeddings.append(out[0].tolist())
            n_patches.append(int(out.shape[1]))
    return all_embeddings, n_patches


def _score_sync(query_embedding: List[List[float]], doc_embeddings: List[List[List[float]]]):
    q = torch.tensor(query_embedding, dtype=torch.float32)
    scores: List[float] = []
    for doc in doc_embeddings:
        d = torch.tensor(doc, dtype=torch.float32)
        sim = torch.matmul(q, d.T)
        scores.append(float(sim.max(dim=1).values.sum().item()))
    return scores


@asynccontextmanager
async def _slot(name: str):
    if _semaphore is None:
        yield
        return
    await _semaphore.acquire()
    try:
        logger.info("inference slot acquired: %s", name)
        yield
    finally:
        _semaphore.release()


def _load_model() -> None:
    global _model, _processor, _model_name, _device, _quantization, _load_time_s, _max_concurrent, _semaphore

    _model_name = os.getenv("COLQWEN_MODEL", "vidore/colqwen2-v1.0")
    _quantization = os.getenv("COLQWEN_QUANTIZATION", "8bit").strip().lower()
    _max_concurrent = max(1, int(os.getenv("COLQWEN_MAX_CONCURRENT_INFERENCES", "2")))
    _semaphore = asyncio.Semaphore(_max_concurrent)

    started = time.time()
    _device = "cuda" if torch.cuda.is_available() else "cpu"
    model_kwargs = {}

    if _quantization in {"4bit", "8bit"} and _device == "cuda":
        from transformers import BitsAndBytesConfig

        if _quantization == "4bit":
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
        else:
            model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
    else:
        model_kwargs["torch_dtype"] = torch.float32 if _device == "cpu" else torch.bfloat16

    is_25 = "2.5" in _model_name.lower()
    if is_25:
        from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor

        _processor = ColQwen2_5_Processor.from_pretrained(_model_name)
        _model = ColQwen2_5.from_pretrained(_model_name, **model_kwargs).eval()
    else:
        from colpali_engine.models import ColQwen2, ColQwen2Processor

        _processor = ColQwen2Processor.from_pretrained(_model_name)
        _model = ColQwen2.from_pretrained(_model_name, **model_kwargs).eval()

    _load_time_s = time.time() - started
    logger.info(
        "ColQwen loaded model=%s device=%s quantization=%s startup_s=%.2f",
        _model_name,
        _device,
        _quantization,
        _load_time_s,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    _load_model()
    yield


app = FastAPI(title="ColQwen SageMaker Server", version="1.0.0", lifespan=lifespan)


@app.get("/ping")
async def ping():
    return Response(status_code=200 if _model is not None else 503)


@app.get("/health")
async def health():
    return {
        "status": "healthy" if _model is not None else "model_not_loaded",
        "model": _model_name,
        "device": _device,
        "quantization": _quantization,
        "model_load_time_s": round(_load_time_s, 3),
        "max_concurrent_inferences": _max_concurrent,
    }


@app.post("/invocations")
async def invocations(req: InvocationRequest = Body(...)):
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    op = req.operation.strip().lower()
    start = time.time()

    if op == "embed-query":
        if not req.query.strip():
            raise HTTPException(status_code=400, detail="query is required for embed-query")
        async with _slot("embed-query"):
            emb = await run_in_threadpool(_embed_query_sync, req.query)
        return {
            "operation": op,
            "embedding": emb[0].tolist(),
            "embed_dim": int(emb.shape[2]),
            "n_tokens": int(emb.shape[1]),
            "inference_time_ms": round((time.time() - start) * 1000, 1),
        }

    if op == "embed-images":
        if not req.images_base64:
            raise HTTPException(status_code=400, detail="images_base64 is required for embed-images")
        images = _decode_images(req.images_base64)
        async with _slot("embed-images"):
            embeddings, n_patches = await run_in_threadpool(_embed_images_sync, images)
        embed_dim = len(embeddings[0][0]) if embeddings and embeddings[0] else 0
        return {
            "operation": op,
            "num_images": len(embeddings),
            "embeddings": embeddings,
            "n_patches_per_image": n_patches,
            "embed_dim": embed_dim,
            "inference_time_ms": round((time.time() - start) * 1000, 1),
        }

    if op == "score":
        if not req.query_embedding or not req.doc_embeddings:
            raise HTTPException(status_code=400, detail="query_embedding and doc_embeddings are required for score")
        scores = await run_in_threadpool(_score_sync, req.query_embedding, req.doc_embeddings)
        return {
            "operation": op,
            "scores": scores,
            "inference_time_ms": round((time.time() - start) * 1000, 1),
        }

    if op == "health":
        return await health()

    raise HTTPException(status_code=400, detail=f"Unsupported operation: {req.operation}")
