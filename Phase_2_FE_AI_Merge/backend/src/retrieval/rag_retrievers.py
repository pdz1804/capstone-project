"""RAG-Focused Retrieval Systems: Text, Image, and Hybrid Search.

Practical retrieval implementations for RAG applications. Processes document chunks
from the document processing pipeline and supports multiple retrieval strategies.

Retrieval Strategies:

BM25 (Sparse/Lexical):
- Traditional keyword-based retrieval using Okapi BM25 algorithm
- Fast, interpretable, works well for exact term matching
- No embedding computation required
- Good baseline for technical documents with specific terminology

Dense (Semantic/Embedding):
- Embedding-based retrieval using Sentence-Transformers (all-MiniLM-L6-v2)
- Captures semantic similarity beyond keyword matching
- Uses FAISS CPU index for efficient similarity search
- Supports approximate nearest neighbor search for scale

Hybrid (RRF Fusion):
- Combines BM25 and Dense retrieval results using Reciprocal Rank Fusion (RRF)
- Min-max normalization of scores across different scales
- Configurable expansion factor (default 130%): dense retriever returns 1.3*K results
- Weighted combination: alpha=0.5 for balanced BM25/Dense contribution
- Superior performance over individual methods on diverse queries

Index Management:
- TextChunker: Splits documents into semantic chunks (configurable size)
- Persistence: Pickle-based index saving/loading for fast startup
- Memory efficient: Lazy loading of embeddings, streaming chunking

Key Classes:
- BaseRetriever: Abstract base for all retrieval strategies
- BM25Retriever: Lexical/keyword-based search
- DenseRetriever: Semantic embedding-based search
- SimpleHybridRetriever: Reciprocal rank fusion combining BM25 + Dense
- ChunkingConfig: Configurable chunking parameters

Architecture:
- Per-document index: Documents indexed independently
- Per-chunk retrieval: Returns ranked chunks with document metadata
- Score fusion: Min-max normalization for combining different score ranges
- Batch operations: Support for large-scale indexing and search

Configuration (from BenchmarkConfig):
- retriever_types: ["bm25", "dense", "hybrid"] (selectable)
- k_values: [1, 3, 5, 10] (evaluation cutoffs)
- embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
- bm25_params: language="en", lowercase=True
"""

import os
import json
import pickle
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from abc import ABC, abstractmethod

import torch
import torch.nn.functional as F
import numpy as np
import gc
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
import faiss

# Import chunking module (canonical location: src/chunking/chunker.py)
try:
    from chunking.chunker import TextChunker, ChunkingConfig
except ImportError:
    try:
        from src.chunking.chunker import TextChunker, ChunkingConfig
    except ImportError:
        from chunking import TextChunker, ChunkingConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseRetriever(ABC):
    """Base class for all retrievers."""
    
    def __init__(self, name: str):
        self.name = name
        self.is_indexed = False
        
    @abstractmethod
    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Index documents for retrieval."""
        pass
    
    @abstractmethod
    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Search for relevant documents."""
        pass
    
    @staticmethod
    def load_documents_from_directory(doc_dir: Path) -> tuple:
        """
        Load documents from the RAG-ready directory structure.
        
        Returns:
            tuple: (regular_documents, prebuilt_chunks)
            - regular_documents: List of docs that need chunking (text from markdown)
            - prebuilt_chunks: List of pre-built chunks from media files (ready for indexing)
        """
        regular_documents = []
        prebuilt_chunks = []
        doc_dir = Path(doc_dir)
        
        if not doc_dir.exists():
            logger.error(f"Document directory not found: {doc_dir}")
            return regular_documents, prebuilt_chunks

        def _load_prebuilt_chunks(
            doc_folder: Path,
            chunks_path: Path,
            *,
            document_type: str,
            log_label: str,
        ) -> None:
            try:
                with open(chunks_path, 'r', encoding='utf-8') as f:
                    chunks_data = json.load(f)

                chunks = chunks_data.get("chunks", [])
                loaded = 0
                for i, chunk in enumerate(chunks):
                    chunk_text = chunk.get("text", "")
                    if not chunk_text.strip():
                        continue

                    meta = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
                    meta = {
                        **meta,
                        "doc_id": meta.get("doc_id") or doc_folder.name,
                        "chunk_index": meta.get("chunk_index", i),
                        "total_chunks": meta.get("total_chunks", len(chunks)),
                        "source": meta.get("source") or str(doc_folder / f"{doc_folder.name}.md"),
                        "document_type": meta.get("document_type") or document_type,
                    }
                    prebuilt_chunks.append({
                        "id": chunk.get("id") or chunk.get("chunk_name") or f"{doc_folder.name}_chunk_{i}",
                        "text": chunk_text,
                        "source": meta["source"],
                        "doc_id": meta["doc_id"],
                        "chunk_index": meta["chunk_index"],
                        "total_chunks": meta["total_chunks"],
                        "metadata": meta,
                    })
                    loaded += 1

                logger.info(
                    f"Loaded {loaded} pre-built {log_label} chunks "
                    f"for doc: {doc_folder.name}"
                )
            except Exception as e:
                logger.error(f"Error loading {log_label} chunks from {chunks_path}: {e}")

        # Look for documents in the RAG-ready structure
        for doc_folder in doc_dir.iterdir():
            if not doc_folder.is_dir():
                continue
            
            # Check if this is a media document (has media_manifest.json)
            media_manifest = doc_folder / "media_manifest.json"
            chunks_file = doc_folder / "transcript_chunks.json"
            
            # Check if this is an EXCEL document (has excel_manifest.json)
            excel_manifest = doc_folder / "excel_manifest.json"
            excel_chunks_file = doc_folder / "excel_chunks.json"
            docx_manifest = doc_folder / "docx_manifest.json"
            docx_chunks_file = doc_folder / "docx_chunks.json"
            pdf_manifest = doc_folder / "pdf_manifest.json"
            pdf_chunks_file = doc_folder / "pdf_chunks.json"

            if excel_manifest.exists() and excel_chunks_file.exists():
                # EXCEL DOCUMENT: Load pre-built table-aware chunks directly
                try:
                    with open(excel_chunks_file, 'r', encoding='utf-8') as f:
                        excel_data = json.load(f)

                    excel_chunks = excel_data.get("chunks", [])

                    for chunk in excel_chunks:
                        chunk_text_val = chunk.get("text", "")
                        if not chunk_text_val.strip():
                            continue
                        prebuilt_chunks.append(chunk)

                    logger.info(
                        f"Loaded {len(excel_chunks)} pre-built Excel chunks "
                        f"for doc: {doc_folder.name}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error loading Excel chunks from {excel_chunks_file}: {e}"
                    )
                continue  # skip further checks for this folder

            if docx_manifest.exists() and docx_chunks_file.exists():
                _load_prebuilt_chunks(
                    doc_folder,
                    docx_chunks_file,
                    document_type="docx_document",
                    log_label="DOCX",
                )
                continue

            if pdf_manifest.exists() and pdf_chunks_file.exists():
                _load_prebuilt_chunks(
                    doc_folder,
                    pdf_chunks_file,
                    document_type="pdf_document",
                    log_label="PDF",
                )
                continue

            if media_manifest.exists() and chunks_file.exists():
                # MEDIA DOCUMENT: Load pre-built transcript chunks directly
                try:
                    with open(chunks_file, 'r', encoding='utf-8') as f:
                        chunks_data = json.load(f)
                    
                    chunks = chunks_data.get("chunks", [])
                    chunk_metadata_info = chunks_data.get("metadata", {})
                    
                    for i, chunk in enumerate(chunks):
                        chunk_text = chunk.get("text", "")
                        if not chunk_text.strip():
                            continue
                        
                        # Build document entry with uniform metadata preserved
                        prebuilt_chunks.append({
                            'id': chunk.get("chunk_name", f"{doc_folder.name}_chunk_{i}"),
                            'text': chunk_text,
                            'source': str(doc_folder / f"{doc_folder.name}.md"),
                            'doc_id': doc_folder.name,
                            'chunk_index': i,
                            'total_chunks': len(chunks),
                            'metadata': {
                                'doc_id': doc_folder.name,
                                'chunk_index': i,
                                'total_chunks': len(chunks),
                                'source': str(doc_folder / f"{doc_folder.name}.md"),
                                'type': 'transcript',
                                'document_type': 'media',
                                # Uniform metadata fields
                                'content_type': chunk.get('content_type', 'transcript_text'),
                                'original_file': chunk.get('original_file', ''),
                                'original_file_format': chunk.get('original_file_format', ''),
                                'current_format': chunk.get('current_format', ''),
                                'start_time': chunk.get('start_time'),
                                'end_time': chunk.get('end_time'),
                                'duration': chunk.get('duration'),
                                'associated_frames': chunk.get('associated_frames', []),
                                'num_associated_frames': len(chunk.get('associated_frames', [])),
                            }
                        })
                    
                    logger.info(f"Loaded {len(chunks)} pre-built chunks for media doc: {doc_folder.name}")
                    
                except Exception as e:
                    logger.error(f"Error loading pre-built chunks from {chunks_file}: {e}")
            else:
                # REGULAR DOCUMENT: Load markdown for chunking
                md_file = doc_folder / f"{doc_folder.name}.md"
                if md_file.exists():
                    try:
                        with open(md_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        regular_documents.append({
                            'id': doc_folder.name,
                            'text': content,
                            'source': str(md_file),
                            'type': 'markdown'
                        })
                        logger.info(f"Loaded document: {doc_folder.name}")
                    except Exception as e:
                        logger.error(f"Error loading {md_file}: {e}")
        
        logger.info(f"Loaded {len(regular_documents)} regular docs + {len(prebuilt_chunks)} pre-built media chunks from {doc_dir}")
        return regular_documents, prebuilt_chunks


class SimpleBM25Retriever(BaseRetriever):
    """Simple BM25 retriever for RAG applications."""
    
    def __init__(self):
        super().__init__("BM25")
        self.bm25 = None
        self.documents = []
        self.tokenized_docs = []
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        return text.lower().split()
    
    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Index documents using BM25."""
        logger.info(f"Indexing {len(documents)} documents with BM25...")
        
        if not documents:
            logger.warning("Cannot index BM25 with empty document list")
            self.documents = []
            self.tokenized_docs = []
            self.bm25 = None
            self.is_indexed = False
            return
        
        self.documents = documents
        self.tokenized_docs = [self._tokenize(doc['text']) for doc in documents]
        self.bm25 = BM25Okapi(self.tokenized_docs)
        self.is_indexed = True
        
        logger.info("BM25 indexing completed")
    
    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Search using BM25."""
        if not self.is_indexed:
            logger.error("Documents not indexed. Call index_documents() first.")
            return []
        
        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        
        # Get top-k results
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for i, idx in enumerate(top_indices):
            if scores[idx] > 0:  # Only return documents with positive scores
                result = {
                    'id': self.documents[idx]['id'],
                    'text': self.documents[idx]['text'],
                    'source': self.documents[idx]['source'],
                    'score': float(scores[idx]),
                    'rank': i + 1
                }
                # Pass through uniform metadata if present
                if 'metadata' in self.documents[idx]:
                    result['metadata'] = self.documents[idx]['metadata']
                results.append(result)
        
        return results


class SimpleDenseRetriever(BaseRetriever):
    """Simple dense retriever using sentence transformers."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        super().__init__("Dense")
        self.model_name = model_name
        self.model = None
        self.documents = []
        self.embeddings = None
        self.index = None
        
    def _load_model(self):
        """Load the sentence transformer model."""
        if self.model is None:
            logger.info(f"Loading model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
    
    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Index documents using dense embeddings."""
        logger.info(f"Indexing {len(documents)} documents with dense embeddings...")
        
        if not documents:
            logger.warning("Cannot index Dense retriever with empty document list")
            self.documents = []
            self.embeddings = None
            self.index = None
            self.is_indexed = False
            return
        
        self._load_model()
        self.documents = documents
        
        # Extract texts for embedding
        texts = [doc['text'] for doc in documents]
        
        # Generate embeddings
        logger.info("Generating embeddings...")
        self.embeddings = self.model.encode(texts, show_progress_bar=True)
        
        # Create FAISS index
        dimension = self.embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(self.embeddings)
        self.index.add(self.embeddings)
        
        self.is_indexed = True
        logger.info("Dense indexing completed")
    
    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Search using dense embeddings."""
        if not self.is_indexed:
            logger.error("Documents not indexed. Call index_documents() first.")
            return []
        
        # Encode query
        query_embedding = self.model.encode([query])
        faiss.normalize_L2(query_embedding)
        
        # Search
        scores, indices = self.index.search(query_embedding, top_k)
        
        results = []
        for i, (idx, score) in enumerate(zip(indices[0], scores[0])):
            if idx != -1:  # Valid result
                result = {
                    'id': self.documents[idx]['id'],
                    'text': self.documents[idx]['text'],
                    'source': self.documents[idx]['source'],
                    'score': float(score),
                    'rank': i + 1
                }
                # Pass through uniform metadata if present
                if 'metadata' in self.documents[idx]:
                    result['metadata'] = self.documents[idx]['metadata']
                results.append(result)
        
        return results


class SimpleHybridRetriever(BaseRetriever):
    """Simple hybrid retriever combining BM25 and dense retrieval."""
    
    # Expansion factor for hybrid search - retrieve more candidates for better fusion
    HYBRID_EXPANSION_FACTOR = 1.3  # 130% of requested top_k
    
    def __init__(self, alpha: float = 0.5):
        super().__init__("Hybrid")
        self.alpha = alpha  # Weight for dense retrieval (1-alpha for BM25)
        self.bm25_retriever = SimpleBM25Retriever()
        self.dense_retriever = SimpleDenseRetriever()
    
    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Index documents with both retrievers."""
        logger.info(f"Indexing {len(documents)} documents with hybrid retrieval...")
        
        if not documents:
            logger.warning("Cannot index Hybrid retriever with empty document list")
            self.is_indexed = False
            return
        
        self.bm25_retriever.index_documents(documents)
        self.dense_retriever.index_documents(documents)
        self.is_indexed = True
        
        logger.info("Hybrid indexing completed")
    
    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Search using hybrid approach with min-max normalization and weighted sum."""
        if not self.is_indexed:
            logger.error("Documents not indexed. Call index_documents() first.")
            return []
        
        # Expand search to get more candidates for fusion (130% of requested)
        expanded_k = max(top_k, int(top_k * self.HYBRID_EXPANSION_FACTOR))
        
        # Get results from both retrievers with expanded k
        bm25_results = self.bm25_retriever.search(query, expanded_k)
        dense_results = self.dense_retriever.search(query, expanded_k)
        
        # Track individual retriever rankings and raw scores
        bm25_scores_dict = {}  # doc_id -> raw_score
        dense_scores_dict = {}  # doc_id -> raw_score
        bm25_ranks = {}  # doc_id -> rank
        dense_ranks = {}  # doc_id -> rank
        
        # Collect raw scores
        for rank, result in enumerate(bm25_results, 1):
            doc_id = result['id']
            bm25_scores_dict[doc_id] = result.get('score', 0)
            bm25_ranks[doc_id] = rank
        
        for rank, result in enumerate(dense_results, 1):
            doc_id = result['id']
            dense_scores_dict[doc_id] = result.get('score', 0)
            dense_ranks[doc_id] = rank
        
        # Min-max normalization for BM25 scores
        def min_max_normalize(scores_dict):
            """Normalize scores to [0, 1] range using min-max normalization."""
            if not scores_dict:
                return {}
            scores = list(scores_dict.values())
            min_score = min(scores)
            max_score = max(scores)
            
            if max_score == min_score:
                # All scores are the same, return uniform normalized scores
                return {doc_id: 1.0 for doc_id in scores_dict.keys()}
            
            return {
                doc_id: (score - min_score) / (max_score - min_score)
                for doc_id, score in scores_dict.items()
            }
        
        # Normalize BM25 scores (Dense scores are already normalized from cosine similarity)
        bm25_normalized = min_max_normalize(bm25_scores_dict)
        
        # Combine scores using weighted sum: 0.5 * BM25_normalized + 0.5 * Dense
        # Note: self.alpha is the weight for dense, so (1 - self.alpha) is for BM25
        # Default alpha=0.5 means equal weights
        all_doc_ids = set(bm25_scores_dict.keys()) | set(dense_scores_dict.keys())
        combined_scores = {}
        
        for doc_id in all_doc_ids:
            bm25_norm_score = bm25_normalized.get(doc_id, 0.0)
            dense_score = dense_scores_dict.get(doc_id, 0.0)
            
            # Weighted combination: (1-alpha) * BM25_normalized + alpha * Dense
            combined_score = (1 - self.alpha) * bm25_norm_score + self.alpha * dense_score
            combined_scores[doc_id] = combined_score
        
        # Sort by combined score
        sorted_docs = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        # Create result objects with source information
        results = []
        doc_map = {doc['id']: doc for doc in self.bm25_retriever.documents}
        
        for i, (doc_id, score) in enumerate(sorted_docs):
            if doc_id in doc_map:
                doc = doc_map[doc_id]
                
                # Get individual retriever info
                bm25_raw = bm25_scores_dict.get(doc_id)
                bm25_norm = bm25_normalized.get(doc_id)
                bm25_rank = bm25_ranks.get(doc_id)
                dense_raw = dense_scores_dict.get(doc_id)
                dense_rank = dense_ranks.get(doc_id)
                
                results.append({
                    'id': doc_id,
                    'text': doc['text'],
                    'source': doc['source'],
                    'score': float(score),
                    'rank': i + 1,
                    # Pass through uniform metadata if present
                    'metadata': doc.get('metadata', {}),
                    # Hybrid fusion details with raw scores
                    'retrieval_info': {
                        'bm25_rank': bm25_rank,
                        'bm25_score': float(bm25_raw) if bm25_raw is not None else None,
                        'bm25_score_normalized': float(bm25_norm) if bm25_norm is not None else None,
                        'dense_rank': dense_rank,
                        'dense_score': float(dense_raw) if dense_raw is not None else None,
                        'in_bm25': doc_id in bm25_scores_dict,
                        'in_dense': doc_id in dense_scores_dict,
                        'in_both': doc_id in bm25_scores_dict and doc_id in dense_scores_dict
                    }
                })
        
        return results


class CrossEncoderReranker:
    """
    Cross-encoder reranker for improving retrieval quality.
    
    Supports:
    - BGE-Large Reranker (BAAI/bge-reranker-large)
    - MiniLM Cross-Encoder (cross-encoder/ms-marco-MiniLM-L-12-v2)
    """
    
    SUPPORTED_MODELS = {
        "bge-large": "BAAI/bge-reranker-large",
        "minilm-l12": "cross-encoder/ms-marco-MiniLM-L-12-v2",
        "bge-base": "BAAI/bge-reranker-base",
    }
    
    def __init__(self, model_name: str = "bge-large", batch_size: int = 32, device: str = None):
        """
        Initialize reranker.
        
        Args:
            model_name: Short name (bge-large, minilm-l12) or full HuggingFace model path
            batch_size: Batch size for reranking
            device: Device to use (cuda, cpu, auto)
        """
        self.batch_size = batch_size
        
        # Resolve model name
        if model_name in self.SUPPORTED_MODELS:
            self.model_path = self.SUPPORTED_MODELS[model_name]
        else:
            self.model_path = model_name
        
        self.model_name = model_name
        
        # Set device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        
        self.model = None
        self.tokenizer = None
        self._is_loaded = False
    
    def _load_model(self):
        """Lazy load the reranker model."""
        if self._is_loaded:
            return
        
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
        except ImportError:
            raise ImportError("transformers required. Install with: pip install transformers")
        
        logger.info(f"Loading reranker model: {self.model_path}...")
        
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.model_path,
            torch_dtype=torch.float16 if self.device == 'cuda' else torch.float32
        ).to(self.device).eval()
        
        self.num_labels = self.model.config.num_labels
        self._is_loaded = True
        logger.info(f"Reranker loaded on {self.device} (labels: {self.num_labels})")
    
    @torch.no_grad()
    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Rerank documents using cross-encoder.
        
        Args:
            query: Query string
            documents: List of documents with 'text' field
            top_k: Number of top results to return
            
        Returns:
            Reranked list of documents with 'rerank_score' field added
        """
        if not documents:
            logger.warning("Reranker called with empty document list")
            return []
        
        logger.info(f"🤖 CrossEncoderReranker.rerank() called: query='{query[:50]}...', docs={len(documents)}, top_k={top_k}")
        self._load_model()
        
        # Prepare input pairs
        input_pairs = []
        valid_indices = []
        
        for idx, doc in enumerate(documents):
            text = doc.get('text', '')
            if text:
                input_pairs.append((query, text))
                valid_indices.append(idx)
        
        if not input_pairs:
            logger.warning("No valid input pairs for reranking, returning documents as-is")
            return documents[:top_k]
        
        # Score in batches
        all_scores = []
        logger.info(f"📈 Scoring {len(input_pairs)} documents in batches of {self.batch_size}...")
        
        for i in range(0, len(input_pairs), self.batch_size):
            batch = input_pairs[i:i + self.batch_size]
            
            # Tokenize
            inputs = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=512
            ).to(self.device)
            
            # Get scores
            outputs = self.model(**inputs)
            logits = outputs.logits
            
            if self.num_labels == 1:
                scores = logits.squeeze(-1).cpu().tolist()
            else:
                probabilities = torch.softmax(logits, dim=-1)
                scores = probabilities[:, 1].cpu().tolist()
            
            all_scores.extend(scores)
            
            # Cleanup temporary tensors; avoid forcing GC/CUDA cache flush per batch.
            del inputs, outputs, logits
        
        logger.info(f"✔️  Scoring complete: {len(all_scores)} documents scored")
        
        # Assign scores to documents
        scored_docs = []
        for idx, score in zip(valid_indices, all_scores):
            doc = documents[idx].copy()
            doc['rerank_score'] = float(score)
            doc['original_score'] = doc.get('score', 0.0)
            scored_docs.append(doc)
        
        # Sort by rerank score and return top_k
        reranked = sorted(scored_docs, key=lambda x: x.get('rerank_score', 0.0), reverse=True)
        logger.info(f"🔄 Sorted {len(reranked)} documents by rerank score")
        
        # Update rank field
        for i, doc in enumerate(reranked, 1):
            doc['rank'] = i
            doc['score'] = doc['rerank_score']  # Use rerank score as main score
        
        top_results = reranked[:top_k]
        logger.info(f"📍 Reranking complete: Top result score={top_results[0]['rerank_score']:.4f}, Bottom result score={top_results[-1]['rerank_score']:.4f}")
        return top_results
    
    def unload(self):
        """Unload model to free memory."""
        if self.model is not None:
            del self.model
            del self.tokenizer
            self.model = None
            self.tokenizer = None
            self._is_loaded = False
            
            if self.device == 'cuda':
                torch.cuda.empty_cache()
            gc.collect()
            logger.info(f"Reranker {self.model_name} unloaded")


class RAGRetrieverManager:
    """Manager for RAG retrieval systems with document chunking and optional reranking."""
    
    def __init__(
        self, 
        doc_dir: Path, 
        index_dir: Path = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        enable_chunking: bool = True,
        reranker_model: str = None
    ):
        self.doc_dir = Path(doc_dir)
        self.index_dir = Path(index_dir) if index_dir else self.doc_dir.parent / "retrieval_index"
        self.retrievers = {}
        self.documents = []  # Chunked documents (for retrieval)
        self.raw_documents = []  # Original documents (before chunking)
        
        # Chunking configuration
        self.enable_chunking = enable_chunking
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunker = TextChunker(ChunkingConfig(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        ))
        
        # Reranker configuration
        self.reranker = None
        self.reranker_model = reranker_model
        if reranker_model:
            logger.info(f"🎯 RERANKER ENABLED: Initializing {reranker_model}")
            self.setup_reranker(reranker_model)
        else:
            logger.info("⏭️  Reranker disabled (no model specified)")
    
    def load_documents(self) -> None:
        """Load and chunk documents from the RAG-ready directory."""
        logger.info(f"Loading documents from: {self.doc_dir}")
        
        # Load raw documents and pre-built chunks separately
        regular_docs, prebuilt_chunks = BaseRetriever.load_documents_from_directory(self.doc_dir)
        self.raw_documents = regular_docs
        
        if not regular_docs and not prebuilt_chunks:
            logger.warning("No documents found!")
            self.documents = []
            return
        
        logger.info(f"Loaded {len(regular_docs)} regular documents + {len(prebuilt_chunks)} pre-built media chunks")
        
        # Chunk regular documents if enabled
        chunked_docs = []
        if regular_docs and self.enable_chunking:
            logger.info(f"Chunking {len(regular_docs)} regular documents (size={self.chunk_size}, overlap={self.chunk_overlap})...")
            chunked_docs = self.chunker.chunk_documents(regular_docs)
            logger.info(f"Created {len(chunked_docs)} chunks from {len(regular_docs)} regular documents")
        elif regular_docs:
            chunked_docs = regular_docs
            logger.info(f"Chunking disabled, using {len(chunked_docs)} full documents")
        
        # Combine chunked regular docs with pre-built media chunks
        self.documents = chunked_docs + prebuilt_chunks
        
        logger.info(f"Total documents for indexing: {len(self.documents)} "
                     f"({len(chunked_docs)} from regular docs + {len(prebuilt_chunks)} pre-built media chunks)")
    
    def setup_retriever(self, retriever_type: str, **kwargs) -> None:
        """Setup a specific retriever type."""
        if not self.documents:
            self.load_documents()
        
        if retriever_type == "bm25":
            retriever = SimpleBM25Retriever()
        elif retriever_type == "dense":
            model_name = kwargs.get("model_name", "all-MiniLM-L6-v2")
            retriever = SimpleDenseRetriever(model_name)
        elif retriever_type == "hybrid":
            alpha = kwargs.get("alpha", 0.5)
            retriever = SimpleHybridRetriever(alpha)
        else:
            raise ValueError(f"Unknown retriever type: {retriever_type}")
        
        retriever.index_documents(self.documents)
        self.retrievers[retriever_type] = retriever
        logger.info(f"Setup {retriever_type} retriever")
    
    def setup_reranker(self, model_name: str = "bge-large", batch_size: int = 32) -> None:
        """
        Setup a reranker for improving retrieval quality.
        
        Args:
            model_name: 'bge-large', 'minilm-l12', 'bge-base', or full HuggingFace path
            batch_size: Batch size for reranking
        """
        logger.info(f"⚙️  Setting up CrossEncoderReranker: model={model_name}, batch_size={batch_size}")
        self.reranker = CrossEncoderReranker(model_name, batch_size)
        self.reranker_model = model_name
        logger.info(f"✅ Reranker setup complete: {model_name}")
    
    def search(
        self, 
        query: str, 
        retriever_type: str = "hybrid", 
        top_k: int = 10,
        use_reranker: bool = None,
        rerank_top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Search using a specific retriever with optional reranking.
        
        Args:
            query: Search query
            retriever_type: Type of retriever to use
            top_k: Number of results to return
            use_reranker: Whether to use reranker (default: use if available)
            rerank_top_k: Number of candidates for reranking (default: top_k * 3)
            
        Returns:
            List of search results
        """
        if retriever_type not in self.retrievers:
            logger.error(f"Retriever {retriever_type} not setup. Available: {list(self.retrievers.keys())}")
            return []
        
        # Determine if we should rerank
        should_rerank = use_reranker if use_reranker is not None else (self.reranker is not None)
        
        if should_rerank and self.reranker:
            # Get more candidates for reranking
            candidates_k = rerank_top_k or max(top_k * 3, 30)
            logger.info(f"🔍 RERANKING IN PROGRESS: Fetching {candidates_k} candidates from {retriever_type} retriever for reranking")
            candidates = self.retrievers[retriever_type].search(query, candidates_k)
            logger.info(f"📊 Got {len(candidates)} candidates, reranking with {self.reranker_model}...")
            
            # Rerank and return top_k
            results = self.reranker.rerank(query, candidates, top_k)
            
            # Mark as reranked
            for r in results:
                r['reranked'] = True
                r['reranker_model'] = self.reranker_model
            
            logger.info(f"✨ RERANKING COMPLETE: Returned top-{len(results)} reranked results")
            return results
        else:
            logger.info(f"⏭️  Skipping reranking - using {retriever_type} retriever directly")
            return self.retrievers[retriever_type].search(query, top_k)
    
    def get_available_retrievers(self) -> List[str]:
        """Get list of available retrievers."""
        return list(self.retrievers.keys())
    
    def save_index(self) -> Path:
        """Save all retriever indexes to disk."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        # Save documents
        docs_path = self.index_dir / "documents.json"
        with open(docs_path, 'w', encoding='utf-8') as f:
            json.dump(self.documents, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(self.documents)} documents to {docs_path}")
        
        # Save each retriever's index
        for name, retriever in self.retrievers.items():
            retriever_dir = self.index_dir / name
            retriever_dir.mkdir(parents=True, exist_ok=True)
            
            if isinstance(retriever, SimpleBM25Retriever):
                # Save BM25 index
                bm25_path = retriever_dir / "bm25_index.pkl"
                with open(bm25_path, 'wb') as f:
                    pickle.dump({
                        'bm25': retriever.bm25,
                        'tokenized_docs': retriever.tokenized_docs
                    }, f)
                logger.info(f"Saved BM25 index to {bm25_path}")
                
            elif isinstance(retriever, SimpleDenseRetriever):
                # Save FAISS index
                faiss_path = retriever_dir / "faiss_index.bin"
                faiss.write_index(retriever.index, str(faiss_path))
                
                # Save embeddings and metadata
                meta_path = retriever_dir / "dense_meta.pkl"
                with open(meta_path, 'wb') as f:
                    pickle.dump({
                        'model_name': retriever.model_name,
                        'embeddings': retriever.embeddings
                    }, f)
                logger.info(f"Saved Dense index to {retriever_dir}")
                
            elif isinstance(retriever, SimpleHybridRetriever):
                # Save both BM25 and Dense indexes for hybrid
                # BM25 in hybrid folder
                bm25_path = retriever_dir / "bm25_index.pkl"
                with open(bm25_path, 'wb') as f:
                    pickle.dump({
                        'bm25': retriever.bm25_retriever.bm25,
                        'tokenized_docs': retriever.bm25_retriever.tokenized_docs
                    }, f)
                
                # Dense in hybrid folder
                faiss_path = retriever_dir / "faiss_index.bin"
                faiss.write_index(retriever.dense_retriever.index, str(faiss_path))
                
                meta_path = retriever_dir / "dense_meta.pkl"
                with open(meta_path, 'wb') as f:
                    pickle.dump({
                        'model_name': retriever.dense_retriever.model_name,
                        'embeddings': retriever.dense_retriever.embeddings,
                        'alpha': retriever.alpha
                    }, f)
                logger.info(f"Saved Hybrid index to {retriever_dir}")
                
                # Also save standalone BM25 and Dense folders for flexibility
                # This allows users to query with bm25/dense even if they only built hybrid
                
                # Save standalone BM25 folder
                bm25_dir = self.index_dir / "bm25"
                if not bm25_dir.exists():
                    bm25_dir.mkdir(parents=True, exist_ok=True)
                    bm25_standalone_path = bm25_dir / "bm25_index.pkl"
                    with open(bm25_standalone_path, 'wb') as f:
                        pickle.dump({
                            'bm25': retriever.bm25_retriever.bm25,
                            'tokenized_docs': retriever.bm25_retriever.tokenized_docs
                        }, f)
                    logger.info(f"Also saved standalone BM25 index to {bm25_dir}")
                
                # Save standalone Dense folder
                dense_dir = self.index_dir / "dense"
                if not dense_dir.exists():
                    dense_dir.mkdir(parents=True, exist_ok=True)
                    faiss_standalone_path = dense_dir / "faiss_index.bin"
                    faiss.write_index(retriever.dense_retriever.index, str(faiss_standalone_path))
                    
                    meta_standalone_path = dense_dir / "dense_meta.pkl"
                    with open(meta_standalone_path, 'wb') as f:
                        pickle.dump({
                            'model_name': retriever.dense_retriever.model_name,
                            'embeddings': retriever.dense_retriever.embeddings
                        }, f)
                    logger.info(f"Also saved standalone Dense index to {dense_dir}")
        
        # Save index metadata
        # Include all available retriever folders (including standalone ones created from hybrid)
        available_retrievers = set(self.retrievers.keys())
        for folder in self.index_dir.iterdir():
            if folder.is_dir() and folder.name in ['bm25', 'dense', 'hybrid']:
                available_retrievers.add(folder.name)
        
        meta = {
            'doc_count': len(self.documents),
            'raw_doc_count': len(self.raw_documents),
            'retrievers': sorted(list(available_retrievers)),
            'doc_dir': str(self.doc_dir),
            'chunking': {
                'enabled': self.enable_chunking,
                'chunk_size': self.chunk_size,
                'chunk_overlap': self.chunk_overlap
            }
        }
        with open(self.index_dir / "index_meta.json", 'w') as f:
            json.dump(meta, f, indent=2)
        
        logger.info(f"✅ Index saved to: {self.index_dir}")
        logger.info(f"   {len(self.raw_documents)} documents → {len(self.documents)} chunks")
        return self.index_dir
    
    def load_index(self) -> bool:
        """Load retriever indexes from disk."""
        if not self.index_dir.exists():
            logger.warning(f"Index directory not found: {self.index_dir}")
            return False
        
        # Load documents (these are the chunked documents)
        docs_path = self.index_dir / "documents.json"
        if not docs_path.exists():
            logger.warning(f"Documents file not found: {docs_path}")
            return False
        
        with open(docs_path, 'r', encoding='utf-8') as f:
            self.documents = json.load(f)
        logger.info(f"Loaded {len(self.documents)} chunks from index")
        
        # Load index metadata
        meta_path = self.index_dir / "index_meta.json"
        if meta_path.exists():
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            retriever_types = meta.get('retrievers', [])
            
            # Load chunking config
            chunking_config = meta.get('chunking', {})
            self.enable_chunking = chunking_config.get('enabled', True)
            self.chunk_size = chunking_config.get('chunk_size', 1000)
            self.chunk_overlap = chunking_config.get('chunk_overlap', 200)
            
            raw_doc_count = meta.get('raw_doc_count', 'unknown')
            logger.info(f"Index info: {raw_doc_count} docs → {len(self.documents)} chunks (size={self.chunk_size}, overlap={self.chunk_overlap})")
        else:
            # Auto-detect retrievers from directories
            retriever_types = [d.name for d in self.index_dir.iterdir() if d.is_dir()]
        
        # Load each retriever
        for retriever_type in retriever_types:
            retriever_dir = self.index_dir / retriever_type
            if not retriever_dir.exists():
                continue
            
            try:
                if retriever_type == "bm25":
                    retriever = SimpleBM25Retriever()
                    retriever.documents = self.documents
                    
                    bm25_path = retriever_dir / "bm25_index.pkl"
                    with open(bm25_path, 'rb') as f:
                        data = pickle.load(f)
                    retriever.bm25 = data['bm25']
                    retriever.tokenized_docs = data['tokenized_docs']
                    retriever.is_indexed = True
                    self.retrievers[retriever_type] = retriever
                    logger.info(f"Loaded BM25 index from {bm25_path}")
                    
                elif retriever_type == "dense":
                    meta_path = retriever_dir / "dense_meta.pkl"
                    with open(meta_path, 'rb') as f:
                        data = pickle.load(f)
                    
                    retriever = SimpleDenseRetriever(data['model_name'])
                    retriever.documents = self.documents
                    retriever.embeddings = data['embeddings']
                    
                    faiss_path = retriever_dir / "faiss_index.bin"
                    retriever.index = faiss.read_index(str(faiss_path))
                    retriever._load_model()  # Load model for query encoding
                    retriever.is_indexed = True
                    self.retrievers[retriever_type] = retriever
                    logger.info(f"Loaded Dense index from {retriever_dir}")
                    
                elif retriever_type == "hybrid":
                    meta_path = retriever_dir / "dense_meta.pkl"
                    with open(meta_path, 'rb') as f:
                        data = pickle.load(f)
                    
                    retriever = SimpleHybridRetriever(data.get('alpha', 0.5))
                    
                    # Load BM25
                    retriever.bm25_retriever.documents = self.documents
                    bm25_path = retriever_dir / "bm25_index.pkl"
                    with open(bm25_path, 'rb') as f:
                        bm25_data = pickle.load(f)
                    retriever.bm25_retriever.bm25 = bm25_data['bm25']
                    retriever.bm25_retriever.tokenized_docs = bm25_data['tokenized_docs']
                    retriever.bm25_retriever.is_indexed = True
                    
                    # Load Dense
                    retriever.dense_retriever = SimpleDenseRetriever(data['model_name'])
                    retriever.dense_retriever.documents = self.documents
                    retriever.dense_retriever.embeddings = data['embeddings']
                    faiss_path = retriever_dir / "faiss_index.bin"
                    retriever.dense_retriever.index = faiss.read_index(str(faiss_path))
                    retriever.dense_retriever._load_model()
                    retriever.dense_retriever.is_indexed = True
                    
                    retriever.is_indexed = True
                    self.retrievers[retriever_type] = retriever
                    logger.info(f"Loaded Hybrid index from {retriever_dir}")
                    
            except Exception as e:
                logger.error(f"Failed to load {retriever_type} index: {e}")
        
        logger.info(f"✅ Loaded indexes: {list(self.retrievers.keys())}")
        return len(self.retrievers) > 0


# Convenience functions for the unified pipeline
def create_rag_retriever(
    doc_dir: Path, 
    retriever_types: List[str] = None, 
    index_dir: Path = None, 
    save_index: bool = True,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    enable_chunking: bool = True,
    reranker_model: str = None
) -> RAGRetrieverManager:
    """Create and setup RAG retriever manager with document chunking and optional reranking.
    
    Args:
        doc_dir: Directory containing RAG-ready documents
        retriever_types: List of retriever types to setup (default: ["bm25", "dense", "hybrid"])
        index_dir: Directory to save/load indexes (default: doc_dir/../retrieval_index)
        save_index: Whether to save the index after building (default: True)
        chunk_size: Size of text chunks in characters (default: 1000)
        chunk_overlap: Overlap between chunks (default: 200)
        enable_chunking: Whether to chunk documents (default: True)
        reranker_model: Reranker model name ('bge-large', 'minilm-l12', etc.) or None
    
    Returns:
        RAGRetrieverManager with configured retrievers
    """
    if retriever_types is None:
        retriever_types = ["bm25", "dense", "hybrid"]
    
    manager = RAGRetrieverManager(
        doc_dir, 
        index_dir,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        enable_chunking=enable_chunking,
        reranker_model=reranker_model
    )
    manager.load_documents()
    
    for retriever_type in retriever_types:
        try:
            manager.setup_retriever(retriever_type)
        except Exception as e:
            logger.error(f"Failed to setup {retriever_type} retriever: {e}")
    
    # Save index to disk
    if save_index and manager.retrievers:
        manager.save_index()
    
    return manager


def load_rag_retriever(index_dir: Path, reranker_model: str = None) -> Optional[RAGRetrieverManager]:
    """Load a previously saved RAG retriever from disk.
    
    Args:
        index_dir: Directory containing saved indexes
        reranker_model: Optional reranker model name to apply to loaded retriever
    
    Returns:
        RAGRetrieverManager with loaded retrievers, or None if loading failed
    """
    index_dir = Path(index_dir)
    
    # Read metadata to get doc_dir
    meta_path = index_dir / "index_meta.json"
    if meta_path.exists():
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        doc_dir = Path(meta.get('doc_dir', index_dir.parent / "stage4_rag_ready"))
    else:
        doc_dir = index_dir.parent / "stage4_rag_ready"
    
    manager = RAGRetrieverManager(doc_dir, index_dir, reranker_model=reranker_model)
    
    if manager.load_index():
        return manager
    return None
