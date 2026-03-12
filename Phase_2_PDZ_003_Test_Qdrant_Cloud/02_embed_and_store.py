"""
02_embed_and_store.py
======================
STEP 2: Generate ColPali multi-vector embeddings for images and
        store them as points in Qdrant Cloud.

WHAT YOU WILL LEARN:
  1. How to load the ColQwen2 model (same as Phase_2 — vidore/colqwen2-v1.0)
     with configurable dtype and optional 4-bit / 8-bit weight quantization
  2. Understanding the SHAPE of ColPali embeddings:
       image  →  [ num_patches × 128 ]   (a list of patch vectors)
       query  →  [ num_query_tokens × 128 ]
  3. How to convert torch tensors → Python lists for Qdrant storage
  4. How to upsert PointStructs with:
       - id      (unique integer per image)
       - vector  (the multi-vector embedding — dict of name → list-of-lists)
       - payload (metadata: filename, image size, timestamp, …)
  5. Batch upsert to avoid sending one HTTP request per image
  6. Timing every step to understand where latency comes from

COLPALI MULTI-VECTOR EXPLAINED:
  Traditional RAG:  each document → one flat vector  (e.g., 768 dims)
  ColPali / ColQwen: each image  → many patch vectors (e.g., 1030 × 128)

  Why does that help?
  A whole-image embedding loses spatial detail.
  ColPali keeps a separate 128-d embedding per visual patch, so at query time
  the MaxSim operator can match "is there a chart in the top-right corner?"
  against exactly the patches that came from that region.

RUN THIS SCRIPT:
  1. Add some .jpg / .png images to the  input/  folder
  2. python 02_embed_and_store.py
"""

import sys
import logging
from pathlib import Path
from typing import List, Dict, Any

import torch
from tqdm import tqdm

# Qdrant point model
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

# Our project files
sys.path.insert(0, str(Path(__file__).parent))
from config import cfg
from utils import setup_logging, Timer, LatencyTracker, load_images, log_tensor_stats

logger = setup_logging(logging.INFO)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: LOAD THE COLQWEN MODEL
# ─────────────────────────────────────────────────────────────────────────────

def load_colqwen_model():
    """
    Load ColQwen2 (vidore/colqwen2-v1.0) — the same model used in Phase_2.

    WHAT colpali-engine GIVES YOU:
      ColQwen2          — the neural network (Qwen2-VL backbone + 128-d projection head)
      ColQwen2Processor — handles image/text preprocessing:
                            • resizes and tokenises images
                            • tokenises query text with special ColPali tokens

    DTYPE OPTIONS (set in config.py :: cfg.torch_dtype):
      "bfloat16"  — 2 bytes/param.  Modern NVIDIA GPUs (Ampere+) run this natively.
                    Same as Phase_2 default.  NOT supported on all CPUs.
      "float16"   — 2 bytes/param.  Supported on most CUDA GPUs.
      "float32"   — 4 bytes/param.  Always works, even on CPU. Slower but safest.

    MODEL WEIGHT QUANTIZATION (optional, mirrors Phase_2):
      4-bit (load_in_4bit=True):  uses BitsAndBytes NF4 quantisation
          → model fits in ~4 GB VRAM instead of ~16 GB
          → requires `pip install bitsandbytes`
      8-bit (load_in_8bit=True):  LLM.int8() quantisation
          → ~8 GB VRAM
          → also requires bitsandbytes
      None: standard dtype loading (bfloat16 / float16 / float32)

    NOTE: if no GPU is available, the code automatically falls back to float32
    so it always works, even on a CPU-only machine (though it will be slow).
    """
    logger.info("─" * 55)
    logger.info("Loading ColQwen2 model …")
    logger.info(f"  Model : {cfg.colqwen_model}")
    logger.info(f"  dtype : {cfg.torch_dtype}")
    logger.info(f"  4-bit : {cfg.load_in_4bit}")
    logger.info(f"  8-bit : {cfg.load_in_8bit}")

    # ── Determine torch dtype ────────────────────────────────────────────────
    dtype_map = {
        "bfloat16": torch.bfloat16,
        "float16":  torch.float16,
        "float32":  torch.float32,
    }
    # On CPU, bfloat16 operations can be slow or unsupported on older PyTorch builds.
    # Switch to float32 automatically when no CUDA device is available.
    has_cuda = torch.cuda.is_available()
    if not has_cuda and cfg.torch_dtype != "float32":
        logger.warning(
            f"No CUDA GPU detected! Falling back to float32 "
            f"(requested: {cfg.torch_dtype})."
        )
        torch_dtype = torch.float32
    else:
        torch_dtype = dtype_map.get(cfg.torch_dtype, torch.bfloat16)

    logger.info(f"  Resolved torch dtype: {torch_dtype}  (CUDA={has_cuda})")

    # ── Build model kwargs ───────────────────────────────────────────────────
    model_kwargs: Dict[str, Any] = {}

    if cfg.load_in_4bit or cfg.load_in_8bit:
        # BitsAndBytes quantization for model weights
        # This reduces the GPU RAM needed to load ColQwen from ~16 GB → ~4–8 GB
        try:
            from transformers import BitsAndBytesConfig
            if cfg.load_in_4bit:
                logger.info("Using 4-bit NF4 weight quantisation (BitsAndBytes)")
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch_dtype,
                    bnb_4bit_use_double_quant=True,   # reduces quantisation error
                    bnb_4bit_quant_type="nf4",         # NF4 = best for LLM weights
                )
            else:
                logger.info("Using 8-bit LLM.int8() weight quantisation (BitsAndBytes)")
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_8bit=True,
                )
            # When using BitsAndBytes, device placement is handled internally.
            # Do NOT add device_map — it conflicts with bitsandbytes.
        except ImportError:
            logger.warning(
                "bitsandbytes is not installed — quantisation disabled.\n"
                "  Install with: pip install bitsandbytes"
            )
            model_kwargs["dtype"] = torch_dtype
    else:
        # Standard loading — 'dtype' is the current keyword (torch_dtype is deprecated)
        model_kwargs["dtype"] = torch_dtype

    # ── Load model and processor ─────────────────────────────────────────────
    logger.info("Downloading / loading model weights … (first run may take a while)")
    with Timer("model_load"):
        try:
            from colpali_engine.models import ColQwen2, ColQwen2Processor

            # Processor: tokenises images and text into tensors the model can read
            processor = ColQwen2Processor.from_pretrained(cfg.colqwen_model)

            # Model: returns multi-vector embeddings from images or text queries
            model = ColQwen2.from_pretrained(
                cfg.colqwen_model,
                **model_kwargs,
            ).eval()   # .eval() disables dropout — important for inference!

            # ── Move to GPU if available and NOT using BitsAndBytes quantization ──
            # WHY: from_pretrained() WITHOUT device_map always loads to CPU first,
            # even when CUDA is available. We must call .to("cuda") manually.
            # EXCEPTION: when using 4-bit/8-bit BitsAndBytes, the library handles
            # device placement internally — calling .to() on top of it will crash.
            if has_cuda and not (cfg.load_in_4bit or cfg.load_in_8bit):
                logger.info("Moving model to CUDA …")
                model = model.to("cuda")

        except ImportError as exc:
            raise ImportError(
                f"colpali_engine import failed: {exc}\n"
                "Install with: pip install colpali-engine==0.3.13"
            )

    # ── Report where the model ended up ─────────────────────────────────────
    try:
        device = next(model.parameters()).device
    except StopIteration:
        device = "unknown"
    logger.info(f"ColQwen2 ready on device: {device}")
    logger.info("─" * 55)

    return model, processor


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: EMBED A SINGLE IMAGE
# ─────────────────────────────────────────────────────────────────────────────

def embed_image(image, model, processor) -> torch.Tensor:
    """
    Generate a multi-vector embedding for one PIL image.

    ColQwen2 processes the image in two conceptual steps:
      1. Vision encoder (Qwen2-VL): converts the image into a sequence of
         patch feature vectors (like how a ViT chops an image into patches).
      2. Projection head: maps each patch feature to a 128-dimensional
         normalised embedding (the "ColPali token").

    OUTPUT SHAPE:  [1, num_patches, 128]
      • dim 0 = batch size (always 1 here since we embed one image at a time)
      • dim 1 = number of image patch tokens (varies with image resolution,
                typically 875–1030 for a standard slide/page image)
      • dim 2 = 128  (the projection dimension, same across all ColQwen models)

    WHAT IS RETURNED:
      A torch.Tensor on CPU.  We call .cpu() to move it off the GPU before
      queuing it for Qdrant upsert — this frees GPU memory sooner.

    Args:
        image     : PIL.Image (already converted to RGB)
        model     : Loaded ColQwen2 model
        processor : ColQwen2Processor
    """
    model_device = next(model.parameters()).device

    # processor.process_images() handles:
    #   - Resizing the image to the model's expected resolution
    #   - Converting to a tensor and applying normalisation
    #   - Creating the attention_mask template
    image_inputs = processor.process_images([image]).to(model_device)

    # torch.no_grad(): disables gradient tracking during inference
    #   This saves ~50 % memory and speeds up the forward pass.
    with torch.no_grad():
        embedding = model(**image_inputs)
        # Shape: [1, num_patches, 128]

    # Move result to CPU so we can free GPU memory immediately
    return embedding.cpu()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: BUILD QDRANT POINTS
# ─────────────────────────────────────────────────────────────────────────────

def build_point(
    image_record: Dict[str, Any],
    embedding: torch.Tensor,
    point_id: int,
) -> PointStruct:
    """
    Convert an image + its embedding into a Qdrant PointStruct.

    A PointStruct has three parts:
      id      — unique identifier (integer or UUID string).
                Qdrant uses this for lookups, updates, and deletes.
      vector  — a dict mapping vector-name → the actual embedding.
                For multi-vector we pass a list-of-lists  [[128 floats], …]
      payload — arbitrary JSON metadata you want to store alongside the vector.
                Qdrant can filter searches by payload fields.

    VECTOR FORMAT FOR MULTI-VECTOR:
      Qdrant expects  List[List[float]].
      embedding shape is [1, num_patches, 128] → we take [0] to drop the batch dim,
      then call .float().tolist() to convert:
          torch.Tensor [num_patches, 128]  →  [[f, f, …], [f, f, …], …]
                                              ↑ num_patches outer lists
                                                each with 128 floats

    Args:
        image_record : dict from load_images() with keys image/path/name/filename/index
        embedding    : [1, num_patches, 128] CPU tensor from embed_image()
        point_id     : integer ID to assign to this point in Qdrant
    """
    # ── Convert embedding tensor → Python list-of-lists ──────────────────────
    # [0]     : drop the batch dimension  → [num_patches, 128]
    # .float(): cast bfloat16/float16 → float32  (standard Python float)
    # .tolist(): convert to nested Python lists   [[f…], [f…], …]
    patch_vectors: List[List[float]] = embedding[0].float().tolist()

    # ── Build payload (metadata) ─────────────────────────────────────────────
    # Payload can contain any JSON-serialisable data.
    # You can later FILTER searches by payload fields, e.g.:
    #   "only return results where image_width > 1000"
    payload = {
        "filename":      image_record["filename"],
        "name":          image_record["name"],
        "path":          str(image_record["path"]),
        "num_patches":   len(patch_vectors),       # how many patch tokens
        "embed_dim":     len(patch_vectors[0]) if patch_vectors else 0,
        "image_width":   image_record["image"].width,
        "image_height":  image_record["image"].height,
        "original_index": image_record["index"],  # position in the input/ folder
    }

    return PointStruct(
        id=point_id,
        vector={
            # Key must match the vector name defined in create_collection()
            cfg.vector_name: patch_vectors
        },
        payload=payload,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: EMBED ALL IMAGES AND UPSERT TO QDRANT
# ─────────────────────────────────────────────────────────────────────────────

def embed_and_store(
    client: QdrantClient,
    model,
    processor,
    batch_size: int = 4,
) -> None:
    """
    Main function: embed all images in input/ and store them in Qdrant Cloud.

    FLOW:
      1. Load images from cfg.input_dir
      2. For each image:  embed → build PointStruct
      3. Every batch_size images: upsert the batch to Qdrant (one HTTP request)
      4. Log timing for every step

    BATCH UPSERT:
      Sending one HTTP request per image would be very slow over the network.
      Instead we accumulate `batch_size` points and send them together.
      Qdrant's upsert() accepts a list of PointStructs.

      Typical batch_size values:
        1–4   : safe for CPU / limited RAM
        8–16  : good for GPU
        32–64 : fine if images are small (< 500 patches each)

    Args:
        client     : Connected QdrantClient
        model      : Loaded ColQwen2 model
        processor  : Loaded ColQwen2Processor
        batch_size : Number of points per upsert call
    """
    tracker = LatencyTracker()

    # ── Load images ──────────────────────────────────────────────────────────
    logger.info(f"Loading images from: {cfg.input_dir}")
    with tracker.measure("load_images"):
        image_records = load_images(cfg.input_dir)

    if not image_records:
        logger.error(
            "No images found!\n"
            f"  Add .jpg or .png files to: {cfg.input_dir}\n"
            "  Then re-run this script."
        )
        return

    logger.info(f"Loaded {len(image_records)} image(s). Starting embedding …")

    # ── Embed images one at a time, flush to Qdrant every `batch_size` ───────
    batch: List[PointStruct] = []
    total_patches = 0          # track total patch count across all images
    upsert_count = 0           # total points successfully stored

    # tqdm wraps the list and renders a progress bar in the terminal
    for record in tqdm(image_records, desc="Embedding images", unit="img"):
        point_id = record["index"]  # use zero-based index as the Qdrant point ID

        # ── Embed one image ──────────────────────────────────────────────────
        with tracker.measure(f"embed_img_{record['filename']}"):
            embedding = embed_image(record["image"], model, processor)

        # Log tensor statistics to teach about embedding shape
        log_tensor_stats(
            embedding[0],        # [num_patches, 128]
            label=f"embedding({record['filename']})"
        )

        num_patches = embedding.shape[1]
        total_patches += num_patches
        logger.info(
            f"  [{point_id:03d}] {record['filename']:<30}  "
            f"{num_patches} patches × {embedding.shape[2]} dims"
        )

        # ── Build the Qdrant point ───────────────────────────────────────────
        point = build_point(record, embedding, point_id)
        batch.append(point)

        # ── Flush batch to Qdrant when it's full or on the last image ────────
        is_last_image = (record["index"] == image_records[-1]["index"])
        if len(batch) >= batch_size or is_last_image:
            logger.info(
                f"  Upserting batch of {len(batch)} point(s) to Qdrant Cloud …"
            )
            with tracker.measure(f"upsert_batch_{upsert_count}"):
                client.upsert(
                    collection_name=cfg.collection_name,
                    # wait=True:  block until Qdrant confirms the write to disk
                    # wait=False: fire-and-forget (faster, but no confirmation)
                    wait=True,
                    points=batch,
                )
            upsert_count += 1
            logger.info(f"  Batch {upsert_count} stored successfully.")
            batch = []   # reset for next batch

    # ── Final counts ─────────────────────────────────────────────────────────
    avg_patches = total_patches / len(image_records) if image_records else 0
    logger.info("─" * 55)
    logger.info(f"Done! Stored {len(image_records)} image(s) in '{cfg.collection_name}'")
    logger.info(f"  Total patches stored : {total_patches:,}")
    logger.info(f"  Average patches/image: {avg_patches:.0f}")

    # ── Print latency summary ────────────────────────────────────────────────
    tracker.print_summary()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: VERIFY STORAGE
# ─────────────────────────────────────────────────────────────────────────────

def verify_storage(client: QdrantClient) -> None:
    """
    Confirm that points were actually written by:
      1. Checking the collection's point count
      2. Fetching and displaying one stored point by ID

    This is a good sanity check after upserting — always verify your writes!
    """
    # ── Check point count ────────────────────────────────────────────────────
    info = client.get_collection(cfg.collection_name)
    logger.info(f"Collection '{cfg.collection_name}' now has {info.points_count} point(s)")

    if info.points_count == 0:
        logger.warning("No points found in the collection! Did the upsert succeed?")
        return

    # ── Fetch the first stored point ─────────────────────────────────────────
    # client.retrieve() fetches points by their IDs
    # with_vectors=True: include the actual embedding in the response
    # with_payload=True: include the metadata dict
    results = client.retrieve(
        collection_name=cfg.collection_name,
        ids=[0],                # fetch the point with id=0
        with_vectors=True,
        with_payload=True,
    )

    if not results:
        logger.warning("Could not retrieve point id=0 — it may not exist.")
        return

    point = results[0]
    vectors = point.vector or {}
    myvec = vectors.get(cfg.vector_name, [])

    print("\n" + "═" * 62)
    print("  STORED POINT VERIFICATION  (id=0)")
    print("═" * 62)
    print(f"  Point ID           : {point.id}")
    print(f"  Num patch vectors  : {len(myvec)}")
    print(f"  Each vector dim    : {len(myvec[0]) if myvec else '?'}")
    print(f"  Payload keys       : {list((point.payload or {}).keys())}")
    if point.payload:
        for k, v in point.payload.items():
            print(f"    {k:<22}: {v}")
    print("═" * 62 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "═" * 65)
    print("   STEP 2 — Embed Images with ColQwen + Store in Qdrant")
    print("═" * 65 + "\n")

    # ── Prerequisites check ──────────────────────────────────────────────────
    cfg.validate()

    # Make sure the collection exists (run 01_... first if needed)
    # cfg.build_client() automatically picks Docker or Cloud based on QDRANT_MODE
    client = cfg.build_client()
    existing = [c.name for c in client.get_collections().collections]
    if cfg.collection_name not in existing:
        logger.error(
            f"Collection '{cfg.collection_name}' does not exist!\n"
            "  Run  01_create_client_collection.py  first."
        )
        sys.exit(1)

    # ── Load the model (this takes a while on first run) ─────────────────────
    logger.info("=== SECTION 1: Loading ColQwen2 model ===")
    model, processor = load_colqwen_model()

    # ── Embed and store ──────────────────────────────────────────────────────
    logger.info("\n=== SECTION 2: Embedding + Storing images ===")
    embed_and_store(
        client=client,
        model=model,
        processor=processor,
        # Number of images per upsert batch:
        # Smaller  → less memory, more HTTP round-trips
        # Larger   → more memory, fewer HTTP round-trips (faster for many images)
        batch_size=4,
    )

    # ── Verify ───────────────────────────────────────────────────────────────
    logger.info("\n=== SECTION 3: Verifying stored data ===")
    verify_storage(client)

    print("✓  All images indexed!")
    print("   Next step → run  03_search_retrieve.py  to test search.\n")
