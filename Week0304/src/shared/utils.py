"""
Shared utilities for RAG pipeline comparison
"""
import time
import psutil
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import numpy as np
from sentence_transformers import SentenceTransformer

# PDF processing
try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# Use standard logging if loguru is not available
try:
    from loguru import logger
    LOGURU_AVAILABLE = True
except ImportError:
    LOGURU_AVAILABLE = False
    logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Container for performance metrics"""
    embedding_time: float = 0.0
    indexing_time: float = 0.0
    retrieval_time: float = 0.0
    generation_time: float = 0.0
    total_time: float = 0.0
    memory_usage: float = 0.0
    retrieval_accuracy: float = 0.0
    answer_quality: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class PerformanceTracker:
    """Tracks performance metrics for RAG operations"""
    
    def __init__(self, method_name: str):
        self.method_name = method_name
        self.metrics = PerformanceMetrics()
        self.start_time = None
        self.process = psutil.Process()
        
    def start_timer(self):
        """Start timing an operation"""
        self.start_time = time.time()
        
    def stop_timer(self, metric_name: str):
        """Stop timer and record the metric"""
        if self.start_time is None:
            return
        elapsed = time.time() - self.start_time
        setattr(self.metrics, metric_name, elapsed)
        self.start_time = None
        
    def reset_metrics(self):
        """Reset all metrics to initial state"""
        self.metrics = PerformanceMetrics()
        self.start_time = None
        
    def record_memory_usage(self):
        """Record current memory usage"""
        memory_info = self.process.memory_info()
        self.metrics.memory_usage = memory_info.rss / 1024 / 1024  # MB
        
    def save_metrics(self, output_path: str):
        """Save metrics to JSON file"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump({
                'method': self.method_name,
                'metrics': self.metrics.to_dict()
            }, f, indent=2)

class DocumentProcessor:
    """Utility class for document processing"""
    
    @staticmethod
    def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
        """Chunk text into smaller pieces with overlap"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Find the end of the chunk
            end = start + chunk_size
            
            # If this isn't the last chunk, try to break at a sentence or word boundary
            if end < len(text):
                # Look for sentence boundaries first
                for boundary in ['. ', '! ', '? ']:
                    last_boundary = text.rfind(boundary, start, end)
                    if last_boundary != -1:
                        end = last_boundary + len(boundary)
                        break
                else:
                    # Fall back to word boundary
                    last_space = text.rfind(' ', start, end)
                    if last_space != -1:
                        end = last_space
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Calculate next start position with overlap
            start = end - chunk_overlap
            if start >= len(text):
                break
                
        return chunks
    
    @staticmethod
    def load_documents_from_directory(directory: str) -> List[Dict[str, str]]:
        """Load all supported documents from a directory"""
        from tqdm import tqdm
        
        documents = []
        data_dir = Path(directory)
        
        # Supported file extensions
        supported_extensions = ['.txt', '.pdf']
        
        # Find all supported files first
        all_files = []
        for ext in supported_extensions:
            all_files.extend(list(data_dir.rglob(f"*{ext}")))
        
        print(f"Found {len(all_files)} supported files in {directory}")
        
        # Process files with progress bar
        for file_path in tqdm(all_files, desc="Loading documents", unit="file"):
            try:
                content = ""
                print(f"Processing: {file_path.name}")
                
                if file_path.suffix.lower() == '.txt':
                    # Handle text files
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    print(f"  → Loaded {len(content)} characters from text file")
                
                elif file_path.suffix.lower() == '.pdf' and PDF_AVAILABLE:
                    # Handle PDF files
                    print(f"  → Reading PDF file...")
                    reader = PdfReader(str(file_path))
                    content_parts = []
                    
                    total_pages = len(reader.pages)
                    print(f"  → PDF has {total_pages} pages")
                    
                    for i, page in enumerate(tqdm(reader.pages, desc=f"  Processing {file_path.name}", leave=False, unit="page")):
                        page_text = page.extract_text()
                        if page_text.strip():
                            content_parts.append(page_text)
                        
                        # Progress update every 10 pages
                        if (i + 1) % 10 == 0 or i == total_pages - 1:
                            print(f"    → Processed {i + 1}/{total_pages} pages")
                    
                    content = "\n\n".join(content_parts)
                    print(f"  → Extracted {len(content)} characters from {len(content_parts)} pages")
                
                if content.strip():  # Only add if content is not empty
                    documents.append({
                        'content': content,
                        'source': str(file_path),
                        'filename': file_path.name
                    })
                    print(f"  ✓ Successfully loaded {file_path.name}")
                else:
                    print(f"  ⚠ No content extracted from {file_path.name}")
                    
            except Exception as e:
                print(f"  ❌ Error loading {file_path}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n📚 Successfully loaded {len(documents)} documents")
        return documents

class EmbeddingGenerator:
    """Utility class for generating embeddings"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        
    def load_model(self):
        """Load the embedding model"""
        if self.model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            
    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a list of texts"""
        self.load_model()
        logger.info(f"Generating embeddings for {len(texts)} texts")
        embeddings = self.model.encode(texts, show_progress_bar=True)
        return embeddings

class QueryEvaluator:
    """Utility class for evaluating query responses"""
    
    @staticmethod
    def calculate_retrieval_accuracy(retrieved_docs: List[str], query: str) -> float:
        """Calculate retrieval accuracy based on query-document relevance"""
        if not retrieved_docs or not query:
            return 0.0
        
        # Simple relevance scoring: check if key query terms appear in retrieved docs
        query_terms = set(query.lower().split())
        relevant_docs = 0
        
        for doc in retrieved_docs:
            doc_terms = set(doc.lower().split())
            # Consider a document relevant if it contains at least 30% of query terms
            overlap = len(query_terms.intersection(doc_terms))
            if overlap >= len(query_terms) * 0.3:
                relevant_docs += 1
        
        return relevant_docs / len(retrieved_docs) if retrieved_docs else 0.0
    
    @staticmethod
    def calculate_answer_quality(answer: str, query: str = None, retrieved_docs: List[str] = None) -> float:
        """Enhanced answer quality evaluation"""
        if not answer or len(answer.strip()) < 10:
            return 0.0
        
        scores = []
        
        # 1. Length and completeness (30% weight)
        length_score = min(len(answer) / 150, 1.0)  # Normalized to 150 chars
        completeness_score = 1.0 if answer.strip().endswith(('.', '!', '?')) else 0.7
        structure_score = (length_score + completeness_score) / 2
        scores.append(structure_score * 0.3)
        
        # 2. Query relevance (40% weight)
        query_relevance = 0.5  # Default
        if query:
            query_terms = set(query.lower().split())
            answer_terms = set(answer.lower().split())
            if query_terms:
                query_relevance = len(query_terms.intersection(answer_terms)) / len(query_terms)
        scores.append(query_relevance * 0.4)
        
        # 3. Grounding in retrieved documents (30% weight)
        grounding_score = 0.5  # Default
        if retrieved_docs:
            # Check if answer contains information from retrieved docs
            answer_lower = answer.lower()
            grounded_terms = 0
            total_terms = 0
            
            for doc in retrieved_docs:
                doc_terms = doc.lower().split()
                total_terms += len(doc_terms)
                for term in doc_terms:
                    if len(term) > 3 and term in answer_lower:  # Skip short words
                        grounded_terms += 1
            
            if total_terms > 0:
                grounding_score = min(grounded_terms / (total_terms * 0.1), 1.0)  # Normalize
        scores.append(grounding_score * 0.3)
        
        return sum(scores)
    
    @staticmethod
    def evaluate_query_response(query: str, answer: str, retrieved_docs: List[str]) -> Dict[str, float]:
        """Comprehensive evaluation of a query response"""
        retrieval_accuracy = QueryEvaluator.calculate_retrieval_accuracy(retrieved_docs, query)
        answer_quality = QueryEvaluator.calculate_answer_quality(answer, query, retrieved_docs)
        
        return {
            'retrieval_accuracy': retrieval_accuracy,
            'answer_quality': answer_quality
        }

def setup_logging(method_name: str, log_dir: str = "./logs"):
    """Setup logging for a specific method"""
    log_path = Path(log_dir) / f"{method_name}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    if LOGURU_AVAILABLE:
        # Configure loguru
        from loguru import logger as loguru_logger
        loguru_logger.add(
            str(log_path),
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
            level="INFO",
            retention="7 days"
        )
        return loguru_logger
    else:
        # Configure standard logging
        method_logger = logging.getLogger(method_name)
        method_logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        for handler in method_logger.handlers[:]:
            method_logger.removeHandler(handler)
        
        # File handler
        file_handler = logging.FileHandler(str(log_path))
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        method_logger.addHandler(file_handler)
        method_logger.addHandler(console_handler)
        
        return method_logger