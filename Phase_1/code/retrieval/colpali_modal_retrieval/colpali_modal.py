"""
Modal GPU deployment for ColPali vs OCR Retrieval System
Simple CLI interface - no web API, just run queries on GPU
"""

import modal
import os
import json
from pathlib import Path

# Create Modal app
app = modal.App("colpali-ocr-retrieval")

# Get the directory where this script is located
script_dir = Path(__file__).parent

# Define the image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "tesseract-ocr",
        "tesseract-ocr-vie",
        "poppler-utils",
        "build-essential"
    )
    .pip_install(
        "pillow",
        "pytesseract",
        "pdf2image",
        "rank_bm25",
        "tqdm",
        "numpy",
        "scikit-learn",
        "torch",
        "transformers",
        "bitsandbytes",
        "sentencepiece",
        "accelerate",
        "sentence-transformers",
        "openai",
        "opencv-python-headless",
        "colpali-engine"
    )
    # Add the retriever script to the image
    .add_local_file(
        script_dir / "colpali_ocr_retriever.py",
        "/root/colpali_ocr_retriever.py"
    )
)

# Create persistent volumes for storing indexes and PDFs
pdf_volume = modal.Volume.from_name("colpali-pdfs", create_if_missing=True)
index_volume = modal.Volume.from_name("colpali-indexes", create_if_missing=True)

# Mount paths
PDF_MOUNT_PATH = "/data/pdfs"
INDEX_MOUNT_PATH = "/data/indexes"


@app.function(
    image=image,
    gpu="A10G",  # Use A10G GPU for faster processing
    volumes={
        PDF_MOUNT_PATH: pdf_volume,
        INDEX_MOUNT_PATH: index_volume
    },
    timeout=3600,  # 1 hour timeout
    secrets=[modal.Secret.from_name("openai-secret")]
)
def build_indexes(force_rebuild: bool = False):
    """
    Build or rebuild all indexes on GPU
    This should be called once after uploading PDFs
    """
    import sys
    import logging
    import torch
    import json
    import pickle
    from pathlib import Path
    
    # Import from the main script
    sys.path.append("/root")
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Import pipeline classes
    from colpali_ocr_retriever import (
        SlideOCR,
        PipelineA_BM25,
        PipelineB_ColQwen,
        PipelineC_MiniLM,
        Config
    )
    
    # Setup paths
    pdf_dir = Path(PDF_MOUNT_PATH)
    index_dir = Path(INDEX_MOUNT_PATH)
    
    config = Config(str(pdf_dir), str(index_dir), os.getenv("OPENAI_API_KEY"))
    
    logging.info(f"Device: {config.DEVICE}")
    logging.info(f"PDF Directory: {pdf_dir}")
    logging.info(f"Index Directory: {index_dir}")
    
    # Process OCR
    ocr_data = []
    if force_rebuild or not config.OCR_DATA_PATH.exists():
        logging.info("Starting OCR process...")
        ocr_processor = SlideOCR()
        # Use rglob to find PDFs recursively (in case they are in subdirectories in the volume)
        pdf_files = list(pdf_dir.rglob("*.pdf"))
        
        if not pdf_files:
            # List directory to help debugging
            try:
                files = [str(f) for f in pdf_dir.rglob("*")]
                logging.info(f"Files in {pdf_dir}: {files}")
            except Exception as e:
                logging.error(f"Could not list files: {e}")
            return {"error": f"No PDF files found in {pdf_dir}"}
        
        logging.info(f"Found {len(pdf_files)} PDF files.")
        ocr_data = ocr_processor.process_slides(pdf_files)
        
        # Save OCR data
        with open(config.OCR_DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(ocr_data, f, indent=2, ensure_ascii=False)
        
        logging.info(f"OCR complete! Processed {len(ocr_data)} pages.")
    else:
        with open(config.OCR_DATA_PATH, 'r', encoding='utf-8') as f:
            ocr_data = json.load(f)
        logging.info(f"Loaded {len(ocr_data)} pages from existing OCR data.")
    
    # Build indexes
    logging.info("Building indexes...")
    p_a = PipelineA_BM25(config.BM25_INDEX_PATH)
    p_b = PipelineB_ColQwen(config.COLQWEN_INDEX_PATH, config.DEVICE)
    p_c = PipelineC_MiniLM(config.MINILM_INDEX_PATH, config.DEVICE)
    
    p_a.build_index(ocr_data, force_rebuild=force_rebuild)
    p_b.build_index(config.PDF_DIR, force_rebuild=force_rebuild)
    p_c.build_index(ocr_data, force_rebuild=force_rebuild)
    
    # Commit volumes to persist changes
    pdf_volume.commit()
    index_volume.commit()
    
    return {
        "status": "success",
        "ocr_pages": len(ocr_data),
        "message": "All indexes built successfully"
    }


@app.function(
    image=image,
    gpu="T4",
    volumes={
        PDF_MOUNT_PATH: pdf_volume,
        INDEX_MOUNT_PATH: index_volume
    },
    timeout=300,
    secrets=[modal.Secret.from_name("openai-secret")]
)
def run_query(query: str, top_k: int = 5):
    """
    Run a query using all three pipelines and return results with LLM summaries
    """
    import sys
    import logging
    import torch
    import json
    import pickle
    from pathlib import Path
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Import from the main script
    from colpali_ocr_retriever import (
        PipelineA_BM25,
        PipelineB_ColQwen,
        PipelineC_MiniLM,
        Config,
        get_llm_answer
    )
    from openai import OpenAI
    
    # Setup paths
    pdf_dir = Path(PDF_MOUNT_PATH)
    index_dir = Path(INDEX_MOUNT_PATH)
    
    config = Config(str(pdf_dir), str(index_dir), os.getenv("OPENAI_API_KEY"))
    
    logging.info(f"Running query: {query}")
    logging.info(f"Device: {config.DEVICE}")
    
    # Load OCR data
    if not config.OCR_DATA_PATH.exists():
        return {"error": "OCR data not found. Please run build_indexes first."}
    
    with open(config.OCR_DATA_PATH, 'r', encoding='utf-8') as f:
        ocr_data = json.load(f)
    
    # Initialize pipelines
    p_a = PipelineA_BM25(config.BM25_INDEX_PATH)
    p_b = PipelineB_ColQwen(config.COLQWEN_INDEX_PATH, config.DEVICE)
    p_c = PipelineC_MiniLM(config.MINILM_INDEX_PATH, config.DEVICE)
    
    # Load indexes
    p_a.build_index(ocr_data, force_rebuild=False)
    p_b.build_index(config.PDF_DIR, force_rebuild=False)
    p_c.build_index(ocr_data, force_rebuild=False)
    
    # Initialize OpenAI client
    client = None
    if config.OPENAI_API_KEY:
        client = OpenAI(api_key=config.OPENAI_API_KEY)
    
    # Run all three pipelines
    results = {}
    
    # Pipeline A (BM25)
    logging.info("Running Pipeline A (BM25)...")
    results_a = p_a.search(query, top_k=top_k)
    llm_answer_a = get_llm_answer(query, results_a, 'A', client, config.PDF_DIR)
    results["pipeline_a_bm25"] = {
        "retrieved_contexts": results_a,
        "llm_summary": llm_answer_a
    }
    
    # Pipeline B (ColQwen)
    logging.info("Running Pipeline B (ColQwen)...")
    results_b = p_b.search(query, top_k=top_k)
    llm_answer_b = get_llm_answer(query, results_b, 'B', client, config.PDF_DIR)
    results["pipeline_b_colqwen"] = {
        "retrieved_contexts": results_b,
        "llm_summary": llm_answer_b
    }
    
    # Pipeline C (MiniLM)
    logging.info("Running Pipeline C (MiniLM)...")
    results_c = p_c.search(query, top_k=top_k)
    llm_answer_c = get_llm_answer(query, results_c, 'C', client, config.PDF_DIR)
    results["pipeline_c_minilm"] = {
        "retrieved_contexts": results_c,
        "llm_summary": llm_answer_c
    }
    
    return {
        "query": query,
        "top_k": top_k,
        "results": results
    }


@app.local_entrypoint()
def main(
    build: bool = False,
    query: str = None,
    top_k: int = 5,
    force_rebuild: bool = False
):
    """
    Local entrypoint for running on Modal GPU
    
    Usage:
        # Build indexes first (do this once after uploading PDFs)
        modal run colpali_modal.py --build
        
        # Run a query
        modal run colpali_modal.py --query "What is the A* algorithm?"
        
        # Run with more results
        modal run colpali_modal.py --query "What is the A* algorithm?" --top-k 10
        
        # Force rebuild indexes
        modal run colpali_modal.py --build --force-rebuild
    """
    
    if build:
        print("🔨 Building indexes on GPU...")
        result = build_indexes.remote(force_rebuild=force_rebuild)
        print(json.dumps(result, indent=2))
        return
    
    if not query:
        print("❌ Error: Please provide a query with --query")
        print("\nUsage:")
        print("  modal run colpali_modal.py --build                    # Build indexes")
        print("  modal run colpali_modal.py --query 'Your question'    # Run query")
        return
    
    # Run query
    print(f"🔍 Running query on GPU: {query}")
    results = run_query.remote(query=query, top_k=top_k)
    
    # Pretty print results
    print("\n" + "="*80)
    print(f"QUERY: {results['query']}")
    print("="*80)
    
    for pipeline_name, pipeline_results in results['results'].items():
        print(f"\n{'='*80}")
        print(f"{pipeline_name.upper()}")
        print(f"{'='*80}")
        
        print("\n🔍 Retrieved Contexts:")
        for i, ctx in enumerate(pipeline_results['retrieved_contexts'], 1):
            print(f"  {i}. Source: {ctx['source']}, Page: {ctx['page']}, Score: {ctx['score']:.4f}")
        
        print(f"\n🤖 LLM Summary:")
        print(f"  {pipeline_results['llm_summary']}")
    
    print("\n" + "="*80)
