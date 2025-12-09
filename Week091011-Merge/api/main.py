"""
FastAPI Backend for RAG Pipeline Demo

Provides REST API endpoints for:
- File upload and management
- Document processing
- Indexing
- Search/Query
"""

import os
import sys
import json
import shutil
import logging
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager
from io import BytesIO

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.unified_rag_pipeline import UnifiedRAGPipeline, UnifiedRAGConfig, PipelineConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    try:
        initialize_pipeline()
    except Exception as e:
        logger.error(f"Startup initialization failed: {e}")
    yield
    # Shutdown
    logger.info("Shutting down API...")


# Initialize FastAPI app
app = FastAPI(
    title="RAG Pipeline API",
    description="API for Multimodal Retrieval-Augmented Generation Pipeline",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
BASE_DIR = Path(__file__).parent.parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
CONFIG_PATH = BASE_DIR / "config" / "default.yaml"

# Ensure directories exist
INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Global pipeline instance
pipeline: Optional[UnifiedRAGPipeline] = None


# Pydantic models
class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    retriever_type: str = "hybrid"
    include_images: bool = True
    images_for_generation: int = 3  # Number of top images to include in generation


class FileDeleteRequest(BaseModel):
    path: str


class ProcessingStatus(BaseModel):
    ready: bool
    indexed_docs: int
    image_pages: int
    text_index: Optional[Dict[str, Any]] = None
    image_index: Optional[Dict[str, Any]] = None


def get_file_info(file_path: Path) -> Dict[str, Any]:
    """Get file information."""
    stat = file_path.stat()
    size_bytes = stat.st_size
    if size_bytes < 1024:
        size_str = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
    
    return {
        "name": file_path.name,
        "path": str(file_path),
        "size": size_str,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "type": file_path.suffix.lower()
    }


def initialize_pipeline():
    """Initialize or get the pipeline instance."""
    global pipeline
    
    if pipeline is None:
        try:
            # Load config from YAML
            import yaml
            with open(CONFIG_PATH, 'r') as f:
                yaml_config = yaml.safe_load(f) or {}
            
            # Get colqwen config
            yaml_colqwen = yaml_config.get('image_retrieval', {}).get('colqwen', {})
            
            # Create pipeline config
            config = UnifiedRAGConfig(
                enable_processing=False,  # Processing is done separately
                enable_retrieval=True,
                enable_generation=True,
                enable_evaluation=False,
                rag_mode="both",
                retrieval_methods=["bm25", "dense", "hybrid"],
                retrieval_top_k=10,
                enable_image_retrieval=True,
                colqwen_model=yaml_colqwen.get('model', 'vidore/colqwen2-v1.0'),
                colqwen_dtype=yaml_colqwen.get('dtype', 'bfloat16'),

                # Prioritize environment variable, then YAML, then default to 8bit
                colqwen_quantization=os.environ.get('RAG_COLQWEN_QUANTIZATION') if os.environ.get('RAG_COLQWEN_QUANTIZATION') and os.environ.get('RAG_COLQWEN_QUANTIZATION') != 'none' else (None if os.environ.get('RAG_COLQWEN_QUANTIZATION') == 'none' else yaml_colqwen.get('quantization', '8bit')),
                colqwen_pdf_dpi=yaml_colqwen.get('pdf_dpi', 150),
            )
            
            pipeline = UnifiedRAGPipeline(
                input_dir=INPUT_DIR,
                output_dir=OUTPUT_DIR,
                config=config
            )
            
            # Try to load existing indexes
            try:
                pipeline.setup_retrievers(load_existing=True)
            except Exception as e:
                logger.warning(f"Could not load existing text index: {e}")
            
            try:
                pipeline.setup_image_retrievers(load_existing=True)
            except Exception as e:
                logger.warning(f"Could not load existing image index: {e}")
            
            logger.info("Pipeline initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize pipeline: {e}")
            raise
    
    return pipeline


@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    """Get pipeline status."""
    try:
        pipe = initialize_pipeline()
        
        status = {
            "ready": pipe.retriever_manager is not None or pipe.image_retriever_manager is not None,
            "indexed_docs": 0,
            "image_pages": 0,
            "text_index": None,
            "image_index": None
        }
        
        # Text index info
        if pipe.retriever_manager:
            status["text_index"] = {
                "chunks": len(pipe.retriever_manager.documents) if hasattr(pipe.retriever_manager, 'documents') else 0,
                "docs": pipe.retriever_manager.raw_doc_count if hasattr(pipe.retriever_manager, 'raw_doc_count') else 0,
                "retrievers": pipe.retriever_manager.get_available_retrievers() if hasattr(pipe.retriever_manager, 'get_available_retrievers') else []
            }
            status["indexed_docs"] = status["text_index"]["chunks"]
        
        # Image index info
        if pipe.image_retriever_manager:
            total_pages = 0
            for name, retriever in pipe.image_retriever_manager.retrievers.items():
                total_pages += len(retriever.index) if hasattr(retriever, 'index') else 0
            
            status["image_index"] = {
                "pages": total_pages,
                "pdfs": len(set(doc.get('source', '') for retriever in pipe.image_retriever_manager.retrievers.values() for doc in getattr(retriever, 'index', [])))
            }
            status["image_pages"] = total_pages
        
        return status
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {"ready": False, "indexed_docs": 0, "image_pages": 0, "error": str(e)}


@app.get("/api/config")
async def get_config() -> Dict[str, Any]:
    """Get current pipeline configuration."""
    try:
        import yaml
        
        with open(CONFIG_PATH, 'r') as f:
            config_dict = yaml.safe_load(f)
        
        return {
            "config_path": str(CONFIG_PATH),
            "config": config_dict,
            "key_settings": {
                "pipeline_mode": config_dict.get("pipeline", {}).get("mode", "unknown"),
                "rag_mode": config_dict.get("pipeline", {}).get("rag_mode", "unknown"),
                "enable_processing": config_dict.get("pipeline", {}).get("enable_processing", False),
                "enable_retrieval": config_dict.get("pipeline", {}).get("enable_retrieval", False),
                "enable_generation": config_dict.get("pipeline", {}).get("enable_generation", False),
                "image_retrieval_enabled": config_dict.get("image_retrieval", {}).get("enabled", False),
                "colqwen_model": config_dict.get("image_retrieval", {}).get("colqwen", {}).get("model", "unknown"),
                "colqwen_quantization": config_dict.get("image_retrieval", {}).get("colqwen", {}).get("quantization", "none"),
                "text_embedding_model": config_dict.get("text_retrieval", {}).get("embedding_model", "unknown"),
                "retrieval_methods": config_dict.get("text_retrieval", {}).get("methods", [])
            }
        }
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {"error": str(e), "config_path": str(CONFIG_PATH)}


@app.get("/api/files")
async def get_files() -> Dict[str, List[Dict]]:
    """Get all files in input, processed, and indexed directories."""
    files = {
        "input": [],
        "processed": [],
        "indexed": []
    }
    
    # Input files
    if INPUT_DIR.exists():
        for f in INPUT_DIR.rglob("*"):
            if f.is_file() and not f.name.startswith('.'):
                files["input"].append(get_file_info(f))
    
    # Processed files (from processing stages)
    processing_dir = OUTPUT_DIR / "processing"
    if processing_dir.exists():
        for stage_dir in processing_dir.iterdir():
            if stage_dir.is_dir():
                for f in stage_dir.rglob("*"):
                    if f.is_file() and f.suffix in ['.json', '.md', '.txt']:
                        info = get_file_info(f)
                        info["stage"] = stage_dir.name
                        
                        # Add preview for text files
                        try:
                            with open(f, 'r', encoding='utf-8', errors='ignore') as fp:
                                content = fp.read(500)
                                info["preview"] = content[:500] + ("..." if len(content) >= 500 else "")
                        except Exception as preview_error:
                            logger.debug(f"Could not read preview for {f.name}: {preview_error}")
                        
                        files["processed"].append(info)
    
    # Indexed files info
    retrieval_dir = OUTPUT_DIR / "retrieval"
    if retrieval_dir.exists():
        docs_file = retrieval_dir / "documents.json"
        if docs_file.exists():
            try:
                with open(docs_file, 'r', encoding='utf-8', errors='ignore') as f:
                    docs = json.load(f)
                
                # Group by source
                sources = {}
                for doc in docs:
                    source = doc.get('source', 'unknown')
                    if source not in sources:
                        sources[source] = 0
                    sources[source] += 1
                
                for source, count in sources.items():
                    files["indexed"].append({
                        "name": source,
                        "chunks": count,
                        "type": "text"
                    })
            except Exception as e:
                logger.error(f"Failed to read indexed docs: {e}")
    
    # Image indexed files
    image_dir = OUTPUT_DIR / "image_retrieval"
    if image_dir.exists():
        meta_file = image_dir / "image_index_meta.json"
        if meta_file.exists():
            try:
                with open(meta_file, 'r', encoding='utf-8', errors='ignore') as f:
                    meta = json.load(f)
                
                # Read colqwen meta for page counts
                colqwen_meta = image_dir / "colqwen" / "colqwen_meta.json"
                if colqwen_meta.exists():
                    with open(colqwen_meta, 'r', encoding='utf-8', errors='ignore') as f:
                        cq_meta = json.load(f)
                    files["indexed"].append({
                        "name": "Image Index (ColQwen)",
                        "pages": cq_meta.get('num_pages', 0),
                        "type": "image"
                    })
            except Exception as e:
                logger.error(f"Failed to read image index meta: {e}")
    
    return files


@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload files to input directory."""
    uploaded = []
    
    for file in files:
        try:
            file_path = INPUT_DIR / file.filename
            
            # Ensure unique filename
            if file_path.exists():
                base = file_path.stem
                suffix = file_path.suffix
                counter = 1
                while file_path.exists():
                    file_path = INPUT_DIR / f"{base}_{counter}{suffix}"
                    counter += 1
            
            # Save file
            with open(file_path, 'wb') as f:
                content = await file.read()
                f.write(content)
            
            uploaded.append({
                "name": file_path.name,
                "size": len(content)
            })
            logger.info(f"Uploaded: {file_path.name}")
        
        except Exception as e:
            logger.error(f"Failed to upload {file.filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    return {"uploaded": uploaded, "count": len(uploaded)}


@app.delete("/api/files")
async def delete_file(request: FileDeleteRequest):
    """Delete a file."""
    try:
        file_path = Path(request.path)
        if file_path.exists():
            file_path.unlink()
            return {"deleted": request.path}
        else:
            raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/process")
async def process_documents(background_tasks: BackgroundTasks):
    """Process uploaded documents."""
    try:
        logger.info("Starting document processing...")
        logger.info(f"Input directory: {INPUT_DIR}")
        logger.info(f"Output directory: {OUTPUT_DIR}")
        logger.info(f"Config path: {CONFIG_PATH}")
        
        # Import here to ensure fresh import
        import sys
        from src.unified_rag_pipeline import UnifiedRAGPipeline, UnifiedRAGConfig, PipelineConfig
        
        # Create processing config
        config = UnifiedRAGConfig(
            enable_processing=True,
            enable_retrieval=False,
            enable_generation=False,
            enable_evaluation=False,
            rag_mode="text"
        )
        
        # Initialize pipeline
        pipeline_instance = UnifiedRAGPipeline(
            input_dir=str(INPUT_DIR),
            output_dir=str(OUTPUT_DIR),
            config=config
        )
        
        logger.info("Pipeline initialized, starting processing...")
        
        # Run the pipeline
        results = pipeline_instance.run()
        
        logger.info(f"Processing completed: {results}")
        
        if results.get("status") == "failed":
            raise HTTPException(status_code=500, detail=results.get("error", "Processing failed"))
        
        return {
            "status": "completed",
            "results": results
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Processing failed with exception: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@app.post("/api/index")
async def build_index():
    """Build/rebuild retrieval index using config file (same as CLI)."""
    global pipeline
    
    try:
        logger.info("Starting index building...")
        logger.info(f"Input directory: {INPUT_DIR}")
        logger.info(f"Output directory: {OUTPUT_DIR}")
        logger.info(f"Config path: {CONFIG_PATH}")
        
        # Import here to ensure fresh import
        import shutil
        import yaml
        from src.unified_rag_pipeline import UnifiedRAGPipeline, UnifiedRAGConfig
        from src.generation.generator import GenerationConfig
        from src.processing.document_processor import PipelineConfig
        
        # Clean old image retrieval index to force rebuild
        image_retrieval_dir = OUTPUT_DIR / "image_retrieval"
        if image_retrieval_dir.exists():
            logger.info(f"Removing old image retrieval index: {image_retrieval_dir}")
            shutil.rmtree(image_retrieval_dir)
        
        # Load config from YAML file (exactly like CLI does)
        logger.info(f"Loading config from: {CONFIG_PATH}")
        with open(CONFIG_PATH, 'r') as f:
            yaml_config = yaml.safe_load(f) or {}
        
        logger.info(f"Config loaded: rag_mode={yaml_config.get('pipeline', {}).get('rag_mode')}, "
                   f"enable_retrieval={yaml_config.get('pipeline', {}).get('enable_retrieval')}, "
                   f"image_retrieval_enabled={yaml_config.get('image_retrieval', {}).get('enabled')}")
        
        # Build UnifiedRAGConfig from YAML (matching CLI behavior)
        processing_config = PipelineConfig()
        generation_config = GenerationConfig()
        
        yaml_colqwen = yaml_config.get('image_retrieval', {}).get('colqwen', {})
        yaml_image_retrieval_enabled = yaml_config.get('image_retrieval', {}).get('enabled', False)
        rag_mode = yaml_config.get('pipeline', {}).get('rag_mode', 'text')
        
        enable_image_retrieval = rag_mode in ["image", "both"] or yaml_image_retrieval_enabled
        
        config = UnifiedRAGConfig(
            enable_processing=False,  # Index mode doesn't process
            enable_retrieval=True,
            enable_generation=False,
            enable_evaluation=False,
            processing_config=processing_config,
            rag_mode=rag_mode,
            retrieval_methods=yaml_config.get('pipeline', {}).get('retrievers', ['bm25', 'dense', 'hybrid']),
            enable_image_retrieval=enable_image_retrieval,
            image_retrieval_methods=yaml_config.get('image_retrieval', {}).get('methods', ['colqwen']),
            colqwen_model=yaml_colqwen.get('model', 'vidore/colqwen2-v1.0'),
            colqwen_dtype=yaml_colqwen.get('dtype', 'bfloat16'),
            colqwen_quantization=yaml_colqwen.get('quantization', None),
            colqwen_pdf_dpi=yaml_colqwen.get('pdf_dpi', 150),
            generation_config=generation_config
        )
        
        # Create pipeline instance with loaded config
        pipeline_instance = UnifiedRAGPipeline(
            input_dir=str(INPUT_DIR),
            output_dir=str(OUTPUT_DIR),
            config=config
        )
        
        logger.info(f"Pipeline config: enable_retrieval={pipeline_instance.config.enable_retrieval}, "
                   f"enable_image_retrieval={pipeline_instance.config.enable_image_retrieval}, "
                   f"rag_mode={pipeline_instance.config.rag_mode}")
        
        # Run the pipeline
        logger.info("Pipeline initialized, starting indexing...")
        results = pipeline_instance.run()
        
        logger.info(f"Indexing completed: {results}")
        
        if results.get("status") == "failed":
            raise HTTPException(status_code=500, detail=results.get("error", "Indexing failed"))
        
        # Reinitialize the global pipeline to load new index
        logger.info("Reinitializing global pipeline...")
        pipeline = None
        initialize_pipeline()
        
        return {
            "status": "completed",
            "results": results
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Indexing failed with exception: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Indexing error: {str(e)}")


@app.post("/api/search")
async def search(request: SearchRequest) -> Dict[str, Any]:
    """Search the indexed documents."""
    try:
        pipe = initialize_pipeline()
        
        results = {
            "query": request.query,
            "text_results": [],
            "image_results": [],
            "answer": None
        }
        
        # Text search
        if pipe.retriever_manager:
            try:
                text_results = pipe.retriever_manager.search(
                    request.query, 
                    request.retriever_type, 
                    top_k=request.top_k
                )
                results["text_results"] = text_results
            except Exception as e:
                logger.error(f"Text search failed: {e}")
        
        # Image search
        if request.include_images and pipe.image_retriever_manager:
            try:
                image_results = pipe.search_images(request.query, "colqwen", top_k=request.top_k)
                results["image_results"] = image_results
            except Exception as e:
                logger.error(f"Image search failed: {e}")
        
        # Generate answer
        if pipe.generator and (results["text_results"] or results["image_results"]):
            try:
                # Use all text results but only top N images for generation
                images_for_gen = results["image_results"][:request.images_for_generation]
                
                # Debug: log image info
                logger.info(f"Sending {len(images_for_gen)} images to generator")
                for img in images_for_gen:
                    logger.info(f"  Image: {img.get('source')}, page {img.get('page')}, path: {img.get('source_path')}")
                
                all_results = results["text_results"] + images_for_gen
                gen_result = pipe.generator.generate(request.query, all_results)
                results["answer"] = gen_result.get("answer", "")
            except Exception as e:
                logger.error(f"Generation failed: {e}")
                import traceback
                traceback.print_exc()
        
        return results
    
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/image")
async def get_image(path: str):
    """Get image by path."""
    try:
        file_path = Path(path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")
        return FileResponse(str(file_path), media_type="image/jpeg")
    except Exception as e:
        logger.error(f"Failed to serve image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pdf-page-image")
async def get_pdf_page_image(pdf_name: str, page: int):
    """
    Render a specific page from a PDF as an image.
    
    Args:
        pdf_name: Name of the PDF file (without extension or with .pdf)
        page: Page number (1-indexed)
    """
    try:
        # Try to import pdf2image
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise HTTPException(
                status_code=500, 
                detail="pdf2image not installed. Run: pip install pdf2image"
            )
        
        # Find the PDF file in stage4_rag_ready
        rag_ready_dir = OUTPUT_DIR / "processing" / "stage4_rag_ready"
        
        # Normalize pdf name
        if not pdf_name.endswith('.pdf'):
            pdf_name = pdf_name + '.pdf'
        
        pdf_path = None
        
        # Search for the PDF
        if rag_ready_dir.exists():
            for f in rag_ready_dir.rglob("*.pdf"):
                if f.name == pdf_name:
                    pdf_path = f
                    break
        
        # Also search in input directory
        if not pdf_path and INPUT_DIR.exists():
            for f in INPUT_DIR.rglob("*.pdf"):
                if f.name == pdf_name:
                    pdf_path = f
                    break
        
        if not pdf_path:
            raise HTTPException(status_code=404, detail=f"PDF not found: {pdf_name}")
        
        # Convert specific page to image
        try:
            images = convert_from_path(
                str(pdf_path), 
                first_page=page, 
                last_page=page,
                dpi=150  # Balance quality vs speed
            )
        except Exception as e:
            logger.error(f"pdf2image conversion failed: {e}")
            raise HTTPException(status_code=500, detail=f"PDF conversion failed: {str(e)}")
        
        if not images:
            raise HTTPException(status_code=404, detail=f"Page {page} not found in PDF")
        
        # Convert PIL image to bytes
        img_byte_arr = BytesIO()
        images[0].save(img_byte_arr, format='PNG', optimize=True)
        img_byte_arr.seek(0)
        
        return StreamingResponse(img_byte_arr, media_type="image/png")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to render PDF page: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser(description="RAG Pipeline API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    parser.add_argument("--quantization", "-q", choices=["none", "4bit", "8bit"], 
                       help="Quantization level for ColQwen/ColPali models (none=unquantized/original)")
    
    args = parser.parse_args()
    
    # Set environment variable for quantization if specified
    if args.quantization:
        os.environ["RAG_COLQWEN_QUANTIZATION"] = args.quantization
        print(f"Configuration: Quantization set to '{args.quantization}'")
    
    # Run the server
    print(f"Starting server on http://{args.host}:{args.port} (reload={args.reload})")
    uvicorn.run("main:app", host=args.host, port=args.port, reload=args.reload)
