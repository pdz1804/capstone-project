"""
End-to-end test with a real PDF file.

Converts PDF pages to images, sends them to the ColQwen server,
then queries and retrieves the most relevant pages.

Usage:
  python test_with_pdf.py --pdf /path/to/document.pdf
  python test_with_pdf.py --pdf /path/to/document.pdf --host <ec2-ip>
  python test_with_pdf.py --pdf /path/to/document.pdf --query "neural networks"
"""

import argparse
import json
import io
import time
import sys
import requests
from pathlib import Path

try:
    from pdf2image import convert_from_path
except ImportError:
    print("pdf2image not installed. Install with: pip install pdf2image")
    print("Also needs poppler: sudo apt-get install poppler-utils")
    sys.exit(1)

from PIL import Image


def make_url(host: str, port: int, path: str) -> str:
    return f"http://{host}:{port}{path}"


def pdf_to_images(pdf_path: str, dpi: int = 150) -> list:
    """Convert PDF pages to PIL images."""
    print(f"Converting PDF to images (DPI={dpi})...")
    images = convert_from_path(pdf_path, dpi=dpi)
    print(f"  Converted {len(images)} pages")
    return images


def embed_pages(host: str, port: int, images: list, batch_size: int = 5) -> list:
    """Send page images to the server for embedding."""
    url = make_url(host, port, "/embed-images")
    all_embeddings = []
    all_n_patches = []
    
    total_time = 0
    
    # Process in batches to avoid huge payloads
    for batch_start in range(0, len(images), batch_size):
        batch_end = min(batch_start + batch_size, len(images))
        batch_images = images[batch_start:batch_end]
        
        print(f"  Embedding pages {batch_start + 1}-{batch_end}...", end=" ", flush=True)
        
        files = []
        for i, img in enumerate(batch_images):
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            files.append(("files", (f"page_{batch_start + i + 1}.png", buf, "image/png")))
        
        r = requests.post(url, files=files, timeout=300)
        if r.status_code != 200:
            print(f"FAILED: HTTP {r.status_code}: {r.text}")
            continue
        
        data = r.json()
        all_embeddings.extend(data["embeddings"])
        all_n_patches.extend(data["n_patches_per_image"])
        total_time += data["inference_time_ms"]
        
        print(f"{data['inference_time_ms']:.0f} ms")
    
    print(f"  Total embedding time: {total_time:.0f} ms for {len(all_embeddings)} pages")
    return all_embeddings, all_n_patches


def query_pages(host: str, port: int, query: str, doc_embeddings: list) -> list:
    """Embed a query and score it against all page embeddings."""
    
    # Step 1: Embed the query
    print(f"\nQuerying: '{query}'")
    
    url_query = make_url(host, port, "/embed-query")
    r = requests.post(url_query, json={"query": query}, timeout=60)
    assert r.status_code == 200, f"Query embed failed: {r.text}"
    query_data = r.json()
    print(f"  Query embedded in {query_data['inference_time_ms']:.1f} ms")
    
    # Step 2: Score against all pages
    url_score = make_url(host, port, "/score")
    payload = {
        "query_embedding": query_data["embedding"],
        "doc_embeddings": doc_embeddings,
    }
    r = requests.post(url_score, json=payload, timeout=60)
    assert r.status_code == 200, f"Scoring failed: {r.text}"
    score_data = r.json()
    
    # Step 3: Rank pages
    scores = score_data["scores"]
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    
    print(f"  Scoring done in {score_data['inference_time_ms']:.1f} ms")
    print(f"\n  Top 5 most relevant pages:")
    for rank, (page_idx, score) in enumerate(ranked[:5], 1):
        print(f"    #{rank}: Page {page_idx + 1} (score: {score:.4f})")
    
    return ranked


def main():
    parser = argparse.ArgumentParser(description="Test ColQwen with a real PDF")
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--query", default="What is the main topic of this document?",
                        help="Search query")
    parser.add_argument("--dpi", type=int, default=150, help="PDF to image DPI")
    parser.add_argument("--batch-size", type=int, default=5, help="Batch size for embedding")
    parser.add_argument("--save-embeddings", action="store_true",
                        help="Save embeddings to JSON file for reuse")
    args = parser.parse_args()
    
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    print(f"PDF: {pdf_path}")
    print(f"Server: {args.host}:{args.port}")
    print(f"Query: '{args.query}'")
    print("=" * 60)
    
    # Check server health
    try:
        r = requests.get(make_url(args.host, args.port, "/health"), timeout=10)
        health = r.json()
        print(f"Server status: {health['status']}")
        print(f"Model: {health['model']}")
    except Exception as e:
        print(f"Cannot reach server: {e}")
        sys.exit(1)
    
    # Convert PDF to images
    images = pdf_to_images(str(pdf_path), dpi=args.dpi)
    
    # Embed all pages
    print(f"\nEmbedding {len(images)} pages...")
    embeddings, n_patches = embed_pages(args.host, args.port, images, args.batch_size)
    
    if not embeddings:
        print("No embeddings generated. Check server logs.")
        sys.exit(1)
    
    # Optionally save embeddings
    if args.save_embeddings:
        out_path = pdf_path.with_suffix(".embeddings.json")
        with open(out_path, "w") as f:
            json.dump({
                "source": str(pdf_path),
                "num_pages": len(embeddings),
                "n_patches_per_page": n_patches,
                "embeddings": embeddings,
            }, f)
        print(f"\nEmbeddings saved to: {out_path}")
    
    # Query
    ranked = query_pages(args.host, args.port, args.query, embeddings)
    
    print("\nDone!")


if __name__ == "__main__":
    main()
