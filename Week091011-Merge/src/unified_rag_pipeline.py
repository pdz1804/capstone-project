"""
Unified RAG Pipeline
Combines document processing and information retrieval into a complete RAG system.

This pipeline orchestrates:
1. Document Processing (from Week070809_QPhu_Processor)
   - Normalization (DOCX/PPTX/HTML → PDF, TXT → MD)
   - Media Processing (Video/Audio → Text)
   - Document Processing (Docling-based extraction)
   - Consolidation (RAG-ready structure)

2. Information Retrieval (from Week070809_NKhoi_Retrieval)
   - Multiple retrieval strategies (BM25, Dense, Hybrid, ColBERT)
   - Multi-modal retrieval (ColQwen for image-based)
   - Reranking capabilities
   - Evaluation metrics

Usage:
    python run_pipeline.py --input input/ --output output/ --mode full
"""

import os
import sys
import json
import logging
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, asdict
import argparse
from datetime import datetime

# Fix Windows encoding issue with Unicode characters in logging
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Import processor components
try:
    # Try relative imports first (when run as module)
    from .processor.pipeline import DocumentProcessingPipeline, PipelineConfig
    from .processor.normalizer import NormalizerConfig
    from .processor.media_processor import MediaProcessorConfig
    from .processor.document_processor import ProcessingConfig
    from .processor.consolidator import ConsolidatorConfig
    from .retrieval.rag_retrievers import RAGRetrieverManager, create_rag_retriever, load_rag_retriever
    from .retrieval.image_retrievers import ImageRAGManager, create_image_retriever, load_image_retriever
    from .generation.generator import RAGGenerator, GenerationConfig, create_generator
except ImportError:
    # Fall back to absolute imports (when run directly)
    from processor.pipeline import DocumentProcessingPipeline, PipelineConfig
    from processor.normalizer import NormalizerConfig
    from processor.media_processor import MediaProcessorConfig
    from processor.document_processor import ProcessingConfig
    from processor.consolidator import ConsolidatorConfig
    from retrieval.rag_retrievers import RAGRetrieverManager, create_rag_retriever, load_rag_retriever
    from retrieval.image_retrievers import ImageRAGManager, create_image_retriever, load_image_retriever
    from generation.generator import RAGGenerator, GenerationConfig, create_generator


@dataclass
class UnifiedRAGConfig:
    """Configuration for the unified RAG pipeline."""
    
    # Processing configuration
    enable_processing: bool = True
    processing_config: Optional[PipelineConfig] = None
    
    # RAG Mode: "text", "image", or "both"
    rag_mode: str = "text"  # "text" = text-based only, "image" = image-based only, "both" = combined
    
    # Text Retrieval configuration
    enable_retrieval: bool = True
    retrieval_methods: List[str] = None  # ['bm25', 'dense', 'hybrid']
    retrieval_top_k: int = 10  # Number of chunks to retrieve per query
    default_retriever: str = "hybrid"  # Default retriever to use
    
    # Reranker configuration (for text retrieval)
    enable_reranker: bool = False
    reranker_model: str = None  # 'bge-large', 'minilm-l12', or HuggingFace path
    
    # Chunking configuration
    chunk_size: int = 1000  # Chunk size in characters
    chunk_overlap: int = 200  # Overlap between chunks
    enable_chunking: bool = True  # Whether to chunk documents
    
    # Image retrieval configuration
    enable_image_retrieval: bool = False  # Whether to enable image-based retrieval (ColQwen)
    image_retrieval_methods: List[str] = None  # ['colqwen']
    image_retrieval_top_k: int = 5  # Number of image pages to retrieve
    
    # ColQwen configuration
    colqwen_model: str = "vidore/colqwen2-v1.0"  # ColQwen model name
    colqwen_dtype: str = "bfloat16"  # Data type: bfloat16, float16, float32
    colqwen_quantization: str = None  # Quantization: null, "4bit", "8bit"
    colqwen_pdf_dpi: int = 150  # PDF to image DPI
    
    # Generation configuration
    enable_generation: bool = True
    generation_config: Optional[GenerationConfig] = None
    
    # Evaluation configuration
    enable_evaluation: bool = False
    evaluation_dataset: Optional[str] = None
    
    # Output configuration
    output_format: str = "json"  # json, jsonl
    
    # Logging configuration
    log_to_file: bool = True
    log_level: str = "INFO"
    
    def __post_init__(self):
        """Initialize default configurations."""
        if self.processing_config is None:
            self.processing_config = PipelineConfig(
                enable_normalization=True,
                enable_media_processing=True,
                enable_document_processing=True,
                use_gpu=True
            )
        
        if self.retrieval_methods is None:
            self.retrieval_methods = ['bm25', 'dense', 'hybrid']
        
        if self.image_retrieval_methods is None:
            self.image_retrieval_methods = ['colqwen']
        
        if self.generation_config is None:
            self.generation_config = GenerationConfig()
        
        # Sync rag_mode with enable flags - but only if flags are at their defaults
        # This allows explicit enable_retrieval=False to be respected
        default_enable_retrieval = True
        default_enable_image_retrieval = False
        
        if self.rag_mode == "text":
            # Only sync if flags are at defaults (not explicitly overridden)
            if self.enable_retrieval == default_enable_retrieval and self.enable_image_retrieval == default_enable_image_retrieval:
                self.enable_retrieval = True
                self.enable_image_retrieval = False
        elif self.rag_mode == "image":
            if self.enable_retrieval == default_enable_retrieval and self.enable_image_retrieval == default_enable_image_retrieval:
                self.enable_retrieval = False
                self.enable_image_retrieval = True
        elif self.rag_mode == "both":
            if self.enable_retrieval == default_enable_retrieval and self.enable_image_retrieval == default_enable_image_retrieval:
                self.enable_retrieval = True
                self.enable_image_retrieval = True
        
        # Enable reranker if model specified
        if self.reranker_model:
            self.enable_reranker = True


class UnifiedRAGPipeline:
    """
    Unified RAG Pipeline that combines document processing and information retrieval.
    """
    
    def __init__(
        self,
        input_dir: Union[str, Path],
        output_dir: Union[str, Path],
        config: Optional[UnifiedRAGConfig] = None
    ):
        """Initialize the unified RAG pipeline."""
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.config = config or UnifiedRAGConfig()
        
        # Create output directories
        # Structure:
        #   output/
        #     processing/
        #       stage1_normalized/
        #       stage2_media_processed/
        #       stage3_document_processed/
        #       stage4_rag_ready/
        #     retrieval/              <- Index saved here
        #     evaluation/
        #     unified_rag_pipeline_*.log
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.processing_output_dir = self.output_dir / "processing"
        self.retrieval_output_dir = self.output_dir / "retrieval"
        self.evaluation_output_dir = self.output_dir / "evaluation"
        
        # Setup logging
        self._setup_logging()
        
        # Initialize components
        self.document_processor = None
        self.retriever_manager = None  # Text-based retrieval
        self.image_retriever_manager = None  # Image-based retrieval (ColQwen)
        self.generator = None
        
        # Image retrieval output directory
        self.image_retrieval_output_dir = self.output_dir / "image_retrieval"
        
        # Initialize generator if enabled
        if self.config.enable_generation:
            try:
                self.generator = RAGGenerator(self.config.generation_config)
                logging.info(f"Generator initialized with {self.config.generation_config.provider}/{self.config.generation_config.model_name}")
            except Exception as e:
                logging.warning(f"Failed to initialize generator: {e}. Generation will be disabled.")
        
        logging.info(f"Unified RAG Pipeline initialized")
        logging.info(f"Input directory: {self.input_dir}")
        logging.info(f"Output directory: {self.output_dir}")
    
    def _setup_logging(self):
        """Setup logging configuration with file and console output."""
        # Create logs directory
        logs_dir = self.output_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Log file path
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = logs_dir / f"rag_pipeline_{timestamp}.log"
        self.retrieval_log_file = logs_dir / f"retrieval_{timestamp}.log"
        self.generation_log_file = logs_dir / f"generation_{timestamp}.log"
        
        # Set log level from config
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        
        # Configure root logger
        handlers = [logging.StreamHandler()]
        
        if self.config.log_to_file:
            handlers.append(logging.FileHandler(self.log_file, encoding='utf-8'))
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers,
            force=True  # Reset any existing handlers
        )
        
        # Create dedicated logger for this pipeline
        self.logger = logging.getLogger("UnifiedRAGPipeline")
        self.logger.setLevel(log_level)
        
        # Create retrieval logger
        self.retrieval_logger = logging.getLogger("Retrieval")
        if self.config.log_to_file:
            retrieval_handler = logging.FileHandler(self.retrieval_log_file, encoding='utf-8')
            retrieval_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.retrieval_logger.addHandler(retrieval_handler)
        
        # Create generation logger
        self.generation_logger = logging.getLogger("Generation")
        if self.config.log_to_file:
            generation_handler = logging.FileHandler(self.generation_log_file, encoding='utf-8')
            generation_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.generation_logger.addHandler(generation_handler)
    
    def run_document_processing(self) -> Dict[str, Any]:
        """Run the document processing pipeline."""
        if not self.config.enable_processing:
            logging.info("Document processing disabled, skipping...")
            return {"status": "skipped"}
        
        logging.info("Starting document processing pipeline...")
        
        # Initialize document processor
        self.document_processor = DocumentProcessingPipeline(
            input_dir=self.input_dir,
            output_dir=self.processing_output_dir,
            config=self.config.processing_config
        )
        
        # Run processing
        processing_stats = self.document_processor.run()
        
        logging.info("Document processing completed")
        logging.info(f"Processing stats: {processing_stats}")
        
        return processing_stats
    
    def setup_retrievers(self, load_existing: bool = True) -> Dict[str, Any]:
        """Setup retrieval systems based on processed documents.
        
        Args:
            load_existing: If True, try to load existing index from disk first
        """
        if not self.config.enable_retrieval:
            logging.info("Retrieval setup disabled, skipping...")
            return {"status": "skipped"}
        
        logging.info("Setting up retrieval systems...")
        
        setup_stats = {"retrievers_initialized": [], "document_count": 0}
        
        # Try to load existing index first
        if load_existing and self.retrieval_output_dir.exists():
            index_meta = self.retrieval_output_dir / "index_meta.json"
            if index_meta.exists():
                try:
                    logging.info(f"Loading existing index from: {self.retrieval_output_dir}")
                    self.retriever_manager = load_rag_retriever(self.retrieval_output_dir)
                    
                    if self.retriever_manager:
                        setup_stats["retrievers_initialized"] = self.retriever_manager.get_available_retrievers()
                        setup_stats["document_count"] = len(self.retriever_manager.documents)
                        setup_stats["index_dir"] = str(self.retrieval_output_dir)
                        setup_stats["index_loaded"] = True
                        logging.info(f"[OK] Loaded existing index: {setup_stats}")
                        return setup_stats
                except Exception as e:
                    logging.warning(f"Failed to load existing index: {e}. Will rebuild index.")
        
        # Build new index from documents
        # Determine document source - prioritize processed documents if they exist
        processed_docs = self.processing_output_dir / "stage4_rag_ready"
        if processed_docs.exists() and any(processed_docs.iterdir()):
            # Use processed documents from stage4_rag_ready (preferred)
            doc_source = processed_docs
            logging.info(f"Using processed documents from: {doc_source}")
        elif self.config.enable_processing:
            # Use processed documents from stage4_rag_ready
            doc_source = processed_docs
        else:
            # Use input directory directly (should be RAG-ready format)
            doc_source = self.input_dir
        
        if not doc_source.exists():
            raise ValueError(f"Document source not found: {doc_source}")
        
        try:
            # Initialize RAG retriever manager with chunking
            # Index is saved in output/retrieval/
            logging.info(f"Building index with chunking: size={self.config.chunk_size}, overlap={self.config.chunk_overlap}, enabled={self.config.enable_chunking}")
            
            self.retriever_manager = create_rag_retriever(
                doc_dir=doc_source,
                retriever_types=self.config.retrieval_methods,
                index_dir=self.retrieval_output_dir,
                save_index=True,
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                enable_chunking=self.config.enable_chunking,
                reranker_model=self.config.reranker_model if self.config.enable_reranker else None
            )
            
            setup_stats["retrievers_initialized"] = self.retriever_manager.get_available_retrievers()
            setup_stats["document_count"] = len(self.retriever_manager.documents)
            setup_stats["chunk_count"] = len(self.retriever_manager.documents)
            setup_stats["raw_doc_count"] = len(self.retriever_manager.raw_documents)
            setup_stats["index_dir"] = str(self.retrieval_output_dir)
            setup_stats["index_loaded"] = False
            setup_stats["index_built"] = True
            setup_stats["chunking"] = {
                "enabled": self.config.enable_chunking,
                "chunk_size": self.config.chunk_size,
                "chunk_overlap": self.config.chunk_overlap
            }
            
            logging.info(f"Retrieval setup completed: {setup_stats}")
            
        except Exception as e:
            logging.error(f"Failed to setup retrievers: {e}")
            setup_stats["error"] = str(e)
        
        return setup_stats
    
    def setup_image_retrievers(self, load_existing: bool = True) -> Dict[str, Any]:
        """Setup image-based retrieval systems (ColQwen)."""
        if not self.config.enable_image_retrieval:
            logging.info("Image retrieval disabled, skipping...")
            return {"status": "skipped"}
        
        logging.info("Setting up image retrieval systems...")
        setup_stats = {
            "retrievers_initialized": [],
            "page_count": 0
        }
        
        # Try to load existing index first
        if load_existing and self.image_retrieval_output_dir.exists():
            index_meta = self.image_retrieval_output_dir / "image_index_meta.json"
            if index_meta.exists():
                try:
                    logging.info(f"Loading existing image index from: {self.image_retrieval_output_dir}")
                    
                    # Build ColQwen config from pipeline config (same as when building index)
                    colqwen_config = {
                        "model": self.config.colqwen_model,
                        "dtype": self.config.colqwen_dtype,
                        "load_in_4bit": self.config.colqwen_quantization == "4bit",
                        "load_in_8bit": self.config.colqwen_quantization == "8bit",
                        "device_map": "auto",
                        "pdf_dpi": self.config.colqwen_pdf_dpi
                    }
                    
                    # Debug logging
                    logging.info(f"[DEBUG] setup_image_retrievers: colqwen_quantization={self.config.colqwen_quantization}, colqwen_config={colqwen_config}")
                    
                    self.image_retriever_manager = load_image_retriever(
                        self.image_retrieval_output_dir,
                        colqwen_config=colqwen_config
                    )
                    
                    if self.image_retriever_manager:
                        setup_stats["retrievers_initialized"] = self.image_retriever_manager.get_available_retrievers()
                        # Count total pages
                        for name, retriever in self.image_retriever_manager.retrievers.items():
                            setup_stats["page_count"] += len(retriever.index)
                        setup_stats["index_dir"] = str(self.image_retrieval_output_dir)
                        setup_stats["index_loaded"] = True
                        logging.info(f"[OK] Loaded existing image index: {setup_stats}")
                        return setup_stats
                except Exception as e:
                    logging.warning(f"Failed to load existing image index: {e}. Will rebuild index.")
        
        # Find PDF source - prefer stage4_rag_ready PDFs
        processed_docs = self.processing_output_dir / "stage4_rag_ready"
        if processed_docs.exists():
            pdf_source = processed_docs
        else:
            pdf_source = self.input_dir
        
        if not pdf_source.exists():
            logging.error(f"PDF source not found: {pdf_source}")
            return {"status": "failed", "error": f"PDF source not found: {pdf_source}"}
        
        try:
            logging.info(f"Building image index from: {pdf_source}")
            
            # Build ColQwen config from pipeline config
            colqwen_config = {
                "model": self.config.colqwen_model,
                "dtype": self.config.colqwen_dtype,
                "load_in_4bit": self.config.colqwen_quantization == "4bit",
                "load_in_8bit": self.config.colqwen_quantization == "8bit",
                "device_map": "auto",
                "pdf_dpi": self.config.colqwen_pdf_dpi
            }
            
            self.image_retriever_manager = create_image_retriever(
                pdf_dir=pdf_source,
                retriever_types=self.config.image_retrieval_methods,
                index_dir=self.image_retrieval_output_dir,
                save_index=True,
                colqwen_config=colqwen_config
            )
            
            setup_stats["retrievers_initialized"] = self.image_retriever_manager.get_available_retrievers()
            for name, retriever in self.image_retriever_manager.retrievers.items():
                setup_stats["page_count"] += len(retriever.index)
            setup_stats["index_dir"] = str(self.image_retrieval_output_dir)
            setup_stats["index_built"] = True
            
            logging.info(f"Image retrieval setup completed: {setup_stats}")
            
        except Exception as e:
            logging.error(f"Failed to setup image retrievers: {e}")
            setup_stats["error"] = str(e)
        
        return setup_stats
    
    def run_retrieval_evaluation(self, queries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run retrieval evaluation on the given queries."""
        if not self.config.enable_evaluation:
            logging.info("Retrieval evaluation disabled, skipping...")
            return {"status": "skipped"}
        
        if not self.retriever_manager:
            logging.error("Retriever manager not initialized. Run setup_retrievers() first.")
            return {"status": "failed", "error": "Retriever manager not initialized"}
        
        logging.info("Starting retrieval evaluation...")
        
        evaluation_results = {}
        available_retrievers = self.retriever_manager.get_available_retrievers()
        
        for retriever_name in available_retrievers:
            logging.info(f"Evaluating {retriever_name} retriever...")
            
            try:
                # Run retrieval for each query
                retriever_results = []
                for query in queries:
                    query_text = query.get("text", query.get("query", ""))
                    if query_text:
                        results = self.retriever_manager.search(
                            query=query_text, 
                            retriever_type=retriever_name, 
                            top_k=10
                        )
                        retriever_results.append({
                            "query_id": query.get("id", "unknown"),
                            "query_text": query_text,
                            "results": results
                        })
                
                evaluation_results[retriever_name] = {
                    "status": "completed",
                    "num_queries": len(queries),
                    "results": retriever_results
                }
                
            except Exception as e:
                logging.error(f"Error evaluating {retriever_name}: {e}")
                evaluation_results[retriever_name] = {
                    "status": "failed",
                    "error": str(e)
                }
        
        # Save evaluation results
        eval_output_file = self.evaluation_output_dir / "retrieval_evaluation_results.json"
        self.evaluation_output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(eval_output_file, 'w', encoding='utf-8') as f:
            json.dump(evaluation_results, f, indent=2, ensure_ascii=False)
        
        logging.info(f"Retrieval evaluation completed. Results saved to: {eval_output_file}")
        return evaluation_results
    
    def run(self, queries: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Run the complete unified RAG pipeline."""
        logging.info("Starting Unified RAG Pipeline...")
        
        pipeline_stats = {
            "start_time": datetime.now().isoformat(),
            "processing": {},
            "retrieval_setup": {},
            "image_retrieval_setup": {},
            "evaluation": {},
            "end_time": None,
            "total_duration": None
        }
        
        try:
            # Step 1: Document Processing (skip in test mode)
            if self.config.enable_processing:
                pipeline_stats["processing"] = self.run_document_processing()
            
            # Step 2: Setup Text Retrievers
            pipeline_stats["retrieval_setup"] = self.setup_retrievers()
            
            # Step 3: Setup Image Retrievers (if enabled)
            if self.config.enable_image_retrieval:
                pipeline_stats["image_retrieval_setup"] = self.setup_image_retrievers()
            
            # Step 4: Retrieval Evaluation (if queries provided)
            if queries:
                pipeline_stats["evaluation"] = self.run_retrieval_evaluation(queries)
            
            # Finalize stats
            pipeline_stats["end_time"] = datetime.now().isoformat()
            start_time = datetime.fromisoformat(pipeline_stats["start_time"])
            end_time = datetime.fromisoformat(pipeline_stats["end_time"])
            pipeline_stats["total_duration"] = str(end_time - start_time)
            
            # Save pipeline stats
            stats_file = self.output_dir / "unified_rag_pipeline_stats.json"
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(pipeline_stats, f, indent=2, ensure_ascii=False)
            
            logging.info("Unified RAG Pipeline completed successfully!")
            logging.info(f"Total duration: {pipeline_stats['total_duration']}")
            logging.info(f"Stats saved to: {stats_file}")
            
            return pipeline_stats
            
        except Exception as e:
            logging.error(f"Pipeline failed: {e}")
            pipeline_stats["error"] = str(e)
            pipeline_stats["status"] = "failed"
            return pipeline_stats
    
    def search(self, query: str, retriever_type: str = "hybrid", top_k: int = 10) -> List[Dict[str, Any]]:
        """Search for documents using the specified retriever."""
        if not self.retriever_manager:
            logging.error("Retriever manager not initialized. Run the pipeline first.")
            return []
        
        return self.retriever_manager.search(query, retriever_type, top_k)
    
    def search_images(self, query: str, retriever_type: str = "colqwen", top_k: int = 10) -> List[Dict[str, Any]]:
        """Search for relevant PDF pages using image-based retrieval."""
        if not self.image_retriever_manager:
            logging.error("Image retriever manager not initialized. Enable --image-retrieval.")
            return []
        
        return self.image_retriever_manager.search(query, retriever_type, top_k)
    
    def generate_answer(self, query: str, retrieved_docs: List[Dict[str, Any]], include_citations: bool = True) -> Dict[str, Any]:
        """
        Generate an answer from retrieved documents using the LLM.
        
        Args:
            query: The user's question
            retrieved_docs: List of retrieved documents from search()
            include_citations: Whether to include citations in the answer
            
        Returns:
            Dict with 'answer', 'citations', 'files', 'contents'
        """
        if not self.generator:
            logging.error("Generator not initialized. Check API key configuration.")
            return {
                "answer": "Generation not available. Please check API key configuration.",
                "error": "Generator not initialized"
            }
        
        return self.generator.generate(query, retrieved_docs, include_citations)
    
    def query(
        self, 
        question: str, 
        retriever_type: str = None, 
        top_k: int = None, 
        generate: bool = True,
        use_reranker: bool = None,
        rag_mode: str = None
    ) -> Dict[str, Any]:
        """
        Complete RAG query: retrieve relevant documents and optionally generate an answer.
        
        Args:
            question: The user's question
            retriever_type: Which retriever to use (bm25, dense, hybrid) - uses config default if None
            top_k: Number of documents to retrieve - uses config default if None
            generate: Whether to generate an answer using LLM
            use_reranker: Whether to use reranker (uses config if None)
            rag_mode: Override RAG mode ("text", "image", "both") - uses config if None
            
        Returns:
            Dict with 'question', 'retrieved_docs', 'image_docs', and optionally 'answer'
        """
        # Use defaults from config
        retriever_type = retriever_type or self.config.default_retriever
        top_k = top_k or self.config.retrieval_top_k
        use_reranker = use_reranker if use_reranker is not None else self.config.enable_reranker
        rag_mode = rag_mode or self.config.rag_mode
        
        # Log query
        self.retrieval_logger.info(f"Query: {question[:100]}...")
        self.retrieval_logger.info(f"RAG Mode: {rag_mode}, Retriever: {retriever_type}, Top-K: {top_k}")
        
        result = {
            "question": question,
            "rag_mode": rag_mode,
            "retriever_type": retriever_type,
            "text_docs": [],
            "image_docs": [],
            "retrieved_docs": [],  # Combined for generation
        }
        
        # Text-based retrieval
        if rag_mode in ["text", "both"] and self.retriever_manager:
            text_docs = self.retriever_manager.search(
                question, 
                retriever_type, 
                top_k,
                use_reranker=use_reranker
            )
            result["text_docs"] = text_docs
            result["num_text_results"] = len(text_docs)
            self.retrieval_logger.info(f"Text retrieval: {len(text_docs)} chunks")
            
            # Log text results
            for i, doc in enumerate(text_docs[:5], 1):
                self.retrieval_logger.info(f"  [{i}] {doc.get('id', 'N/A')} (score: {doc.get('score', 0):.4f})")
        
        # Image-based retrieval
        if rag_mode in ["image", "both"] and self.image_retriever_manager:
            image_top_k = self.config.image_retrieval_top_k
            image_docs = self.search_images(question, "colqwen", image_top_k)
            result["image_docs"] = image_docs
            result["num_image_results"] = len(image_docs)
            self.retrieval_logger.info(f"Image retrieval: {len(image_docs)} pages")
            
            # Log image results
            for i, doc in enumerate(image_docs[:5], 1):
                self.retrieval_logger.info(f"  [IMG {i}] {doc.get('source', 'N/A')} p.{doc.get('page', '?')} (score: {doc.get('score', 0):.4f})")
        
        # Combine results for generation (text docs first, then image docs)
        result["retrieved_docs"] = result["text_docs"] + result["image_docs"]
        result["num_results"] = len(result["retrieved_docs"])
        
        # Generate answer if requested and generator available
        if generate and self.generator:
            self.generation_logger.info(f"Generating answer for: {question[:100]}...")
            self.generation_logger.info(f"Context: {len(result['text_docs'])} text chunks, {len(result['image_docs'])} images")
            
            generation_result = self.generate_answer(question, result["retrieved_docs"])
            result.update(generation_result)
            
            self.generation_logger.info(f"Answer generated ({len(generation_result.get('answer', ''))} chars)")
        
        return result
    
    def query_combined(
        self, 
        question: str, 
        text_top_k: int = 5, 
        image_top_k: int = 3,
        generate: bool = True
    ) -> Dict[str, Any]:
        """
        Query using both text and image retrieval pipelines.
        
        This is a convenience method that always uses both pipelines regardless of config.
        
        Args:
            question: The user's question
            text_top_k: Number of text chunks to retrieve
            image_top_k: Number of image pages to retrieve
            generate: Whether to generate an answer
            
        Returns:
            Combined results from both pipelines
        """
        return self.query(
            question=question,
            top_k=text_top_k,
            generate=generate,
            rag_mode="both"
        )
    
    def run_test_mode(self, test_query: Optional[str] = None, interactive: bool = False) -> Dict[str, Any]:
        """Run test mode for interactive querying of processed documents."""
        logging.info("Starting Test Mode...")
        
        # Check if index or processed documents exist
        processed_docs = self.processing_output_dir / "stage4_rag_ready"
        if not self.retrieval_output_dir.exists() and not (processed_docs.exists() and any(processed_docs.iterdir())):
            error_msg = (
                f"Neither index nor processed documents found.\n"
                f"  Index: {self.retrieval_output_dir}\n"
                f"  Documents: {processed_docs}\n"
                f"Please run the pipeline in 'full' or 'processing' mode first."
            )
            logging.error(error_msg)
            print(f"❌ Error: {error_msg}")
            return {"status": "failed", "error": error_msg}
        
        # Setup text retrievers if needed (will load existing index if available, otherwise build from documents)
        setup_stats = {}
        if self.config.rag_mode in ["text", "both"]:
            setup_stats = self.setup_retrievers(load_existing=True)
            if setup_stats.get("status") == "skipped" or "error" in setup_stats:
                logging.error("Failed to setup text retrievers for test mode")
                return {"status": "failed", "error": "Text retriever setup failed"}
        
        # Setup image retrievers if enabled
        image_setup_stats = {}
        if self.config.enable_image_retrieval:
            image_setup_stats = self.setup_image_retrievers(load_existing=True)
        
        test_results = {
            "mode": "test",
            "setup_stats": setup_stats,
            "image_setup_stats": image_setup_stats,
            "queries_tested": [],
            "available_retrievers": self.retriever_manager.get_available_retrievers() if self.retriever_manager else [],
            "available_image_retrievers": self.image_retriever_manager.get_available_retrievers() if self.image_retriever_manager else []
        }
        
        try:
            # Try to print with emoji support, fallback to ASCII if it fails
            print("\n" + "="*60)
            print("🧪 RAG PIPELINE TEST MODE")
            print("="*60)
            if setup_stats.get("index_loaded"):
                print(f"✅ Loaded existing index from: {setup_stats.get('index_dir', 'N/A')}")
            elif setup_stats.get("index_built"):
                print(f"🔨 Built new index (saved to: {setup_stats.get('index_dir', 'N/A')})")
            
            # Show chunk info (only if text retrieval was used)
            if setup_stats:
                chunk_count = setup_stats.get('chunk_count', setup_stats.get('document_count', 'N/A'))
                raw_doc_count = setup_stats.get('raw_doc_count', 'N/A')
                print(f"📚 Loaded {raw_doc_count} documents → {chunk_count} chunks")
                print(f"📏 Chunk config: size={self.config.chunk_size}, overlap={self.config.chunk_overlap}")
            print(f"🔍 Text retrievers: {', '.join(test_results['available_retrievers']) if test_results['available_retrievers'] else 'None'}")
            if test_results['available_image_retrievers']:
                print(f"🖼️ Image retrievers: {', '.join(test_results['available_image_retrievers'])}")
                print(f"   Pages indexed: {image_setup_stats.get('page_count', 'N/A')}")
            print(f"📊 Top-K: {self.config.retrieval_top_k} chunks per query")
            if self.generator:
                print(f"🤖 Generator: {self.config.generation_config.provider}/{self.config.generation_config.model_name}")
            else:
                print(f"⚠️ Generator: Not available (retrieval only)")
            print("="*60)
        except UnicodeEncodeError:
            # Fallback to ASCII output on Windows
            print("\n" + "="*60)
            print("[*] RAG PIPELINE TEST MODE")
            print("="*60)
            if setup_stats.get("index_loaded"):
                print(f"[OK] Loaded existing index from: {setup_stats.get('index_dir', 'N/A')}")
            elif setup_stats.get("index_built"):
                print(f"[BUILD] Built new index (saved to: {setup_stats.get('index_dir', 'N/A')})")
            
            if setup_stats:
                chunk_count = setup_stats.get('chunk_count', setup_stats.get('document_count', 'N/A'))
                raw_doc_count = setup_stats.get('raw_doc_count', 'N/A')
                print(f"[INFO] Loaded {raw_doc_count} documents -> {chunk_count} chunks")
                print(f"[INFO] Chunk config: size={self.config.chunk_size}, overlap={self.config.chunk_overlap}")
            print(f"[SEARCH] Text retrievers: {', '.join(test_results['available_retrievers']) if test_results['available_retrievers'] else 'None'}")
            if test_results['available_image_retrievers']:
                print(f"[IMAGE] Image retrievers: {', '.join(test_results['available_image_retrievers'])}")
                print(f"        Pages indexed: {image_setup_stats.get('page_count', 'N/A')}")
            print(f"[CONFIG] Top-K: {self.config.retrieval_top_k} chunks per query")
            if self.generator:
                print(f"[GEN] Generator: {self.config.generation_config.provider}/{self.config.generation_config.model_name}")
            else:
                print(f"[WARN] Generator: Not available (retrieval only)")
            print("="*60)
        
        if test_query:
            # Single query test with generation
            print(f"\n[QUERY] Testing query: '{test_query}'")
            query_results = self._test_single_query_with_generation(test_query)
            test_results["queries_tested"].append(query_results)
            
        elif interactive:
            # Interactive mode with generation
            test_results["queries_tested"] = self._run_interactive_test()
            
        else:
            # Default demo queries (retrieval only for speed)
            demo_queries = [
                "What is the main topic of this document?",
                "Can you find information about methodology?",
                "What are the key findings or results?"
            ]
            
            print("\n🎯 Running demo queries (retrieval only)...")
            for query in demo_queries:
                print(f"\n🔍 Testing: '{query}'")
                query_results = self._test_single_query(query)
                test_results["queries_tested"].append(query_results)
        
        print("\n" + "="*60)
        print("✅ Test mode completed!")
        print("="*60)
        
        return test_results
    
    def _test_single_query(self, query: str) -> Dict[str, Any]:
        """Test a single query against all available retrievers (retrieval only)."""
        top_k = self.config.retrieval_top_k
        query_results = {
            "query": query,
            "top_k": top_k,
            "retriever_results": {}
        }
        
        for retriever_type in self.retriever_manager.get_available_retrievers():
            try:
                results = self.retriever_manager.search(query, retriever_type, top_k=top_k)
                query_results["retriever_results"][retriever_type] = results
                
                print(f"\n  📊 {retriever_type.upper()} Results (top {top_k}):")
                if results:
                    for i, result in enumerate(results, 1):
                        print(f"    {i}. {result['id']} (score: {result['score']:.4f})")
                        # Show first 100 chars of text
                        preview = result['text'][:100] + "..." if len(result['text']) > 100 else result['text']
                        print(f"       {preview}")
                else:
                    print("    No results found")
                    
            except Exception as e:
                print(f"    ❌ Error with {retriever_type}: {e}")
                query_results["retriever_results"][retriever_type] = {"error": str(e)}
        
        return query_results
    
    def _test_single_query_with_generation(self, query: str, retriever_type: str = "hybrid") -> Dict[str, Any]:
        """Test a single query with retrieval and answer generation."""
        top_k = self.config.retrieval_top_k
        query_results = {
            "query": query,
            "retriever_type": retriever_type,
            "top_k": top_k,
            "rag_mode": self.config.rag_mode
        }
        
        try:
            results = []
            image_results = []
            
            # Text-based retrieval (if enabled)
            if self.config.rag_mode in ["text", "both"] and self.retriever_manager:
                print(f"\n  📊 Retrieving with {retriever_type.upper()} (top {top_k})...")
                results = self.retriever_manager.search(query, retriever_type, top_k=top_k)
                query_results["retrieved_docs"] = results
                
                if results:
                    print(f"  ✅ Found {len(results)} relevant documents")
                    
                    # Check if this is hybrid results (has retrieval_info)
                    has_hybrid_info = any(r.get('retrieval_info') for r in results)
                    if has_hybrid_info:
                        print(f"  📌 Legend: 🔗=Both BM25+Dense, 📝=BM25 only, 🧠=Dense only")
                    
                    # Show results with hybrid fusion details if available
                    for i, result in enumerate(results, 1):
                        retrieval_info = result.get('retrieval_info', {})
                        if retrieval_info:
                            # Hybrid result - show BM25 and Dense ranks
                            bm25_rank = retrieval_info.get('bm25_rank', '-')
                            dense_rank = retrieval_info.get('dense_rank', '-')
                            in_both = retrieval_info.get('in_both', False)
                            source_indicator = "🔗" if in_both else ("📝" if retrieval_info.get('in_bm25') else "🧠")
                            print(f"    {i}. {result['id']} (RRF: {result['score']:.4f}) {source_indicator}")
                            print(f"       BM25 rank: {bm25_rank}, Dense rank: {dense_rank}")
                        else:
                            print(f"    {i}. {result['id']} (score: {result['score']:.4f})")
                else:
                    print("  ⚠️ No text results found")
            
            # Image-based retrieval (if enabled)
            if self.config.rag_mode in ["image", "both"] and self.image_retriever_manager:
                try:
                    print(f"\n  🖼️ Image Retrieval (ColQwen) - top {top_k} pages:")
                except UnicodeEncodeError:
                    print(f"\n  [IMG] Image Retrieval (ColQwen) - top {top_k} pages:")
                image_results = self.search_images(query, "colqwen", top_k)
                query_results["image_retrieved_docs"] = image_results
                
                if image_results:
                    try:
                        print(f"  ✅ Found {len(image_results)} relevant image pages")
                    except UnicodeEncodeError:
                        print(f"  [OK] Found {len(image_results)} relevant image pages")
                    for i, result in enumerate(image_results, 1):
                        print(f"    {i}. {result['source']} page {result['page']} (score: {result['score']:.4f})")
                else:
                    print("    No image results found")
            
            # Combine results for generation
            all_results = results + image_results
            if not all_results:
                try:
                    print("  ⚠️ No results found from any retrieval method")
                except UnicodeEncodeError:
                    print("  [WARN] No results found from any retrieval method")
                query_results["answer"] = "No relevant documents or images found to answer the question."
                return query_results
            
            # Generate answer if generator available
            if self.generator:
                try:
                    print(f"\n  🤖 Generating answer...")
                except UnicodeEncodeError:
                    print(f"\n  [GEN] Generating answer...")
                generation_result = self.generator.generate(query, all_results)
                query_results.update(generation_result)
                
                # Display formatted answer
                try:
                    print("\n" + self.generator.format_answer_for_display(generation_result))
                except UnicodeEncodeError:
                    # Fallback: print a simpler version without emoji
                    print(f"\n{'='*60}")
                    print("ANSWER")
                    print(f"{'='*60}")
                    print(generation_result.get("answer", "No answer generated"))
                    if generation_result.get("files"):
                        print(f"\n{'-'*60}")
                        print("FILES")
                        print(f"{'-'*60}")
                        for file_num, filename in sorted(generation_result["files"].items()):
                            print(f"[{file_num}] {filename}")
                    if generation_result.get("contents"):
                        print(f"\n{'-'*60}")
                        print("CONTENTS")
                        print(f"{'-'*60}")
                        for citation_id, content in sorted(generation_result["contents"].items()):
                            text_preview = content['text'][:100] + "..." if len(content['text']) > 100 else content['text']
                            print(f"{citation_id} {text_preview}")
                            print(f"    └─ {content['filename']} (score: {content['score']:.4f})")
                    print(f"{'='*60}")
            else:
                try:
                    print("\n  ⚠️ Generator not available. Showing retrieval results only.")
                except UnicodeEncodeError:
                    print("\n  [WARN] Generator not available. Showing retrieval results only.")
                
        except Exception as e:
            try:
                print(f"  ❌ Error: {e}")
            except UnicodeEncodeError:
                print(f"  [ERR] Error: {e}")
            query_results["error"] = str(e)
        
        return query_results
    
    def _run_interactive_test(self) -> List[Dict[str, Any]]:
        """Run interactive testing mode with generation."""
        print("\n🎮 Interactive Test Mode")
        print("Enter your queries to test the RAG system.")
        print("Commands:")
        print("  - Type your question to get an answer")
        print("  - Type 'retrieval' to switch to retrieval-only mode")
        print("  - Type 'generation' to switch to full RAG mode (default)")
        print("  - Type 'quit' or 'exit' to finish")
        print("-" * 40)
        
        queries_tested = []
        use_generation = True  # Default to full RAG with generation
        
        while True:
            try:
                mode_indicator = "🤖 RAG" if use_generation else "🔍 Retrieval"
                query = input(f"\n[{mode_indicator}] Enter query: ").strip()
                
                if query.lower() in ['quit', 'exit', 'q']:
                    break
                
                if query.lower() == 'retrieval':
                    use_generation = False
                    print("✅ Switched to retrieval-only mode")
                    continue
                    
                if query.lower() == 'generation':
                    use_generation = True
                    print("✅ Switched to full RAG mode (with generation)")
                    continue
                
                if not query:
                    continue
                
                print(f"\n🔍 Processing: '{query}'")
                
                if use_generation:
                    query_results = self._test_single_query_with_generation(query)
                else:
                    query_results = self._test_single_query(query)
                    
                queries_tested.append(query_results)
                
            except KeyboardInterrupt:
                print("\n\n👋 Exiting interactive mode...")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        return queries_tested


def main():
    """Main entry point for the unified RAG pipeline."""
    parser = argparse.ArgumentParser(description="Unified RAG Pipeline")
    
    # Required arguments
    parser.add_argument("--input", "-i", required=True, help="Input directory containing documents")
    parser.add_argument("--output", "-o", required=True, help="Output directory for processed results")
    
    # Pipeline mode
    parser.add_argument("--mode", choices=["processing", "retrieval", "full", "test"], default="full",
                       help="Pipeline mode: processing only, retrieval only, full pipeline, or test mode")
    
    # Processing options
    parser.add_argument("--skip-normalization", action="store_true", help="Skip document normalization")
    parser.add_argument("--skip-media", action="store_true", help="Skip media processing")
    parser.add_argument("--fast-mode", action="store_true", help="Fast processing mode (disable VLM)")
    parser.add_argument("--no-gpu", action="store_true", help="Disable GPU acceleration")
    
    # Text retrieval options
    parser.add_argument("--retrievers", nargs="+", 
                       choices=["bm25", "dense", "hybrid"],
                       default=["bm25", "dense", "hybrid"],
                       help="Text retrieval methods to use")
    
    # Image retrieval options
    parser.add_argument("--image-retrieval", action="store_true", 
                       help="Enable image-based retrieval (ColQwen)")
    parser.add_argument("--image-retrievers", nargs="+",
                       choices=["colqwen"],
                       default=["colqwen"],
                       help="Image retrieval methods to use")
    parser.add_argument("--colqwen-model", default=None,
                       help="ColQwen model to use (defaults to YAML config, or vidore/colqwen2-v1.0)")
    parser.add_argument("--colqwen-quantization", choices=["none", "4bit", "8bit"], default="none",
                       help="ColQwen quantization (requires bitsandbytes): none, 4bit, 8bit")
    parser.add_argument("--colqwen-dtype", choices=["bfloat16", "float16", "float32"], default=None,
                       help="ColQwen data type (defaults to YAML config, or bfloat16)")
    parser.add_argument("--pdf-dpi", type=int, default=None,
                       help="DPI for PDF to image conversion (defaults to YAML config, or 150)")
    
    # Configuration file option
    parser.add_argument("--config", "-c", default="config/default.yaml", help="Path to YAML configuration file")
    
    # RAG mode options
    parser.add_argument("--rag-mode", choices=["text", "image", "both"], default="text",
                       help="RAG mode: text-only, image-only, or both combined")
    
    # Reranker options
    parser.add_argument("--reranker", choices=["bge-large", "minilm-l12", "bge-base", "none"], 
                       default="none", help="Reranker model to use (default: none)")
    
    # Evaluation options
    parser.add_argument("--evaluate", action="store_true", help="Enable retrieval evaluation")
    parser.add_argument("--queries", help="Path to queries file for evaluation (JSON/JSONL)")
    
    # Test mode options
    parser.add_argument("--test-query", help="Single query for testing (use with --mode test)")
    parser.add_argument("--interactive", action="store_true", help="Interactive testing mode")
    
    # Retrieval options
    parser.add_argument("--top-k", type=int, default=10, help="Number of text chunks to retrieve per query (default: 10)")
    parser.add_argument("--image-top-k", type=int, default=5, help="Number of image pages to retrieve per query (default: 5)")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Chunk size in characters (default: 1000)")
    parser.add_argument("--chunk-overlap", type=int, default=200, help="Chunk overlap in characters (default: 200)")
    parser.add_argument("--no-chunking", action="store_true", help="Disable document chunking (use full documents)")
    
    # Logging options
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                       default="INFO", help="Logging level")
    parser.add_argument("--no-log-file", action="store_true", help="Disable logging to file")
    
    # Generation options
    parser.add_argument("--no-generation", action="store_true", help="Disable answer generation (retrieval only)")
    parser.add_argument("--llm-provider", choices=["openai", "azure", "ollama"], default="openai",
                       help="LLM provider for answer generation")
    parser.add_argument("--llm-model", default="gpt-4o-mini", help="LLM model name")
    parser.add_argument("--api-key", help="API key for LLM provider (or use OPENAI_API_KEY env var)")
    
    args = parser.parse_args()
    
    # Load YAML config if provided (will be overridden by CLI args)
    yaml_config = {}
    if args.config:
        try:
            config_path = Path(args.config)
            logging.info(f"[DEBUG] Initial config path: {config_path}, absolute: {config_path.is_absolute()}, exists: {config_path.exists()}")
            
            # If relative path and doesn't exist, try from script directory
            if not config_path.is_absolute() and not config_path.exists():
                script_dir = Path(__file__).parent.parent  # Go up from src/ to project root
                config_path = script_dir / args.config
                logging.info(f"[DEBUG] Adjusted config path to: {config_path}, exists: {config_path.exists()}")
            
            if config_path.exists():
                with open(config_path, 'r') as f:
                    yaml_config = yaml.safe_load(f) or {}
                logging.info(f"[OK] Loaded YAML config from: {config_path}")
                logging.info(f"[DEBUG] yaml_config keys: {yaml_config.keys()}")
            else:
                logging.warning(f"[ERROR] Config file not found: {config_path}")
        except Exception as e:
            logging.warning(f"Failed to load config file {args.config}: {e}")
    
    # Create configuration
    processing_config = PipelineConfig(
        enable_normalization=not args.skip_normalization,
        enable_media_processing=not args.skip_media,
        enable_document_processing=True,
        use_gpu=not args.no_gpu
    )
    
    if args.fast_mode:
        processing_config.document_config.enable_vlm = False
    
    # Create generation config
    generation_config = GenerationConfig(
        provider=args.llm_provider,
        model_name=args.llm_model,
        api_key=args.api_key,
        enable_citations=True
    )
    
    # Determine reranker model
    reranker_model = None if args.reranker == "none" else args.reranker
    
    # Get image_retrieval from YAML if not specified in CLI
    # image_retrieval is enabled by --image-retrieval flag OR if rag_mode is image/both
    yaml_image_retrieval_enabled = yaml_config.get('image_retrieval', {}).get('enabled', False)
    enable_image_retrieval = args.image_retrieval or args.rag_mode in ["image", "both"] or yaml_image_retrieval_enabled
    
    # Get colqwen config from YAML if provided (CLI args override YAML)
    yaml_colqwen = yaml_config.get('image_retrieval', {}).get('colqwen', {})
    colqwen_model = args.colqwen_model if args.colqwen_model is not None else yaml_colqwen.get('model', 'vidore/colqwen2-v1.0')
    colqwen_dtype = args.colqwen_dtype if args.colqwen_dtype is not None else yaml_colqwen.get('dtype', 'bfloat16')
    colqwen_quantization = args.colqwen_quantization if args.colqwen_quantization != "none" else yaml_colqwen.get('quantization', None)
    pdf_dpi = args.pdf_dpi if args.pdf_dpi is not None else yaml_colqwen.get('pdf_dpi', 150)
    
    # Debug logging for quantization config
    logging.info(f"[DEBUG] yaml_colqwen keys: {yaml_colqwen.keys()}, colqwen config: {yaml_colqwen}")
    logging.info(f"[DEBUG] args.colqwen_model={args.colqwen_model}, yaml model={yaml_colqwen.get('model')}, final colqwen_model={colqwen_model}")
    logging.info(f"[DEBUG] args.colqwen_quantization={args.colqwen_quantization}, yaml quantization={yaml_colqwen.get('quantization')}, final colqwen_quantization={colqwen_quantization}")
    
    config = UnifiedRAGConfig(
        enable_processing=(args.mode in ["processing", "full"]),
        enable_retrieval=(args.mode in ["retrieval", "full", "test"]),
        enable_generation=not args.no_generation,
        enable_evaluation=args.evaluate,
        processing_config=processing_config,
        # RAG mode
        rag_mode=args.rag_mode,
        # Text retrieval
        retrieval_methods=args.retrievers,
        retrieval_top_k=args.top_k,
        default_retriever="hybrid",
        # Reranker
        enable_reranker=reranker_model is not None,
        reranker_model=reranker_model,
        # Chunking
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        enable_chunking=not args.no_chunking,
        # Image retrieval - use merged YAML + CLI config
        enable_image_retrieval=enable_image_retrieval,
        image_retrieval_methods=args.image_retrievers,
        image_retrieval_top_k=args.image_top_k,
        # ColQwen configuration - use merged YAML + CLI config
        colqwen_model=colqwen_model,
        colqwen_dtype=colqwen_dtype,
        colqwen_quantization=colqwen_quantization,
        colqwen_pdf_dpi=pdf_dpi,
        # Generation
        generation_config=generation_config,
        # Logging
        log_to_file=not args.no_log_file,
        log_level=args.log_level
    )
    
    # Load queries if provided
    queries = None
    if args.queries:
        queries_path = Path(args.queries)
        if queries_path.exists():
            with open(queries_path, 'r', encoding='utf-8') as f:
                if queries_path.suffix == '.jsonl':
                    queries = [json.loads(line) for line in f if line.strip()]
                else:
                    queries = json.load(f)
        else:
            print(f"Warning: Queries file not found: {queries_path}")
    
    # Initialize pipeline
    pipeline = UnifiedRAGPipeline(
        input_dir=args.input,
        output_dir=args.output,
        config=config
    )
    
    # Run based on mode
    if args.mode == "test":
        # Test mode - interactive querying
        results = pipeline.run_test_mode(
            test_query=args.test_query,
            interactive=args.interactive
        )
    else:
        # Normal pipeline modes
        results = pipeline.run(queries=queries)
    
    if results.get("status") == "failed":
        sys.exit(1)
    
    if args.mode == "test":
        print(f"[OK] Test results saved to: {args.output}")
    else:
        print("[OK] Unified RAG Pipeline completed successfully!")
        print(f"[OK] Results saved to: {args.output}")


if __name__ == "__main__":
    main()
