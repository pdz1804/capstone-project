"""
Image-based RAG Retrievers

Multi-modal retrieval systems that work directly on PDF page images,
using vision-language models like ColQwen for semantic understanding.
"""

import os
import json
import pickle
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

import torch
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseImageRetriever(ABC):
    """Base class for image-based retrievers."""
    
    def __init__(self, name: str):
        self.name = name
        self.is_indexed = False
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    @abstractmethod
    def index_pdfs(self, pdf_dir: Path) -> None:
        """Index PDF documents for retrieval."""
        pass
    
    @abstractmethod
    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Search for relevant pages."""
        pass
    
    @abstractmethod
    def save_index(self, index_dir: Path) -> None:
        """Save index to disk."""
        pass
    
    @abstractmethod
    def load_index(self, index_dir: Path) -> bool:
        """Load index from disk."""
        pass


class ColQwenRetriever(BaseImageRetriever):
    """
    ColQwen-based image retrieval.
    
    Uses vision-language model to embed PDF pages as images and 
    perform semantic search based on visual content.
    
    Configuration options:
    - model_name: HuggingFace model ID (e.g., "vidore/colqwen2-v1.0")
    - dtype: Data type for model weights ("bfloat16", "float16", "float32")
    - load_in_4bit: Enable 4-bit quantization (requires bitsandbytes)
    - load_in_8bit: Enable 8-bit quantization (requires bitsandbytes)
    - device_map: Device placement ("auto", "cuda", "cpu")
    - pdf_dpi: DPI for PDF to image conversion (default: 150)
    """
    
    def __init__(
        self, 
        model_name: str = "vidore/colqwen2-v1.0",
        dtype: str = "bfloat16",
        load_in_4bit: bool = False,
        load_in_8bit: bool = False,
        device_map: str = "auto",
        pdf_dpi: int = 150
    ):
        super().__init__("ColQwen")
        self.model_name = model_name
        self.dtype = dtype
        self.load_in_4bit = load_in_4bit
        self.load_in_8bit = load_in_8bit
        self.device_map = device_map
        self.pdf_dpi = pdf_dpi
        self.processor = None
        self.model = None
        self.index = []  # List of {source, page, embeddings}
        self.pdf_dir = None
    
    def _get_torch_dtype(self):
        """Get torch dtype from string configuration."""
        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        # Use float32 on CPU, configured dtype on CUDA
        if self.device.type == 'cpu':
            return torch.float32
        return dtype_map.get(self.dtype, torch.bfloat16)
    
    def _get_quantization_config(self):
        """Get quantization config if enabled."""
        if not (self.load_in_4bit or self.load_in_8bit):
            return None
        
        try:
            from transformers import BitsAndBytesConfig
            
            if self.load_in_4bit:
                logger.info("Using 4-bit quantization for ColQwen model")
                return BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=self._get_torch_dtype(),
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
            elif self.load_in_8bit:
                logger.info("Using 8-bit quantization for ColQwen model")
                return BitsAndBytesConfig(
                    load_in_8bit=True
                )
        except ImportError:
            logger.warning(
                "bitsandbytes not installed. Quantization disabled. "
                "Install with: pip install bitsandbytes"
            )
            return None
        
        return None
    
    def _load_model(self):
        """Lazy load the ColQwen model."""
        if self.model is not None:
            return
        
        # Determine model version from model name
        is_colqwen25 = "colqwen2.5" in self.model_name.lower() or "2.5" in self.model_name
        
        # Get quantization config
        quantization_config = self._get_quantization_config()
        
        # Prepare model loading kwargs
        # CRITICAL: device_map and quantization DO NOT MIX WELL with transformers/accelerate
        # When using quantization, BitsAndBytes handles device placement - don't override it
        # When NOT using quantization, explicitly manage device placement to avoid OOM
        model_kwargs = {}
        
        if quantization_config:
            model_kwargs["quantization_config"] = quantization_config
            # BitsAndBytes handles all device placement internally
            # Do NOT add device_map as it conflicts with quantization
            logger.info("Loading with 8-bit quantization - device placement handled by BitsAndBytes")
        else:
            # For non-quantized models, we still can't use "auto" because it tries fancy offloading
            # Instead, just set dtype and let torch handle CPU/CUDA naturally
            model_kwargs["torch_dtype"] = self._get_torch_dtype()
            logger.info(f"Loading non-quantized model with dtype: {self.dtype}")
        
        try:
            if is_colqwen25:
                # Use ColQwen2.5 for colqwen2.5 models
                from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor
                logger.info(f"Loading ColQwen 2.5 model: {self.model_name}...")
                if quantization_config:
                    logger.info(f"  Quantization: {'4-bit' if self.load_in_4bit else '8-bit'}")
                else:
                    logger.info(f"  Dtype: {self.dtype}")
                
                self.processor = ColQwen2_5_Processor.from_pretrained(self.model_name)
                self.model = ColQwen2_5.from_pretrained(
                    self.model_name,
                    **model_kwargs
                ).eval()
            else:
                # Use ColQwen2 for older colqwen2 models
                from colpali_engine.models import ColQwen2, ColQwen2Processor
                logger.info(f"Loading ColQwen 2 model: {self.model_name}...")
                if quantization_config:
                    logger.info(f"  Quantization: {'4-bit' if self.load_in_4bit else '8-bit'}")
                else:
                    logger.info(f"  Dtype: {self.dtype}")
                
                self.processor = ColQwen2Processor.from_pretrained(self.model_name)
                self.model = ColQwen2.from_pretrained(
                    self.model_name,
                    **model_kwargs
                ).eval()
                
        except ImportError as e:
            raise ImportError(
                f"colpali_engine import failed: {e}\n"
                f"Install/upgrade with: pip install --upgrade colpali-engine"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load ColQwen model '{self.model_name}': {e}")
        
        logger.info(f"ColQwen model loaded successfully on {self.device}")
    
    def index_pdfs(self, pdf_dir: Path) -> None:
        """Index all PDFs in the directory."""
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError(
                "pdf2image not installed. Install with: pip install pdf2image"
            )
        
        self._load_model()
        self.pdf_dir = Path(pdf_dir)
        
        # Find all PDFs
        pdf_files = list(self.pdf_dir.rglob("*.pdf"))
        if not pdf_files:
            logger.warning(f"No PDF files found in {pdf_dir}")
            return
        
        logger.info(f"Indexing {len(pdf_files)} PDF files with ColQwen...")
        self.index = []
        
        with torch.no_grad():
            for pdf_path in tqdm(pdf_files, desc="Processing PDFs"):
                try:
                    # Convert PDF to images
                    images = convert_from_path(pdf_path, dpi=self.pdf_dpi)
                    
                    for page_num, page_image in enumerate(tqdm(images, desc=f"  {pdf_path.name}", leave=False), 1):
                        # Process image
                        image_inputs = self.processor.process_images([page_image]).to(self.model.device)
                        
                        # Get embeddings
                        doc_outputs = self.model(**image_inputs)
                        
                        self.index.append({
                            'source': pdf_path.name,
                            'source_path': str(pdf_path),
                            'page': page_num,
                            'total_pages': len(images),
                            'embeddings': doc_outputs.cpu()
                        })
                
                except Exception as e:
                    logger.error(f"Error processing {pdf_path}: {e}")
        
        self.is_indexed = len(self.index) > 0
        logger.info(f"Indexed {len(self.index)} pages from {len(pdf_files)} PDFs")
    
    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Search for relevant pages using ColQwen."""
        if not self.index:
            logger.error("Index is empty. Call index_pdfs() first.")
            return []
        
        self._load_model()
        
        # Embed query
        query_inputs = self.processor.process_queries([query]).to(self.model.device)
        with torch.no_grad():
            query_embeds = self.model(**query_inputs)
        
        # Score all pages
        page_scores = []
        for doc in self.index:
            doc_embeds = doc['embeddings'].to(self.model.device)
            score = self.processor.score_multi_vector(query_embeds, doc_embeds).item()
            page_scores.append(score)
        
        # Get top results
        top_indices = sorted(range(len(page_scores)), key=lambda i: page_scores[i], reverse=True)[:top_k]
        
        results = []
        for rank, i in enumerate(top_indices, 1):
            doc_info = self.index[i]
            results.append({
                'id': f"{doc_info['source']}_page_{doc_info['page']}",
                'source': doc_info['source'],
                'source_path': doc_info.get('source_path', ''),
                'page': doc_info['page'],
                'total_pages': doc_info.get('total_pages', 0),
                'score': float(page_scores[i]),
                'rank': rank,
                'text': f"[Image Page {doc_info['page']} from {doc_info['source']}]",
                'retrieval_type': 'colqwen'
            })
        
        return results
    
    def save_index(self, index_dir: Path) -> None:
        """Save ColQwen index to disk."""
        index_dir = Path(index_dir)
        index_dir.mkdir(parents=True, exist_ok=True)
        
        # Save index
        index_path = index_dir / "colqwen_index.pkl"
        with open(index_path, 'wb') as f:
            pickle.dump(self.index, f)
        
        # Save metadata
        meta = {
            'model_name': self.model_name,
            'num_pages': len(self.index),
            'pdf_dir': str(self.pdf_dir) if self.pdf_dir else None
        }
        meta_path = index_dir / "colqwen_meta.json"
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2)
        
        logger.info(f"Saved ColQwen index ({len(self.index)} pages) to {index_dir}")
    
    def load_index(self, index_dir: Path) -> bool:
        """Load ColQwen index from disk."""
        index_dir = Path(index_dir)
        index_path = index_dir / "colqwen_index.pkl"
        meta_path = index_dir / "colqwen_meta.json"
        
        if not index_path.exists():
            logger.warning(f"ColQwen index not found at {index_path}")
            return False
        
        try:
            with open(index_path, 'rb') as f:
                self.index = pickle.load(f)
            
            if meta_path.exists():
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
                self.model_name = meta.get('model_name', self.model_name)
                self.pdf_dir = Path(meta['pdf_dir']) if meta.get('pdf_dir') else None
            
            self.is_indexed = len(self.index) > 0
            logger.info(f"Loaded ColQwen index ({len(self.index)} pages) from {index_dir}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to load ColQwen index: {e}")
            return False


class ImageRAGManager:
    """Manager for image-based RAG retrieval systems."""
    
    def __init__(
        self, 
        pdf_dir: Path, 
        index_dir: Path = None, 
        colqwen_config: Dict[str, Any] = None
    ):
        self.pdf_dir = Path(pdf_dir)
        self.index_dir = Path(index_dir) if index_dir else self.pdf_dir.parent / "image_retrieval_index"
        
        # ColQwen configuration with defaults
        self.colqwen_config = colqwen_config or {}
        self.retrievers = {}
    
    def setup_retriever(self, retriever_type: str = "colqwen") -> None:
        """Setup a specific image retriever."""
        if retriever_type == "colqwen":
            retriever = ColQwenRetriever(
                model_name=self.colqwen_config.get("model", "vidore/colqwen2-v1.0"),
                dtype=self.colqwen_config.get("dtype", "bfloat16"),
                load_in_4bit=self.colqwen_config.get("load_in_4bit", False),
                load_in_8bit=self.colqwen_config.get("load_in_8bit", False),
                device_map=self.colqwen_config.get("device_map", "auto"),
                pdf_dpi=self.colqwen_config.get("pdf_dpi", 150)
            )
        else:
            raise ValueError(f"Unknown image retriever type: {retriever_type}")
        
        retriever.index_pdfs(self.pdf_dir)
        self.retrievers[retriever_type] = retriever
        logger.info(f"Setup {retriever_type} image retriever")
    
    def search(self, query: str, retriever_type: str = "colqwen", top_k: int = 10) -> List[Dict[str, Any]]:
        """Search using a specific retriever."""
        if retriever_type not in self.retrievers:
            logger.error(f"Retriever {retriever_type} not setup. Available: {list(self.retrievers.keys())}")
            return []
        
        return self.retrievers[retriever_type].search(query, top_k)
    
    def get_available_retrievers(self) -> List[str]:
        """Get list of available retrievers."""
        return list(self.retrievers.keys())
    
    def save_index(self) -> Path:
        """Save all indexes to disk."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        for name, retriever in self.retrievers.items():
            retriever_dir = self.index_dir / name
            retriever.save_index(retriever_dir)
        
        # Save metadata
        meta = {
            'retrievers': list(self.retrievers.keys()),
            'pdf_dir': str(self.pdf_dir)
        }
        with open(self.index_dir / "image_index_meta.json", 'w') as f:
            json.dump(meta, f, indent=2)
        
        logger.info(f"Saved image indexes to {self.index_dir}")
        return self.index_dir
    
    def load_index(self) -> bool:
        """Load indexes from disk."""
        meta_path = self.index_dir / "image_index_meta.json"
        
        if not meta_path.exists():
            logger.warning(f"Image index metadata not found at {meta_path}")
            return False
        
        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            
            retriever_types = meta.get('retrievers', [])
            
            for retriever_type in retriever_types:
                retriever_dir = self.index_dir / retriever_type
                
                if retriever_type == "colqwen":
                    # Load ColQwen with the same config used during indexing
                    retriever = ColQwenRetriever(
                        model_name=self.colqwen_config.get("model", "vidore/colqwen2-v1.0"),
                        dtype=self.colqwen_config.get("dtype", "bfloat16"),
                        load_in_4bit=self.colqwen_config.get("load_in_4bit", False),
                        load_in_8bit=self.colqwen_config.get("load_in_8bit", False),
                        device_map=self.colqwen_config.get("device_map", "auto"),
                        pdf_dpi=self.colqwen_config.get("pdf_dpi", 150)
                    )
                    if retriever.load_index(retriever_dir):
                        self.retrievers[retriever_type] = retriever
            
            logger.info(f"Loaded image indexes: {list(self.retrievers.keys())}")
            return len(self.retrievers) > 0
        
        except Exception as e:
            logger.error(f"Failed to load image indexes: {e}")
            return False


# Convenience functions
def create_image_retriever(
    pdf_dir: Path,
    retriever_types: List[str] = None,
    index_dir: Path = None,
    save_index: bool = True,
    colqwen_config: Dict[str, Any] = None
) -> ImageRAGManager:
    """
    Create and setup image RAG retriever manager.
    
    Args:
        pdf_dir: Directory containing PDF files to index
        retriever_types: List of retriever types to setup (default: ["colqwen"])
        index_dir: Directory to save/load index
        save_index: Whether to save the index after building
        colqwen_config: ColQwen configuration dict with keys:
            - model: Model name (default: "vidore/colqwen2-v1.0")
            - dtype: Data type ("bfloat16", "float16", "float32")
            - load_in_4bit: Enable 4-bit quantization
            - load_in_8bit: Enable 8-bit quantization
            - device_map: Device placement ("auto", "cuda", "cpu")
            - pdf_dpi: DPI for PDF conversion (default: 150)
    
    Returns:
        Configured ImageRAGManager instance
    """
    if retriever_types is None:
        retriever_types = ["colqwen"]
    
    manager = ImageRAGManager(pdf_dir, index_dir, colqwen_config=colqwen_config)
    
    for retriever_type in retriever_types:
        try:
            manager.setup_retriever(retriever_type)
        except Exception as e:
            logger.error(f"Failed to setup {retriever_type} retriever: {e}")
    
    if save_index and manager.retrievers:
        manager.save_index()
    
    return manager


def load_image_retriever(index_dir: Path, colqwen_config: Dict[str, Any] = None) -> Optional[ImageRAGManager]:
    """Load image RAG retriever from saved index."""
    manager = ImageRAGManager(Path("."), index_dir, colqwen_config=colqwen_config)
    
    if manager.load_index():
        return manager
    return None



