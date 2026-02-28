"""
Test script for the ColQwen inference server.

Tests all endpoints with synthetic data (no PDF needed).

Usage:
  python test_server.py                          # Test against localhost:8000
  python test_server.py --host 54.123.45.67      # Test against EC2 instance
  python test_server.py --host <ip> --port 8080  # Custom port
"""

import argparse
import json
import time
import sys
import io
import requests
import numpy as np
from PIL import Image


def make_url(host: str, port: int, path: str) -> str:
    return f"http://{host}:{port}{path}"


def test_health(host: str, port: int) -> bool:
    """Test /health endpoint."""
    print("\n" + "=" * 60)
    print("TEST: GET /health")
    print("=" * 60)
    
    url = make_url(host, port, "/health")
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        print(f"  Status: {r.status_code}")
        print(f"  Model: {data.get('model')}")
        print(f"  Load time: {data.get('model_load_time_s')}s")
        
        gpu = data.get("gpu", {})
        if gpu.get("cuda_available"):
            print(f"  GPU: {gpu.get('gpu_name')}")
            print(f"  VRAM Total: {gpu.get('gpu_memory_total_gb')} GB")
            print(f"  VRAM Allocated: {gpu.get('gpu_memory_allocated_gb')} GB")
            print(f"  VRAM Free: {gpu.get('gpu_memory_free_gb')} GB")
            if "gpu_utilization_percent" in gpu:
                print(f"  GPU Utilization: {gpu['gpu_utilization_percent']}%")
        else:
            print("  GPU: Not available (running on CPU)")
        
        assert data.get("status") == "healthy", f"Server not healthy: {data.get('status')}"
        print("  PASSED")
        return True
    except requests.ConnectionError:
        print(f"  FAILED: Cannot connect to {url}")
        print(f"  Make sure the server is running on {host}:{port}")
        return False
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def test_embed_query(host: str, port: int) -> dict:
    """Test /embed-query endpoint."""
    print("\n" + "=" * 60)
    print("TEST: POST /embed-query")
    print("=" * 60)
    
    url = make_url(host, port, "/embed-query")
    payload = {"query": "What is machine learning?"}
    
    try:
        r = requests.post(url, json=payload, timeout=60)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
        
        data = r.json()
        print(f"  Query: '{data['query']}'")
        print(f"  Embedding shape: [{data['n_tokens']}, {data['embed_dim']}]")
        print(f"  Inference time: {data['inference_time_ms']:.1f} ms")
        
        # Basic sanity checks
        assert data["n_tokens"] > 0, "n_tokens should be > 0"
        assert data["embed_dim"] > 0, "embed_dim should be > 0"
        assert len(data["embedding"]) == data["n_tokens"]
        assert len(data["embedding"][0]) == data["embed_dim"]
        
        print("  PASSED")
        return data
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def test_embed_images(host: str, port: int) -> dict:
    """Test /embed-images with a synthetic test image."""
    print("\n" + "=" * 60)
    print("TEST: POST /embed-images (synthetic image)")
    print("=" * 60)
    
    url = make_url(host, port, "/embed-images")
    
    # Create a synthetic "document page" image (white page with text-like patterns)
    img = Image.new("RGB", (800, 1100), color=(255, 255, 255))
    # Add some colored rectangles to simulate text/figures
    pixels = img.load()
    for y in range(100, 200):
        for x in range(50, 700):
            pixels[x, y] = (0, 0, 0)  # Simulate a text line
    for y in range(300, 600):
        for x in range(100, 500):
            pixels[x, y] = (50, 50, 200)  # Simulate a figure
    
    # Save to bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    
    try:
        files = [("files", ("test_page.png", buf, "image/png"))]
        r = requests.post(url, files=files, timeout=120)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
        
        data = r.json()
        print(f"  Num images: {data['num_images']}")
        print(f"  Embed dim: {data['embed_dim']}")
        print(f"  Patches per image: {data['n_patches_per_image']}")
        print(f"  Inference time: {data['inference_time_ms']:.1f} ms")
        
        # Sanity checks
        assert data["num_images"] == 1
        assert data["embed_dim"] > 0
        assert len(data["embeddings"]) == 1
        assert len(data["embeddings"][0]) == data["n_patches_per_image"][0]
        
        print("  PASSED")
        return data
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def test_score(host: str, port: int, query_data: dict, image_data: dict) -> dict:
    """Test /score endpoint using embeddings from previous tests."""
    print("\n" + "=" * 60)
    print("TEST: POST /score")
    print("=" * 60)
    
    if query_data is None or image_data is None:
        print("  SKIPPED: Need embeddings from previous tests")
        return None
    
    url = make_url(host, port, "/score")
    payload = {
        "query_embedding": query_data["embedding"],
        "doc_embeddings": image_data["embeddings"],
    }
    
    try:
        r = requests.post(url, json=payload, timeout=30)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
        
        data = r.json()
        print(f"  Scores: {data['scores']}")
        print(f"  Inference time: {data['inference_time_ms']:.1f} ms")
        
        assert len(data["scores"]) == 1, "Expected 1 score for 1 document"
        assert isinstance(data["scores"][0], float)
        
        print("  PASSED")
        return data
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def test_multiple_images(host: str, port: int) -> dict:
    """Test embedding multiple images in one request."""
    print("\n" + "=" * 60)
    print("TEST: POST /embed-images (multiple images)")
    print("=" * 60)
    
    url = make_url(host, port, "/embed-images")
    
    # Create 3 different synthetic pages
    colors = [(255, 200, 200), (200, 255, 200), (200, 200, 255)]
    files = []
    for i, bg_color in enumerate(colors):
        img = Image.new("RGB", (600, 800), color=bg_color)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        files.append(("files", (f"page_{i+1}.png", buf, "image/png")))
    
    try:
        r = requests.post(url, files=files, timeout=180)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
        
        data = r.json()
        print(f"  Num images: {data['num_images']}")
        print(f"  Embed dim: {data['embed_dim']}")
        print(f"  Patches per image: {data['n_patches_per_image']}")
        print(f"  Inference time: {data['inference_time_ms']:.1f} ms")
        
        assert data["num_images"] == 3
        assert len(data["embeddings"]) == 3
        
        print("  PASSED")
        return data
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def test_score_multiple_docs(host: str, port: int, query_data: dict, multi_image_data: dict):
    """Test scoring query against multiple documents."""
    print("\n" + "=" * 60)
    print("TEST: POST /score (query vs 3 documents)")
    print("=" * 60)
    
    if query_data is None or multi_image_data is None:
        print("  SKIPPED: Need embeddings from previous tests")
        return None
    
    url = make_url(host, port, "/score")
    payload = {
        "query_embedding": query_data["embedding"],
        "doc_embeddings": multi_image_data["embeddings"],
    }
    
    try:
        r = requests.post(url, json=payload, timeout=30)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
        
        data = r.json()
        print(f"  Scores: {[round(s, 4) for s in data['scores']]}")
        print(f"  Best page: page_{data['scores'].index(max(data['scores'])) + 1}")
        print(f"  Inference time: {data['inference_time_ms']:.1f} ms")
        
        assert len(data["scores"]) == 3
        
        print("  PASSED")
        return data
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Test ColQwen inference server")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    args = parser.parse_args()
    
    print(f"Testing ColQwen server at {args.host}:{args.port}")
    print(f"{'=' * 60}")
    
    results = {"passed": 0, "failed": 0, "skipped": 0}
    
    # Test 1: Health check
    if test_health(args.host, args.port):
        results["passed"] += 1
    else:
        results["failed"] += 1
        print("\nServer not reachable. Aborting remaining tests.")
        print_summary(results)
        sys.exit(1)
    
    # Test 2: Embed query
    query_data = test_embed_query(args.host, args.port)
    if query_data:
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 3: Embed single image
    image_data = test_embed_images(args.host, args.port)
    if image_data:
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 4: Score query vs document
    score_data = test_score(args.host, args.port, query_data, image_data)
    if score_data:
        results["passed"] += 1
    elif score_data is None and (query_data is None or image_data is None):
        results["skipped"] += 1
    else:
        results["failed"] += 1
    
    # Test 5: Embed multiple images
    multi_data = test_multiple_images(args.host, args.port)
    if multi_data:
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 6: Score query vs multiple docs
    multi_score = test_score_multiple_docs(args.host, args.port, query_data, multi_data)
    if multi_score:
        results["passed"] += 1
    elif multi_score is None and (query_data is None or multi_data is None):
        results["skipped"] += 1
    else:
        results["failed"] += 1
    
    print_summary(results)

    
def print_summary(results: dict):
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total = results["passed"] + results["failed"] + results["skipped"]
    print(f"  Total:   {total}")
    print(f"  Passed:  {results['passed']}")
    print(f"  Failed:  {results['failed']}")
    print(f"  Skipped: {results['skipped']}")
    
    if results["failed"] == 0:
        print("\n  ALL TESTS PASSED!")
    else:
        print(f"\n  {results['failed']} TEST(S) FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
