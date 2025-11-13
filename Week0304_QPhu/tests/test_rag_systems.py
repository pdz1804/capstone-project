"""
Test suite for RAG implementations
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from shared.config import Config
from shared.utils import DocumentProcessor, PerformanceTracker, EmbeddingGenerator
from manual_rag.rag_system import ManualRAG

class TestSharedUtils:
    """Test shared utilities"""
    
    def test_document_chunking(self):
        """Test document chunking functionality"""
        text = "This is a test document. " * 100  # Create a long text
        chunks = DocumentProcessor.chunk_text(text, chunk_size=50, chunk_overlap=10)
        
        assert len(chunks) > 1
        assert all(len(chunk) <= 60 for chunk in chunks)  # Allow some flexibility
    
    def test_performance_tracker(self):
        """Test performance tracking"""
        tracker = PerformanceTracker("test")
        
        tracker.start_timer()
        import time
        time.sleep(0.1)
        tracker.stop_timer("test_metric")
        
        assert tracker.metrics.test_metric >= 0.1
    
    def test_embedding_generator(self):
        """Test embedding generation"""
        generator = EmbeddingGenerator()
        texts = ["This is a test sentence.", "Another test sentence."]
        
        embeddings = generator.generate_embeddings(texts)
        
        assert embeddings.shape[0] == 2
        assert embeddings.shape[1] > 0  # Should have some dimensions

class TestManualRAG:
    """Test manual RAG implementation"""
    
    @pytest.fixture
    def sample_documents(self):
        """Sample documents for testing"""
        return [
            {
                "content": "Artificial intelligence is a field of computer science that aims to create intelligent machines.",
                "source": "test_doc_1.txt",
                "filename": "test_doc_1.txt"
            },
            {
                "content": "Machine learning is a subset of AI that enables computers to learn without being explicitly programmed.",
                "source": "test_doc_2.txt", 
                "filename": "test_doc_2.txt"
            }
        ]
    
    def test_manual_rag_initialization(self):
        """Test manual RAG initialization"""
        rag = ManualRAG(vector_store_type="faiss", llm_provider="openai")
        
        assert rag.vector_store_type == "faiss"
        assert rag.llm_provider == "openai"
        assert rag.embeddings is None
    
    def test_document_processing(self, sample_documents):
        """Test document processing"""
        rag = ManualRAG()
        rag.process_documents(sample_documents)
        
        assert len(rag.documents) == 2
        assert len(rag.chunks) >= 2
        assert rag.embeddings is not None

# Integration tests
class TestIntegration:
    """Integration tests for complete pipeline"""
    
    @pytest.mark.integration
    def test_manual_rag_pipeline(self):
        """Test complete manual RAG pipeline"""
        # This test requires actual API keys and is marked as integration
        pytest.skip("Integration test - requires API keys")
    
    @pytest.mark.integration  
    def test_benchmark_runner(self):
        """Test benchmark runner"""
        # This test requires all dependencies and is marked as integration
        pytest.skip("Integration test - requires all dependencies")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])