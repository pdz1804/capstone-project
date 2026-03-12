"""
ColQwen Inference Server for AWS EC2 (g4dn.xlarge)

Serves the ColQwen2 model (8-bit quantized) as a FastAPI REST API
for the Multimodal RAG pipeline.

Endpoints:
  POST /embed-images   - Embed PDF page images → multi-vector embeddings
  POST /embed-query    - Embed a text query → query embedding  
  POST /score          - Score query embedding vs document embeddings
  GET  /health         - Health check with GPU/memory stats
  POST /shutdown       - Graceful shutdown (to stop EC2 and save costs)

Usage:
  python server.py                         # Start on 0.0.0.0:8000
  python server.py --port 8080             # Custom port
  python server.py --model vidore/colqwen2.5-v0.2  # Different model
"""

import os
import io
import sys
import time
import signal
import logging
import argparse
import subprocess
from pathlib import Path
from typing import List, Optional
from contextlib import asynccontextmanager

import torch
import numpy as np
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
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


def load_model(model_name: str = "vidore/colqwen2-v1.0", quantize_8bit: bool = True):
    """
    Load ColQwen model with 8-bit quantization.
    
    On g4dn.xlarge (T4 16GB):
      - 8-bit model: ~3.5GB VRAM → leaves ~12GB for batch processing
      - BF16 model:  ~6GB VRAM  → leaves ~10GB for batch processing
    """
    global _model, _processor, _model_name, _device, _load_time
    
    start = time.time()
    _model_name = model_name
    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    logger.info(f"Loading model: {model_name}")
    logger.info(f"Device: {_device}")
    logger.info(f"8-bit quantization: {quantize_8bit}")
    
    if _device.type == "cuda":
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_mem / (1024**3)
        logger.info(f"GPU: {gpu_name} ({gpu_mem:.1f} GB)")
    
    # Build model kwargs
    model_kwargs = {}
    
    if quantize_8bit and _device.type == "cuda":
        try:
            from transformers import BitsAndBytesConfig
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_8bit=True
            )
            logger.info("8-bit quantization enabled via BitsAndBytes")
        except ImportError:
            logger.warning("bitsandbytes not available, loading in bfloat16")
            model_kwargs["torch_dtype"] = torch.bfloat16
    else:
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
            "gpu_memory_total_gb": round(torch.cuda.get_device_properties(0).total_mem / (1024**3), 2),
            "gpu_memory_allocated_gb": round(torch.cuda.memory_allocated(0) / (1024**3), 2),
            "gpu_memory_reserved_gb": round(torch.cuda.memory_reserved(0) / (1024**3), 2),
            "gpu_memory_free_gb": round(
                (torch.cuda.get_device_properties(0).total_mem - torch.cuda.memory_reserved(0)) / (1024**3), 2
            ),
        })
        
        # Try to get GPU utilization via pynvml
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            stats["gpu_utilization_percent"] = util.gpu
            stats["gpu_memory_utilization_percent"] = util.memory
            pynvml.nvmlShutdown()
        except Exception:
            pass
    
    return stats


# ─── FastAPI App ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup."""
    model_name = os.environ.get("COLQWEN_MODEL", "vidore/colqwen2-v1.0")
    quantize = os.environ.get("COLQWEN_QUANTIZE_8BIT", "true").lower() == "true"
    load_model(model_name=model_name, quantize_8bit=quantize)
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


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check with GPU status."""
    return {
        "status": "healthy" if _model is not None else "model_not_loaded",
        "model": _model_name,
        "model_load_time_s": round(_load_time, 1) if _load_time else None,
        "gpu": get_gpu_stats(),
        "timestamp": time.time(),
    }


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
        with torch.no_grad():
            all_embeddings = []
            n_patches = []
            
            # Process one by one to avoid OOM on large batches
            for img in images:
                inputs = _processor.process_images([img]).to(_model.device)
                outputs = _model(**inputs)
                emb = outputs.cpu().numpy()  # [1, n_patches, embed_dim]
                all_embeddings.append(emb[0].tolist())
                n_patches.append(emb.shape[1])
        
        elapsed_ms = (time.time() - start) * 1000
        
        return EmbedImagesResponse(
            num_images=len(images),
            embeddings=all_embeddings,
            embed_dim=all_embeddings[0][0].__len__() if all_embeddings else 0,
            n_patches_per_image=n_patches,
            inference_time_ms=round(elapsed_ms, 1),
        )
    
    except torch.cuda.OutOfMemoryError:
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
        with torch.no_grad():
            inputs = _processor.process_queries([req.query]).to(_model.device)
            outputs = _model(**inputs)
            emb = outputs.cpu().numpy()  # [1, n_tokens, embed_dim]
        
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
        query_emb = torch.tensor(req.query_embedding, dtype=torch.float32)  # [n_q, d]
        
        scores = []
        for doc_emb_list in req.doc_embeddings:
            doc_emb = torch.tensor(doc_emb_list, dtype=torch.float32)  # [n_p, d]
            
            # MaxSim: for each query token, find max similarity across all doc patches
            # sim: [n_q, n_p]
            sim = torch.matmul(query_emb, doc_emb.T)
            # max over doc patches for each query token, then sum
            max_sim = sim.max(dim=1).values.sum().item()
            scores.append(max_sim)
        
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
    Graceful shutdown. Call this when you're done using the model.
    
    After the server shuts down, stop the EC2 instance to save costs:
      aws ec2 stop-instances --instance-ids <your-instance-id>
    
    Or use the stop_server.sh script which does both.
    """
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
    parser.add_argument("--no-quantize", action="store_true", help="Disable 8-bit quantization")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers (keep 1 for GPU)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    # Set env vars for lifespan handler
    os.environ["COLQWEN_MODEL"] = args.model
    os.environ["COLQWEN_QUANTIZE_8BIT"] = "false" if args.no_quantize else "true"
    
    logger.info(f"Starting ColQwen server on {args.host}:{args.port}")
    logger.info(f"Model: {args.model}")
    logger.info(f"Quantization: {'disabled' if args.no_quantize else '8-bit'}")
    
    uvicorn.run(
        "server:app",
        host=args.host,
        port=args.port,
        workers=args.workers,  # Keep at 1 — single GPU
        log_level="info",
    )
