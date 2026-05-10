"""
03_search_retrieve.py
======================
STEP 3: Search Qdrant Cloud using ColPali query embeddings and inspect results.

WHAT YOU WILL LEARN:
  1. How a TEXT QUERY is encoded into a multi-vector by ColQwen2
       query → [ num_query_tokens × 128 ]
     (note: query produces fewer tokens than an image, typically 12–30)
  2. How IMAGE-TO-IMAGE search works (use any image as the query)
  3. How Qdrant computes MaxSim scoring at search time:
       score(Q, D) = Σ_i  max_j  dot(Q_i, D_j)
  4. How to measure and interpret end-to-end LATENCY:
       • query encoding time  (model inference)
       • Qdrant search time   (network + server-side MaxSim)
       • total time
  5. Reading and interpreting ScoredPoint results
  6. Optional: filtering results by payload metadata

SEARCH FLOW DIAGRAM:
                     ┌─────────────┐
  "show me a chart"  │ ColQwen2    │   query embedding [T × 128]
  ─────────────────► │ processor + │ ──────────────────────────►
                     │ model       │                            │
                     └─────────────┘                           ▼
                                                       ┌──────────────┐
                                                       │ Qdrant Cloud │
                                                       │  MaxSim      │
                                                       │  search      │
                                                       └──────┬───────┘
                     ┌─────────────────┐                      │
                     │ Top-k results   │ ◄────────────────────┘
                     │ [{id, score,    │
                     │   payload}, …]  │
                     └─────────────────┘

RUN THIS SCRIPT:
  python 03_search_retrieve.py
"""

import sys
import logging
from pathlib import Path
from typing import List, Any, Optional

import torch
from PIL import Image

from qdrant_client import QdrantClient
from qdrant_client.models import (
    # Filter: lets you restrict search to points matching metadata conditions
    Filter, FieldCondition, MatchValue,
)

sys.path.insert(0, str(Path(__file__).parent))
from config import cfg
from utils import (
    setup_logging, Timer, LatencyTracker,
    print_results, log_tensor_stats,
)

logger = setup_logging(logging.INFO)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: LOAD MODEL (same as 02, extracted for reuse)
# ─────────────────────────────────────────────────────────────────────────────

def load_colqwen_model():
    """
    Load ColQwen2 model and processor.
    Identical to the function in 02_embed_and_store.py   in a real project
    you would move this to a shared module (e.g., model_loader.py).
    """
    logger.info("Loading ColQwen2 for query encoding …")

    has_cuda = torch.cuda.is_available()
    dtype_map = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
    torch_dtype = dtype_map.get(cfg.torch_dtype, torch.bfloat16)
    if not has_cuda:
        torch_dtype = torch.float32
        logger.warning("No GPU   using float32 on CPU (will be slower)")

    with Timer("model_load"):
        try:
            from colpali_engine.models import ColQwen2, ColQwen2Processor
            processor = ColQwen2Processor.from_pretrained(cfg.colqwen_model)

            # Build kwargs the same as 02_embed_and_store so both scripts
            # respect the load_in_8bit / load_in_4bit settings from config.
            search_model_kwargs = {}
            if cfg.load_in_4bit or cfg.load_in_8bit:
                try:
                    from transformers import BitsAndBytesConfig
                    if cfg.load_in_4bit:
                        search_model_kwargs["quantization_config"] = BitsAndBytesConfig(
                            load_in_4bit=True,
                            bnb_4bit_compute_dtype=torch_dtype,
                            bnb_4bit_use_double_quant=True,
                            bnb_4bit_quant_type="nf4",
                        )
                    else:
                        search_model_kwargs["quantization_config"] = BitsAndBytesConfig(
                            load_in_8bit=True,
                        )
                except ImportError:
                    logger.warning("bitsandbytes not installed   quantisation disabled")
                    search_model_kwargs["dtype"] = torch_dtype
            else:
                search_model_kwargs["dtype"] = torch_dtype

            model = ColQwen2.from_pretrained(
                cfg.colqwen_model,
                **search_model_kwargs,
            ).eval()

            # Move to GPU only when NOT using BitsAndBytes quantisation.
            # BitsAndBytes places the model on CUDA internally; calling .to("cuda")
            # afterwards raises an error ("Cannot copy a quantized model").
            if has_cuda and not (cfg.load_in_4bit or cfg.load_in_8bit):
                logger.info("Moving model to CUDA …")
                model = model.to("cuda")

        except ImportError as exc:
            raise ImportError(
                f"colpali_engine import failed: {exc}\n"
                "Install with: pip install colpali-engine==0.3.13"
            )

    device = next(model.parameters()).device
    logger.info(f"Model ready on {device} (dtype={torch_dtype})")
    return model, processor


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: ENCODE A TEXT QUERY
# ─────────────────────────────────────────────────────────────────────────────

def encode_query(query_text: str, model, processor) -> List[List[float]]:
    """
    Convert a plain-text query string into a multi-vector embedding.

    ColQwen2 was trained with special query tokens:
      - The processor wraps the query in  "<query>" + text + "</query>"  markers
      - The model produces one 128-d vector per query token
      - Typical output: 12–30 query tokens (much fewer than image patches)

    OUTPUT FORMAT for Qdrant:
      List[List[float]]    e.g., [[q1_dim0, q1_dim1, …, q1_dim127], [q2_dim0, …], …]
                                   ↑ token 1                         ↑ token 2

    WHY FEWER QUERY TOKENS THAN IMAGE PATCHES?
      Images are rich   a full slide has ~1000 patches.
      A short query like "what is the accuracy?" has ~10 tokens.
      MaxSim is asymmetric: for each query token we find its best match among
      ALL document patches.  Even 10 query tokens can match rich visual content.

    Args:
        query_text : The question or search phrase
        model      : Loaded ColQwen2 model
        processor  : Loaded ColQwen2Processor

    Returns:
        List[List[float]] ready to pass to client.query_points(query=...)
    """
    model_device = next(model.parameters()).device

    # process_queries() tokenises the text with ColPali-specific query prompts
    query_inputs = processor.process_queries([query_text]).to(model_device)

    with torch.no_grad():
        query_embedding = model(**query_inputs)
        # Shape: [1, num_query_tokens, 128]

    log_tensor_stats(query_embedding[0], label=f"query_embedding('{query_text[:30]}')")
    logger.info(
        f"Query '{query_text[:50]}' → "
        f"{query_embedding.shape[1]} tokens × {query_embedding.shape[2]} dims"
    )

    # Convert: [1, num_tokens, 128] → List[List[float]]
    # [0] drops batch dimension, .float() ensures float32, .tolist() serialises
    return query_embedding[0].float().tolist()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: ENCODE AN IMAGE QUERY (image-to-image search)
# ─────────────────────────────────────────────────────────────────────────────

def encode_image_query(image_path: str, model, processor) -> List[List[float]]:
    """
    Use an image as the query   this is "image-to-image" similarity search.

    Instead of asking "show me a chart", you show Qdrant an example image
    and ask "find images that look like this".

    The encoding is identical to indexing an image (see 02_embed_and_store.py),
    because ColQwen uses the same patch embedding approach for both images and
    image-based queries.

    Args:
        image_path : Path to the query image file
        model      : Loaded ColQwen2 model
        processor  : Loaded ColQwen2Processor

    Returns:
        List[List[float]] ready for Qdrant search
    """
    img = Image.open(image_path).convert("RGB")
    logger.info(f"Image query: {image_path}  ({img.size[0]}×{img.size[1]} px)")

    model_device = next(model.parameters()).device
    image_inputs = processor.process_images([img]).to(model_device)

    with torch.no_grad():
        embedding = model(**image_inputs)

    logger.info(
        f"Image query embedding: {embedding.shape[1]} patches × {embedding.shape[2]} dims"
    )
    return embedding[0].float().tolist()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: SEARCH QDRANT
# ─────────────────────────────────────────────────────────────────────────────

def search(
    client: QdrantClient,
    query_vector: List[List[float]],
    query_label: str = "query",
    top_k: Optional[int] = None,
    score_threshold: Optional[float] = None,
    payload_filter: Optional[Filter] = None,
) -> List[Any]:
    """
    Execute a multi-vector MaxSim search on Qdrant Cloud.

    HOW QDRANT SCORES MULTI-VECTOR QUERIES:
      For each stored point D (an indexed image):
        score(Q, D) = Σ_{i=1}^{|Q|}  max_{j=1}^{|D|}  dot(Q_i, D_j)

      In English: for every query token Q_i, find the closest document patch D_j
      (by dot product), then sum all those best-matches.
      → This captures PARTIAL matches: a query about one corner of a slide
        still scores well even if the rest of the slide is irrelevant.

    QDRANT SEARCH INTERNALS (simplified):
      1. It loads a quantised copy of all stored vectors from RAM
      2. For each candidate point it applies the MaxSim operator
      3. It returns the top-k highest-scoring points

    SCORING NOTES:
      • Higher score = more similar (MaxSim sum increases with more matches)
      • Scores are NOT bounded to [0, 1]   they depend on the number of
        query tokens and document patches
      • For rough guidance: score > 8 is often a good match in practice

    PAYLOAD FILTER (optional):
      Qdrant can pre-filter points BEFORE scoring them, e.g.:
        "only search images where image_width > 1000"
      This is useful in production to narrow the search space.

    Args:
        client          : Connected QdrantClient
        query_vector    : List[List[float]] from encode_query() or encode_image_query()
        query_label     : Human-readable label for logging
        top_k           : Max results to return (default: cfg.top_k)
        score_threshold : Only return results with score ≥ this (default: cfg.score_threshold)
        payload_filter  : Optional Qdrant filter on payload fields

    Returns:
        List of ScoredPoint objects (qdrant_client.models.ScoredPoint)
    """
    top_k = top_k or cfg.top_k
    score_threshold = score_threshold if score_threshold is not None else cfg.score_threshold

    logger.info(f"Searching for: '{query_label}'  (top_k={top_k})")

    with Timer("qdrant_search_total") as search_timer:
        results = client.query_points(
            collection_name=cfg.collection_name,

            # The multi-vector query: List[List[float]]
            # Qdrant automatically uses MaxSim once it sees a list-of-lists
            query=query_vector,

            # Which named vector slot to search in
            using=cfg.vector_name,

            # Maximum number of results to return
            limit=top_k,

            # Optional minimum score filter
            score_threshold=score_threshold,

            # Optional payload filter (pass None to search everything)
            query_filter=payload_filter,

            # with_payload=True: include metadata in results (needed for display)
            with_payload=True,

            # with_vectors=False: don't return the raw vectors (saves bandwidth)
            with_vectors=False,
        ).points

    logger.info(
        f"Search completed: {len(results)} result(s) in "
        f"{search_timer.elapsed_ms:.2f} ms"
    )
    return results


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: DETAILED LATENCY BENCHMARK
# ─────────────────────────────────────────────────────────────────────────────

def benchmark_queries(
    queries: List[str],
    client: QdrantClient,
    model,
    processor,
) -> None:
    """
    Run a list of queries and print a comprehensive latency report.

    This function shows:
      1. Per-query timing breakdown (encoding vs network search)
      2. Multi-query summary (min, max, mean latency)
      3. Where the time is actually spent in the pipeline

    Understanding latency matters in production because:
      • Model inference (encoding) dominates on CPU (~200–500 ms per query)
      • Qdrant network search is fast (~5–50 ms even in the cloud)
      • GPU inference cuts encoding down to ~10–50 ms

    Args:
        queries   : List of text strings to search for
        client    : Connected QdrantClient
        model     : Loaded ColQwen2 model
        processor : Loaded ColQwen2Processor
    """
    all_encode_ms: List[float] = []
    all_search_ms: List[float] = []
    all_total_ms:  List[float] = []

    for i, query_text in enumerate(queries):
        tracker = LatencyTracker()

        print(f"\n{'─' * 65}")
        print(f"  Query {i + 1}/{len(queries)}: \"{query_text}\"")
        print(f"{'─' * 65}")

        # ── Encode the query ─────────────────────────────────────────────────
        with tracker.measure("1_query_encoding"):
            query_vec = encode_query(query_text, model, processor)

        logger.info(
            f"  Query tokens  : {len(query_vec)}  "
            f"(each {len(query_vec[0])} dims)"
        )

        # ── Send to Qdrant ───────────────────────────────────────────────────
        with tracker.measure("2_qdrant_network_search"):
            results = search(client, query_vec, query_label=query_text)

        # ── Display results ──────────────────────────────────────────────────
        with tracker.measure("3_result_formatting"):
            print_results(results, query=query_text)

        # ── Print per-query latency ──────────────────────────────────────────
        tracker.print_summary()

        # Accumulate for the overall benchmark summary
        enc_ms  = tracker.get("1_query_encoding")
        srch_ms = tracker.get("2_qdrant_network_search")
        tot_ms  = tracker.total_ms()

        all_encode_ms.append(enc_ms)
        all_search_ms.append(srch_ms)
        all_total_ms.append(tot_ms)

    # ── Multi-query latency summary ──────────────────────────────────────────
    if len(queries) > 1:
        _print_benchmark_summary(
            queries=queries,
            encode_times=all_encode_ms,
            search_times=all_search_ms,
            total_times=all_total_ms,
        )


def _print_benchmark_summary(
    queries: List[str],
    encode_times: List[float],
    search_times: List[float],
    total_times: List[float],
) -> None:
    """Print min / max / mean latency across all queries."""

    def stats(vals: List[float]):
        mn = min(vals)
        mx = max(vals)
        avg = sum(vals) / len(vals)
        return mn, mx, avg

    enc_mn,  enc_mx,  enc_avg  = stats(encode_times)
    srch_mn, srch_mx, srch_avg = stats(search_times)
    tot_mn,  tot_mx,  tot_avg  = stats(total_times)

    print("\n" + "═" * 72)
    print(f"{'  BENCHMARK SUMMARY   ' + str(len(queries)) + ' queries':^72}")
    print("═" * 72)
    print(f"  {'Stage':<28}  {'Min (ms)':>10}  {'Max (ms)':>10}  {'Avg (ms)':>10}")
    print("  " + "─" * 66)
    print(f"  {'query_encoding':<28}  {enc_mn:>10.1f}  {enc_mx:>10.1f}  {enc_avg:>10.1f}")
    print(f"  {'qdrant_network_search':<28}  {srch_mn:>10.1f}  {srch_mx:>10.1f}  {srch_avg:>10.1f}")
    print(f"  {'total_end_to_end':<28}  {tot_mn:>10.1f}  {tot_mx:>10.1f}  {tot_avg:>10.1f}")
    print("═" * 72)

    # Give human-readable interpretation
    print("\n  INTERPRETATION:")
    if enc_avg > 300:
        print("  • Encoding is slow (>300 ms avg)   consider running on a GPU.")
    else:
        print(f"  • Encoding avg {enc_avg:.0f} ms   {'GPU detected, good!' if torch.cuda.is_available() else 'CPU mode'}")

    if srch_avg < 100:
        print(f"  • Qdrant search avg {srch_avg:.0f} ms   fast! Network latency is low.")
    else:
        print(f"  • Qdrant search avg {srch_avg:.0f} ms   consider your region/tier.")

    print(f"  • Total avg: {tot_avg:.0f} ms  ({tot_avg / 1000:.2f} s per query)")
    print("═" * 72 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: PAYLOAD FILTER DEMO
# ─────────────────────────────────────────────────────────────────────────────

def demo_payload_filter(
    client: QdrantClient,
    model,
    processor,
    query_text: str,
) -> None:
    """
    Show how to pre-filter Qdrant points by payload metadata BEFORE scoring.

    Use case: you have 10,000 indexed images from 50 different lecture series.
    You want to search ONLY within "Lecture 3 slides"   pass a payload filter
    to restrict the MaxSim computation to that subset.

    This example filters by `image_width`   in a real project you'd assign
    meaningful metadata like "lecture_id", "course", "date", etc.

    HOW FILTERS WORK IN QDRANT:
      Filter(must=[FieldCondition(key=..., match=MatchValue(value=...))])
          ↑ "must" means ALL conditions must match (AND logic)
          ↑ "should" = any condition matches (OR logic)
          ↑ "must_not" = exclude matches

    Qdrant checks the filter FIRST (very fast   index-based),
    then runs MaxSim ONLY on the matching subset.
    """
    logger.info("─" * 55)
    logger.info("Demo: payload-filtered search")

    # First, check what image widths we have stored
    # (in your real project, replace with a meaningful field like "lecture_id")
    scroll_results, _ = client.scroll(
        collection_name=cfg.collection_name,
        limit=5,
        with_payload=True,
        with_vectors=False,
    )

    if not scroll_results:
        logger.warning("No points in collection   skipping filter demo.")
        return

    # Pick a width from the first stored point to use as a filter example
    example_width = scroll_results[0].payload.get("image_width")
    example_filename = scroll_results[0].payload.get("filename", "")
    logger.info(f"Filter example: image_width = {example_width}  ({example_filename})")

    if example_width is None:
        logger.warning("image_width not in payload   skipping filter demo.")
        return

    # Build a payload filter: only search points where image_width == example_width
    payload_filter = Filter(
        must=[
            FieldCondition(
                key="image_width",
                match=MatchValue(value=example_width),
            )
        ]
    )

    with Timer("filtered_search"):
        query_vec = encode_query(query_text, model, processor)
        filtered_results = search(
            client,
            query_vec,
            query_label=f"{query_text} [filter: width={example_width}]",
            payload_filter=payload_filter,
        )

    print_results(
        filtered_results,
        query=f"{query_text}  [filtered: image_width={example_width}]",
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "═" * 65)
    print("   STEP 3   Search Qdrant Cloud with ColPali Queries")
    print("═" * 65 + "\n")

    cfg.validate()

    # ── Connect to Qdrant (Docker or Cloud, based on QDRANT_MODE in .env) ────
    with Timer("qdrant_connect"):
        client = cfg.build_client()

    # Check that the collection exists and has data
    info = client.get_collection(cfg.collection_name)
    logger.info(
        f"Collection '{cfg.collection_name}': "
        f"{info.points_count} point(s) stored"
    )
    if info.points_count == 0:
        logger.error(
            "Collection is empty! Run 02_embed_and_store.py first to index your images."
        )
        sys.exit(1)

    # ── Load the model for query encoding ────────────────────────────────────
    logger.info("\n=== Loading model for query encoding ===")
    model, processor = load_colqwen_model()

    # ─────────────────────────────────────────────────────────────────────────
    # DEMO 1: Run a list of text queries and measure latency
    # Customise these queries to match the content of your input/ images!
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("\n=== DEMO 1: Text query benchmark ===")

    sample_queries = [
        "Introduction about LLM",          # visual query
        "Diagram of VideoRAG framework", # text-heavy slide query
        "what is multimodal context encoding?",
    ]

    benchmark_queries(
        queries=sample_queries,
        client=client,
        model=model,
        processor=processor,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # DEMO 2: Single search with full timing trace
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("\n=== DEMO 2: Single query with detailed timing ===")

    custom_query = "find the most visually complex image"
    tracker = LatencyTracker()

    with tracker.measure("step_a_encode_query"):
        qvec = encode_query(custom_query, model, processor)

    with tracker.measure("step_b_qdrant_search"):
        top_results = search(client, qvec, query_label=custom_query, top_k=cfg.top_k)

    with tracker.measure("step_c_display"):
        print_results(top_results, query=custom_query)

    tracker.print_summary()

    # ─────────────────────────────────────────────────────────────────────────
    # DEMO 3: Image-to-image search (use an image from input/ as the query)
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("\n=== DEMO 3: Image-to-image search ===")

    image_files = sorted(cfg.input_dir.glob("*.*"))
    image_files = [
        p for p in image_files
        if p.suffix.lower() in cfg.image_extensions
    ]

    if len(image_files) >= 2:
        # Use the second image as a query to find similar images
        query_image_path = image_files[1]
        logger.info(f"Using '{query_image_path.name}' as the query image")

        tracker2 = LatencyTracker()

        with tracker2.measure("encode_image_query"):
            img_qvec = encode_image_query(str(query_image_path), model, processor)

        with tracker2.measure("qdrant_search"):
            img_results = search(
                client,
                img_qvec,
                query_label=f"image:{query_image_path.name}",
            )

        print_results(img_results, query=f"[image] {query_image_path.name}")
        tracker2.print_summary()
    else:
        logger.info("Need at least 2 images in input/ for image-to-image demo   skipping.")

    # ─────────────────────────────────────────────────────────────────────────
    # DEMO 4: Payload-filtered search
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("\n=== DEMO 4: Payload-filtered search ===")
    demo_payload_filter(
        client=client,
        model=model,
        processor=processor,
        query_text="interesting visual",
    )

    print("\n✓  All search demos complete!\n")
    print("─" * 65)
    print(" SUMMARY OF WHAT YOU LEARNED:")
    print("  1. Text queries → multi-vector (ColQwen query tokens)")
    print("  2. Image queries → same multi-vector (ColQwen image patches)")
    print("  3. MaxSim scoring: best patch per query token, summed")
    print("  4. Qdrant search is fast (~10–50 ms after encoding)")
    print("  5. Encoding dominates latency on CPU, GPU makes it ~10x faster")
    print("  6. Payload filters let you restrict search to a subset of images")
    print("─" * 65 + "\n")
