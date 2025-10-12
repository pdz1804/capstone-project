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
    vector_processing_time: float = 0.0  # Combined embedding + indexing time
    retrieval_time: float = 0.0
    generation_time: float = 0.0
    total_time: float = 0.0
    memory_usage: float = 0.0
    relevance: float = 0.0
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
                    # Handle PDF files - optimized for speed
                    print(f"  → Reading PDF file...")
                    reader = PdfReader(str(file_path))
                    content_parts = []
                    
                    total_pages = len(reader.pages)
                    print(f"  → PDF has {total_pages} pages - extracting text...")
                    
                    # Fast processing without nested progress bars
                    for i, page in enumerate(reader.pages):
                        try:
                            page_text = page.extract_text()
                            if page_text.strip():
                                content_parts.append(page_text)
                        except Exception as e:
                            print(f"    ⚠ Error on page {i+1}: {e}")
                            continue
                        
                        # Only print progress for large PDFs every 20 pages
                        if total_pages > 20 and (i + 1) % 20 == 0:
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
    """Utility class for evaluating query responses using both manual and LLM-based metrics"""
    
    def __init__(self, llm_provider: str = "openai"):
        """Initialize evaluator with LLM provider for advanced evaluation"""
        self.llm_provider = llm_provider
        self._llm_client = None
    
    def _get_llm_client(self):
        """Initialize LLM client for evaluation"""
        if self._llm_client is None:
            if self.llm_provider == "openai":
                from openai import OpenAI
                from shared.config import Config
                self._llm_client = OpenAI(api_key=Config.LLM_CONFIGS["openai"].api_key)
        return self._llm_client
    
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
    def calculate_precision_at_k(retrieved_docs: List[str], relevant_docs: List[str], k: int = None) -> float:
        """Calculate Precision@K metric"""
        if k is None:
            k = len(retrieved_docs)
        
        retrieved_k = retrieved_docs[:k]
        if not retrieved_k:
            return 0.0
        
        relevant_retrieved = len([doc for doc in retrieved_k if doc in relevant_docs])
        return relevant_retrieved / len(retrieved_k)
    
    @staticmethod
    def calculate_recall_at_k(retrieved_docs: List[str], relevant_docs: List[str], k: int = None) -> float:
        """Calculate Recall@K metric"""
        if not relevant_docs:
            return 0.0
        
        if k is None:
            k = len(retrieved_docs)
        
        retrieved_k = retrieved_docs[:k]
        relevant_retrieved = len([doc for doc in retrieved_k if doc in relevant_docs])
        return relevant_retrieved / len(relevant_docs)
    
    @staticmethod
    def calculate_mrr(retrieved_docs: List[str], relevant_docs: List[str]) -> float:
        """Calculate Mean Reciprocal Rank (MRR)"""
        for i, doc in enumerate(retrieved_docs):
            if doc in relevant_docs:
                return 1.0 / (i + 1)
        return 0.0
    
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
    
    def evaluate_with_llm(self, query: str, answer: str, retrieved_docs: List[str]) -> Dict[str, float]:
        """Use LLM to evaluate answer quality and relevance"""
        try:
            client = self._get_llm_client()
            
            # Prepare context from retrieved documents
            context = "\n\n---\n\n".join(retrieved_docs[:3])  # Top 3 docs
            
            # Create evaluation prompt
            evaluation_prompt = f"""
You are an expert evaluator for RAG (Retrieval-Augmented Generation) systems. Please evaluate the following query-answer pair based on the provided context.

**Query:** {query}

**Retrieved Context:**
{context}

**Generated Answer:** {answer}

Please evaluate the answer on the following criteria and provide scores from 0.0 to 1.0:

1. **Relevance** (0.0-1.0): How well does the answer address the specific query?
2. **Accuracy** (0.0-1.0): How factually correct is the answer based on the provided context?
3. **Completeness** (0.0-1.0): How thoroughly does the answer cover the query topic?
4. **Grounding** (0.0-1.0): How well is the answer supported by the retrieved context?
5. **Coherence** (0.0-1.0): How well-structured and clear is the answer?

Return your evaluation as a JSON object with scores for each criterion:
{{
  "relevance": 0.0-1.0,
  "accuracy": 0.0-1.0,
  "completeness": 0.0-1.0,
  "grounding": 0.0-1.0,
  "coherence": 0.0-1.0,
  "overall": 0.0-1.0
}}
"""
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert RAG system evaluator. Provide objective, numerical scores in JSON format."},
                    {"role": "user", "content": evaluation_prompt}
                ],
                temperature=0.0,
                max_tokens=500
            )
            
            # Parse the JSON response
            import json
            evaluation_text = response.choices[0].message.content

            # Extract JSON from response (handle cases where LLM adds extra text)
            start_idx = evaluation_text.find('{')
            end_idx = evaluation_text.rfind('}') + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = evaluation_text[start_idx:end_idx]
                evaluation_scores = json.loads(json_str)
                # Only keep overall and relevance if present
                result = {}
                if 'overall' in evaluation_scores:
                    result['overall'] = float(evaluation_scores['overall'])
                if 'relevance' in evaluation_scores:
                    result['relevance'] = float(evaluation_scores['relevance'])
                return result
            else:
                raise ValueError("No valid JSON found in LLM response")
                
        except Exception as e:
            # Fallback to manual evaluation if LLM fails
            logger.warning(f"LLM evaluation failed: {e}, falling back to manual evaluation")
            manual_score = self.calculate_answer_quality(answer, query, retrieved_docs)
            return {
                "relevance": manual_score,
                "accuracy": manual_score,
                "completeness": manual_score,
                "grounding": manual_score,
                "coherence": manual_score,
                "overall": manual_score
            }
    
    @staticmethod
    def evaluate_query_response(query: str, answer: str, retrieved_docs: List[str]) -> Dict[str, float]:
        """Comprehensive evaluation of a query response with RAG metrics"""
        # Simplified evaluation: prefer LLM judgement for answer quality
        # and a relevance score that measures how on-topic the answer is to the query.
        llm_evaluator = QueryEvaluator()
        llm_scores = llm_evaluator.evaluate_with_llm(query, answer, retrieved_docs)

        # Ensure we always get valid scores (not None)
        overall = llm_scores.get('overall') if llm_scores.get('overall') is not None else 0.0
        relevance = llm_scores.get('relevance') if llm_scores.get('relevance') is not None else 0.0
        
        # If both scores are 0 (indicating LLM failure), use simple heuristics as fallback
        if overall == 0.0 and relevance == 0.0:
            # Simple fallback: if answer is not empty and not a failure message, give basic score
            if answer and len(answer.strip()) > 10 and "cannot answer" not in answer.lower() and "provided context" not in answer.lower():
                overall = 0.5  # Default reasonable score for valid answers
                relevance = 0.5  # Default reasonable score for valid answers
            # Otherwise keep them as 0.0 for truly failed responses

        return {
            'answer_quality': float(overall),
            'relevance': float(relevance)
        }
    
    def evaluate_comprehensive(self, query: str, answer: str, retrieved_docs: List[str]) -> Dict[str, float]:
        """Comprehensive evaluation combining manual metrics and LLM evaluation"""
        # Get manual metrics
        manual_metrics = self.evaluate_query_response(query, answer, retrieved_docs)
        
        # Get LLM evaluation
        llm_metrics = self.evaluate_with_llm(query, answer, retrieved_docs)
        
        # Combine both evaluations
        combined_metrics = {
            **manual_metrics,
            **{f"llm_{k}": v for k, v in llm_metrics.items()}
        }
        
        return combined_metrics

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
    
    