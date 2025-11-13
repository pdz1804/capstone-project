"""
Manual RAG implementation from scratch
"""
import os
import time
import json
import pickle
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import sys

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import chromadb
import openai
import requests

# Use minimal LangChain imports for better text splitting while keeping most functionality manual
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import chromadb
import openai
import requests

# Import LangChain text splitter for better chunking
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from shared.config import Config
from shared.utils import PerformanceTracker, DocumentProcessor, setup_logging, QueryEvaluator

class ManualRAG:
    """
    Manual RAG implementation with minimal dependencies
    
    This implementation provides maximum control over the RAG pipeline with custom
    implementations for most components: embedding, indexing, retrieval, and generation.
    Uses LangChain's RecursiveCharacterTextSplitter for consistent chunking with other pipelines,
    but implements everything else manually. Serves as both an educational example and performance baseline.
    """
    
    def __init__(self, vector_store_type: str = "faiss", llm_provider: str = "openai"):
        self.vector_store_type = vector_store_type
        self.llm_provider = llm_provider
        
        # Document storage
        self.documents = []
        self.chunks = []
        self.embeddings = None
        
        # Vector store components
        self.vector_index = None
        self.embedding_model = None
        
        # Performance tracking
        self.tracker = PerformanceTracker("manual")
        self.logger = setup_logging("manual")
        
        self.logger.info(f"Initializing Manual RAG with {vector_store_type} and {llm_provider}")
        
    def cleanup_storage(self):
        """Clean up existing vector stores to ensure fresh start"""
        import shutil
        # NOTE: On some platforms (Windows) files in use can cause
        # race conditions when attempting to delete persistent stores.
        # To make benchmarks safer and non-destructive, we intentionally
        # avoid deleting existing vector store files here. Instead, the
        # benchmark flow will overwrite or persist new data when rebuilding.
        self.logger.info("Skipping destructive cleanup of Manual vector stores (non-destructive mode)")
        print("🧹 Skipping deletion of Manual vector stores (kept for safety)")
        
        # Reset internal state so the instance will recreate stores when asked
        self.vector_index = None
        self.documents = []
        self.chunks = []
        self.embeddings = None
        
        print(f"✅ Manual storage cleanup skipped")
        
    def cleanup_storage_destructive(self):
        """Destructive cleanup - actually delete vector store files from disk"""
        import shutil
        self.logger.warning("Performing DESTRUCTIVE cleanup - deleting Manual vector store files")
        print(f"🧹 Destructively cleaning up existing vector stores...")
        
        # Delete actual files from disk
        try:
            if self.vector_store_type == "faiss":
                index_path = Path(Config.VECTOR_STORE_CONFIGS["faiss"].index_path)
                if index_path.exists():
                    shutil.rmtree(index_path, ignore_errors=True)
                    self.logger.info(f"Deleted FAISS index at {index_path}")
                    print(f"  ✓ Removed FAISS index at {index_path}")
            
            elif self.vector_store_type == "chroma":
                index_path = Path(Config.VECTOR_STORE_CONFIGS["chroma"].index_path)
                if index_path.exists():
                    shutil.rmtree(index_path, ignore_errors=True)
                    self.logger.info(f"Deleted Chroma DB at {index_path}")
                    print(f"  ✓ Removed Chroma DB at {index_path}")
                    
        except Exception as e:
            self.logger.error(f"Failed to delete Manual vector store files: {e}")
            # Don't raise - continue with benchmark even if deletion fails
        
        # Reset internal state
        self.vector_index = None
        self.documents = []
        self.chunks = []
        self.embeddings = None
        
        print(f"🗑️ Manual destructive cleanup completed")
    
    def _load_embedding_model(self):
        """Load the embedding model"""
        if self.embedding_model is None:
            self.logger.info(f"Loading embedding model: {Config.EMBEDDING_CONFIG.model_name}")
            self.embedding_model = SentenceTransformer(
                Config.EMBEDDING_CONFIG.model_name,
                device=Config.EMBEDDING_CONFIG.device
            )
    
    def _chunk_documents(self, documents: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Chunk documents using LangChain's RecursiveCharacterTextSplitter (same as LangChain pipeline)"""
        from tqdm import tqdm
        
        self.logger.info(f"Chunking {len(documents)} documents")
        print(f"📄 Starting to chunk {len(documents)} documents using LangChain's RecursiveCharacterTextSplitter...")
        
        # Setup text splitter (same as LangChain pipeline)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNKING_CONFIG.chunk_size,
            chunk_overlap=Config.CHUNKING_CONFIG.chunk_overlap,
            separators=Config.CHUNKING_CONFIG.separators
        )
        
        chunks = []
        chunk_id = 0
        
        print(f"  Using LangChain RecursiveCharacterTextSplitter")
        print(f"  Chunk size: {Config.CHUNKING_CONFIG.chunk_size}")
        print(f"  Chunk overlap: {Config.CHUNKING_CONFIG.chunk_overlap}")
        print(f"  Separators: {Config.CHUNKING_CONFIG.separators}")
        
        for doc_idx, doc in enumerate(tqdm(documents, desc="Chunking documents", unit="doc")):
            print(f"  Processing document {doc_idx + 1}/{len(documents)}: {doc.get('filename', 'Unknown')}")
            text = doc['content']
            
            # Use LangChain text splitter for better chunking
            text_chunks = text_splitter.split_text(text)
            
            print(f"    → Created {len(text_chunks)} chunks from {len(text)} characters")
            
            for chunk_text in text_chunks:
                chunk = {
                    'id': chunk_id,
                    'text': chunk_text,
                    'doc_id': doc_idx,
                    'source': doc['source'],
                    'filename': doc.get('filename', ''),
                    'metadata': {
                        'doc_id': doc_idx,
                        'chunk_id': chunk_id,
                        'source': doc['source'],
                        'filename': doc.get('filename', '')
                    }
                }
                chunks.append(chunk)
                chunk_id += 1
        
        print(f"✅ Successfully created {len(chunks)} chunks total")
        self.logger.info(f"Created {len(chunks)} chunks")
        return chunks
    
    def _generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts"""
        from tqdm import tqdm
        
        self.logger.info(f"Generating embeddings for {len(texts)} texts")
        print(f"🔢 Generating embeddings for {len(texts)} text chunks...")
        self._load_embedding_model()
        
        # Batch processing for efficiency
        batch_size = Config.EMBEDDING_CONFIG.batch_size
        all_embeddings = []
        
        print(f"  Using batch size: {batch_size}")
        num_batches = (len(texts) + batch_size - 1) // batch_size
        print(f"  Processing {num_batches} batches...")
        
        for i in tqdm(range(0, len(texts), batch_size), desc="Generating embeddings", unit="batch"):
            batch_texts = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            print(f"  Processing batch {batch_num}/{num_batches} ({len(batch_texts)} texts)")
            
            batch_embeddings = self.embedding_model.encode(
                batch_texts,
                show_progress_bar=False,  # We're showing our own progress
                convert_to_numpy=True
            )
            all_embeddings.append(batch_embeddings)
            
            print(f"    → Generated embeddings shape: {batch_embeddings.shape}")
        
        embeddings = np.vstack(all_embeddings)
        print(f"✅ Final embeddings shape: {embeddings.shape}")
        self.logger.info(f"Generated embeddings shape: {embeddings.shape}")
        return embeddings
    
    def _setup_faiss_index(self, embeddings: np.ndarray):
        """Setup FAISS vector index"""
        self.logger.info("Setting up FAISS index")
        
        dimension = embeddings.shape[1]
        
        # Create FAISS index
        if Config.VECTOR_STORE_CONFIGS["faiss"].similarity_metric == "cosine":
            # Normalize embeddings for cosine similarity
            faiss.normalize_L2(embeddings)
            self.vector_index = faiss.IndexFlatIP(dimension)  # Inner product for cosine
        else:
            self.vector_index = faiss.IndexFlatL2(dimension)  # L2 distance
        
        # Add embeddings to index
        self.vector_index.add(embeddings.astype(np.float32))
        
        self.logger.info(f"FAISS index created with {self.vector_index.ntotal} vectors")
    
    def _setup_chroma_index(self, embeddings: np.ndarray):
        """Setup Chroma vector index"""
        self.logger.info("Setting up Chroma index")
        
        # Initialize Chroma client
        persist_directory = Config.VECTOR_STORE_CONFIGS["chroma"].index_path
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        
        self.chroma_client = chromadb.PersistentClient(path=persist_directory)
        
        # Create or get collection - handle existing collection properly
        try:
            # Try to delete existing collection if it exists
            existing_collection = self.chroma_client.get_collection("rag_documents")
            self.chroma_client.delete_collection("rag_documents")
            self.logger.info("Deleted existing collection")
        except Exception as e:
            self.logger.info(f"No existing collection to delete: {e}")
        
        self.chroma_collection = self.chroma_client.create_collection(
            name="rag_documents",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Add documents to collection
        ids = [str(i) for i in range(len(self.chunks))]
        documents = [chunk['text'] for chunk in self.chunks]
        metadatas = [chunk['metadata'] for chunk in self.chunks]
        
        self.chroma_collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings.tolist()
        )
        
        self.logger.info(f"Chroma index created with {len(documents)} documents")
    
    def process_documents(self, documents: List[Dict[str, str]]):
        """Process documents: chunk and embed"""
        print(f"\n🚀 Starting document processing pipeline...")
        print(f"📋 Input: {len(documents)} documents")
        
        self.logger.info("Processing documents")
        self.tracker.start_timer()
        
        # Store original documents
        self.documents = documents
        
        # Chunk documents
        print(f"\n1️⃣ CHUNKING PHASE")
        self.chunks = self._chunk_documents(documents)

        # Generate embeddings
        print(f"\n2️⃣ EMBEDDING PHASE")
        chunk_texts = [chunk['text'] for chunk in self.chunks]
        self.embeddings = self._generate_embeddings(chunk_texts)

        # Do not stop vector_processing_time here. We want vector_processing_time to
        # include both embedding and indexing (index creation/persist). The timer
        # will be stopped in create_vector_index() after the index is created.
        print(f"\n✅ Document processing complete!")
        print(f"📊 Summary:")
        print(f"  - Documents processed: {len(documents)}")
        print(f"  - Chunks created: {len(self.chunks)}")
        print(f"  - Embeddings generated: {self.embeddings.shape}")
        print(f"  - Vector processing time: {self.tracker.metrics.vector_processing_time:.2f}s")
    
    def create_vector_index(self):
        """Create vector index"""
        print(f"\n3️⃣ INDEXING PHASE")
        self.logger.info(f"Creating {self.vector_store_type} vector index")
        print(f"🔗 Creating {self.vector_store_type.upper()} vector index...")
        # Note: We don't time indexing separately as it's included in vector_processing_time
        
        if self.embeddings is None:
            raise ValueError("Embeddings not generated. Call process_documents() first.")
        
        if self.vector_store_type == "faiss":
            print(f"  Setting up FAISS index...")
            self._setup_faiss_index(self.embeddings)
            
            # Save FAISS index
            index_path = Config.VECTOR_STORE_CONFIGS["faiss"].index_path
            # Ensure the directory exists
            Path(index_path).mkdir(parents=True, exist_ok=True)
            print(f"  Saving FAISS index to {index_path}")
            faiss.write_index(self.vector_index, f"{index_path}/index.faiss")
            
            # Save chunks and metadata
            print(f"  Saving chunks and metadata...")
            with open(f"{index_path}/chunks.pkl", 'wb') as f:
                pickle.dump(self.chunks, f)
            with open(f"{index_path}/embeddings.npy", 'wb') as f:
                np.save(f, self.embeddings)
            print(f"  ✓ FAISS index saved successfully")
                
        elif self.vector_store_type == "chroma":
            print(f"  Setting up Chroma index...")
            self._setup_chroma_index(self.embeddings)
            print(f"  ✓ Chroma index created successfully")
        else:
            raise ValueError(f"Unsupported vector store: {self.vector_store_type}")
        
        # Stop the combined embedding + indexing timer now that index creation finished
        self.tracker.stop_timer("vector_processing_time")

        print(f"✅ Vector index created successfully")
        self.logger.info("Vector index created successfully")
    
    def load_existing_index(self):
        """Load existing vector index"""
        self.logger.info(f"Loading existing {self.vector_store_type} index")
        
        if self.vector_store_type == "faiss":
            index_path = Config.VECTOR_STORE_CONFIGS["faiss"].index_path
            
            # Load FAISS index
            index_file = f"{index_path}/index.faiss"
            if not Path(index_file).exists():
                raise FileNotFoundError(f"FAISS index not found at {index_file}")
            
            self.vector_index = faiss.read_index(index_file)
            
            # Load chunks and embeddings
            with open(f"{index_path}/chunks.pkl", 'rb') as f:
                self.chunks = pickle.load(f)
            with open(f"{index_path}/embeddings.npy", 'rb') as f:
                self.embeddings = np.load(f)
                
        elif self.vector_store_type == "chroma":
            persist_directory = Config.VECTOR_STORE_CONFIGS["chroma"].index_path
            
            if not Path(persist_directory).exists():
                raise FileNotFoundError(f"Chroma DB not found at {persist_directory}")
            
            self.chroma_client = chromadb.PersistentClient(path=persist_directory)
            self.chroma_collection = self.chroma_client.get_collection("rag_documents")
        
        # Load embedding model
        self._load_embedding_model()
        
        self.logger.info("Vector index loaded successfully")
    
    def _retrieve_faiss(self, query_embedding: np.ndarray, k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve using FAISS"""
        if Config.VECTOR_STORE_CONFIGS["faiss"].similarity_metric == "cosine":
            faiss.normalize_L2(query_embedding)
        
        scores, indices = self.vector_index.search(query_embedding.astype(np.float32), k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.chunks):
                result = {
                    'chunk': self.chunks[idx],
                    'score': float(score),
                    'index': int(idx)
                }
                results.append(result)
        
        return results
    
    def _retrieve_chroma(self, query_text: str, k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve using Chroma"""
        # Query the collection
        results = self.chroma_collection.query(
            query_texts=[query_text],
            n_results=k,
            include=['documents', 'metadatas', 'distances']
        )
        
        retrieved = []
        for i, (doc, metadata, distance) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0], 
            results['distances'][0]
        )):
            result = {
                'chunk': {
                    'text': doc,
                    'metadata': metadata
                },
                'score': 1.0 - distance,  # Convert distance to similarity
                'index': i
            }
            retrieved.append(result)
        
        return retrieved
    
    def retrieve(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks for a query"""
        self.logger.info(f"Retrieving top {k} chunks for query")
        self.tracker.start_timer()
        
        if self.vector_store_type == "faiss":
            # Generate query embedding
            query_embedding = self._generate_embeddings([query])
            results = self._retrieve_faiss(query_embedding, k)
        elif self.vector_store_type == "chroma":
            results = self._retrieve_chroma(query, k)
        else:
            raise ValueError(f"Unsupported vector store: {self.vector_store_type}")
        
        self.tracker.stop_timer("retrieval_time")
        
        self.logger.info(f"Retrieved {len(results)} chunks")
        return results
    
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API"""
        llm_config = Config.LLM_CONFIGS["openai"]
        
        client = openai.OpenAI(api_key=llm_config.api_key)
        
        response = client.chat.completions.create(
            model=llm_config.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens
        )
        
        return response.choices[0].message.content
    
    def _call_azure_openai(self, prompt: str) -> str:
        """Call Azure OpenAI API"""
        llm_config = Config.LLM_CONFIGS["azure"]
        
        client = openai.AzureOpenAI(
            api_key=llm_config.api_key,
            api_version="2023-12-01-preview",
            azure_endpoint=llm_config.base_url
        )
        
        response = client.chat.completions.create(
            model=llm_config.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens
        )
        
        return response.choices[0].message.content
    
    def _call_gemini(self, prompt: str) -> str:
        """Call Google Gemini API"""
        if genai is None:
            raise ImportError("google-generativeai package not installed")
            
        llm_config = Config.LLM_CONFIGS["gemini"]
        genai.configure(api_key=llm_config.api_key)
        
        model = genai.GenerativeModel(llm_config.model_name)
        response = model.generate_content(prompt)
        
        return response.text
    
    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API"""
        llm_config = Config.LLM_CONFIGS["ollama"]
        
        url = f"{llm_config.base_url}/api/generate"
        data = {
            "model": llm_config.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": llm_config.temperature
            }
        }
        
        response = requests.post(url, json=data)
        response.raise_for_status()
        
        return response.json()["response"]
    
    def generate_answer(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """Generate answer using LLM with standardized prompt"""
        self.logger.info(f"Generating answer using {self.llm_provider}")
        self.tracker.start_timer()
        
        # Prepare context
        context = "\n\n".join([chunk['chunk']['text'] for chunk in context_chunks])
        
        # Use standardized prompt template from config
        prompt = Config.RAG_PROMPT_TEMPLATE.format(
            context=context,
            question=query
        )
        
        # Call appropriate LLM
        if self.llm_provider == "openai":
            answer = self._call_openai(prompt)
        elif self.llm_provider == "azure":
            answer = self._call_azure_openai(prompt)
        elif self.llm_provider == "gemini":
            answer = self._call_gemini(prompt)
        elif self.llm_provider == "ollama":
            answer = self._call_ollama(prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")
        
        self.tracker.stop_timer("generation_time")
        return answer
    
    def query(self, question: str, k: int = 3) -> Dict[str, Any]:
        """Complete RAG query pipeline"""
        self.logger.info(f"Processing query: {question}")
        
        # Retrieve relevant chunks
        retrieved_chunks = self.retrieve(question, k)
        
        # Generate answer
        answer = self.generate_answer(question, retrieved_chunks)
        
        # Prepare response
        response = {
            "question": question,
            "answer": answer,
            "source_documents": [chunk['chunk']['text'] for chunk in retrieved_chunks],
            "metadata": [chunk['chunk']['metadata'] for chunk in retrieved_chunks],
            "scores": [chunk['score'] for chunk in retrieved_chunks]
        }
        
        self.logger.info("Query processed successfully")
        return response
    
    def run_benchmark(self, test_queries: List[str], save_results: bool = True, num_queries: int = None) -> Dict[str, Any]:
        """Run benchmark tests with advanced evaluation"""
        from tqdm import tqdm
        
        # Limit number of queries if specified
        if num_queries is not None:
            test_queries = test_queries[:num_queries]
        
        print(f"\n🎯 Starting benchmark with {len(test_queries)} test queries...")
        self.logger.info("Starting benchmark tests")
        
        results = {
            "method": "manual",
            "vector_store": self.vector_store_type,
            "llm_provider": self.llm_provider,
            "queries": [],
            "performance": {}
        }
        
        total_start_time = time.time()
        
        # Track evaluation metrics
        total_answer_quality = 0.0
        total_relevance = 0.0
        
        for i, query in enumerate(tqdm(test_queries, desc="Running benchmark queries", unit="query")):
            print(f"\n📝 Query {i+1}/{len(test_queries)}: {query}")
            self.logger.info(f"Benchmarking query: {query}")
            
            query_start_time = time.time()
            response = self.query(query)
            query_end_time = time.time()
            
            query_time = query_end_time - query_start_time
            print(f"  ⏱️ Query completed in {query_time:.2f}s")
            
            # Evaluate the response (LLM-based answer quality & relevance)
            evaluation = QueryEvaluator.evaluate_query_response(
                query=query,
                answer=response["answer"],
                retrieved_docs=response["source_documents"]
            )

            total_answer_quality += evaluation.get('answer_quality', 0.0)
            total_relevance += evaluation.get('relevance', 0.0)

            print(f"  📊 Answer Quality: {evaluation.get('answer_quality', 0.0):.3f}")
            print(f"  📊 Relevance: {evaluation.get('relevance', 0.0):.3f}")
            
            query_result = {
                "query": query,
                "response": response,
                "query_time": query_time,
                "evaluation": evaluation
            }
            results["queries"].append(query_result)
        
        total_time = time.time() - total_start_time
        
        # Calculate average evaluation metrics
        num_queries = len(test_queries)
        self.tracker.metrics.answer_quality = total_answer_quality / num_queries if num_queries > 0 else 0.0
        self.tracker.metrics.relevance = total_relevance / num_queries if num_queries > 0 else 0.0
        
        # Record performance metrics
        self.tracker.record_memory_usage()
        self.tracker.metrics.total_time = total_time
        
        results["performance"] = self.tracker.metrics.to_dict()
        
        print(f"\n📊 Benchmark Results Summary:")
        print(f"  - Total queries: {len(test_queries)}")
        print(f"  - Total time: {total_time:.2f}s")
        print(f"  - Average time per query: {total_time/len(test_queries):.2f}s")
        print(f"  - Memory usage: {self.tracker.metrics.memory_usage:.2f}MB")
        print(f"  - Average Answer Quality: {self.tracker.metrics.answer_quality:.3f}")
        print(f"  - Average Relevance: {getattr(self.tracker.metrics, 'relevance', 0.0):.3f}")
        
        if save_results:
            # Save detailed results
            results_path = f"{Config.RESULTS_DIR}/manual_{self.vector_store_type}_{self.llm_provider}_results.json"
            Path(results_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(results_path, 'w') as f:
                json.dump(results, f, indent=2)
            
            # Save performance metrics
            metrics_path = f"{Config.LOGS_DIR}/manual_{self.vector_store_type}_{self.llm_provider}_metrics.json"
            self.tracker.save_metrics(metrics_path)
            
            print(f"  💾 Results saved to: {results_path}")
            print(f"  📋 Metrics saved to: {metrics_path}")
        
        self.logger.info(f"Benchmark completed - Avg Answer Quality: {self.tracker.metrics.answer_quality:.3f}, Avg Relevance: {getattr(self.tracker.metrics, 'relevance', 0.0):.3f}")
        return results

def main():
    """Main function for testing Manual RAG"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Manual RAG Implementation")
    parser.add_argument("--vector-store", choices=["faiss", "chroma"], default="faiss")
    parser.add_argument("--llm", choices=["openai", "azure", "gemini", "ollama"], default="openai")
    parser.add_argument("--data-dir", default="./data")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild vector store")
    parser.add_argument("--num-queries", type=int, default=Config.DEFAULT_NUM_QUERIES, 
                        help=f"Number of test queries to run (default: {Config.DEFAULT_NUM_QUERIES})")
    
    args = parser.parse_args()
    
    # Initialize RAG system
    rag = ManualRAG(vector_store_type=args.vector_store, llm_provider=args.llm)
    
    try:
        if args.rebuild:
            # Clean up existing storage first
            rag.cleanup_storage()
            
            # Load documents
            documents = DocumentProcessor.load_documents_from_directory(args.data_dir)
            if not documents:
                print(f"No documents found in {args.data_dir}")
                return
            
            # Process documents
            rag.process_documents(documents)
            
            # Create vector index
            rag.create_vector_index()
        else:
            # Load existing index
            rag.load_existing_index()
        
        # Run benchmark with specified number of queries
        results = rag.run_benchmark(Config.TEST_QUERIES, num_queries=args.num_queries)
        
        print(f"Benchmark completed. Results saved to results directory.")
        print(f"Total time: {results['performance']['total_time']:.2f}s")
        print(f"Memory usage: {results['performance']['memory_usage']:.2f}MB")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()