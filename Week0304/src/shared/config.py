"""
Shared configuration for RAG pipeline comparison
"""
import os
from typing import Dict, Any, List
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class LLMConfig:
    """Configuration for different LLM providers"""
    provider: str
    model_name: str
    api_key: str = None
    base_url: str = None
    temperature: float = 0.0
    max_tokens: int = 1000

@dataclass
class EmbeddingConfig:
    """Configuration for embedding models"""
    model_name: str = "all-MiniLM-L6-v2"
    device: str = "cpu"
    batch_size: int = 32

@dataclass
class VectorStoreConfig:
    """Configuration for vector stores"""
    store_type: str  # "faiss" or "chroma"
    index_path: str
    similarity_metric: str = "cosine"

@dataclass
class ChunkingConfig:
    """Configuration for document chunking"""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    separators: List[str] = None

    def __post_init__(self):
        if self.separators is None:
            self.separators = ["\n\n", "\n", " ", ""]

class Config:
    """Main configuration class"""
    
    # Embedding configuration
    EMBEDDING_CONFIG = EmbeddingConfig()
    
    # Chunking configuration
    CHUNKING_CONFIG = ChunkingConfig()
    
    # LLM configurations
    LLM_CONFIGS = {
        "openai": LLMConfig(
            provider="openai",
            model_name="gpt-4o-mini",
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.0
        ),
        "azure": LLMConfig(
            provider="azure",
            model_name="gpt-4o-mini",
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            base_url=os.getenv("AZURE_OPENAI_ENDPOINT"),
            temperature=0.0
        ),
        "gemini": LLMConfig(
            provider="gemini",
            model_name="gemini-pro",
            api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.0
        ),
        "ollama": LLMConfig(
            provider="ollama",
            model_name="llama2",
            base_url="http://localhost:11434",
            temperature=0.0
        )
    }
    
    # Vector store configurations
    VECTOR_STORE_CONFIGS = {
        "faiss": VectorStoreConfig(
            store_type="faiss",
            index_path="./data/faiss_index"
        ),
        "chroma": VectorStoreConfig(
            store_type="chroma",
            index_path="./data/chroma_db"
        )
    }
    
    # Test configuration - Updated for RAG research papers
    TEST_QUERIES = [
        "What is Re2G and how does it combine retrieval and reranking?",
        "How does the joint training scheme in OK-VQA differ from using DPR separately?",
        "What compression ratios can LLMLingua achieve and what is the performance impact?",
        "What are the three dimensions that ARES evaluates in RAG systems?",
        "What are the main advantages of neural retrieval over BM25 in these papers?",
        "How do these papers address the challenge of end-to-end training in RAG systems?",
        "What evaluation metrics are proposed for assessing RAG system performance?",
        "What are the computational benefits mentioned for non-parametric memory in transformers?",
        "How does prompt compression in LLMLingua maintain semantic integrity?",
        "What role does knowledge distillation play in training Re2G?"
    ]
    
    # Paths
    DATA_DIR = "./data"
    LOGS_DIR = "./logs"
    RESULTS_DIR = "./results"
    
    # Performance metrics to track
    METRICS = [
        "embedding_time",
        "indexing_time", 
        "retrieval_time",
        "generation_time",
        "total_time",
        "memory_usage",
        "retrieval_accuracy",
        "answer_quality"
    ]