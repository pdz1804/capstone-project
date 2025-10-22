# 🚀 Detailed RAG Pipeline Implementation Flows

**Generated on**: October 13, 2025  
**Version**: 1.0  
**Repository**: Week0304 RAG Benchmark Suite

## 📋 Table of Contents
1. [Overview](#overview)
2. [Manual RAG Implementation Flow](#manual-rag-implementation-flow)
3. [LangChain RAG Implementation Flow](#langchain-rag-implementation-flow)
4. [LlamaIndex RAG Implementation Flow](#llamaindex-rag-implementation-flow)
5. [Timing and Performance Measurement](#timing-and-performance-measurement)
6. [Flow Comparison Matrix](#flow-comparison-matrix)

---

## 🎯 Overview

This document provides a detailed, phase-by-phase breakdown of each RAG pipeline implementation showing exactly how each component works, what libraries are used, and how the timing is measured. Each implementation follows the same high-level pattern but with different underlying architectures and optimization strategies.

### 🔄 Universal RAG Pipeline Pattern
```
Documents → Chunking → Embedding → Indexing → Storage → Query → Retrieval → Generation → Response
```

### 📊 Shared Components
- **Text Splitter**: All implementations use `RecursiveCharacterTextSplitter` from LangChain for consistency
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` via different wrappers
- **Vector Stores**: FAISS (in-memory/persistent) and ChromaDB (persistent)
- **LLM Providers**: OpenAI GPT-4o-mini, Azure OpenAI, Google Gemini, Ollama
- **Performance Tracking**: Custom `PerformanceTracker` measuring vector_processing_time, retrieval_time, generation_time, memory_usage

---

## 🔧 Manual RAG Implementation Flow

### **Architecture Philosophy**
Maximum control with minimal dependencies. Custom implementations for embedding, indexing, retrieval, and generation. Uses direct API calls and native libraries for educational clarity and performance optimization.

### **Phase 1: Initialization**
```python
def __init__(self, vector_store_type: str = "faiss", llm_provider: str = "openai"):
    self.vector_store_type = vector_store_type  # "faiss" or "chroma"
    self.llm_provider = llm_provider           # "openai", "azure", "gemini", "ollama"
    
    # Storage containers
    self.documents = []        # Original documents
    self.chunks = []          # Text chunks with metadata
    self.embeddings = None    # NumPy array of embeddings
    self.vector_index = None  # FAISS index or ChromaDB collection
    
    # Models (lazy loaded)
    self.embedding_model = None  # SentenceTransformer
    
    # Performance tracking
    self.tracker = PerformanceTracker("manual")
```

**Key Dependencies:**
- `sentence_transformers.SentenceTransformer` - Direct embedding generation
- `faiss` - Native FAISS library for vector similarity search
- `chromadb` - ChromaDB client for persistent vector storage
- `langchain_text_splitters.RecursiveCharacterTextSplitter` - Text chunking only

### **Phase 2: Document Processing**
```python
def process_documents(self, documents: List[Dict[str, str]]):
    """
    PHASE 2A: CHUNKING
    - Input: Raw documents [{content, filename, ...}]
    - Process: RecursiveCharacterTextSplitter (chunk_size=1000, overlap=200)
    - Output: Text chunks with preserved metadata
    """
    self.tracker.start_timer()  # Start vector_processing_time
    
    # Store original documents
    self.documents = documents
    
    # Initialize text splitter (shared with other implementations)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=Config.CHUNKING_CONFIG.chunk_size,      # 1000
        chunk_overlap=Config.CHUNKING_CONFIG.chunk_overlap  # 200
    )
    
    # Chunk each document and preserve metadata
    self.chunks = []
    for doc_id, doc in enumerate(documents):
        chunks = text_splitter.split_text(doc["content"])
        for chunk_id, chunk_text in enumerate(chunks):
            self.chunks.append({
                "text": chunk_text,
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "source": doc.get("filename", f"doc_{doc_id}"),
                "filename": doc.get("filename", f"doc_{doc_id}")
            })
    
    """
    PHASE 2B: EMBEDDING GENERATION
    - Input: Text chunks (list of strings)
    - Process: SentenceTransformer.encode() with batching and normalization
    - Output: NumPy array (n_chunks, embedding_dim)
    """
    
    # Load embedding model (lazy initialization)
    if self.embedding_model is None:
        self.embedding_model = SentenceTransformer(
            Config.EMBEDDING_CONFIG.model_name,  # "sentence-transformers/all-MiniLM-L6-v2"
            device=Config.EMBEDDING_CONFIG.device  # "cpu" or "cuda"
        )
    
    # Generate embeddings in batches for memory efficiency
    chunk_texts = [chunk['text'] for chunk in self.chunks]
    self.embeddings = self.embedding_model.encode(
        chunk_texts,
        batch_size=Config.EMBEDDING_CONFIG.batch_size,  # 32
        show_progress_bar=True,
        normalize_embeddings=True  # L2 normalization for cosine similarity
    )
    
    # Convert to NumPy array for FAISS compatibility
    self.embeddings = np.array(self.embeddings, dtype=np.float32)
    
    # Note: Timer continues running to include indexing phase
```

### **Phase 3: Vector Index Creation**
```python
def create_vector_index(self):
    """
    PHASE 3A: INDEX SETUP (FAISS)
    - Input: Embeddings (NumPy array)
    - Process: FAISS IndexFlatIP (Inner Product for cosine similarity)
    - Output: Searchable FAISS index
    """
    if self.vector_store_type == "faiss":
        # Create FAISS index for cosine similarity
        embedding_dim = self.embeddings.shape[1]  # 384 for all-MiniLM-L6-v2
        self.vector_index = faiss.IndexFlatIP(embedding_dim)  # Inner Product
        
        # Add embeddings to index (already L2 normalized)
        self.vector_index.add(self.embeddings)
        
        # Persist to disk
        index_path = Config.VECTOR_STORE_CONFIGS["faiss"].index_path
        Path(index_path).mkdir(parents=True, exist_ok=True)
        
        # Save FAISS index binary
        faiss.write_index(self.vector_index, f"{index_path}/index.faiss")
        
        # Save metadata separately (FAISS doesn't store metadata)
        with open(f"{index_path}/chunks.pkl", 'wb') as f:
            pickle.dump(self.chunks, f)
        with open(f"{index_path}/embeddings.npy", 'wb') as f:
            np.save(f, self.embeddings)
    
    """
    PHASE 3B: INDEX SETUP (CHROMA)
    - Input: Embeddings + Metadata
    - Process: ChromaDB collection with persistent storage
    - Output: ChromaDB collection with built-in metadata support
    """
    elif self.vector_store_type == "chroma":
        # Initialize persistent ChromaDB client
        persist_directory = Config.VECTOR_STORE_CONFIGS["chroma"].index_path
        chroma_client = chromadb.PersistentClient(path=persist_directory)
        
        # Create or get collection
        collection_name = Config.VECTOR_STORE_CONFIGS["chroma"].collection_name
        self.vector_index = chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # Cosine similarity
        )
        
        # Prepare data for ChromaDB (requires string IDs)
        chunk_ids = [f"chunk_{i}" for i in range(len(self.chunks))]
        chunk_texts = [chunk['text'] for chunk in self.chunks]
        chunk_metadata = [{k: v for k, v in chunk.items() if k != 'text'} 
                         for chunk in self.chunks]
        
        # Add to collection (ChromaDB handles embedding storage internally)
        self.vector_index.add(
            embeddings=self.embeddings.tolist(),  # Convert NumPy to list
            documents=chunk_texts,
            metadatas=chunk_metadata,
            ids=chunk_ids
        )
    
    # Stop combined embedding + indexing timer
    self.tracker.stop_timer("vector_processing_time")
```

### **Phase 4: Query Processing**
```python
def query(self, question: str, k: int = 3) -> Dict[str, Any]:
    """
    PHASE 4A: QUERY EMBEDDING
    - Input: Query string
    - Process: Same embedding model as documents
    - Output: Query embedding vector
    """
    # Load embedding model if not already loaded
    if self.embedding_model is None:
        self._load_embedding_model()
    
    # Embed query using same model and normalization
    query_embedding = self.embedding_model.encode(
        [question], 
        normalize_embeddings=True
    )[0]
    
    """
    PHASE 4B: RETRIEVAL
    - Input: Query embedding + k (top-k results)
    - Process: Vector similarity search
    - Output: Most similar document chunks with scores
    """
    self.tracker.start_timer()  # Start retrieval timing
    
    if self.vector_store_type == "faiss":
        # FAISS similarity search (Inner Product on normalized vectors = cosine)
        scores, indices = self.vector_index.search(
            query_embedding.reshape(1, -1).astype(np.float32), 
            k
        )
        
        # Retrieve corresponding chunks
        retrieved_chunks = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx != -1:  # Valid result
                chunk = self.chunks[idx].copy()
                chunk['score'] = float(score)
                chunk['rank'] = i
                retrieved_chunks.append(chunk)
    
    elif self.vector_store_type == "chroma":
        # ChromaDB query (handles embedding internally)
        results = self.vector_index.query(
            query_texts=[question],
            n_results=k
        )
        
        # Convert ChromaDB results to standard format
        retrieved_chunks = []
        for i, (doc, metadata, score) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0], 
            results['distances'][0]
        )):
            chunk = {
                'text': doc,
                'score': float(1 - score),  # Convert distance to similarity
                'rank': i,
                **metadata
            }
            retrieved_chunks.append(chunk)
    
    self.tracker.stop_timer("retrieval_time")
    
    """
    PHASE 4C: ANSWER GENERATION
    - Input: Query + Retrieved chunks
    - Process: LLM inference with RAG prompt template
    - Output: Generated answer
    """
    self.tracker.start_timer()  # Start generation timing
    
    # Prepare context from retrieved chunks
    context = "\n\n".join([
        f"[Source {i+1}]: {chunk['text']}" 
        for i, chunk in enumerate(retrieved_chunks)
    ])
    
    # Use standardized prompt template
    prompt = Config.RAG_PROMPT_TEMPLATE.format(
        context=context,
        question=question
    )
    
    # Call appropriate LLM provider
    if self.llm_provider == "openai":
        answer = self._call_openai(prompt)
    elif self.llm_provider == "azure":
        answer = self._call_azure_openai(prompt)
    elif self.llm_provider == "gemini":
        answer = self._call_gemini(prompt)
    elif self.llm_provider == "ollama":
        answer = self._call_ollama(prompt)
    
    self.tracker.stop_timer("generation_time")
    
    # Return structured response
    return {
        "question": question,
        "answer": answer,
        "source_documents": [chunk['text'] for chunk in retrieved_chunks],
        "metadata": [
            {k: v for k, v in chunk.items() if k != 'text'} 
            for chunk in retrieved_chunks
        ]
    }
```

### **Phase 5: LLM Integration (OpenAI Example)**
```python
def _call_openai(self, prompt: str) -> str:
    """
    Direct OpenAI API integration
    - Input: Complete prompt with context + question
    - Process: OpenAI Chat Completions API
    - Output: Generated answer text
    """
    try:
        import openai
        
        # Configure client (API key from environment)
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Make chat completion request
        response = client.chat.completions.create(
            model=Config.LLM_CONFIGS["openai"].model_name,  # "gpt-4o-mini"
            messages=[{"role": "user", "content": prompt}],
            max_tokens=Config.LLM_CONFIGS["openai"].max_tokens,  # 500
            temperature=Config.LLM_CONFIGS["openai"].temperature  # 0.1
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        self.logger.error(f"OpenAI API error: {e}")
        return f"Error generating answer: {str(e)}"
```

---

## 🦜 LangChain RAG Implementation Flow

### **Architecture Philosophy**
High-level abstractions for rapid development. Leverages LangChain's ecosystem for pre-built components, chains, and integrations. Focuses on ease of use and extensive provider support.

### **Phase 1: Initialization**
```python
def __init__(self, vector_store_type: str = "faiss", llm_provider: str = "openai"):
    self.vector_store_type = vector_store_type
    self.llm_provider = llm_provider
    
    # LangChain components (lazy loaded)
    self.vector_store = None      # FAISS or Chroma VectorStore
    self.retrieval_chain = None   # RetrievalQA chain
    self.embeddings = None        # HuggingFaceEmbeddings wrapper
    self.llm = None              # LLM wrapper (ChatOpenAI, etc.)
    
    self.tracker = PerformanceTracker("langchain")
```

**Key Dependencies:**
- `langchain_community.embeddings.HuggingFaceEmbeddings` - SentenceTransformer wrapper
- `langchain_community.vectorstores.FAISS` - FAISS integration with LangChain
- `langchain_community.vectorstores.Chroma` - ChromaDB integration
- `langchain.chains.RetrievalQA` - High-level RAG chain
- `langchain_openai.ChatOpenAI` - OpenAI integration

### **Phase 2: Component Setup**
```python
def _setup_embeddings(self):
    """
    Setup embedding model via LangChain wrapper
    - Wraps SentenceTransformer in LangChain interface
    - Provides consistent embed_documents() and embed_query() methods
    """
    self.embeddings = HuggingFaceEmbeddings(
        model_name=Config.EMBEDDING_CONFIG.model_name,
        model_kwargs={
            'device': Config.EMBEDDING_CONFIG.device
        },
        encode_kwargs={
            'normalize_embeddings': True,
            'batch_size': Config.EMBEDDING_CONFIG.batch_size
        }
    )

def _setup_llm(self):
    """
    Setup LLM via LangChain wrapper
    - Provides unified interface across providers
    - Handles authentication and configuration
    """
    if self.llm_provider == "openai":
        self.llm = ChatOpenAI(
            model=Config.LLM_CONFIGS["openai"].model_name,
            temperature=Config.LLM_CONFIGS["openai"].temperature,
            max_tokens=Config.LLM_CONFIGS["openai"].max_tokens,
            api_key=os.getenv("OPENAI_API_KEY")
        )
    elif self.llm_provider == "ollama":
        self.llm = ChatOllama(
            model=Config.LLM_CONFIGS["ollama"].model_name,
            base_url=Config.LLM_CONFIGS["ollama"].base_url
        )
```

### **Phase 3: Document Processing & Indexing**
```python
def create_vector_store(self, documents: List[Dict[str, str]]):
    """
    PHASE 3A: DOCUMENT CONVERSION
    - Convert raw documents to LangChain Document objects
    - Preserves metadata in LangChain's standard format
    """
    self.tracker.start_timer()  # Start vector_processing_time
    
    # Setup embeddings
    self._setup_embeddings()
    
    # Convert to LangChain Documents
    langchain_docs = []
    for doc in documents:
        langchain_docs.append(Document(
            page_content=doc["content"],
            metadata={
                "filename": doc.get("filename", "unknown"),
                "source": doc.get("source", "unknown")
            }
        ))
    
    """
    PHASE 3B: CHUNKING & EMBEDDING & INDEXING (Combined)
    - LangChain handles chunking internally via text splitter
    - Embedding and indexing happen in single method call
    - More convenient but less granular control
    """
    
    # Initialize text splitter (same as manual implementation)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=Config.CHUNKING_CONFIG.chunk_size,
        chunk_overlap=Config.CHUNKING_CONFIG.chunk_overlap
    )
    
    if self.vector_store_type == "faiss":
        # FAISS: from_documents() does chunking + embedding + indexing
        self.vector_store = FAISS.from_documents(
            documents=langchain_docs,
            embedding=self.embeddings,
            text_splitter=text_splitter
        )
        
        # Persist to disk
        index_path = Config.VECTOR_STORE_CONFIGS["faiss"].index_path
        Path(index_path).parent.mkdir(parents=True, exist_ok=True)
        self.vector_store.save_local(index_path)
        
    elif self.vector_store_type == "chroma":
        # ChromaDB: from_documents() with persistence
        persist_directory = Config.VECTOR_STORE_CONFIGS["chroma"].index_path
        self.vector_store = Chroma.from_documents(
            documents=langchain_docs,
            embedding=self.embeddings,
            text_splitter=text_splitter,
            persist_directory=persist_directory,
            collection_name=Config.VECTOR_STORE_CONFIGS["chroma"].collection_name
        )
        self.vector_store.persist()
    
    self.tracker.stop_timer("vector_processing_time")
```

### **Phase 4: Retrieval Chain Setup**
```python
def setup_retrieval_chain(self):
    """
    Setup high-level RetrievalQA chain
    - Combines retriever + LLM + prompt template
    - Handles retrieval and generation automatically
    """
    self._setup_llm()
    
    # Create retrieval chain with "stuff" strategy
    # "stuff" = concatenate all retrieved docs into single prompt
    self.retrieval_chain = RetrievalQA.from_chain_type(
        llm=self.llm,
        chain_type="stuff",
        retriever=self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 3}
        ),
        return_source_documents=True,
        verbose=False
    )
```

### **Phase 5: Query Processing (Manual Timing)**
```python
def query(self, question: str) -> Dict[str, Any]:
    """
    Manual timing approach for benchmarking accuracy
    - Separates retrieval and generation phases
    - Production code would use self.retrieval_chain({"query": question})
    """
    
    """
    PHASE 5A: RETRIEVAL
    - Use vector store's retriever directly
    - Measures only similarity search time
    """
    self.tracker.start_timer()
    
    retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
    retrieved_docs = retriever.get_relevant_documents(question)
    
    self.tracker.stop_timer("retrieval_time")
    
    """
    PHASE 5B: GENERATION
    - Use LLM directly with retrieved context
    - Measures only LLM inference time
    """
    self.tracker.start_timer()
    
    # Prepare context from retrieved documents
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])
    
    # Use standardized prompt template
    prompt = Config.RAG_PROMPT_TEMPLATE.format(
        context=context,
        question=question
    )
    
    # Call LLM directly (bypassing retrieval_chain for timing)
    if hasattr(self.llm, 'invoke'):
        # Newer LangChain versions
        llm_response = self.llm.invoke(prompt)
        answer = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
    else:
        # Older LangChain versions
        answer = self.llm(prompt)
    
    self.tracker.stop_timer("generation_time")
    
    return {
        "question": question,
        "answer": answer,
        "source_documents": [doc.page_content for doc in retrieved_docs],
        "metadata": [doc.metadata for doc in retrieved_docs]
    }
```

### **Phase 6: Production Query Method**
```python
def query_production(self, question: str) -> Dict[str, Any]:
    """
    Production-ready query using RetrievalQA chain
    - Single method call handles everything
    - Better performance but less timing granularity
    """
    # High-level chain execution
    result = self.retrieval_chain({"query": question})
    
    return {
        "question": question,
        "answer": result["result"],
        "source_documents": [doc.page_content for doc in result["source_documents"]],
        "metadata": [doc.metadata for doc in result["source_documents"]]
    }
```

---

## 🦙 LlamaIndex RAG Implementation Flow

### **Architecture Philosophy**
Data-centric design optimized for document understanding and advanced indexing. Focuses on flexible node structures, sophisticated retrieval strategies, and seamless integration with various data sources.

### **Phase 1: Initialization & Global Settings**
```python
def __init__(self, vector_store_type: str = "faiss", llm_provider: str = "openai"):
    self.vector_store_type = vector_store_type
    self.llm_provider = llm_provider
    
    # LlamaIndex components
    self.index = None         # VectorStoreIndex
    self.query_engine = None  # Query engine with retrieval + generation
    self.nodes = None         # Processed document nodes
    
    self.tracker = PerformanceTracker("llamaindex")
    
    # Configure global LlamaIndex settings
    self._setup_global_settings()

def _setup_global_settings(self):
    """
    Configure global LlamaIndex settings
    - Sets default embedding model and LLM for all operations
    - Centralized configuration approach
    """
    # Setup embedding model
    Settings.embed_model = HuggingFaceEmbedding(
        model_name=Config.EMBEDDING_CONFIG.model_name,
        device=Config.EMBEDDING_CONFIG.device,
        normalize=True,
        batch_size=Config.EMBEDDING_CONFIG.batch_size
    )
    
    # Setup LLM
    if self.llm_provider == "openai":
        Settings.llm = OpenAI(
            model=Config.LLM_CONFIGS["openai"].model_name,
            temperature=Config.LLM_CONFIGS["openai"].temperature,
            max_tokens=Config.LLM_CONFIGS["openai"].max_tokens,
            api_key=os.getenv("OPENAI_API_KEY")
        )
```

**Key Dependencies:**
- `llama_index.core.VectorStoreIndex` - Core indexing functionality
- `llama_index.core.Document` - Document abstraction with metadata
- `llama_index.core.Settings` - Global configuration system
- `llama_index.embeddings.huggingface.HuggingFaceEmbedding` - Embedding wrapper
- `llama_index.vector_stores.faiss.FaissVectorStore` - FAISS integration

### **Phase 2: Document Processing**
```python
def process_documents(self, documents: List[Dict[str, str]]):
    """
    PHASE 2A: DOCUMENT CONVERSION TO NODES
    - Convert raw documents to LlamaIndex Document objects
    - Transform Documents to Nodes (text chunks with embeddings)
    """
    
    # Convert to LlamaIndex Documents
    llamaindex_docs = []
    for doc in documents:
        llamaindex_docs.append(Document(
            text=doc["content"],
            metadata={
                "filename": doc.get("filename", "unknown"),
                "source": doc.get("source", "unknown")
            }
        ))
    
    """
    PHASE 2B: NODE PARSING (CHUNKING)
    - Use SimpleNodeParser for text chunking
    - Creates Node objects with metadata preservation
    """
    
    # Initialize node parser (equivalent to text splitter)
    node_parser = SimpleNodeParser.from_defaults(
        chunk_size=Config.CHUNKING_CONFIG.chunk_size,
        chunk_overlap=Config.CHUNKING_CONFIG.chunk_overlap
    )
    
    # Parse documents into nodes
    self.nodes = node_parser.get_nodes_from_documents(llamaindex_docs)
    
    print(f"✅ Processed {len(documents)} documents into {len(self.nodes)} nodes")
```

### **Phase 3: Index Creation**
```python
def create_index(self):
    """
    PHASE 3A: VECTOR STORE SETUP
    - Initialize vector store backend (FAISS or ChromaDB)
    - Configure storage context for persistence
    """
    self.tracker.start_timer()  # Start indexing timing
    
    if self.vector_store_type == "faiss":
        # FAISS vector store setup
        import faiss
        
        # Create FAISS index (dimension auto-detected from embedding model)
        embedding_dim = 384  # all-MiniLM-L6-v2 dimension
        faiss_index = faiss.IndexFlatIP(embedding_dim)  # Inner Product for cosine
        
        # Wrap in LlamaIndex FaissVectorStore
        vector_store = FaissVectorStore(faiss_index=faiss_index)
        
        # Configure storage context with persistence
        storage_context = StorageContext.from_defaults(
            vector_store=vector_store
        )
    
    elif self.vector_store_type == "chroma":
        # ChromaDB vector store setup
        import chromadb
        
        persist_directory = Config.VECTOR_STORE_CONFIGS["chroma"].index_path
        chroma_client = chromadb.PersistentClient(path=persist_directory)
        
        chroma_collection = chroma_client.get_or_create_collection(
            name=Config.VECTOR_STORE_CONFIGS["chroma"].collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        # Wrap in LlamaIndex ChromaVectorStore
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    """
    PHASE 3B: INDEX CONSTRUCTION
    - Create VectorStoreIndex from nodes
    - Handles embedding generation and storage automatically
    """
    
    # Create index from nodes (this triggers embedding generation)
    self.index = VectorStoreIndex(
        nodes=self.nodes,
        storage_context=storage_context,
        show_progress=True
    )
    
    # Stop timing and record vector processing time
    self.tracker.stop_timer("indexing_time")
    self.tracker.metrics.vector_processing_time = getattr(self.tracker.metrics, 'indexing_time', 0.0)
    
    """
    PHASE 3C: PERSISTENCE
    - Save index to disk for future loading
    - Includes both vector data and metadata
    """
    if self.vector_store_type == "faiss":
        persist_dir = Config.VECTOR_STORE_CONFIGS["faiss"].index_path
        Path(persist_dir).parent.mkdir(parents=True, exist_ok=True)
        self.index.storage_context.persist(persist_dir=persist_dir)
```

### **Phase 4: Query Engine Setup**
```python
def setup_query_engine(self):
    """
    Configure query engine with retrieval and generation settings
    - Creates optimized retrieval pipeline
    - Configures response synthesis strategy
    """
    if self.index is None:
        raise ValueError("Index not created. Call create_index() first.")
    
    # Create query engine with similarity-based retrieval
    self.query_engine = self.index.as_query_engine(
        similarity_top_k=3,              # Top-3 retrieval
        response_mode="compact",         # Compact response synthesis
        streaming=False                  # Disable streaming for benchmarking
    )
```

### **Phase 5: Query Processing (Manual Timing)**
```python
def query(self, question: str) -> Dict[str, Any]:
    """
    Manual timing approach for accurate benchmarking
    - Separates retrieval and generation phases
    - Production code would use self.query_engine.query(question)
    """
    
    """
    PHASE 5A: RETRIEVAL
    - Create retriever from index
    - Perform similarity search with node scoring
    """
    self.tracker.start_timer()
    
    # Create retriever (similarity-based)
    retriever = self.index.as_retriever(similarity_top_k=3)
    retrieved_nodes = retriever.retrieve(question)
    
    self.tracker.stop_timer("retrieval_time")
    
    """
    PHASE 5B: GENERATION
    - Prepare context from retrieved nodes
    - Call LLM directly for precise timing
    """
    self.tracker.start_timer()
    
    # Extract text from retrieved nodes
    context = "\n\n".join([node.node.text for node in retrieved_nodes])
    
    # Create prompt manually (replicating query engine behavior)
    prompt = f"""Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.

{context}

Question: {question}
Answer:"""
    
    # Get LLM from global settings and call directly
    llm = Settings.llm
    
    if hasattr(llm, 'chat'):
        # Chat-based LLMs (OpenAI, etc.)
        from llama_index.core.llms import ChatMessage
        messages = [ChatMessage(role="user", content=prompt)]
        llm_response = llm.chat(messages)
        answer = llm_response.message.content
    else:
        # Completion-based LLMs
        llm_response = llm.complete(prompt)
        answer = llm_response.text
    
    self.tracker.stop_timer("generation_time")
    
    """
    PHASE 5C: RESPONSE FORMATTING
    - Extract source information from nodes
    - Include similarity scores and metadata
    """
    result = {
        "question": question,
        "answer": answer,
        "source_documents": [node.node.text for node in retrieved_nodes],
        "metadata": [node.node.metadata for node in retrieved_nodes],
        "scores": [node.score for node in retrieved_nodes]  # LlamaIndex provides scores
    }
    
    return result
```

### **Phase 6: Production Query Method**
```python
def query_production(self, question: str) -> Dict[str, Any]:
    """
    Production-ready query using query engine
    - Single method call with optimized pipeline
    - Better performance but less timing control
    """
    # High-level query engine execution
    response = self.query_engine.query(question)
    
    return {
        "question": question,
        "answer": str(response),
        "source_documents": [node.text for node in response.source_nodes],
        "metadata": [node.metadata for node in response.source_nodes],
        "scores": [node.score for node in response.source_nodes]
    }
```

### **Phase 7: Advanced Features**
```python
def load_existing_index(self):
    """
    Load pre-built index from disk
    - Faster startup for repeated queries
    - Preserves vector store and metadata
    """
    from llama_index.core import load_index_from_storage
    
    if self.vector_store_type == "faiss":
        persist_dir = Config.VECTOR_STORE_CONFIGS["faiss"].index_path
        storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
        self.index = load_index_from_storage(storage_context)
    
    elif self.vector_store_type == "chroma":
        # Recreate storage context for ChromaDB
        persist_directory = Config.VECTOR_STORE_CONFIGS["chroma"].index_path
        chroma_client = chromadb.PersistentClient(path=persist_directory)
        chroma_collection = chroma_client.get_collection(
            name=Config.VECTOR_STORE_CONFIGS["chroma"].collection_name
        )
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        self.index = load_index_from_storage(storage_context)
```

---

## ⏱️ Timing and Performance Measurement

### **Performance Tracker Implementation**
All implementations use a shared `PerformanceTracker` class for consistent measurement:

```python
class PerformanceTracker:
    def __init__(self, method_name: str):
        self.method_name = method_name
        self.metrics = PerformanceMetrics()
        self.start_time = None
        self.process = psutil.Process()  # For memory measurement
    
    def start_timer(self):
        """Start timing operation"""
        self.start_time = time.perf_counter()
    
    def stop_timer(self, metric_name: str):
        """Stop timer and record duration"""
        if self.start_time is None:
            return
        
        duration = time.perf_counter() - self.start_time
        setattr(self.metrics, metric_name, duration)
        self.start_time = None
    
    def record_memory_usage(self):
        """Record current memory usage (RSS)"""
        memory_info = self.process.memory_info()
        self.metrics.memory_usage = memory_info.rss / 1024 / 1024  # Convert to MB
```

### **Timing Semantics**

#### **Vector Processing Time**
- **Manual**: `embedding_time + indexing_time` (timer starts at embedding, stops after index persistence)
- **LangChain**: `chunking + embedding + indexing` (timer around `from_documents()` call)
- **LlamaIndex**: `node_parsing + embedding + indexing` (timer around index creation)

#### **Retrieval Time**
- **Manual**: Pure similarity search time (FAISS.search() or ChromaDB.query())
- **LangChain**: Retriever.get_relevant_documents() including query embedding
- **LlamaIndex**: Retriever.retrieve() including query embedding and node scoring

#### **Generation Time**
- **Manual**: Direct LLM API call time (OpenAI, Gemini, etc.)
- **LangChain**: LLM.invoke() or LLM.call() time only
- **LlamaIndex**: LLM.chat() or LLM.complete() time only

#### **Memory Usage**
- **All Implementations**: RSS (Resident Set Size) of entire Python process
- **Includes**: Loaded models, vector indices, document data, and runtime overhead
- **Measured At**: Peak usage during query processing phase

---

## 📊 Flow Comparison Matrix

| Aspect | Manual RAG | LangChain RAG | LlamaIndex RAG |
|--------|------------|---------------|----------------|
| **🏗️ Architecture** | ||||
| Abstraction Level | Low (direct APIs) | High (chains & components) | Medium (node-centric) |
| Dependencies | Minimal (4 core libs) | Moderate (LangChain ecosystem) | Moderate (LlamaIndex ecosystem) |
| Customization | Maximum control | Component swapping | Node & engine customization |
| Learning Curve | Steep (requires ML knowledge) | Gentle (high-level abstractions) | Moderate (data-centric concepts) |
| **📋 Document Processing** | ||||
| Chunking Strategy | RecursiveCharacterTextSplitter | RecursiveCharacterTextSplitter | SimpleNodeParser |
| Embedding Generation | SentenceTransformer.encode() | HuggingFaceEmbeddings.embed() | HuggingFaceEmbedding.embed() |
| Metadata Handling | Manual dict management | Document.metadata | Node.metadata |
| Batch Processing | Manual batching control | Automatic batching | Automatic batching |
| **🔍 Vector Storage** | ||||
| FAISS Implementation | Native faiss library | LangChain FAISS wrapper | LlamaIndex FaissVectorStore |
| ChromaDB Implementation | Native chromadb client | LangChain Chroma wrapper | LlamaIndex ChromaVectorStore |
| Persistence Strategy | Manual save/load | .save_local()/.load_local() | StorageContext.persist() |
| Index Configuration | Direct FAISS/Chroma setup | Wrapper configuration | VectorStore abstraction |
| **🔎 Retrieval Process** | ||||
| Similarity Search | faiss.search() / chromadb.query() | retriever.get_relevant_documents() | retriever.retrieve() |
| Query Embedding | Manual encode() call | Automatic in retriever | Automatic in retriever |
| Result Formatting | Manual chunk extraction | Document objects | Node objects with scores |
| Score Calculation | Raw similarity scores | LangChain normalization | LlamaIndex scoring |
| **🧠 Generation Process** | ||||
| LLM Integration | Direct API calls | LangChain LLM wrappers | LlamaIndex LLM abstraction |
| Prompt Construction | Manual string formatting | Template system available | Query engine templates |
| Context Assembly | Manual concatenation | Automatic in chains | Automatic in query engine |
| Error Handling | Custom try/catch | LangChain error handling | LlamaIndex error handling |
| **⚡ Performance Characteristics** | ||||
| Memory Efficiency | Highest (minimal overhead) | Moderate (wrapper overhead) | Moderate (framework overhead) |
| Startup Time | Fast (lazy loading) | Moderate (component setup) | Slow (global settings) |
| Query Latency | Lowest (direct calls) | Moderate (chain overhead) | Moderate (engine overhead) |
| Customization Cost | Low (direct control) | Medium (component replacement) | Medium (engine configuration) |
| **🔧 Development Experience** | ||||
| Code Complexity | High (explicit everything) | Low (declarative) | Medium (node-oriented) |
| Debugging | Direct stack traces | Framework stack traces | Framework stack traces |
| Provider Support | Manual integration | Extensive built-in support | Good built-in support |
| Production Readiness | Requires custom work | Production-ready | Production-ready |
| **📈 Scalability** | ||||
| Horizontal Scaling | Manual implementation | LangChain distributed tools | LlamaIndex async support |
| Caching Strategy | Custom implementation | Built-in caching options | Built-in caching options |
| Monitoring | Custom metrics | LangChain callbacks | LlamaIndex callbacks |
| Resource Management | Manual optimization | Framework optimization | Framework optimization |

---

## 🎯 Implementation Recommendations

### **Choose Manual RAG When:**
- ✅ Maximum performance is critical
- ✅ You need complete control over every component
- ✅ Educational/research purposes
- ✅ Minimal dependencies are required
- ✅ Custom optimization strategies needed

### **Choose LangChain RAG When:**
- ✅ Rapid prototyping and development
- ✅ Extensive LLM provider support needed
- ✅ Complex multi-step workflows
- ✅ Large ecosystem of integrations required
- ✅ Team familiar with LangChain patterns

### **Choose LlamaIndex RAG When:**
- ✅ Document-heavy applications
- ✅ Advanced indexing strategies needed
- ✅ Data-centric approach preferred
- ✅ Built-in query optimization required
- ✅ Structured data integration important

---

## 📚 Additional Resources

### **Configuration Files**
- `src/shared/config.py` - Global configuration and model settings
- `src/shared/utils.py` - Performance tracking and evaluation utilities

### **Implementation Files**
- `src/manual_rag/rag_system.py` - Complete manual implementation
- `src/langchain_rag/rag_system.py` - LangChain-based implementation  
- `src/llamaindex_rag/rag_system.py` - LlamaIndex-based implementation

### **Benchmark Runner**
- `src/benchmark_runner.py` - Orchestrates all implementations with timing and evaluation

---

*This document was generated from the actual implementation code in the Week0304 RAG benchmark suite. For the most current implementation details, refer to the source code.*