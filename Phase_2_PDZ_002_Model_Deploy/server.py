"""
ColQwen Inference Server for AWS SageMaker or local GPU hosts.

Serves the ColQwen2 model as a FastAPI REST API for the Multimodal RAG pipeline.

Endpoints:
    GET  /ping           - SageMaker health probe endpoint
    POST /invocations    - SageMaker unified inference endpoint
    POST /embed-images   - Embed PDF page images into multi-vector embeddings
    POST /embed-query    - Embed a text query
    POST /score          - Score query embedding vs document embeddings
    GET  /health         - Detailed health check with GPU and runtime stats
    POST /shutdown       - Graceful shutdown (local mode only)

Usage:
    python server.py                         # Local mode on 0.0.0.0:8000
    python server.py --port 8080             # SageMaker container port
    python server.py --managed-runtime       # Disable unsafe local-only actions
"""

import os
import io
import time
import asyncio
import signal
import logging
import argparse
import importlib
import base64
from typing import List
from contextlib import asynccontextmanager

import torch
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException, Body, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
import uvicorn

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("colqwen-server")

# ─── Global Model State ───────────────────────────────────────────────────────
_model = None
_processor = None
_model_name = None
_device = None
_load_time = None
_quantization = None
_max_concurrent_inferences = 1
_inference_semaphore = None
_active_gpu_requests = 0
_managed_runtime = False


def _parse_positive_int(value: str, default: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def configure_runtime(max_concurrent_inferences: int = 1):
    """Configure bounded GPU inference concurrency for the single loaded model."""
    global _max_concurrent_inferences, _inference_semaphore

    _max_concurrent_inferences = max(1, int(max_concurrent_inferences))
    _inference_semaphore = asyncio.Semaphore(_max_concurrent_inferences)


@asynccontextmanager
async def acquire_inference_slot(operation_name: str):
    """Serialize or bound GPU-heavy requests to avoid VRAM spikes on a single card."""
    global _active_gpu_requests

    if _inference_semaphore is None:
        configure_runtime(1)

    logger.info(
        "Waiting for inference slot: %s (active=%s/%s)",
        operation_name,
        _active_gpu_requests,
        _max_concurrent_inferences,
    )

    await _inference_semaphore.acquire()
    _active_gpu_requests += 1
    logger.info(
        "Acquired inference slot: %s (active=%s/%s)",
        operation_name,
        _active_gpu_requests,
        _max_concurrent_inferences,
    )

    try:
        yield
    finally:
        _active_gpu_requests -= 1
        _inference_semaphore.release()
        logger.info(
            "Released inference slot: %s (active=%s/%s)",
            operation_name,
            _active_gpu_requests,
            _max_concurrent_inferences,
        )


def load_model(model_name: str = "vidore/colqwen2-v1.0", quantization: str = "8bit"):
    """
    Load ColQwen model with optional quantization.
    
        On T4 16GB-class GPUs:
      - 8-bit model: ~3.5GB VRAM → leaves ~12GB for batch processing
      - 4-bit model: ~2.5-3.0GB VRAM → leaves more headroom, sometimes less stable
      - BF16 model:  ~6GB VRAM  → leaves ~10GB for batch processing
    """
    global _model, _processor, _model_name, _device, _load_time, _quantization
    
    start = time.time()
    _model_name = model_name
    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _quantization = quantization
    
    logger.info(f"Loading model: {model_name}")
    logger.info(f"Device: {_device}")
    logger.info(f"Quantization: {quantization}")
    
    if _device.type == "cuda":
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        logger.info(f"GPU: {gpu_name} ({gpu_mem:.1f} GB)")
    
    # Build model kwargs
    model_kwargs = {}
    
    if quantization in {"4bit", "8bit"} and _device.type == "cuda":
        try:
            from transformers import BitsAndBytesConfig

            if quantization == "4bit":
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.bfloat16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
                logger.info("4-bit quantization enabled via BitsAndBytes")
            else:
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_8bit=True
                )
                logger.info("8-bit quantization enabled via BitsAndBytes")
        except ImportError:
            logger.warning("bitsandbytes not available, loading in bfloat16")
            model_kwargs["torch_dtype"] = torch.bfloat16
    else:
        if quantization in {"4bit", "8bit"} and _device.type != "cuda":
            logger.warning("Quantization requested on CPU. Falling back to float32.")
        model_kwargs["torch_dtype"] = torch.float32 if _device.type == "cpu" else torch.bfloat16
    
    # Detect model version and load accordingly
    is_colqwen25 = "colqwen2.5" in model_name.lower() or "2.5" in model_name
    
    try:
        if is_colqwen25:
            from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor
            _processor = ColQwen2_5_Processor.from_pretrained(model_name)
            _model = ColQwen2_5.from_pretrained(model_name, **model_kwargs).eval()
            logger.info("Loaded ColQwen 2.5 model")
        else:
            from colpali_engine.models import ColQwen2, ColQwen2Processor
            _processor = ColQwen2Processor.from_pretrained(model_name)
            _model = ColQwen2.from_pretrained(model_name, **model_kwargs).eval()
            logger.info("Loaded ColQwen 2 model")
    except ImportError as e:
        logger.error(f"colpali_engine import failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Model loading failed: {e}")
        raise
    
    _load_time = time.time() - start
    
    # Log memory usage
    if _device.type == "cuda":
        allocated = torch.cuda.memory_allocated(0) / (1024**3)
        reserved = torch.cuda.memory_reserved(0) / (1024**3)
        logger.info(f"Model loaded in {_load_time:.1f}s")
        logger.info(f"GPU memory: {allocated:.2f} GB allocated, {reserved:.2f} GB reserved")
    else:
        logger.info(f"Model loaded in {_load_time:.1f}s (CPU mode)")


def get_gpu_stats() -> dict:
    """Get current GPU utilization and memory stats."""
    stats = {
        "device": str(_device),
        "cuda_available": torch.cuda.is_available(),
    }
    
    if torch.cuda.is_available():
        stats.update({
            "gpu_name": torch.cuda.get_device_name(0),
            "gpu_memory_total_gb": round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2),
            "gpu_memory_allocated_gb": round(torch.cuda.memory_allocated(0) / (1024**3), 2),
            "gpu_memory_reserved_gb": round(torch.cuda.memory_reserved(0) / (1024**3), 2),
            "gpu_memory_free_gb": round(
                (torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_reserved(0)) / (1024**3), 2
            ),
        })
        
        # Try to get GPU utilization via pynvml
        try:
            pynvml = importlib.import_module("pynvml")
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            stats["gpu_utilization_percent"] = util.gpu
            stats["gpu_memory_utilization_percent"] = util.memory
            pynvml.nvmlShutdown()
        except Exception:
            pass
    
    return stats


def _extract_tensor(outputs: torch.Tensor) -> torch.Tensor:
    """Normalize model outputs into a tensor for downstream serialization."""
    if isinstance(outputs, torch.Tensor):
        return outputs
    if hasattr(outputs, "last_hidden_state"):
        return outputs.last_hidden_state
    if isinstance(outputs, (tuple, list)) and outputs:
        first = outputs[0]
        if isinstance(first, torch.Tensor):
            return first
    raise TypeError(f"Unsupported model output type: {type(outputs)!r}")


def _embed_images_sync(images: List[Image.Image]):
    with torch.no_grad():
        all_embeddings = []
        n_patches = []

        for img in images:
            inputs = _processor.process_images([img]).to(_model.device)
            outputs = _extract_tensor(_model(**inputs)).detach().cpu().numpy()
            all_embeddings.append(outputs[0].tolist())
            n_patches.append(outputs.shape[1])

    return all_embeddings, n_patches


def _embed_query_sync(query: str):
    with torch.no_grad():
        inputs = _processor.process_queries([query]).to(_model.device)
        outputs = _extract_tensor(_model(**inputs)).detach().cpu().numpy()
    return outputs


def _score_sync(query_embedding: List[List[float]], doc_embeddings: List[List[List[float]]]):
    query_emb = torch.tensor(query_embedding, dtype=torch.float32)

    scores = []
    for doc_emb_list in doc_embeddings:
        doc_emb = torch.tensor(doc_emb_list, dtype=torch.float32)
        sim = torch.matmul(query_emb, doc_emb.T)
        max_sim = sim.max(dim=1).values.sum().item()
        scores.append(max_sim)

    return scores


def _decode_base64_images(images_base64: List[str]) -> List[Image.Image]:
    images = []
    for idx, encoded in enumerate(images_base64):
        try:
            # Support both raw base64 and data URL prefixed strings.
            if "," in encoded and "base64" in encoded.split(",", 1)[0]:
                encoded = encoded.split(",", 1)[1]
            data = base64.b64decode(encoded)
            images.append(Image.open(io.BytesIO(data)).convert("RGB"))
        except Exception as exc:
            raise HTTPException(400, f"Invalid base64 image at index {idx}: {exc}")
    return images


# ─── FastAPI App ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup."""
    global _managed_runtime

    model_name = os.environ.get("COLQWEN_MODEL", "vidore/colqwen2-v1.0")
    quantization = os.environ.get("COLQWEN_QUANTIZATION", "8bit").lower()
    max_concurrent_inferences = _parse_positive_int(
        os.environ.get("COLQWEN_MAX_CONCURRENT_INFERENCES", "1"),
        default=1,
    )
    _managed_runtime = os.environ.get("SAGEMAKER_SERVICE_MODE", "false").lower() == "true"

    configure_runtime(max_concurrent_inferences=max_concurrent_inferences)
    load_model(model_name=model_name, quantization=quantization)
    yield
    logger.info("Shutting down server...")


app = FastAPI(
    title="ColQwen Inference Server",
    description="8-bit quantized ColQwen model for Multimodal RAG image retrieval",
    version="1.0.0",
    lifespan=lifespan,
)


# ─── Request/Response Models ──────────────────────────────────────────────────

class EmbedQueryRequest(BaseModel):
    query: str


class ScoreRequest(BaseModel):
    """Score a query against pre-computed document embeddings."""
    query_embedding: List[List[float]]           # [n_query_tokens, embed_dim]
    doc_embeddings: List[List[List[float]]]      # [n_docs, n_patches, embed_dim]


class EmbedQueryResponse(BaseModel):
    query: str
    embedding: List[List[float]]   # [n_tokens, embed_dim]
    embed_dim: int
    n_tokens: int
    inference_time_ms: float


class EmbedImagesResponse(BaseModel):
    num_images: int
    embeddings: List[List[List[float]]]  # [n_images, n_patches, embed_dim]  
    embed_dim: int
    n_patches_per_image: List[int]
    inference_time_ms: float


class ScoreResponse(BaseModel):
    scores: List[float]   # one score per document
    inference_time_ms: float


class SageMakerInvocationRequest(BaseModel):
    operation: str
    query: str = ""
    query_embedding: List[List[float]] = Field(default_factory=list)
    doc_embeddings: List[List[List[float]]] = Field(default_factory=list)
    images_base64: List[str] = Field(default_factory=list)


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/ping")
async def ping():
    """SageMaker-compatible health probe endpoint."""
    if _model is None:
        return Response(status_code=503)
    return Response(status_code=200)

@app.get("/health")
async def health():
    """Health check with GPU status."""
    return {
        "status": "healthy" if _model is not None else "model_not_loaded",
        "model": _model_name,
        "quantization": _quantization,
        "model_load_time_s": round(_load_time, 1) if _load_time else None,
        "inference": {
            "max_concurrent_requests": _max_concurrent_inferences,
            "active_gpu_requests": _active_gpu_requests,
            "workers": 1,
        },
        "runtime": {
            "managed_mode": _managed_runtime,
            "sagemaker_service_mode": _managed_runtime,
        },
        "gpu": get_gpu_stats(),
        "timestamp": time.time(),
    }


@app.post("/invocations")
async def invocations(req: SageMakerInvocationRequest = Body(...)):
    """SageMaker-compatible single endpoint for model operations."""
    op = req.operation.strip().lower()

    if _model is None:
        raise HTTPException(503, "Model not loaded")

    if op == "embed-query":
        if not req.query.strip():
            raise HTTPException(400, "query is required for operation=embed-query")

        start = time.time()
        async with acquire_inference_slot("invocations:embed-query"):
            emb = await run_in_threadpool(_embed_query_sync, req.query)

        elapsed_ms = (time.time() - start) * 1000
        return {
            "operation": op,
            "query": req.query,
            "embedding": emb[0].tolist(),
            "embed_dim": int(emb.shape[2]),
            "n_tokens": int(emb.shape[1]),
            "inference_time_ms": round(elapsed_ms, 1),
        }

    if op == "embed-images":
        if not req.images_base64:
            raise HTTPException(400, "images_base64 is required for operation=embed-images")

        images = _decode_base64_images(req.images_base64)
        start = time.time()
        async with acquire_inference_slot("invocations:embed-images"):
            all_embeddings, n_patches = await run_in_threadpool(_embed_images_sync, images)

        elapsed_ms = (time.time() - start) * 1000
        return {
            "operation": op,
            "num_images": len(images),
            "embeddings": all_embeddings,
            "embed_dim": all_embeddings[0][0].__len__() if all_embeddings else 0,
            "n_patches_per_image": n_patches,
            "inference_time_ms": round(elapsed_ms, 1),
        }

    if op == "score":
        if not req.query_embedding:
            raise HTTPException(400, "query_embedding is required for operation=score")
        if not req.doc_embeddings:
            raise HTTPException(400, "doc_embeddings is required for operation=score")

        start = time.time()
        scores = await run_in_threadpool(_score_sync, req.query_embedding, req.doc_embeddings)
        elapsed_ms = (time.time() - start) * 1000
        return {
            "operation": op,
            "scores": scores,
            "inference_time_ms": round(elapsed_ms, 1),
        }

    if op == "health":
        return {
            "operation": op,
            "status": "healthy",
            "model": _model_name,
            "quantization": _quantization,
            "model_load_time_s": round(_load_time, 1) if _load_time else None,
            "inference": {
                "max_concurrent_requests": _max_concurrent_inferences,
                "active_gpu_requests": _active_gpu_requests,
            },
            "runtime": {
                "managed_mode": _managed_runtime,
            },
            "gpu": get_gpu_stats(),
        }

    raise HTTPException(400, f"Unsupported operation: {req.operation}")


@app.post("/embed-images", response_model=EmbedImagesResponse)
async def embed_images(files: List[UploadFile] = File(...)):
    """
    Embed PDF page images into ColQwen multi-vector representations.
    
    Send one or more images (PNG/JPEG). Each image is treated as one PDF page.
    Returns multi-vector embeddings for late-interaction scoring.
    
    Typical workflow:
      1. Convert PDF pages to images (client-side via pdf2image)
      2. POST images to this endpoint
      3. Store returned embeddings in your vector DB
    """
    if _model is None:
        raise HTTPException(503, "Model not loaded")
    
    if not files:
        raise HTTPException(400, "No images provided")
    
    start = time.time()
    
    # Read images
    images = []
    for f in files:
        try:
            data = await f.read()
            img = Image.open(io.BytesIO(data)).convert("RGB")
            images.append(img)
        except Exception as e:
            raise HTTPException(400, f"Failed to read image '{f.filename}': {e}")
    
    # Embed images
    try:
        async with acquire_inference_slot("embed-images"):
            all_embeddings, n_patches = await run_in_threadpool(_embed_images_sync, images)
        
        elapsed_ms = (time.time() - start) * 1000
        
        return EmbedImagesResponse(
            num_images=len(images),
            embeddings=all_embeddings,
            embed_dim=all_embeddings[0][0].__len__() if all_embeddings else 0,
            n_patches_per_image=n_patches,
            inference_time_ms=round(elapsed_ms, 1),
        )
    
    except torch.cuda.OutOfMemoryError:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        raise HTTPException(503, "GPU out of memory. Try sending fewer/smaller images.")
    except Exception as e:
        logger.error(f"Embedding failed: {e}", exc_info=True)
        raise HTTPException(500, f"Embedding failed: {e}")


@app.post("/embed-query", response_model=EmbedQueryResponse)
async def embed_query(req: EmbedQueryRequest):
    """
    Embed a text query for late-interaction scoring against document embeddings.
    
    Use this to get the query embedding, then use /score to compare against
    pre-stored document embeddings.
    """
    if _model is None:
        raise HTTPException(503, "Model not loaded")
    
    if not req.query.strip():
        raise HTTPException(400, "Query cannot be empty")
    
    start = time.time()
    
    try:
        async with acquire_inference_slot("embed-query"):
            emb = await run_in_threadpool(_embed_query_sync, req.query)
        
        elapsed_ms = (time.time() - start) * 1000
        
        return EmbedQueryResponse(
            query=req.query,
            embedding=emb[0].tolist(),
            embed_dim=emb.shape[2],
            n_tokens=emb.shape[1],
            inference_time_ms=round(elapsed_ms, 1),
        )
    
    except Exception as e:
        logger.error(f"Query embedding failed: {e}", exc_info=True)
        raise HTTPException(500, f"Query embedding failed: {e}")


@app.post("/score", response_model=ScoreResponse)
async def score(req: ScoreRequest):
    """
    Score a query against multiple document embeddings using late interaction.
    
    This computes MaxSim (ColBERT-style) scores between the query
    and each document's multi-vector representation.
    """
    if _model is None:
        raise HTTPException(503, "Model not loaded")
    
    start = time.time()
    
    try:
        scores = await run_in_threadpool(_score_sync, req.query_embedding, req.doc_embeddings)
        
        elapsed_ms = (time.time() - start) * 1000
        
        return ScoreResponse(
            scores=scores,
            inference_time_ms=round(elapsed_ms, 1),
        )
    
    except Exception as e:
        logger.error(f"Scoring failed: {e}", exc_info=True)
        raise HTTPException(500, f"Scoring failed: {e}")


@app.post("/shutdown")
async def shutdown():
    """
    Graceful shutdown endpoint for local testing only.
    """
    if _managed_runtime:
        raise HTTPException(403, "Shutdown is disabled in managed SageMaker runtime mode")

    logger.info("Shutdown requested via API")
    
    # Schedule shutdown after response is sent
    import asyncio
    
    async def _shutdown():
        await asyncio.sleep(1)
        os.kill(os.getpid(), signal.SIGTERM)
    
    asyncio.create_task(_shutdown())
    
    return {"status": "shutting_down", "message": "Server will stop in ~1 second"}


# ─── Main ──────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="ColQwen Inference Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--model", default="vidore/colqwen2-v1.0", help="Model name")
    parser.add_argument(
        "--quantization",
        default="8bit",
        choices=["none", "4bit", "8bit"],
        help="Model quantization mode",
    )
    parser.add_argument("--no-quantize", action="store_true", help="Disable 8-bit quantization")
    parser.add_argument(
        "--max-concurrent-inferences",
        type=int,
        default=1,
        help="Maximum number of in-flight GPU requests to allow",
    )
    parser.add_argument(
        "--managed-runtime",
        action="store_true",
        help="Enable managed runtime behavior (SageMaker-safe mode)",
    )
    parser.add_argument("--workers", type=int, default=1, help="Number of workers (keep 1 for GPU)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    quantization = "none" if args.no_quantize else args.quantization
    
    # Set env vars for lifespan handler
    os.environ["COLQWEN_MODEL"] = args.model
    os.environ["COLQWEN_QUANTIZATION"] = quantization
    os.environ["COLQWEN_MAX_CONCURRENT_INFERENCES"] = str(args.max_concurrent_inferences)
    os.environ["SAGEMAKER_SERVICE_MODE"] = "true" if args.managed_runtime else "false"
    
    logger.info(f"Starting ColQwen server on {args.host}:{args.port}")
    logger.info(f"Model: {args.model}")
    logger.info(f"Quantization: {quantization}")
    logger.info(f"Max concurrent GPU requests: {args.max_concurrent_inferences}")
    logger.info(f"Managed runtime mode: {args.managed_runtime}")
    
    uvicorn.run(
        "server:app",
        host=args.host,
        port=args.port,
        workers=args.workers,  # Keep at 1   single GPU
        log_level="info",
    )
