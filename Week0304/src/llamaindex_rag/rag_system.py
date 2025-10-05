"""
LlamaIndex-based RAG implementation
"""
import os
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

try:
    # Try newer LlamaIndex imports first
    from llama_index.core import Document, VectorStoreIndex, Settings, SimpleDirectoryReader
    from llama_index.core.node_parser import SimpleNodeParser
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    from llama_index.llms.openai import OpenAI
    from llama_index.llms.ollama import Ollama
    from llama_index.vector_stores.faiss import FaissVectorStore
    from llama_index.vector_stores.chroma import ChromaVectorStore
    from llama_index.core.storage.storage_context import StorageContext
    from llama_index.core.query_engine import RetrieverQueryEngine
    LLAMAINDEX_AVAILABLE = True
    print("✅ Using LlamaIndex core imports")
except ImportError:
    try:
        # Fallback to older LlamaIndex imports
        from llama_index import Document, VectorStoreIndex, Settings, SimpleDirectoryReader
        from llama_index.node_parser import SimpleNodeParser
        from llama_index.embeddings import HuggingFaceEmbedding
        from llama_index.llms import OpenAI, Ollama
        from llama_index.vector_stores import FaissVectorStore, ChromaVectorStore
        from llama_index.storage.storage_context import StorageContext
        from llama_index.query_engine import RetrieverQueryEngine
        LLAMAINDEX_AVAILABLE = True
        print("✅ Using LlamaIndex legacy imports")
    except ImportError as e:
        print(f"❌ LlamaIndex import error: {e}")
        # Create fallback classes
        Document = None
        VectorStoreIndex = None
        Settings = None
        HuggingFaceEmbedding = None
        OpenAI = None
        Ollama = None
        FaissVectorStore = None
        ChromaVectorStore = None
        StorageContext = None
        RetrieverQueryEngine = None
        LLAMAINDEX_AVAILABLE = False
        
    # Try to import additional LLM providers
    try:
        from llama_index.llms.gemini import Gemini
    except ImportError:
        try:
            from llama_index.llms import Gemini
        except ImportError:
            Gemini = None

import faiss
import chromadb

from shared.config import Config
from shared.utils import PerformanceTracker, DocumentProcessor, QueryEvaluator, setup_logging

class LlamaIndexRAG:
    """LlamaIndex-based RAG implementation"""
    
    def __init__(self, vector_store_type: str = "faiss", llm_provider: str = "openai"):
        self.vector_store_type = vector_store_type
        self.llm_provider = llm_provider
        self.index = None
        self.query_engine = None
        self.vector_store = None
        
        # Initialize performance tracker and logging
        self.tracker = PerformanceTracker("llamaindex")
        self.logger = setup_logging("llamaindex")
        
        self.logger.info(f"Initializing LlamaIndex RAG with {vector_store_type} and {llm_provider}")
        
    def _setup_global_settings(self):
        """Setup global settings with embedding model and LLM"""
        self.logger.info("Setting up global settings")
        
        # Setup embedding model
        embed_model = HuggingFaceEmbedding(
            model_name=Config.EMBEDDING_CONFIG.model_name,
            device=Config.EMBEDDING_CONFIG.device
        )
        
        # Setup LLM
        llm_config = Config.LLM_CONFIGS[self.llm_provider]
        
        if self.llm_provider == "openai":
            llm = OpenAI(
                model=llm_config.model_name,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
                api_key=llm_config.api_key
            )
        elif self.llm_provider == "azure":
            # Azure OpenAI configuration
            llm = OpenAI(
                model=llm_config.model_name,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
                api_key=llm_config.api_key,
                api_base=llm_config.base_url,
                api_type="azure",
                api_version="2023-12-01-preview"
            )
        elif self.llm_provider == "gemini" and Gemini:
            llm = Gemini(
                model=llm_config.model_name,
                temperature=llm_config.temperature,
                api_key=llm_config.api_key
            )
        elif self.llm_provider == "ollama":
            llm = Ollama(
                model=llm_config.model_name,
                base_url=llm_config.base_url,
                temperature=llm_config.temperature
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")
        
        # Configure global settings
        Settings.llm = llm
        Settings.embed_model = embed_model
        Settings.chunk_size = Config.CHUNKING_CONFIG.chunk_size
        Settings.chunk_overlap = Config.CHUNKING_CONFIG.chunk_overlap
        
        self.logger.info("Global settings configuration complete")
    
    def _setup_vector_store(self):
        """Setup vector store"""
        self.logger.info(f"Setting up {self.vector_store_type} vector store")
        
        if self.vector_store_type == "faiss":
            # Create FAISS index
            dimension = 384  # MiniLM-L6-v2 embedding dimension
            faiss_index = faiss.IndexFlatL2(dimension)
            
            # Create vector store
            self.vector_store = FaissVectorStore(faiss_index=faiss_index)
            
        elif self.vector_store_type == "chroma":
            # Setup Chroma
            chroma_client = chromadb.PersistentClient(
                path=Config.VECTOR_STORE_CONFIGS["chroma"].index_path
            )
            chroma_collection = chroma_client.get_or_create_collection("rag_documents")
            
            self.vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        else:
            raise ValueError(f"Unsupported vector store: {self.vector_store_type}")
    
    def process_documents(self, documents: List[Dict[str, str]]) -> List[Document]:
        """Process documents into LlamaIndex format"""
        self.logger.info(f"Processing {len(documents)} documents")
        self.tracker.start_timer()
        
        # Convert to LlamaIndex documents
        llamaindex_docs = []
        for doc in documents:
            llamaindex_doc = Document(
                text=doc['content'],
                metadata={'source': doc['source'], 'filename': doc.get('filename', '')}
            )
            llamaindex_docs.append(llamaindex_doc)
        
        self.tracker.stop_timer("document_processing_time")
        self.logger.info(f"Converted {len(llamaindex_docs)} documents")
        
        return llamaindex_docs
    
    def create_index(self, documents: List[Document]):
        """Create vector index from documents"""
        self.logger.info("Creating vector index")
        
        # Setup global settings (track this as embedding setup time)
        embedding_start = time.time()
        self._setup_global_settings()
        self.tracker.metrics.embedding_time = time.time() - embedding_start
        
        # Track indexing time separately
        self.tracker.start_timer()
        
        # Setup vector store
        self._setup_vector_store()
        
        # Create storage context
        storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        
        # Create index
        self.index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context
        )
        
        self.tracker.stop_timer("indexing_time")
        
        # Persist index
        if self.vector_store_type == "faiss":
            persist_dir = Config.VECTOR_STORE_CONFIGS["faiss"].index_path
            Path(persist_dir).parent.mkdir(parents=True, exist_ok=True)
            self.index.storage_context.persist(persist_dir=persist_dir)
        
        self.logger.info("Vector index created successfully")
    
    def setup_query_engine(self):
        """Setup query engine"""
        self.logger.info("Setting up query engine")
        
        if self.index is None:
            raise ValueError("Index not created. Call create_index() first.")
        
        # Create query engine
        self.query_engine = self.index.as_query_engine(
            similarity_top_k=3
        )
        
        self.logger.info("Query engine setup complete")
    
    def query(self, question: str) -> Dict[str, Any]:
        """Query the RAG system"""
        self.logger.info(f"Processing query: {question}")
        
        # NOTE: Manual timing approach for accurate measurement
        # We manually separate retrieval and generation to get precise timing metrics.
        # The high-level self.query_engine.query(question) does both operations internally, making
        # timing separation impossible. For production use, query_engine.query() would be
        # faster and more convenient, but we need this decomposition for benchmarking.
        # 
        # Future optimization: Could use LlamaIndex's callback system or custom query engine
        # with built-in timing hooks to avoid manual separation while maintaining performance.
        
        # Measure retrieval time separately
        self.tracker.start_timer()
        
        # Perform retrieval (this includes embedding the query)
        retriever = self.index.as_retriever(similarity_top_k=3)
        retrieved_nodes = retriever.retrieve(question)
        
        self.tracker.stop_timer("retrieval_time")
        
        # Measure generation time separately  
        self.tracker.start_timer()
        
        # Prepare context from retrieved nodes
        context = "\n\n".join([node.node.text for node in retrieved_nodes])
        
        # Create prompt manually (replicating what query engine does internally)
        # This manual approach allows us to measure only the LLM inference time
        # without including retrieval overhead
        prompt = f"""Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.

{context}

Question: {question}
Answer:"""
        
        # Call LLM directly for generation only (bypassing query_engine for timing)
        # Alternative approach: Use self.query_engine.query(question) for production
        # but implement custom QueryEngine with timing callbacks or middleware
        llm = Settings.llm
        
        if hasattr(llm, 'chat'):
            # For chat-based LLMs
            from llama_index.core.llms import ChatMessage
            messages = [ChatMessage(role="user", content=prompt)]
            llm_response = llm.chat(messages)
            answer = llm_response.message.content
        else:
            # For completion-based LLMs
            llm_response = llm.complete(prompt)
            answer = llm_response.text
        
        self.tracker.stop_timer("generation_time")
        
        # Extract source information
        result = {
            "question": question,
            "answer": answer,
            "source_documents": [node.node.text for node in retrieved_nodes],
            "metadata": [node.node.metadata for node in retrieved_nodes],
            "scores": [node.score for node in retrieved_nodes]
        }
        
        self.logger.info("Query processed successfully")
        return result
    
    def load_existing_index(self):
        """Load existing index from disk"""
        self.logger.info(f"Loading existing {self.vector_store_type} index")
        
        # Setup global settings
        self._setup_global_settings()
        
        if self.vector_store_type == "faiss":
            persist_dir = Config.VECTOR_STORE_CONFIGS["faiss"].index_path
            if not Path(persist_dir).exists():
                raise FileNotFoundError(f"Index not found at {persist_dir}")
            
            # Setup vector store
            self._setup_vector_store()
            storage_context = StorageContext.from_defaults(
                vector_store=self.vector_store,
                persist_dir=persist_dir
            )
            
            self.index = VectorStoreIndex(
                nodes=[],
                storage_context=storage_context
            )
            
        elif self.vector_store_type == "chroma":
            # Setup vector store
            self._setup_vector_store()
            storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
            
            self.index = VectorStoreIndex(
                nodes=[],
                storage_context=storage_context
            )
        
        self.logger.info("Index loaded successfully")
    
    def run_benchmark(self, test_queries: List[str], save_results: bool = True) -> Dict[str, Any]:
        """Run benchmark tests"""
        self.logger.info("Starting benchmark tests")
        
        results = {
            "method": "llamaindex",
            "vector_store": self.vector_store_type,
            "llm_provider": self.llm_provider,
            "queries": [],
            "performance": {}
        }
        
        total_start_time = time.time()
        
        # Initialize evaluation tracking
        all_retrieval_accuracies = []
        all_answer_qualities = []
        
        for query in test_queries:
            self.logger.info(f"Benchmarking query: {query}")
            
            query_start_time = time.time()
            response = self.query(query)
            query_end_time = time.time()
            
            # Evaluate the response
            retrieved_docs = response.get('source_documents', [])
            answer = response.get('answer', '')
            
            evaluation = QueryEvaluator.evaluate_query_response(
                query=query,
                answer=answer,
                retrieved_docs=retrieved_docs
            )
            
            all_retrieval_accuracies.append(evaluation['retrieval_accuracy'])
            all_answer_qualities.append(evaluation['answer_quality'])
            
            query_result = {
                "query": query,
                "response": response,
                "query_time": query_end_time - query_start_time,
                "evaluation": evaluation
            }
            results["queries"].append(query_result)
        
        total_time = time.time() - total_start_time
        
        # Calculate average evaluation metrics
        avg_retrieval_accuracy = sum(all_retrieval_accuracies) / len(all_retrieval_accuracies) if all_retrieval_accuracies else 0.0
        avg_answer_quality = sum(all_answer_qualities) / len(all_answer_qualities) if all_answer_qualities else 0.0
        
        # Record performance metrics
        self.tracker.record_memory_usage()
        self.tracker.metrics.total_time = total_time
        self.tracker.metrics.retrieval_accuracy = avg_retrieval_accuracy
        self.tracker.metrics.answer_quality = avg_answer_quality
        
        results["performance"] = self.tracker.metrics.to_dict()
        
        if save_results:
            # Save detailed results
            results_path = f"{Config.RESULTS_DIR}/llamaindex_{self.vector_store_type}_{self.llm_provider}_results.json"
            Path(results_path).parent.mkdir(parents=True, exist_ok=True)
            
            import json
            with open(results_path, 'w') as f:
                json.dump(results, f, indent=2)
            
            # Save performance metrics
            metrics_path = f"{Config.LOGS_DIR}/llamaindex_{self.vector_store_type}_{self.llm_provider}_metrics.json"
            self.tracker.save_metrics(metrics_path)
        
        self.logger.info("Benchmark completed")
        return results

def main():
    """Main function for testing LlamaIndex RAG"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LlamaIndex RAG Implementation")
    parser.add_argument("--vector-store", choices=["faiss", "chroma"], default="faiss")
    parser.add_argument("--llm", choices=["openai", "azure", "gemini", "ollama"], default="openai")
    parser.add_argument("--data-dir", default="./data")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild vector store")
    
    args = parser.parse_args()
    
    # Initialize RAG system
    rag = LlamaIndexRAG(vector_store_type=args.vector_store, llm_provider=args.llm)
    
    try:
        if args.rebuild:
            # Load and process documents
            documents = DocumentProcessor.load_documents_from_directory(args.data_dir)
            if not documents:
                print(f"No documents found in {args.data_dir}")
                return
            
            # Process documents
            processed_docs = rag.process_documents(documents)
            
            # Create index
            rag.create_index(processed_docs)
        else:
            # Load existing index
            rag.load_existing_index()
        
        # Setup query engine
        rag.setup_query_engine()
        
        # Run benchmark
        results = rag.run_benchmark(Config.TEST_QUERIES)
        
        print(f"Benchmark completed. Results saved to results directory.")
        print(f"Total time: {results['performance']['total_time']:.2f}s")
        print(f"Memory usage: {results['performance']['memory_usage']:.2f}MB")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()