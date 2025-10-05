"""
LangChain-based RAG implementation
"""
import os
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS, Chroma
from langchain.chains import RetrievalQA
from langchain_community.llms import OpenAI
from langchain.schema import Document
from langchain_openai import ChatOpenAI
from langchain_community.llms import Ollama
from langchain_community.chat_models import ChatOllama

try:
    import google.generativeai as genai
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    genai = None
    ChatGoogleGenerativeAI = None

from shared.config import Config
from shared.utils import PerformanceTracker, DocumentProcessor, QueryEvaluator, setup_logging

class LangChainRAG:
    """LangChain-based RAG implementation"""
    
    def __init__(self, vector_store_type: str = "faiss", llm_provider: str = "openai"):
        self.vector_store_type = vector_store_type
        self.llm_provider = llm_provider
        self.vector_store = None
        self.retrieval_chain = None
        self.embeddings = None
        self.llm = None
        
        # Initialize performance tracker and logging
        self.tracker = PerformanceTracker("langchain")
        self.logger = setup_logging("langchain")
        
        self.logger.info(f"Initializing LangChain RAG with {vector_store_type} and {llm_provider}")
        
    def _setup_embeddings(self):
        """Setup embedding model"""
        self.logger.info("Setting up embeddings")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=Config.EMBEDDING_CONFIG.model_name,
            model_kwargs={'device': Config.EMBEDDING_CONFIG.device}
        )
        
    def _setup_llm(self):
        """Setup LLM based on provider"""
        self.logger.info(f"Setting up LLM: {self.llm_provider}")
        llm_config = Config.LLM_CONFIGS[self.llm_provider]
        
        if self.llm_provider == "openai":
            self.llm = ChatOpenAI(
                model_name=llm_config.model_name,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
                openai_api_key=llm_config.api_key
            )
        elif self.llm_provider == "azure":
            # Note: Requires proper Azure OpenAI setup
            self.llm = ChatOpenAI(
                model_name=llm_config.model_name,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
                openai_api_key=llm_config.api_key,
                openai_api_base=llm_config.base_url,
                openai_api_type="azure",
                openai_api_version="2023-12-01-preview"
            )
        elif self.llm_provider == "gemini" and ChatGoogleGenerativeAI:
            genai.configure(api_key=llm_config.api_key)
            self.llm = ChatGoogleGenerativeAI(
                model=llm_config.model_name,
                temperature=llm_config.temperature,
                google_api_key=llm_config.api_key
            )
        elif self.llm_provider == "ollama":
            self.llm = ChatOllama(
                model=llm_config.model_name,
                base_url=llm_config.base_url,
                temperature=llm_config.temperature
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")
    
    def process_documents(self, documents: List[Dict[str, str]]) -> List[Document]:
        """Process and chunk documents"""
        self.logger.info(f"Processing {len(documents)} documents")
        self.tracker.start_timer()
        
        # Setup text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNKING_CONFIG.chunk_size,
            chunk_overlap=Config.CHUNKING_CONFIG.chunk_overlap,
            separators=Config.CHUNKING_CONFIG.separators
        )
        
        # Convert to LangChain documents and split
        langchain_docs = []
        for doc in documents:
            langchain_doc = Document(
                page_content=doc['content'],
                metadata={'source': doc['source'], 'filename': doc.get('filename', '')}
            )
            langchain_docs.append(langchain_doc)
        
        # Split documents
        split_docs = text_splitter.split_documents(langchain_docs)
        
        self.tracker.stop_timer("document_processing_time")
        self.logger.info(f"Created {len(split_docs)} chunks")
        
        return split_docs
    
    def create_vector_store(self, documents: List[Document]):
        """Create and populate vector store"""
        self.logger.info(f"Creating {self.vector_store_type} vector store")
        
        # Setup embeddings (track this as embedding setup time)
        embedding_start = time.time()
        self._setup_embeddings()
        self.tracker.metrics.embedding_time = time.time() - embedding_start
        
        # Track indexing time separately
        self.tracker.start_timer()
        
        # Create vector store
        if self.vector_store_type == "faiss":
            self.vector_store = FAISS.from_documents(documents, self.embeddings)
            
            # Save to disk
            index_path = Config.VECTOR_STORE_CONFIGS["faiss"].index_path
            Path(index_path).parent.mkdir(parents=True, exist_ok=True)
            self.vector_store.save_local(index_path)
            
        elif self.vector_store_type == "chroma":
            persist_directory = Config.VECTOR_STORE_CONFIGS["chroma"].index_path
            Path(persist_directory).mkdir(parents=True, exist_ok=True)
            
            self.vector_store = Chroma.from_documents(
                documents, 
                self.embeddings,
                persist_directory=persist_directory
            )
            self.vector_store.persist()
        else:
            raise ValueError(f"Unsupported vector store: {self.vector_store_type}")
        
        self.tracker.stop_timer("indexing_time")
        self.logger.info("Vector store created successfully")
    
    def setup_retrieval_chain(self):
        """Setup the retrieval QA chain"""
        self.logger.info("Setting up retrieval chain")
        
        # Setup LLM
        self._setup_llm()
        
        # Create retrieval chain
        self.retrieval_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vector_store.as_retriever(search_kwargs={"k": 3}),
            return_source_documents=True
        )
        
        self.logger.info("Retrieval chain setup complete")
    
    def query(self, question: str) -> Dict[str, Any]:
        """Query the RAG system"""
        self.logger.info(f"Processing query: {question}")
        
        # NOTE: Manual timing approach for accurate measurement
        # We manually separate retrieval and generation phases to get precise timing metrics.
        # The high-level self.retrieval_chain({"query": question}) does both operations internally, making
        # timing separation impossible. For production use, the retrieval_chain() would be
        # faster and more convenient, but we need this decomposition for benchmarking.
        # 
        # Future optimization: Could wrap retrieval_chain() with custom timing middleware
        # or use LangChain's callback system for automatic timing without manual separation.
        
        # Measure retrieval time separately
        self.tracker.start_timer()
        
        # Get retriever and perform retrieval (this includes embedding the query)
        retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
        retrieved_docs = retriever.get_relevant_documents(question)
        
        self.tracker.stop_timer("retrieval_time")
        
        # Measure generation time separately using just the LLM
        self.tracker.start_timer()
        
        # Prepare context from retrieved documents
        context = "\n\n".join([doc.page_content for doc in retrieved_docs])
        
        # Create prompt manually (replicating what RetrievalQA does internally)
        # This manual approach allows us to measure only the LLM inference time
        # without including retrieval overhead
        prompt = f"""Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.

{context}

Question: {question}
Answer:"""
        
        # Call LLM directly for generation only (bypassing retrieval_chain for timing)
        # Alternative approach: Use self.retrieval_chain({"query": question}) for production
        # but wrap with timing middleware or callbacks for measurement
        if hasattr(self.llm, 'invoke'):
            # For newer LangChain versions
            llm_response = self.llm.invoke(prompt)
            answer = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
        else:
            # For older LangChain versions
            answer = self.llm(prompt)
        
        self.tracker.stop_timer("generation_time")
        
        # Extract information
        response = {
            "question": question,
            "answer": answer,
            "source_documents": [doc.page_content for doc in retrieved_docs],
            "metadata": [doc.metadata for doc in retrieved_docs]
        }
        
        self.logger.info("Query processed successfully")
        return response
    
    def load_existing_vector_store(self):
        """Load existing vector store from disk"""
        self.logger.info(f"Loading existing {self.vector_store_type} vector store")
        
        self._setup_embeddings()
        
        if self.vector_store_type == "faiss":
            index_path = Config.VECTOR_STORE_CONFIGS["faiss"].index_path
            if Path(index_path).exists():
                self.vector_store = FAISS.load_local(index_path, self.embeddings)
            else:
                raise FileNotFoundError(f"FAISS index not found at {index_path}")
                
        elif self.vector_store_type == "chroma":
            persist_directory = Config.VECTOR_STORE_CONFIGS["chroma"].index_path
            if Path(persist_directory).exists():
                self.vector_store = Chroma(
                    persist_directory=persist_directory,
                    embedding_function=self.embeddings
                )
            else:
                raise FileNotFoundError(f"Chroma DB not found at {persist_directory}")
        
        self.logger.info("Vector store loaded successfully")
    
    def run_benchmark(self, test_queries: List[str], save_results: bool = True) -> Dict[str, Any]:
        """Run benchmark tests"""
        self.logger.info("Starting benchmark tests")
        
        results = {
            "method": "langchain",
            "vector_store": self.vector_store_type,
            "llm_provider": self.llm_provider,
            "queries": [],
            "performance": {}
        }
        
        total_start_time = time.time()
        
        # Track evaluation metrics
        total_retrieval_accuracy = 0.0
        total_answer_quality = 0.0
        
        for query in test_queries:
            self.logger.info(f"Benchmarking query: {query}")
            
            query_start_time = time.time()
            response = self.query(query)
            query_end_time = time.time()
            
            # Evaluate the response
            evaluation = QueryEvaluator.evaluate_query_response(
                query=query,
                answer=response["answer"],
                retrieved_docs=response["source_documents"]
            )
            
            total_retrieval_accuracy += evaluation['retrieval_accuracy']
            total_answer_quality += evaluation['answer_quality']
            
            query_result = {
                "query": query,
                "response": response,
                "query_time": query_end_time - query_start_time,
                "evaluation": evaluation
            }
            results["queries"].append(query_result)
        
        total_time = time.time() - total_start_time
        
        # Calculate average evaluation metrics
        num_queries = len(test_queries)
        self.tracker.metrics.retrieval_accuracy = total_retrieval_accuracy / num_queries if num_queries > 0 else 0.0
        self.tracker.metrics.answer_quality = total_answer_quality / num_queries if num_queries > 0 else 0.0
        
        # Record performance metrics
        self.tracker.record_memory_usage()
        self.tracker.metrics.total_time = total_time
        
        results["performance"] = self.tracker.metrics.to_dict()
        
        if save_results:
            # Save detailed results
            results_path = f"{Config.RESULTS_DIR}/langchain_{self.vector_store_type}_{self.llm_provider}_results.json"
            Path(results_path).parent.mkdir(parents=True, exist_ok=True)
            
            import json
            with open(results_path, 'w') as f:
                json.dump(results, f, indent=2)
            
            # Save performance metrics
            metrics_path = f"{Config.LOGS_DIR}/langchain_{self.vector_store_type}_{self.llm_provider}_metrics.json"
            self.tracker.save_metrics(metrics_path)
        
        self.logger.info(f"Benchmark completed - Avg Retrieval Accuracy: {self.tracker.metrics.retrieval_accuracy:.3f}, Avg Answer Quality: {self.tracker.metrics.answer_quality:.3f}")
        return results

def main():
    """Main function for testing LangChain RAG"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LangChain RAG Implementation")
    parser.add_argument("--vector-store", choices=["faiss", "chroma"], default="faiss")
    parser.add_argument("--llm", choices=["openai", "azure", "gemini", "ollama"], default="openai")
    parser.add_argument("--data-dir", default="./data")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild vector store")
    
    args = parser.parse_args()
    
    # Initialize RAG system
    rag = LangChainRAG(vector_store_type=args.vector_store, llm_provider=args.llm)
    
    try:
        if args.rebuild:
            # Load and process documents
            documents = DocumentProcessor.load_documents_from_directory(args.data_dir)
            if not documents:
                print(f"No documents found in {args.data_dir}")
                return
            
            # Process documents
            processed_docs = rag.process_documents(documents)
            
            # Create vector store
            rag.create_vector_store(processed_docs)
        else:
            # Load existing vector store
            rag.load_existing_vector_store()
        
        # Setup retrieval chain
        rag.setup_retrieval_chain()
        
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