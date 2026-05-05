# BK-MInD High-Level System Architecture

This document presents a high-level overview of the BK-MInD Multimodal Retrieval-Augmented Generation (MRAG) system architecture, showing the four main layers and their interactions without detailed implementation specifics.

## System Architecture Diagram

```mermaid
graph TB
    Users["👥 Users<br/>Students & Instructors"]
    
    subgraph Frontend["🎨 Frontend Layer"]
        FrontendApp["React SPA<br/>Upload • Search • Chat<br/>Insights • Quiz"]
    end

    subgraph Backend["⚙️ Backend API Layer<br/>FastAPI"]
        APIGateway["REST API Gateway<br/>/api/process, /api/search,<br/>/api/chat, /api/insights, etc."]
        
        subgraph Services["Service Layer"]
            ProcessService["ProcessingService<br/>DocumentProcessingPipeline<br/>7-stage pipeline"]
            SearchOrch["SearchOrchestrator<br/>Text + Image Search<br/>LLM Generation"]
            IndexService["IndexingService<br/>Text + Image Indexing"]
            ChatService["ChatService<br/>Chat History<br/>Multi-turn Conversations"]
        end
        
        subgraph Repos["Repository Layer"]
            TextRepo["TextIndexRepository<br/>BM25 + Dense Embeddings"]
            ImageRepo["ImageIndexRepository<br/>ColQwen Embeddings"]
            DataRepo["DataRepository<br/>User Data, Feedback,<br/>Quiz Results"]
            JobRepo["JobRepository<br/>Job State & Tracking"]
        end
    end

    subgraph External["☁️ External Services"]
        Redis["🔴 Redis<br/>Async Job Queue<br/>Job State Tracking"]
        Qdrant["🟣 Qdrant Cloud<br/>Vector Database<br/>Text & Image Indices"]
        Storage["📦 S3<br/>Document Artifacts<br/>Processing Outputs"]
        Database["🗄️ DynamoDB<br/>Chat History<br/>User Metadata"]
        LLM["🤖 Bedrock/API<br/>LLM Generation<br/>Claude/GPT-4o"]
    end

    subgraph Security["🔒 Security Layer"]
        Auth["JWT Auth<br/>& RBAC"]
        WAF["AWS WAF<br/>& CloudFront"]
        Encryption["TLS Encryption<br/>& KMS"]
    end

    Users -->|HTTPS| Frontend
    Frontend -->|REST API calls| APIGateway
    
    APIGateway --> ProcessService
    APIGateway --> SearchOrch
    APIGateway --> ChatService
    APIGateway --> IndexService
    
    ProcessService -->|uses| Repos
    SearchOrch -->|uses| Repos
    IndexService -->|uses| Repos
    ChatService -->|uses| Repos
    
    JobRepo <-->|queues jobs| Redis
    TextRepo <-->|stores/retrieves| Qdrant
    ImageRepo <-->|stores/retrieves| Qdrant
    DataRepo <-->|stores/retrieves| Database
    ProcessService -->|outputs| Storage
    IndexService -->|uses| Storage
    SearchOrch -->|generates with| LLM
    
    Auth -.->|validates| APIGateway
    WAF -.->|filters| Frontend
    Encryption -.->|protects| External
    
    style Users fill:#e1f5ff
    style Frontend fill:#f3e5f5
    style Backend fill:#fff3e0
    style Services fill:#fffacd
    style Repos fill:#ffe4e1
    style External fill:#e8f5e9
    style Security fill:#ffebee
```

## Architecture Overview

### Layer 1: Frontend (React SPA)
- **Role**: User interface for uploading documents, searching, chatting, generating insights
- **Technology**: React 19 + Vite + TailwindCSS
- **Communication**: All interactions via REST API to the backend
- **Features**: Real-time status updates, streaming chat responses, document preview

### Layer 2: Backend API (FastAPI)

The backend is organized into three logical sub-layers:

#### API Gateway Layer
- Central entry point for all client requests
- Route handlers for processing (`/api/process`), search (`/api/search`), chat (`/api/chat`), indexing (`/api/index`)
- HTTP status management, request validation, authentication

#### Service Layer
- **ProcessingService**: Orchestrates the 7-stage document processing pipeline (see DOCS_PIPELINES_CONSOLIDATED_DOCUMENT.md)
- **SearchOrchestrator**: Handles parallel text and image search, delegates to SearchService instances
- **IndexingService**: Orchestrates text and image indexing into Qdrant
- **ChatService**: Manages multi-turn conversation history and context

#### Repository Layer (Data Access)
- **TextIndexRepository**: Interface to Qdrant for text embeddings (BM25 + dense vectors)
- **ImageIndexRepository**: Interface to Qdrant for image embeddings (ColQwen)
- **DataRepository**: Interface to DynamoDB for user data, chat history, feedback
- **JobRepository**: Interface to Redis for async job queuing and state tracking

### Layer 3: External Services (Cloud Infrastructure)

**Redis** (Async Job Management)
- In-memory data store for job queuing
- Tracks async jobs: process, index_all, index_text
- Job states: `accepted` → `running` → `completed` / `failed`
- Per-user concurrency limit: 3 jobs; Global limit: 200 jobs
- Job TTL: 3600 seconds (auto-cleanup)

**Qdrant Cloud** (Vector Database)
- Stores text embeddings (BM25, dense vectors, hybrid indices)
- Stores image embeddings (ColQwen multi-vector)
- Provides similarity search for retrieval

**Amazon S3** (Document Storage)
- Stores original uploads and processed outputs
- Documents partitioned by user ID
- Encrypted with customer-managed KMS keys

**Amazon DynamoDB** (Persistent Storage)
- Chat history and conversations
- User metadata and settings
- Feedback and quiz results
- Fallback job durability (if Redis unavailable)

**AWS Bedrock / OpenAI API** (LLM Generation)
- Generates answers using retrieved context
- Supports Claude 3.5 Sonnet (via Bedrock) or GPT-4o
- Streaming response for interactive chat

### Layer 4: Security

**Authentication & Authorization**
- JWT tokens for API authentication (24-hour expiration)
- Session management via DynamoDB
- Role-Based Access Control (RBAC): Student, Instructor, Admin
- User identity validation via X-User-Id header

**Network Security**
- AWS CloudFront CDN for edge caching and DDoS protection
- AWS WAF with rules for SQL injection, XSS, rate limiting, bot filtering
- TLS 1.2+ for all HTTPS communication

**Data Security**
- Encryption in-transit: TLS/HTTPS
- Encryption at-rest: S3 (SSE-KMS), DynamoDB (KMS), Qdrant (configured at provisioning)
- Key management: AWS Secrets Manager for credentials
- Multi-tenant isolation: S3 prefix-based isolation, DynamoDB partition keys

---

## Async Job Processing Flow

```mermaid
sequenceDiagram
    actor User
    participant Frontend as React Frontend
    participant API as FastAPI Backend
    participant Redis as Redis Job Queue
    participant Worker as Background Worker
    participant Qdrant as Qdrant Vector DB
    participant Storage as S3 Storage

    User->>Frontend: Upload document
    Frontend->>API: POST /api/process
    API->>Redis: Create job (status: accepted)
    API-->>Frontend: HTTP 202 + job_id
    Frontend->>Frontend: Poll for status
    
    note over Redis: Job waits in queue
    Worker->>Redis: Consume job
    Worker->>Worker: Execute 7-stage pipeline
    Worker->>Storage: Store outputs
    Worker->>Qdrant: Store embeddings
    Worker->>Redis: Update job (status: completed)
    
    Frontend->>API: GET /api/process/status/{job_id}
    API->>Redis: Query job status
    API-->>Frontend: Status: completed
    Frontend->>User: Document is ready!
```

---

## Search & Retrieval Flow

```mermaid
graph TD
    Query["User Query"]
    API["FastAPI /api/search"]
    Orch["SearchOrchestrator"]
    TextSearch["TextSearchService<br/>BM25 + Dense"]
    ImageSearch["ImageSearchService<br/>ColQwen"]
    Qdrant["Qdrant<br/>Similarity Search"]
    Merge["Merge & Rank<br/>Results"]
    LLM["LLM Generation<br/>Answer Synthesis"]
    Response["Search Results +<br/>Generated Answer"]
    
    Query -->|REST API| API
    API --> Orch
    Orth --> TextSearch
    Orth --> ImageSearch
    TextSearch --> Qdrant
    ImageSearch --> Qdrant
    Qdrant -->|Top-K results| Merge
    Merge --> LLM
    LLM --> Response
    Response -->|Stream to User| Query
    
    style Query fill:#e3f2fd
    style API fill:#fff3e0
    style Orch fill:#f3e5f5
    style TextSearch fill:#e8f5e9
    style ImageSearch fill:#e8f5e9
    style Merge fill:#fce4ec
    style LLM fill:#f1f8e9
    style Response fill:#e0f2f1
```

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| **Frontend** | React 19, Vite, TailwindCSS 4.1 |
| **API Framework** | FastAPI (Python 3.10+) |
| **Document Processing** | Docling, Whisper, LibreOffice |
| **Text Embeddings** | Sentence Transformers (all-MiniLM-L6-v2) |
| **Sparse Search** | BM25 (rank-bm25) |
| **Dense Search** | FAISS / Qdrant |
| **Image Embeddings** | ColQwen 2.5 |
| **Vector Database** | Qdrant Cloud |
| **Job Queue** | Redis (async jobs) |
| **Persistent Storage** | S3, DynamoDB |
| **LLM** | Bedrock (Claude) or OpenAI API (GPT-4o) |
| **Security** | AWS WAF, CloudFront, KMS |
| **Deployment** | AWS ECS Fargate + EC2 |

---

## Key Performance Metrics

| Metric | Value |
|--------|-------|
| **Max Concurrent Users** | 20+ |
| **Document Processing Time** | 26-28 seconds (per document) |
| **Query Latency (p95)** | <5 seconds |
| **Per-User Job Limit** | 3 concurrent |
| **Global Job Limit** | 200 concurrent |
| **Job TTL** | 3600 seconds |
| **System Availability** | 99.5% (with auto-scaling) |

---

## Design Principles

1. **Asynchronous Processing**: Long-running operations (document processing, indexing) are offloaded to background jobs managed by Redis, allowing the API to remain responsive
2. **Service-Based Architecture**: Clear separation of concerns between processing, indexing, search, and chat services
3. **Multi-Tenancy**: User data is isolated at the storage level (S3 prefixes, DynamoDB partition keys)
4. **Layered Security**: Multiple defensive layers from network edge (WAF) to application (JWT) to data (encryption)
5. **Conditional Pipeline Routing**: Document processing is optimized by routing only through stages necessary for the detected format

---

## References

- **Detailed Component Architecture**: See [Excalidraw-Architecture-Diagram.png](./Excalidraw-Architecture-Diagram.png)
- **Deployment Infrastructure**: See [Deployment Diagram_v2.png](./Deployment%20Diagram_v2.png)
- **Phase 2 Report Section 4.3**: System Architecture Design (this high-level overview)
