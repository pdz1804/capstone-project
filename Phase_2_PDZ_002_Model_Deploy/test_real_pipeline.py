"""
Real end-to-end ColQwen pipeline test against the live SageMaker endpoint.

Exercises the full retrieval flow:
  Step 1   embed-images  : encode actual page images into multi-vector representations
  Step 2   embed-query   : encode a natural-language question
  Step 3   score         : rank each page by relevance to the query

Usage examples
--------------
# Use default sample pages from Phase_2_PDZ_003 and a default query:
  python test_real_pipeline.py

# Supply your own images and query:
  python test_real_pipeline.py \
      --images path/to/page1.png path/to/page2.png \
      --query "What is the main conclusion of this document?"

# Override endpoint / region:
  python test_real_pipeline.py --endpoint-name phase2-colqwen-rt --region us-west-2
"""

import argparse
import base64
import json
import time
from pathlib import Path

import boto3  # type: ignore[import-not-found]

# ── Default sample images (relative to workspace root) ──────────────────────
_WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_IMAGE_DIR = _WORKSPACE_ROOT / "Phase_2_PDZ_003_Test_Qdrant_Cloud" / "input"
_DEFAULT_IMAGES = sorted(_DEFAULT_IMAGE_DIR.glob("page_*.png"))

_DEFAULT_QUERY = "What algorithm or method is being explained on this page?"


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_image_as_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def invoke(runtime, endpoint_name: str, payload: dict) -> dict:
    started = time.perf_counter()
    response = runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="application/json",
        Body=json.dumps(payload).encode("utf-8"),
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    body = response["Body"].read().decode("utf-8")
    return {
        "status": response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0),
        "elapsed_ms": elapsed_ms,
        "body": json.loads(body),
    }


# ── Pipeline steps ────────────────────────────────────────────────────────────

def step_health_check(runtime, endpoint_name: str) -> bool:
    """Call operation=health through /invocations to confirm GPU is active."""
    payload = {"operation": "health"}
    try:
        result = invoke(runtime, endpoint_name, payload)
    except Exception as exc:
        # Older deployed images may not yet implement operation=health.
        if "Unsupported operation: health" in str(exc):
            print("[Pre-flight] Health operation is not available in the current endpoint image.")
            print("           Continuing pipeline test without GPU health details.")
            return False
        raise

    if result["status"] != 200:
        detail = result.get("body", {}).get("detail", "") if isinstance(result.get("body"), dict) else ""
        if "Unsupported operation: health" in str(detail):
            print("[Pre-flight] Health operation is not available in the current endpoint image.")
            print("           Continuing pipeline test without GPU health details.")
            return False
        raise RuntimeError(f"Health check failed: {result}")

    body = result["body"]
    gpu = body.get("gpu", {})
    print("[Pre-flight] Endpoint health")
    print(f"  model       : {body.get('model')}")
    print(f"  quantization: {body.get('quantization')}")
    print(f"  load_time_s : {body.get('model_load_time_s')}")
    device = gpu.get("device", "unknown")
    cuda_ok = gpu.get("cuda_available", False)
    if cuda_ok:
        print(f"  GPU         : {gpu.get('gpu_name')}  ({gpu.get('gpu_memory_total_gb')} GB)")
        print(f"  VRAM used   : {gpu.get('gpu_memory_allocated_gb')} GB allocated  /  "
              f"{gpu.get('gpu_memory_reserved_gb')} GB reserved  /  "
              f"{gpu.get('gpu_memory_free_gb')} GB free")
        util = gpu.get("gpu_utilization_percent")
        if util is not None:
            print(f"  GPU util    : {util}%")
    else:
        print(f"  WARNING: CUDA not available   model is running on {device} (CPU mode!)")

    return True


def step_embed_and_score_per_image(
    runtime,
    endpoint_name: str,
    image_paths: list[Path],
    query_embedding: list[list[float]],
) -> tuple[list[tuple[float, Path]], list[int], int, float, float]:
    """
    Process one image at a time: embed-image -> score immediately.

    This keeps client RAM low by avoiding storage of all document embeddings.
    """
    print(f"\n[Step 2/3] embed-images + score   processing {len(image_paths)} image(s) ...")
    scored_items: list[tuple[float, Path]] = []
    n_patches_per_image: list[int] = []
    embed_dim = 0
    total_embed_ms = 0.0
    total_score_ms = 0.0

    for i, path in enumerate(image_paths, start=1):
        size_kb = path.stat().st_size / 1024
        print(f"  [{i}/{len(image_paths)}] {path.name}  ({size_kb:.0f} KB) ...", end="", flush=True)

        embed_payload = {
            "operation": "embed-images",
            "images_base64": [load_image_as_base64(path)],
        }
        embed_result = invoke(runtime, endpoint_name, embed_payload)
        if embed_result["status"] != 200:
            raise RuntimeError(f"embed-images failed on {path.name}: {embed_result}")

        embed_body = embed_result["body"]
        doc_embedding = embed_body["embeddings"][0]
        patches = int(embed_body["n_patches_per_image"][0])
        embed_dim = int(embed_body["embed_dim"])
        total_embed_ms += embed_result["elapsed_ms"]

        score_payload = {
            "operation": "score",
            "query_embedding": query_embedding,
            "doc_embeddings": [doc_embedding],
        }
        score_result = invoke(runtime, endpoint_name, score_payload)
        if score_result["status"] != 200:
            raise RuntimeError(f"score failed on {path.name}: {score_result}")

        score_body = score_result["body"]
        score = float(score_body["scores"][0])
        total_score_ms += score_result["elapsed_ms"]

        scored_items.append((score, path))
        n_patches_per_image.append(patches)

        print(
            f"  embed={embed_result['elapsed_ms']:.0f} ms  "
            f"score={score_result['elapsed_ms']:.0f} ms  "
            f"(patches={patches}, score={score:.3f})"
        )

    print(f"  ✓ {len(image_paths)} images processed")
    print(f"    embed_dim     : {embed_dim}")
    print(f"    patches/image : {n_patches_per_image}")
    print(f"    embed total   : {total_embed_ms:.0f} ms")
    print(f"    score total   : {total_score_ms:.0f} ms")

    return scored_items, n_patches_per_image, embed_dim, total_embed_ms, total_score_ms


def step_embed_query(runtime, endpoint_name: str, query: str) -> dict:
    print(f"\n[Step 1/3] embed-query   '{query[:80]}' ...")
    payload = {
        "operation": "embed-query",
        "query": query,
    }
    result = invoke(runtime, endpoint_name, payload)
    if result["status"] != 200:
        raise RuntimeError(f"embed-query failed: {result}")

    body = result["body"]
    print(f"  ✓ Query embedded in {result['elapsed_ms']:.0f} ms")
    print(f"    n_tokens  : {body['n_tokens']}")
    print(f"    embed_dim : {body['embed_dim']}")
    return body


def print_ranked_results(scored_items: list[tuple[float, Path]]) -> None:
    ranked = sorted(
        scored_items,
        key=lambda x: x[0],
        reverse=True,
    )
    print("\n[Step 3/3] ranking")
    print("\n──────────────────────────────────────────────────")
    print("Ranked retrieval results (highest relevance first)")
    print("──────────────────────────────────────────────────")
    for rank, (score, path) in enumerate(ranked, start=1):
        print(f"  #{rank:>2}  score={score:>8.3f}  {path.name}")
    print("──────────────────────────────────────────────────")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Real ColQwen pipeline test via SageMaker")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--endpoint-name", default="phase2-colqwen-rt")
    parser.add_argument(
        "--images",
        nargs="+",
        help="Paths to image files (PNG/JPEG).  Defaults to Phase_2_PDZ_003 sample pages.",
    )
    parser.add_argument(
        "--query",
        default=_DEFAULT_QUERY,
        help="Natural-language retrieval query.",
    )
    args = parser.parse_args()

    if args.images:
        image_paths = [Path(p) for p in args.images]
    else:
        image_paths = list(_DEFAULT_IMAGES)
        if not image_paths:
            raise FileNotFoundError(
                f"No sample images found in {_DEFAULT_IMAGE_DIR}. "
                "Pass --images explicitly."
            )

    # Validate all paths exist before sending anything
    missing = [p for p in image_paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Image files not found: {[str(p) for p in missing]}")

    runtime = boto3.client("sagemaker-runtime", region_name=args.region)

    print("=" * 60)
    print(f"Endpoint : {args.endpoint_name}  ({args.region})")
    print(f"Images   : {len(image_paths)} file(s)")
    print(f"Query    : {args.query}")
    print("=" * 60)

    t_start = time.perf_counter()

    step_health_check(runtime, args.endpoint_name)
    query_body = step_embed_query(runtime, args.endpoint_name, args.query)
    scored_items, _, _, _, _ = step_embed_and_score_per_image(
        runtime,
        args.endpoint_name,
        image_paths,
        query_body["embedding"],
    )

    total_ms = (time.perf_counter() - t_start) * 1000
    print(f"\nTotal pipeline time: {total_ms:.0f} ms")

    print_ranked_results(scored_items)
    print("\nReal pipeline test passed ✓")


if __name__ == "__main__":
    main()
