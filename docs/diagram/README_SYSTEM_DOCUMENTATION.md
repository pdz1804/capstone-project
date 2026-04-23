# BK-MInD Capstone System Documentation

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Deployment Architecture](#deployment-architecture)
4. [System Architecture Details](#system-architecture-details)
5. [Data Flows & Processes](#data-flows--processes)
6. [Core Components](#core-components)
7. [API Endpoints](#api-endpoints)
8. [Configuration & Setup](#configuration--setup)
9. [Performance Characteristics](#performance-characteristics)
10. [Technology Stack](#technology-stack)

---

## System Overview

**BK-MInD** (Multimodal Intelligent Notepad for Documents) is a **multimodal RAG (Retrieval-Augmented Generation) system** designed for educational document processing and intelligent question-answering. It processes diverse document types (PDF, DOCX, PPTX, XLSX, Videos, Audio) and provides:

- **Unified document ingestion** with automatic format normalization
- **Multimodal content understanding** (text, images, tables, audio transcripts)
- **Hybrid retrieval** combining sparse (BM25) + dense (embeddings) + visual (ColQwen) search
- **AI-powered generation** using Amazon Bedrock Claude Haiku 4.5
- **Async job-based processing** for scalability (3.6x performance improvement)
- **Multi-tenant architecture** with Firebase authentication and DynamoDB user management

**Key Features**:
- ✅ Process videos, lectures, presentations, spreadsheets, and PDFs
- ✅ Extract text, transcripts, images, tables with full layout preservation
- ✅ Search by content, images, and semantic similarity
- ✅ Generate summaries, study roadmaps, quizzes
- ✅ Real-time async indexing with job tracking
- ✅ Cloud-native deployment (AWS ECS, Qdrant, S3, Bedrock)
- ✅ Enterprise authentication and multi-user isolation

---

## Architecture Diagram

### System Architecture (Logical Components)

**Figure 1: System Architecture - Logical View**

The system comprises five main layers:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ USER LAYER                                                                      │
│ (Browser - HTTP)                                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        ↓
┌─────────────────────────────────────────────────────────────────────────────────┐
│ FRONTEND LAYER (React + Vite + TailwindCSS)                                     │
│ ├─ Upload UI (Drag-and-Drop)                                                    │
│ ├─ Processing Status UI                                                         │
│ ├─ Search / Q&A UI                                                              │
│ └─ Result Display (Markdown + KaTeX + Images)                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        ↓ (HTTP REST API)
┌─────────────────────────────────────────────────────────────────────────────────┐
│ BACKEND LAYER (FastAPI - Python)                                               │
│                                                                                 │
│ ┌──────────────────────────────────────────────────────────────────────────┐   │
│ │ REST API Gateway                                                         │   │
│ ├─ /api/files       - File Upload & Management                            │   │
│ ├─ /api/process     - Document Normalization                             │   │
│ ├─ /api/index       - Async Indexing Jobs (Text + Image)                 │   │
│ ├─ /api/search      - Retrieval & Search                                 │   │
│ ├─ /api/chat        - LLM Chat Completion                                │   │
│ ├─ /api/auth        - User Authentication (Firebase)                     │   │
│ ├─ /api/quiz        - Quiz Generation                                    │   │
│ └─ /api/insights    - Learning Insights & Analytics                      │   │
│ └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│ ┌── Unified RAG Pipeline (Orchestrator) ──────────────────────────────────┐   │
│ │                                                                         │   │
│ │ ┌─────────────────────── PROCESSING PIPELINE ─────────────────────┐   │   │
│ │ │                                                                 │   │   │
│ │ │ Stage 1: Document Normalization                              │   │   │
│ │ │  - Convert DOC/PPT/XLSX/HTML → PDF                           │   │   │
│ │ │  - LibreOffice Converter for compatibility                   │   │   │
│ │ │                                                                 │   │   │
│ │ │ Stage 2: Media Processing                                    │   │   │
│ │ │  - Video/Audio Extraction (MoviePy)                          │   │   │
│ │ │  - Audio Transcription (Whisper ASR - GPU)                   │   │   │
│ │ │  - Frame Deduplication (OpenCV + ImageHash)                  │   │   │
│ │ │                                                                 │   │   │
│ │ │ Stage 3: Document Processing (Docling - GPU)                │   │   │
│ │ │  - Multi-format PDF/XLS/CSV Parsing                          │   │   │
│ │ │  - OCR Engine (RapidOCR / Tesseract / EasyOCR)              │   │   │
│ │ │  - VLM Image Descriptions (Granite Docling)                  │   │   │
│ │ │  - Output: Markdown + Images + Tables + Layout               │   │   │
│ │ │                                                                 │   │   │
│ │ │ Stage 4: RAG-Ready Consolidation                             │   │   │
│ │ │  - Uniform metadata structure                                 │   │   │
│ │ │  - Per-chunk citations and source tracking                    │   │   │
│ │ └─────────────────────────────────────────────────────────────┘   │   │
│ │                                                                 │   │   │
│ │ ┌─────────────────── CHUNKING MODULE ──────────────────────┐   │   │   │
│ │ │ RecursiveCharacterTextSplitter (1000 chars, 200 overlap) │   │   │   │
│ │ │ Format-specific chunking (PDF, DOCX, XLSX)             │   │   │   │
│ │ │ Metadata enrichment (chunk position, source, citations) │   │   │   │
│ │ └─────────────────────────────────────────────────────────┘   │   │   │
│ │                                                                 │   │   │
│ │ ┌─────────────────── RETRIEVAL MODULE ──────────────────────┐   │   │   │
│ │ │                                                            │   │   │   │
│ │ │ TEXT RETRIEVAL:                                           │   │   │   │
│ │ │  - BM25 (Sparse Retrieval) - Per-user sidecar files      │   │   │   │
│ │ │  - Dense Retriever (Sentence-BERT embeddings → Qdrant)   │   │   │   │
│ │ │  - Hybrid (RRF Fusion - α=0.5, combines BM25 + Dense)    │   │   │   │
│ │ │  - Optional Reranking (BGE-Base)                         │   │   │   │
│ │ │                                                            │   │   │   │
│ │ │ IMAGE RETRIEVAL:                                          │   │   │   │
│ │ │  - ColQwen 2.5 (8-bit quantized) Multi-Vector Embeddings │   │   │   │
│ │ │  - Document Page Understanding & Matching                │   │   │   │
│ │ │  - MaxSim fusion for cross-modal scoring                 │   │   │   │
│ │ │                                                            │   │   │   │
│ │ │ SEARCH ORCHESTRATION:                                     │   │   │   │
│ │ │  - Parallel text + image search                           │   │   │   │
│ │ │  - Score normalization and ranking                        │   │   │   │
│ │ │  - Citation extraction from sources                       │   │   │   │
│ │ └────────────────────────────────────────────────────────────┘   │   │   │
│ │                                                                 │   │   │
│ │ ┌──────────────── GENERATION MODULE ────────────────────────┐   │   │   │
│ │ │ Amazon Bedrock Claude Haiku 4.5 (Multimodal)            │   │   │   │
│ │ │ Context-aware answer generation                          │   │   │   │
│ │ │ Citation formatting (inline/numbered)                    │   │   │   │
│ │ │ Token counting & usage tracking                          │   │   │   │
│ │ │ Fallback: OpenAI, Azure, Ollama                          │   │   │   │
│ │ └────────────────────────────────────────────────────────────┘   │   │   │
│ │                                                                 │   │   │
│ │ ┌──────────────── SERVICES LAYER ────────────────────────────┐   │   │   │
│ │ │ User Management & Authentication                          │   │   │   │
│ │ │ Lecture Summary Generator                                 │   │   │   │
│ │ │ Learning Paths & Study Roadmaps                           │   │   │   │
│ │ │ Notification Service                                      │   │   │   │
│ │ │ Quiz Generation & Evaluation                              │   │   │   │
│ │ └────────────────────────────────────────────────────────────┘   │   │   │
│ │                                                                 │   │   │
│ └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        ↓
┌─────────────────────────────────────────────────────────────────────────────────┐
│ GPU MODEL SERVER LAYER (FastAPI - Separate Instance)                            │
│ (Co-located: All GPU-intensive services on single g4dn.xlarge EC2)              │
│                                                                                 │
│ ┌─ Whisper ASR Service ──────────────────────────────────────────────┐         │
│ │ - Audio WAV → Text Transcription (Timestamped Segments)           │         │
│ │ - GPU-Accelerated Inference                                       │         │
│ │ - Endpoint: POST /transcribe                                      │         │
│ └─────────────────────────────────────────────────────────────────────┘        │
│                                                                                 │
│ ┌─ Docling Processing Service ──────────────────────────────────────┐         │
│ │ - Multi-format Document Parsing                                   │         │
│ │ - OCR Engine (RapidOCR on GPU)                                    │         │
│ │ - VLM Picture Descriptions (Granite Docling)                      │         │
│ │ - Output: Markdown + Images + Tables + Layout                     │         │
│ │ - Endpoint: POST /parse-document                                  │         │
│ └─────────────────────────────────────────────────────────────────────┘        │
│                                                                                 │
│ ┌─ ColQwen Inference Service ───────────────────────────────────────┐         │
│ │ - POST /embed-images → Image Pages → Multi-Vector Embeddings     │         │
│ │ - POST /embed-query → Query → Text Embeddings                    │         │
│ │ - POST /score → MaxSim Cross-Modal Scoring                       │         │
│ │ - GET /health → GPU Stats                                         │         │
│ │ - Model: ColQwen 2.5 (8-bit Quantized, ~13GB VRAM)              │         │
│ └─────────────────────────────────────────────────────────────────────┘        │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        ↓
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STORAGE LAYER                                                                   │
│                                                                                 │
│ ┌──────────────────── Vector Database ──────────────────────┐                 │
│ │ Qdrant (Local Docker or Cloud)                            │                 │
│ │ ├─ edu_text_chunks (Dense embeddings + BM25 metadata)     │                 │
│ │ ├─ edu_image_pages (ColQwen multivectors)                 │                 │
│ │ └─ Payload-based user tenancy isolation                   │                 │
│ └──────────────────────────────────────────────────────────┘                  │
│                                                                                 │
│ ┌──────────────────── File Storage ───────────────────────────┐               │
│ │ S3 Buckets (or Local Filesystem):                           │               │
│ │ ├─ ai-service-originals-dev (Raw uploaded files)           │               │
│ │ ├─ ai-service-processed-dev (Normalized + processed docs)  │               │
│ │ └─ Organized by: user_id / document_id / stage output     │               │
│ └──────────────────────────────────────────────────────────┘                  │
│                                                                                 │
│ ┌──────────────────── Sparse Index ───────────────────────────┐               │
│ │ BM25 Indices (Per-user sidecar files)                       │               │
│ │ ├─ Pickled format for fast loading                          │               │
│ │ └─ Stored alongside document metadata                       │               │
│ └──────────────────────────────────────────────────────────┘                  │
│                                                                                 │
│ ┌──────────────────── User & Session DB ──────────────────────┐              │
│ │ DynamoDB (Users Table - phase2-merge-users)                 │              │
│ │ ├─ uid (Partition Key - Firebase UID)                       │              │
│ │ ├─ email, displayName, photoURL                             │              │
│ │ ├─ role, createdAt, lastLogin                               │              │
│ │ └─ User-specific configuration preferences                  │              │
│ └──────────────────────────────────────────────────────────┘                  │
│                                                                                 │
│ ┌──────────────────── Cache & Job Queue ─────────────────────┐               │
│ │ Redis (redis://localhost:6379/0 or AWS ElastiCache)         │               │
│ │ ├─ Search result cache (TTL: 600s)                          │               │
│ │ ├─ Session cache                                            │               │
│ │ ├─ Async job tracking (IndexingJobService)                  │               │
│ │ └─ Job metadata + status + results                          │               │
│ └──────────────────────────────────────────────────────────┘                  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Visual Reference**: See `docs/diagram/Excalidraw-Architecture-Diagram.png`

---

## Deployment Architecture

### Cloud Infrastructure (AWS - us-west-2)

**Figure 2: Deployment Architecture - Physical/Cloud Deployment**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            INTERNET (End Users)                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    ↓ HTTP/HTTPS
┌─────────────────────────────────────────────────────────────────────────────────┐
│ CI/CD PIPELINE (Outside AWS)                                                    │
│                                                                                 │
│  Developer → GitHub Repository                                                  │
│     ↓ (git push)                                                               │
│  GitHub Actions (ubuntu-latest)                                                │
│     ├─ Docker Build (docker buildx)                                            │
│     ├─ Build Backend Image                                                     │
│     ├─ Build Frontend Image                                                    │
│     └─ Push to ECR (sha tag + latest)                                          │
│     ↓ (force-new-deployment)                                                   │
│  ECS Fargate (pulls new images and redeploys)                                  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────────┐
│ AWS CLOUD REGION: us-west-2                                                    │
│                                                                                 │
│ ┌───────────────────────────────────────────────────────────────────────────┐  │
│ │ IMAGE REGISTRY (Amazon ECR)                                              │  │
│ │  ├─ rag-pipeline-backend:latest (SHA tagged for CD)                      │  │
│ │  │  └─ Scan on Push: Enabled (Security scanning)                         │  │
│ │  └─ rag-pipeline-frontend:latest                                         │  │
│ │     └─ Image Retention: 10 latest images                                 │  │
│ └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│ ┌───────────────────────────────────────────────────────────────────────────┐  │
│ │ VPC: Default VPC (us-west-2)                                             │  │
│ │                                                                            │  │
│ │ ┌─ LOAD BALANCER COMPONENT ────────────────────────────────────┐        │  │
│ │ │                                                                 │        │  │
│ │ │ Application Load Balancer (rag-pipeline-alb)                  │        │  │
│ │ │  ├─ HTTP Listener :80                                          │        │  │
│ │ │  ├─ Routing Rules:                                             │        │  │
│ │ │  │  ├─ Default Route: /* → Frontend Target Group :3000         │        │  │
│ │ │  │  └─ Priority 1: /api/* → Backend Target Group :5000        │        │  │
│ │ │  ├─ Security Group: Allow HTTP/HTTPS Inbound                  │        │  │
│ │ │  └─ Planned: HTTPS with AWS Certificate Manager              │        │  │
│ │ │                                                                 │        │  │
│ │ └─────────────────────────────────────────────────────────────────┘        │  │
│ │                                    ↓                                        │  │
│ │ ┌─ CONTAINER ORCHESTRATION ────────────────────────────────────┐        │  │
│ │ │                                                                 │        │  │
│ │ │ ECS Cluster (rag-pipeline-cluster)                            │        │  │
│ │ │  └─ Launch Type: Fargate (Serverless containers)             │        │  │
│ │ │  └─ Platform Version: LATEST                                  │        │  │
│ │ │  └─ Container Insights: Enabled (Performance monitoring)      │        │  │
│ │ │                                                                 │        │  │
│ │ │  ┌─ BACKEND SERVICE ─────────────────────────────┐           │        │  │
│ │ │  │ Service Name: rag-pipeline-cluster-backend-service        │        │  │
│ │ │  │ Desired Count: 1 (with auto-scaling)                      │        │  │
│ │ │  │ Launch Type: Fargate                                       │        │  │
│ │ │  │                                                             │        │  │
│ │ │  │ Task Definition: rag-pipeline-cluster-backend-task        │        │  │
│ │ │  │  ├─ CPU: 512 (0.25 vCPU)                                   │        │  │
│ │ │  │  ├─ Memory: 1024 MB                                        │        │  │
│ │ │  │  ├─ Image: ECR backend:latest                              │        │  │
│ │ │  │  ├─ Port: 5000 (FastAPI)                                   │        │  │
│ │ │  │  ├─ Health Check: GET /health                              │        │  │
│ │ │  │  ├─ Log Driver: awslogs                                    │        │  │
│ │ │  │  │  └─ Log Group: /ecs/rag-pipeline-cluster/backend       │        │  │
│ │ │  │  │  └─ Retention: 7 days                                   │        │  │
│ │ │  │  └─ Environment Variables:                                 │        │  │
│ │ │  │     ├─ QDRANT_MODE (cloud/docker)                          │        │  │
│ │ │  │     ├─ AWS_REGION=us-west-2                                │        │  │
│ │ │  │     ├─ S3 buckets (originals + processed)                  │        │  │
│ │ │  │     ├─ BEDROCK_REGION=us-west-2                            │        │  │
│ │ │  │     └─ FIREBASE_SERVICE_ACCOUNT_PATH (mounted secret)      │        │  │
│ │ │  │                                                             │        │  │
│ │ │  │ Auto-Scaling:                                              │        │  │
│ │ │  │  ├─ Min: 1 | Max: 10 tasks                                 │        │  │
│ │ │  │  ├─ CPU Target: 70%                                        │        │  │
│ │ │  │  ├─ Memory Target: 80%                                     │        │  │
│ │ │  │  ├─ Scale-Out: 60 seconds                                  │        │  │
│ │ │  │  └─ Scale-In: 300 seconds                                  │        │  │
│ │ │  └──────────────────────────────────────────────┘           │        │  │
│ │ │                                                             │        │  │
│ │ │  ┌─ FRONTEND SERVICE ────────────────────────────┐         │        │  │
│ │ │  │ Service Name: rag-pipeline-cluster-frontend-service     │        │  │
│ │ │  │ Desired Count: 1 (with auto-scaling)                    │        │  │
│ │ │  │                                                         │        │  │
│ │ │  │ Task Definition: rag-pipeline-cluster-frontend-task    │        │  │
│ │ │  │  ├─ CPU: 256 (0.25 vCPU)                                 │        │  │
│ │ │  │  ├─ Memory: 512 MB                                       │        │  │
│ │ │  │  ├─ Image: ECR frontend:latest                           │        │  │
│ │ │  │  ├─ Port: 3000 (Nginx serving React build)               │        │  │
│ │ │  │  ├─ Health Check: GET /health                            │        │  │
│ │ │  │  ├─ Log Driver: awslogs                                  │        │  │
│ │ │  │  │  └─ Log Group: /ecs/rag-pipeline-cluster/frontend     │        │  │
│ │ │  │  └─ Environment Variables:                               │        │  │
│ │ │  │     ├─ REACT_APP_API_URL=http://ALB_DNS/api             │        │  │
│ │ │  │     └─ NODE_ENV=production                               │        │  │
│ │ │  │                                                         │        │  │
│ │ │  │ Auto-Scaling:                                            │        │  │
│ │ │  │  ├─ Min: 1 | Max: 5 tasks                                │        │  │
│ │ │  │  ├─ CPU Target: 70%                                      │        │  │
│ │ │  │  └─ Memory Target: 80%                                   │        │  │
│ │ │  └──────────────────────────────────────────────┘         │        │  │
│ │ │                                                             │        │  │
│ │ │  Security Group (ECS Tasks):                               │        │  │
│ │ │   ├─ Inbound: From ALB SG on 3000, 5000                    │        │  │
│ │ │   ├─ Inbound: Inter-task communication                      │        │  │
│ │ │   └─ Outbound: All traffic (to GPU, S3, Qdrant, Bedrock)   │        │  │
│ │ │                                                             │        │  │
│ │ └─────────────────────────────────────────────────────────────┘        │  │
│ │                                                                         │  │
│ │ ┌─ GPU INFERENCE COMPONENT ──────────────────────────────────┐        │  │
│ │ │                                                                │        │  │
│ │ │ EC2 Instance: g4dn.xlarge (NVIDIA T4 GPU - 16GB VRAM)         │        │  │
│ │ │  ├─ Instance Type: GPU-accelerated compute                    │        │  │
│ │ │  ├─ Availability Zone: us-west-2a                             │        │  │
│ │ │  ├─ Security Group: Allow from Backend SG on ports 5001-5003 │        │  │
│ │ │  └─ IAM Role: Allows ECR pull, S3 read, CloudWatch logs       │        │  │
│ │ │                                                                │        │  │
│ │ │  ├─ WHISPER ASR SERVICE (Port 5001)                           │        │  │
│ │ │  │  ├─ Audio WAV → Transcript (Timestamped Segments)          │        │  │
│ │ │  │  ├─ GPU-Accelerated Inference                              │        │  │
│ │ │  │  ├─ Endpoint: POST /transcribe                             │        │  │
│ │ │  │  └─ Model: Whisper (multilingual)                          │        │  │
│ │ │  │                                                                │        │  │
│ │ │  ├─ DOCLING PROCESSING SERVICE (Port 5002)                    │        │  │
│ │ │  │  ├─ Multi-format Document Parsing                          │        │  │
│ │ │  │  ├─ OCR Engine (RapidOCR on GPU)                           │        │  │
│ │ │  │  ├─ VLM Picture Descriptions (Granite Docling)             │        │  │
│ │ │  │  ├─ Endpoint: POST /parse-document                         │        │  │
│ │ │  │  └─ Output: Markdown + Images + Tables + Layout            │        │  │
│ │ │  │                                                                │        │  │
│ │ │  └─ COLQWEN INFERENCE SERVICE (Port 5003)                     │        │  │
│ │ │     ├─ Model: ColQwen 2.5 (8-bit Quantized, ~13GB VRAM)       │        │  │
│ │ │     ├─ Endpoints:                                              │        │  │
│ │ │     │  ├─ POST /embed-images → Multi-Vector Embeddings        │        │  │
│ │ │     │  ├─ POST /embed-query → Query Embeddings                │        │  │
│ │ │     │  ├─ POST /score → MaxSim Cross-Modal Scoring            │        │  │
│ │ │     │  └─ GET /health → GPU Stats                             │        │  │
│ │ │     └─ Late-Interaction Architecture for document pages       │        │  │
│ │ │                                                                │        │  │
│ │ └──────────────────────────────────────────────────────────────┘        │  │
│ │                                                                          │  │
│ └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│ ┌───────────────────────────────────────────────────────────────────────────┐  │
│ │ STORAGE COMPONENTS                                                        │  │
│ │                                                                            │  │
│ │  ┌─ Cloud Vector Database ──────────────────┐                           │  │
│ │  │ Qdrant Cloud (or Docker)                  │                           │  │
│ │  │ ├─ Cluster: cloud.qdrant.io               │                           │  │
│ │  │ ├─ Collections:                           │                           │  │
│ │  │ │  ├─ edu_text_chunks (Dense vectors)    │                           │  │
│ │  │ │  └─ edu_image_pages (ColQwen vectors)  │                           │  │
│ │  │ └─ User isolation via payload            │                           │  │
│ │  └──────────────────────────────────────────┘                           │  │
│ │                                                                            │  │
│ │  ┌─ Object Storage (Amazon S3) ──────────────┐                          │  │
│ │  │ Bucket 1: ai-service-originals-dev        │                          │  │
│ │  │  └─ Raw uploaded files (videos, PDFs)     │                          │  │
│ │  │                                             │                          │  │
│ │  │ Bucket 2: ai-service-processed-dev        │                          │  │
│ │  │  ├─ Normalized PDFs                        │                          │  │
│ │  │  ├─ Extracted markdown + images            │                          │  │
│ │  │  ├─ Extracted audio transcripts            │                          │  │
│ │  │  └─ RAG-ready JSON metadata                │                          │  │
│ │  └──────────────────────────────────────────┘                           │  │
│ │                                                                            │  │
│ │  ┌─ User & Session Database ─────────────────┐                          │  │
│ │  │ Amazon DynamoDB (phase2-merge-users table) │                          │  │
│ │  │ ├─ Partition Key: uid (Firebase UID)       │                          │  │
│ │  │ ├─ Sort Key: None                           │                          │  │
│ │  │ ├─ Attributes: email, displayName, role    │                          │  │
│ │  │ └─ GSI: By email for lookups                │                          │  │
│ │  └──────────────────────────────────────────┘                           │  │
│ │                                                                            │  │
│ │  ┌─ Cache & Session Store ───────────────────┐                          │  │
│ │  │ Redis (ElastiCache or Local Docker)        │                          │  │
│ │  │ ├─ Search result cache (TTL: 600s)         │                          │  │
│ │  │ ├─ Session tokens                          │                          │  │
│ │  │ ├─ Async job tracking                      │                          │  │
│ │  │ └─ Rate limiting counters                  │                          │  │
│ │  └──────────────────────────────────────────┘                           │  │
│ │                                                                            │  │
│ └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│ ┌───────────────────────────────────────────────────────────────────────────┐  │
│ │ MONITORING & OPERATIONS                                                  │  │
│ │                                                                            │  │
│ │  ┌─ Logging (Amazon CloudWatch) ────────────────┐                       │  │
│ │  │ Log Groups:                                   │                       │  │
│ │  │  ├─ /ecs/rag-pipeline-cluster/backend        │                       │  │
│ │  │  │  └─ Retention: 7 days                      │                       │  │
│ │  │  └─ /ecs/rag-pipeline-cluster/frontend       │                       │  │
│ │  │     └─ Retention: 7 days                      │                       │  │
│ │  └────────────────────────────────────────────────┘                      │  │
│ │                                                                            │  │
│ │  ┌─ Auto-Scaling ─────────────────────────────────┐                     │  │
│ │  │ Target Scaling Policies:                       │                     │  │
│ │  │  ├─ Backend: CPU 70%, Memory 80%              │                     │  │
│ │  │  └─ Frontend: CPU 70%, Memory 80%              │                     │  │
│ │  │ Scale-Out: 60s | Scale-In: 300s                │                     │  │
│ │  └────────────────────────────────────────────────┘                     │  │
│ │                                                                            │  │
│ │  ┌─ IAM Roles & Permissions ──────────────────────┐                     │  │
│ │  │ Backend Task Execution Role:                   │                     │  │
│ │  │  ├─ ECR Pull (backend image)                   │                     │  │
│ │  │  └─ CloudWatch Logs Write                      │                     │  │
│ │  │                                                 │                     │  │
│ │  │ Backend Task Role:                             │                     │  │
│ │  │  ├─ S3 Read/Write (buckets)                    │                     │  │
│ │  │  ├─ Bedrock InvokeModel                        │                     │  │
│ │  │  ├─ DynamoDB Read/Write (users table)          │                     │  │
│ │  │  └─ CloudWatch Metrics Put                     │                     │  │
│ │  │                                                 │                     │  │
│ │  │ Frontend Task Execution Role:                  │                     │  │
│ │  │  ├─ ECR Pull (frontend image)                  │                     │  │
│ │  │  └─ CloudWatch Logs Write                      │                     │  │
│ │  └────────────────────────────────────────────────┘                     │  │
│ │                                                                            │  │
│ └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│ ┌───────────────────────────────────────────────────────────────────────────┐  │
│ │ PLANNED / NOT YET PROVISIONED                                            │  │
│ │ (Shown with dashed borders in architecture)                              │  │
│ │                                                                            │  │
│ │  ├─ Amazon CloudFront (CDN for static assets)                            │  │
│ │  ├─ AWS WAF (Web Application Firewall)                                   │  │
│ │  ├─ Amazon RDS PostgreSQL (relational database)                          │  │
│ │  ├─ Amazon ElastiCache Redis (managed cache)                             │  │
│ │  ├─ Amazon SQS (async job queue)                                         │  │
│ │  └─ Amazon Cognito (user authentication)                                 │  │
│ │                                                                            │  │
│ └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Visual Reference**: See `docs/diagram/Deployment Diagram_v3.png`

**Key Infrastructure Details**:
- **Region**: us-west-2 (Oregon)
- **Terraform Managed**: 36+ AWS resources
- **Auto-Scaling**: Min 1, Max 10 (backend), Min 1, Max 5 (frontend)
- **Container Registry**: Amazon ECR with security scanning enabled
- **Monitoring**: CloudWatch with 7-day log retention

---

## System Architecture Details

### 1. Frontend Layer (React 18 + Vite + TailwindCSS)

**Location**: `Phase_2_FE_AI_Merge/frontend/`

**Architecture**:
```
src/
├── api/
│   ├── client.ts              # Axios HTTP client with auth headers
│   └── ragApi.ts              # High-level API wrappers
├── views/
│   ├── ChatAssistantView.tsx       # Main conversation interface
│   ├── KnowledgeDashboardView.tsx  # Knowledge base explorer
│   ├── KnowledgeManagementView.tsx # File upload & indexing UI
│   ├── AdminDashboardView.tsx      # Admin panel
│   ├── LectureView.tsx             # Lecture viewer
│   └── DashboardView.tsx           # User dashboard
├── components/
│   ├── IndexManagement.tsx         # Async job polling UI
│   ├── ProcessingPipeline.tsx      # Progress visualization
│   └── ErrorBoundary.tsx           # Error handling
├── services/
│   └── auth_service.ts             # Firebase authentication
├── database/
│   └── types.ts                    # TypeScript type definitions
└── main.tsx                        # React app entry point
```

**Key Features**:
- **Authentication**: Firebase integration with X-User-Id header
- **File Upload**: Drag-and-drop multipart form upload
- **Job Polling**: Real-time polling of `/api/index/status/{job_id}`
- **Search UI**: Combined text + image search interface
- **Chat Interface**: Streaming response handling
- **Responsive Design**: Tailwind CSS responsive components

### 2. Backend Layer (FastAPI - Python)

**Location**: `Phase_2_FE_AI_Merge/backend/`

**Core Architecture**:
```
backend/
├── app/
│   ├── main.py                 # FastAPI app initialization & middleware
│   ├── api/
│   │   ├── routes/
│   │   │   ├── health_routes.py           # /health, /api/health
│   │   │   ├── status_routes.py           # /api/status/*
│   │   │   ├── config_routes.py           # /api/config
│   │   │   ├── files_routes.py            # /api/upload, /api/files
│   │   │   ├── pipeline_routes.py         # /api/process, /api/index/* (ASYNC)
│   │   │   ├── search_routes.py           # /api/search/*
│   │   │   ├── chat_routes.py             # /api/chat, /api/chat/stream
│   │   │   ├── chat_history_routes.py     # /api/chat-history/*
│   │   │   ├── images_routes.py           # /api/images/*
│   │   │   ├── quiz_routes.py             # /api/quiz/*
│   │   │   ├── feedback_routes.py         # /api/feedback/*
│   │   │   ├── insights_routes.py         # /api/insights/*
│   │   │   └── system_routes.py           # /api/system/*
│   │   ├── deps.py                         # Dependency injection (user_id, etc.)
│   │   └── schemas.py                      # Request/response models
│   ├── core/
│   │   ├── config.py                       # Configuration loading
│   │   ├── paths.py                        # Path utilities
│   │   └── qdrant_errors.py               # Qdrant error handling
│   ├── services/
│   │   ├── indexing_job_service.py        # Async job lifecycle management (NEW)
│   │   ├── indexing_service.py             # Text + Image indexing orchestration
│   │   ├── processing_service.py           # Document processing invocation
│   │   ├── search_orchestrator.py          # Multi-method search coordination
│   │   ├── colqwen_inference.py            # ColQwen embedding service
│   │   ├── document_chunks.py              # Chunk loading from RAG structure
│   │   ├── citation_uris.py                # Citation enrichment
│   │   └── processed_markdown_service.py   # Markdown artifact handling
│   ├── repositories/
│   │   ├── text_index_repository.py        # Qdrant dense + BM25 sidecar
│   │   ├── image_index_repository.py       # Qdrant ColQwen multivectors
│   │   ├── qdrant_point_ids.py             # Point ID mapping
│   │   └── bm25_store.py                   # BM25 persistence
│   ├── identity/
│   │   ├── firebase_auth.py                # Firebase token validation
│   │   ├── local_auth.py                   # Local auth fallback
│   │   ├── user_repository_dynamo.py       # DynamoDB user storage
│   │   └── routes.py                       # Auth endpoints
│   └── admin/
│       └── routes.py                       # Admin endpoints
├── src/
│   ├── processor/
│   │   ├── pipeline.py                    # Main orchestrator (4-stage)
│   │   ├── normalizer.py                  # Stage 1: Format normalization
│   │   ├── media_processor_enhanced.py    # Stage 2: Audio/video extraction
│   │   ├── document_processor_v2_1.py     # Stage 3: Docling-based parsing
│   │   ├── consolidator.py                # Stage 4: RAG-ready assembly
│   │   ├── pdf_reader.py                  # PDF-specific reading
│   │   ├── pptx_reader.py                 # PPTX-specific reading
│   │   ├── xlsx_reader_v2.py              # XLSX-specific reading
│   │   └── utils.py                       # Helper functions
│   ├── chunking/
│   │   ├── chunker.py                    # RecursiveCharacterTextSplitter
│   │   ├── docx_chunker.py               # DOCX-specific chunking
│   │   ├── excel_chunker.py              # XLSX-specific chunking
│   │   ├── pdf_chunker.py                # PDF-specific chunking
│   │   ├── docx_preprocessor.py          # DOCX pre-processing
│   │   └── excel_preprocessor.py         # XLSX pre-processing
│   ├── retrieval/
│   │   ├── rag_retrievers.py             # BM25, Dense, Hybrid
│   │   ├── image_retrievers.py           # ColQwen visual retrieval
│   │   └── chunking_utils.py             # Helper functions
│   ├── generation/
│   │   └── generator.py                  # LLM answer generation (Bedrock)
│   ├── evaluation/
│   │   ├── benchmark.py                  # Benchmark runner
│   │   └── metrics.py                    # Evaluation metrics
│   └── unified_rag_pipeline.py            # CLI entry point
├── config/
│   └── default.yaml                       # Complete pipeline configuration
└── run_api.py                             # FastAPI server launcher
```

**Request Processing Flow**:
```
HTTP Request
    ↓
FastAPI Router (routes/)
    ↓
Dependency Injection (deps.py) - Extract user_id from header
    ↓
Schema Validation
    ↓
Service Layer (services/) - Business logic
    ↓
Repository Layer (repositories/) - Data persistence
    ↓
HTTP Response
```

### 3. Document Processing Pipeline (4-Stage Architecture)

The heart of the system - transforms raw documents into RAG-ready indexed content.

**Stage 1: Document Normalization**
```python
Input: DOCX, PPTX, XLSX, HTML, TXT, DOC, etc.
↓
[Normalizer]
├─ Detect format
├─ If not PDF: Convert via LibreOffice
├─ Extract metadata (title, author, created date)
├─ Preserve structure (chapters, sections)
└─ Output: PDF + Markdown + Images
```

**Stage 2: Media Processing**
```python
Input: Video (MP4, AVI), Audio (MP3, WAV)
↓
[MediaProcessor]
├─ Extract audio (MoviePy)
├─ Convert to WAV format
├─ Send to Whisper ASR Service (GPU)
├─ Receive transcript with timestamps
├─ Extract key frames (OpenCV)
├─ Deduplicate frames (ImageHash)
└─ Output: Transcript + Frame images + Metadata
```

**Stage 3: Document Processing (Docling - GPU-Accelerated)**
```python
Input: PDF, XLSX, CSV, Markdown, Images, TXT
↓
[DocumentProcessor (SageMaker or Local)]
├─ PDF/XLSX parsing
├─ OCR (RapidOCR on GPU)
├─ VLM Image descriptions (Granite Docling)
├─ Table extraction
├─ Formula extraction
├─ Layout understanding
└─ Output: Markdown + Images + Tables + Layout JSON
```

**Stage 4: Consolidation**
```python
Input: Outputs from Stages 1-3
↓
[Consolidator]
├─ Merge all content
├─ Add metadata (source, stage, format)
├─ Create RAG-ready JSON structure
├─ Add citations and source tracking
└─ Output: RAG-ready consolidated document

Final JSON Structure:
{
  "document_id": "uuid",
  "user_id": "firebase_uid",
  "title": "...",
  "source_format": "pptx",
  "stages": {
    "normalization": {...},
    "media": {...},
    "docling": {...}
  },
  "chunks": [
    {
      "chunk_id": "...",
      "text": "...",
      "metadata": {
        "source_file": "...",
        "page": 1,
        "section": "...",
        "images": [...]
      }
    }
  ]
}
```

### 4. Hybrid Retrieval System

**Text Retrieval Pipeline**:
```
Query: "What is supervised learning?"
↓
[Text Retrieval Module]
├─ Path 1: BM25 Sparse Retrieval
│  ├─ Load per-user BM25 index (sidecar file)
│  ├─ Tokenize query
│  ├─ Compute term frequencies
│  └─ Return top-k candidates (default: 50)
│
├─ Path 2: Dense Retrieval
│  ├─ Embed query (Sentence-Transformers)
│  ├─ Query Qdrant (edu_text_chunks collection)
│  ├─ Use vector similarity search
│  └─ Return top-k candidates (default: 50)
│
└─ Path 3: Hybrid (RRF Fusion)
   ├─ Get BM25 rank list
   ├─ Get Dense rank list
   ├─ Normalize scores: (k + rank)^-1
   ├─ Combine: α * dense_score + (1-α) * bm25_score (α=0.5)
   ├─ Re-rank by combined score
   └─ Return top-k (default: 10)

Optional: Reranking with BGE-Base model
```

**Image Retrieval Pipeline**:
```
Query: "Show me diagrams about neural networks"
↓
[Image Retrieval Module]
├─ Embed query (ColQwen)
├─ Query Qdrant (edu_image_pages collection)
├─ Use multi-vector similarity (maxsim)
└─ Return top-k image pages (default: 10)
```

**Combined Search**:
```
User Query
↓
[Search Orchestrator]
├─ Parallel text + image search
├─ Score normalization (0-1 range)
├─ Combine with configurable weights
├─ Re-rank by combined score
├─ Add citations and source URLs
└─ Return unified result set
```

### 5. Async Job-Based Indexing (Recent Optimization)

**Architecture** (commit fbe2906):
```
POST /api/index (Text) or /api/index/image (Image)
    ↓
[IndexingJobService - Redis-backed]
├─ Create job ID (UUID)
├─ Store job metadata: {status: "queued", progress: 0}
├─ Return immediately: {job_id: "...", status: "queued"}
├─ Enqueue background task
└─ Concurrency check:
   ├─ Max 3 jobs per user
   ├─ Max 20 global concurrent jobs
   └─ Queue excess jobs

Background Task Execution:
├─ Update status: "indexing" (progress: 25%)
├─ Process document (CPU-intensive)
├─ Send to Qdrant / Store BM25 (progress: 75%)
├─ Update status: "completed" or "failed"
├─ Store result in Redis (TTL: 1 hour)
└─ Clean up resources

Client Polling:
GET /api/index/status/{job_id}
└─ Response: {status, progress, result, error}
```

---

## Data Flows & Processes

### Flow 1: Document Upload and Indexing

```
┌─────────────────────────────────────────────────────────────────┐
│ DOCUMENT UPLOAD FLOW                                            │
└─────────────────────────────────────────────────────────────────┘

1. USER UPLOADS DOCUMENT
   ├─ Frontend: Drag-drop or file selector
   ├─ File: lecture.pptx (50MB)
   ├─ HTTP: POST /api/upload (multipart form-data)
   └─ Header: X-User-Id: user123

2. BACKEND RECEIVES UPLOAD
   ├─ Validate file (size, type, antivirus scan - planned)
   ├─ Generate document_id (UUID)
   ├─ Save to S3 (ai-service-originals-dev bucket)
   │  └─ Path: s3://originals/user123/document_id/lecture.pptx
   ├─ Create document metadata record
   └─ Response: {document_id, status: "uploaded"}

3. TRIGGER ASYNC PROCESSING
   ├─ HTTP: POST /api/process
   ├─ Payload: {document_id, enable_media: true, enable_docling: true}
   ├─ Create job: {job_id, status: "queued"}
   └─ Response: {job_id, status: "queued"} (immediate)

4. BACKGROUND PROCESSING (Async Task)
   ├─ Status: "processing" (progress: 10%)
   │
   ├─ STAGE 1: NORMALIZATION
   │  ├─ Download from S3
   │  ├─ Detect: PPTX file
   │  ├─ Extract slides as PDF
   │  ├─ Save: s3://processed/user123/doc_id/normalized.pdf
   │  └─ Progress: 25%
   │
   ├─ STAGE 2: MEDIA PROCESSING
   │  ├─ Check for embedded videos/audio
   │  ├─ Extract audio using MoviePy
   │  ├─ Convert to WAV: audio.wav
   │  ├─ Send to GPU Whisper Service (HTTP REST)
   │  ├─ Receive transcript: [{text, start_time, end_time}]
   │  ├─ Save transcript: s3://processed/.../transcript.json
   │  ├─ Extract key frames
   │  ├─ Deduplicate frames
   │  ├─ Save frames: s3://processed/.../frames/
   │  └─ Progress: 40%
   │
   ├─ STAGE 3: DOCUMENT PROCESSING (DOCLING)
   │  ├─ Download normalized.pdf
   │  ├─ Send to GPU Docling Service (HTTP REST)
   │  ├─ Receive: {markdown, images, tables, layout_json}
   │  ├─ Save markdown: s3://processed/.../content.md
   │  ├─ Save images: s3://processed/.../images/
   │  └─ Progress: 60%
   │
   ├─ STAGE 4: CONSOLIDATION
   │  ├─ Merge all stage outputs
   │  ├─ Create RAG-ready JSON
   │  ├─ Add metadata and citations
   │  ├─ Save: s3://processed/.../rag_ready.json
   │  └─ Progress: 75%
   │
   ├─ Status: "indexing" (progress: 80%)
   │
   └─ Job Status Updated in Redis:
      {job_id, status: "completed", result: {document_id, processed_file_path}}
      (TTL: 1 hour)

5. CLIENT POLLS FOR STATUS
   ├─ Polling: GET /api/index/status/{job_id} (every 2 seconds)
   ├─ Response (while processing):
   │  {
   │    "status": "processing",
   │    "job_id": "...",
   │    "progress": 75,
   │    "stage": "indexing"
   │  }
   │
   └─ Response (completed):
      {
        "status": "completed",
        "job_id": "...",
        "progress": 100,
        "result": {
          "document_id": "...",
          "chunks_count": 245,
          "pages": 12,
          "processing_time_ms": 45000
        }
      }

┌─────────────────────────────────────────────────────────────────┐
│ INDEXING FLOW (After Processing)                               │
└─────────────────────────────────────────────────────────────────┘

6. TRIGGER INDEXING
   ├─ HTTP: POST /api/index/text (after processing completes)
   ├─ Payload: {document_id, chunk_strategy: "recursive"}
   ├─ Create indexing job
   └─ Response: {job_id, status: "queued"}

7. TEXT INDEXING (Background Task)
   ├─ Status: "indexing" (progress: 10%)
   │
   ├─ Load RAG-ready JSON from S3
   ├─ Chunk text (RecursiveCharacterTextSplitter)
   │  ├─ Chunk size: 1000 chars
   │  ├─ Overlap: 200 chars
   │  └─ Minimum: 50 chars (skip smaller)
   │
   ├─ For each chunk:
   │  ├─ Compute BM25 tokens → Store in per-user BM25 index
   │  ├─ Embed (Sentence-BERT) → Send to Qdrant
   │  │  └─ Collection: edu_text_chunks
   │  │  └─ Point: {chunk_id, embedding, payload: {user_id, document_id, text, source}}
   │  └─ Progress incremented
   │
   ├─ Save BM25 index (pickle)
   │  └─ s3://processed/user123/bm25_indices/{document_id}.pkl
   │
   └─ Job Status: "completed"

8. IMAGE INDEXING (Background Task)
   ├─ Status: "indexing" (progress: 10%)
   │
   ├─ Load extracted images from s3://processed/.../images/
   ├─ For each image (PDF page):
   │  ├─ Send to GPU ColQwen Service (HTTP REST)
   │  ├─ Receive multi-vector embeddings
   │  ├─ Send to Qdrant
   │  │  └─ Collection: edu_image_pages
   │  │  └─ Point: {image_id, embeddings[], payload: {user_id, page_num, source}}
   │  └─ Progress incremented
   │
   └─ Job Status: "completed"
```

### Flow 2: Search and Answer Generation

```
┌─────────────────────────────────────────────────────────────────┐
│ SEARCH & QUESTION-ANSWERING FLOW                                │
└─────────────────────────────────────────────────────────────────┘

1. USER ASKS QUESTION
   ├─ Frontend: Type question
   ├─ Question: "Explain neural network architecture"
   ├─ HTTP: POST /api/search
   ├─ Payload: {query, search_type: "hybrid", top_k: 10}
   ├─ Header: X-User-Id: user123
   └─ Response: Immediate (fast retrieval)

2. SEARCH ORCHESTRATION
   ├─ Parallel Paths:
   │
   ├─ PATH A: TEXT SEARCH
   │  ├─ BM25 Sparse Retrieval
   │  │  ├─ Load per-user BM25 index from S3
   │  │  ├─ Tokenize query
   │  │  ├─ Compute term frequencies
   │  │  └─ Get top-50 candidates with scores
   │  │
   │  └─ Dense Retrieval
   │     ├─ Embed query (Sentence-BERT)
   │     ├─ Query Qdrant (edu_text_chunks)
   │     ├─ Filter by user_id (payload filter)
   │     └─ Get top-50 candidates with scores
   │
   ├─ PATH B: IMAGE SEARCH
   │  ├─ Embed query (ColQwen)
   │  ├─ Query Qdrant (edu_image_pages)
   │  ├─ Filter by user_id (payload filter)
   │  └─ Get top-10 image candidates with scores
   │
   └─ FUSION
      ├─ Hybrid (RRF) for text:
      │  ├─ Normalize BM25 scores
      │  ├─ Normalize Dense scores
      │  ├─ Combine: 0.5 * normalized_dense + 0.5 * normalized_bm25
      │  └─ Re-rank and get top-10
      │
      ├─ Combine text + image results
      ├─ De-duplicate overlapping chunks
      └─ Final ranking: text (8) + images (2)

3. RESULT ENRICHMENT
   ├─ Add citations (source documents, page numbers)
   ├─ Fetch chunk context (surrounding text)
   ├─ Add URLs (S3 links to source images)
   └─ Response: {chunks, images, citations}

4. QUESTION ANSWERING
   ├─ HTTP: POST /api/chat
   ├─ Payload:
   │  {
   │    "messages": [
   │      {
   │        "role": "user",
   │        "content": "Explain neural network architecture"
   │      }
   │    ],
   │    "search_results": [...], // From search
   │    "generation_config": {temperature: 0.0, max_tokens: 2000}
   │  }
   │
   ├─ [Generation Module]
   │  ├─ Prepare prompt with context from search results
   │  ├─ Prompt template:
   │  │  """
   │  │  Based on the following context, answer the question.
   │  │  
   │  │  Context:
   │  │  [Retrieved chunks]
   │  │  
   │  │  [Images descriptions]
   │  │  
   │  │  Question: [user question]
   │  │  Answer:
   │  │  """
   │  │
   │  ├─ Call Bedrock (Claude Haiku 4.5 - Multimodal)
   │  ├─ Stream response to client
   │  └─ Extract citations and format answer
   │
   ├─ Response Format:
   │  {
   │    "answer": "Neural networks are...",
   │    "citations": [
   │      {
   │        "source": "lecture_01.pptx",
   │        "page": 3,
   │        "chunk_id": "...",
   │        "url": "s3://..."
   │      }
   │    ],
   │    "generation_time_ms": 1200,
   │    "tokens_used": 450
   │  }
   │
   └─ Frontend renders with formatted citations

5. OPTIONAL: CACHE RESULT
   ├─ Store in Redis
   ├─ Key: hash(query + user_id)
   ├─ TTL: 600 seconds (10 minutes)
   └─ Future same queries hit cache
```

### Flow 3: Quiz Generation

```
┌─────────────────────────────────────────────────────────────────┐
│ QUIZ GENERATION FLOW                                            │
└─────────────────────────────────────────────────────────────────┘

1. USER REQUESTS QUIZ
   ├─ HTTP: POST /api/quiz/generate
   ├─ Payload: {document_ids, num_questions: 5, question_type: "mcq"}
   ├─ Header: X-User-Id: user123
   └─ Response: Immediate with job_id

2. QUIZ GENERATION (Async Task)
   ├─ For each document:
   │  ├─ Load document chunks from S3
   │  ├─ Select representative chunks
   │  ├─ Create prompt for LLM
   │  └─ Generate questions via Bedrock
   │
   ├─ Format questions:
   │  {
   │    "question": "What is a neural network?",
   │    "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
   │    "correct_answer": "A",
   │    "source_chunk_id": "...",
   │    "difficulty": "medium"
   │  }
   │
   └─ Store quiz in database

3. DELIVER QUIZ
   ├─ Poll /api/quiz/status/{quiz_id}
   ├─ Response: {quiz_id, questions, generation_time}
   └─ User answers questions in UI

4. EVALUATE ANSWERS
   ├─ HTTP: POST /api/quiz/submit
   ├─ Payload: {quiz_id, answers: [{question_id, selected_answer}]}
   ├─ Calculate score
   ├─ Generate feedback per question
   └─ Response: {score, percentage, feedback, analytics}
```

---

## Core Components

### A. Processing Pipeline (`src/processor/`)

| Component | Purpose | Key Methods |
|---|---|---|
| `pipeline.py` | Main orchestrator | `process()`, `_run_stage()` |
| `normalizer.py` | Format normalization | `normalize_document()`, `convert_to_pdf()` |
| `media_processor_enhanced.py` | Audio/video extraction | `extract_audio()`, `transcribe()`, `extract_frames()` |
| `document_processor_v2_1.py` | Docling-based parsing | `parse_document()` (GPU) |
| `consolidator.py` | RAG-ready consolidation | `consolidate()`, `create_rag_structure()` |

### B. Retrieval Systems (`src/retrieval/`)

| Component | Purpose | Key Methods |
|---|---|---|
| `rag_retrievers.py` | Text retrieval | `bm25_retrieve()`, `dense_retrieve()`, `hybrid_retrieve()` |
| `image_retrievers.py` | Image/visual retrieval | `embed_images()`, `retrieve_images()` |

### C. Chunking (`src/chunking/`)

| Component | Purpose | Key Methods |
|---|---|---|
| `chunker.py` | Text chunking | `chunk_text()`, `get_chunks()` |
| Format-specific chunkers | Format awareness | Format-specific logic |

### D. Generation (`src/generation/`)

| Component | Purpose | Key Methods |
|---|---|---|
| `generator.py` | LLM-based generation | `generate()`, `stream_generate()`, `extract_citations()` |

### E. Services (`app/services/`)

**IndexingJobService** (NEW - Async job tracking):
```python
class IndexingJobService:
  async def create_job(job_id, user_id, document_id, job_type) → job_metadata
  async def get_job_status(job_id) → {status, progress, result, error}
  async def update_job_progress(job_id, progress, stage)
  async def mark_job_completed(job_id, result)
  async def mark_job_failed(job_id, error)
  async def check_concurrency(user_id) → bool (max 3 per user, 20 global)
```

**Other Services**:
- `indexing_service.py` - Text + image indexing coordination
- `processing_service.py` - Document processing invocation
- `search_orchestrator.py` - Multi-method search fusion
- `colqwen_inference.py` - ColQwen embedding calls
- `document_chunks.py` - Chunk loading and retrieval
- `citation_uris.py` - Citation enrichment with URLs

---

## API Endpoints

### Health & Status

```
GET /health                    → "OK"
GET /api/health                → {status: "healthy", timestamp}
GET /api/status/files          → {count, total_size_mb, documents_count}
GET /api/status/system         → {cpu, memory, disk, gpu_stats}
```

### File Management

```
POST /api/upload               → Upload document (multipart/form-data)
                                  Response: {document_id, status, file_info}

GET /api/files                 → List user's documents
                                  Response: [{document_id, name, size, created_at}]

DELETE /api/files/{document_id}→ Delete document
                                  Response: {success: true}

GET /api/images/preview        → Get image preview by ID
                                  Response: Image data (stream)
```

### Processing & Indexing (ASYNC)

```
POST /api/process              → Start document processing
                                  Response: {job_id, status: "queued"}

POST /api/index                → Start text indexing
POST /api/index/text           → Same as above
POST /api/index/image          → Start image indexing
                                  Response: {job_id, status: "queued"}

GET /api/index/status/{job_id} → Poll job status (IMPORTANT)
                                  Response: {status, progress, result, error}

Polling Response Examples:
┌─ Queued: {status: "queued", job_id: "...", progress: 0}
├─ Processing: {status: "processing", job_id: "...", progress: 50}
├─ Indexing: {status: "indexing", job_id: "...", progress: 75}
└─ Completed: {status: "completed", job_id: "...", progress: 100, result: {...}}
```

### Search & Retrieval

```
POST /api/search               → Hybrid search (text + image)
                                  Payload: {query, search_type: "hybrid", top_k: 10}
                                  Response: {chunks, images, citations}

POST /api/search/text          → Text-only search
POST /api/search/images        → Image-only search

Response Format:
{
  "chunks": [
    {
      "chunk_id": "...",
      "text": "...",
      "score": 0.85,
      "source": "document.pdf",
      "page": 3
    }
  ],
  "images": [
    {
      "image_id": "...",
      "url": "s3://...",
      "score": 0.92,
      "page": 2
    }
  ],
  "citations": [...]
}
```

### Chat & Generation

```
POST /api/chat                 → Chat completion
                                  Payload: {messages, search_results, generation_config}
                                  Response: {answer, citations, tokens_used}

POST /api/chat/stream          → Streaming chat completion
                                  Payload: Same
                                  Response: Server-Sent Events (stream)

POST /api/chat-history/create  → Create conversation
POST /api/chat-history/list    → Get conversations
```

### Quiz

```
POST /api/quiz/generate        → Generate quiz from documents
                                  Payload: {document_ids, num_questions, question_type}
                                  Response: {job_id, status}

GET /api/quiz/status/{quiz_id} → Poll quiz generation status

POST /api/quiz/submit          → Submit quiz answers
                                  Payload: {quiz_id, answers}
                                  Response: {score, feedback, analytics}
```

### Insights & Analytics

```
GET /api/insights/summary      → Generate learning summary
GET /api/insights/mcq          → Generate multiple choice questions
GET /api/insights/progress     → User learning progress
```

### Configuration

```
GET /api/config                → System configuration
                                  Response: {pipelines, retrievers, generation_models}
```

### Authentication (Firebase)

```
POST /api/auth/login           → Login with Firebase token
                                  Payload: {id_token}
                                  Response: {user_id, email, role}

GET /api/users/me              → Get current user info
```

---

## Configuration & Setup

### Environment Variables (`.env`)

```ini
# Qdrant Vector Database
QDRANT_MODE=cloud              # or "docker"
QDRANT_URL=https://xxx.cloud.qdrant.io:6333
QDRANT_API_KEY=<api_key>

# File Storage
FILE_STORAGE_BACKEND=s3        # or "local"
S3_ORIGINALS_BUCKET=ai-service-originals-dev
S3_PROCESSED_BUCKET=ai-service-processed-dev
S3_REGION=us-west-2

# Authentication
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-key.json
FIREBASE_PROJECT_ID=<project_id>

# User Database
DYNAMODB_USERS_TABLE=phase2-merge-users
AWS_REGION=us-west-2

# LLM Generation
BEDROCK_REGION=us-west-2
BEDROCK_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0

# Cache & Jobs
REDIS_URL=redis://localhost:6379/0

# GPU Services
GPU_SERVER_URL=http://localhost:8000
WHISPER_API_URL=http://localhost:5001
DOCLING_API_URL=http://localhost:5002
COLQWEN_API_URL=http://localhost:5003

# Logging
LOG_LEVEL=INFO
```

### Pipeline Configuration (`backend/config/default.yaml`)

```yaml
pipeline:
  enable_normalization: true
  enable_media_processing: true
  enable_docling: true
  enable_consolidation: true
  rag_mode: "text_image"        # text, image, or text_image
  enable_generation: true

processing:
  # Stage 1: Normalization
  normalizer:
    output_format: "pdf"
  
  # Stage 2: Media Processing
  media:
    extract_audio: true
    extract_frames: true
    frame_sampling_rate: 1       # Every 1 second
    deduplicate_frames: true
  
  # Stage 3: Docling
  docling:
    enable_ocr: true
    enable_vlm: true
    pdf_dpi: 150
  
  # Stage 4: Consolidation
  consolidation:
    add_citations: true

retrieval:
  text:
    methods: ["bm25", "dense", "hybrid"]
    chunk_size: 1000
    chunk_overlap: 200
    min_chunk_size: 50
    reranker: "bge-base"
    
    bm25:
      top_k: 50
    
    dense:
      model: "sentence-transformers/all-MiniLM-L6-v2"
      top_k: 50
    
    hybrid:
      alpha: 0.5               # Balance between BM25 and dense
      top_k: 10
  
  image:
    model: "colqwen"
    quantization: "8bit"
    top_k: 10

generation:
  provider: "bedrock"          # bedrock, openai, azure, ollama
  model_id: "anthropic.claude-3-5-haiku-20241022-v1:0"
  temperature: 0.0
  max_tokens: 2000
  streaming: true

qdrant:
  mode: "cloud"                # cloud or docker
  collections:
    text: "edu_text_chunks"
    image: "edu_image_pages"

logging:
  level: "INFO"
  file_path: "./logs"
```

---

## Performance Characteristics

### Recent Optimization Summary (v3.6x Improvement)

**Commit fbe2906** introduced async job-based indexing:
- ✅ **Before**: Synchronous indexing blocked HTTP response (blocked for 30-60 seconds)
- ✅ **After**: Async background task returns immediately with job_id
- ✅ **Performance**: 3.6x faster indexing (parallel processing)
- ✅ **Concurrency**: Max 3 jobs per user, 20 global (prevents resource exhaustion)
- ✅ **Reliability**: Job status tracking via Redis; resumed on failure

### Bottleneck Analysis (JMeter Load Tests)

**Processing Stage** (CPU-bound):
- Document parsing: 2-5 seconds (per MB)
- OCR: 5-10 seconds (per page)
- Whisper ASR: 0.5x realtime (5-minute audio = 2.5 minutes)

**Indexing Stage** (I/O-bound):
- BM25 indexing: 1-3 seconds (per 1000 chunks)
- Dense embedding: 2-5 seconds (per 1000 chunks, depends on embedding model)
- Qdrant write: 1-2 seconds (per 1000 vectors)
- S3 upload: 0.5-2 seconds (depends on file size and network)

**Search Stage** (Memory/Query bound):
- BM25 search: 10-50ms (depends on index size)
- Dense search: 50-200ms (depends on Qdrant collection size)
- Hybrid fusion: 100-300ms (combines both)
- Image search: 200-500ms (ColQwen API latency)

**Generation Stage** (API latency):
- Bedrock Claude Haiku 4.5: 500-1500ms (typical)
- Token generation: 50-100ms per token (streaming)
- Total answer generation: 1-3 seconds (typical 500-token response)

### Scalability Profile

| Component | Current Capacity | Scaling Approach |
|---|---|---|
| Qdrant | 100M+ vectors | Cloud cluster supports sharding |
| BM25 Index | Per-user files | Auto-cleanup for old documents |
| Backend Tasks | 1-10 concurrent | ECS auto-scaling (CPU/Memory triggers) |
| Concurrent Users | 100+ simultaneous | ALB + ECS auto-scaling |
| Document Size | Up to 1GB | Chunked processing, S3 streaming |

---

## Technology Stack

### Frontend
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite (fast HMR, optimized builds)
- **Styling**: Tailwind CSS (utility-first responsive design)
- **HTTP**: Axios (with auth interceptors)
- **Authentication**: Firebase SDK

### Backend
- **Framework**: FastAPI (async, type-safe)
- **Server**: Uvicorn (ASGI server)
- **Document Processing**: Docling, PyPDF2, python-pptx, openpyxl
- **Media Processing**: MoviePy, OpenCV
- **Chunking**: LangChain RecursiveCharacterTextSplitter
- **Retrieval**:
  - Text: BM25 (rank-bm25), Sentence-Transformers (embedding)
  - Vector DB: Qdrant Python client
  - Image: ColQwen (vision-language model)
- **Generation**: Amazon Bedrock SDK (Claude Haiku 4.5 multimodal)
- **Database**: DynamoDB (users), Redis (cache + job tracking)
- **Storage**: AWS S3
- **Container**: Docker + Docker Compose
- **Orchestration**: AWS ECS Fargate
- **Infrastructure**: Terraform

### GPU Services
- **Whisper**: OpenAI Whisper (audio transcription)
- **Docling**: IBM Research Docling + RapidOCR
- **ColQwen**: ColQwen 2.5 (multimodal retrieval)
- **Inference Server**: FastAPI

### Deployment
- **Cloud**: AWS (us-west-2)
- **Container Registry**: Amazon ECR
- **Load Balancer**: Application Load Balancer (ALB)
- **Monitoring**: CloudWatch (logs + metrics)
- **CI/CD**: GitHub Actions (docker buildx, ECR push, ECS update)

---

## Key Insights

### Architecture Highlights

1. **Multimodal Processing**: Handles text, images, audio, video with specialized pipelines
2. **Modular Design**: Each component (processor, chunker, retrieval, generation) is independently testable
3. **Async-First**: New job-based indexing (v3.6x faster) enables scalability
4. **Cloud-Native**: Fully containerized, serverless-friendly (ECS Fargate)
5. **Multi-Tenant**: User isolation via Firebase auth + payload-based filtering in Qdrant
6. **Hybrid Retrieval**: BM25 + Dense + Visual search (RRF fusion)

### Recent Improvements

- **Async Job System** (fbe2906): Non-blocking indexing with job tracking
- **Optimization Summary** (ed129f1): Unit tests for IndexingJobService
- **Error Handling** (de0c1d8): Improved module import resolution
- **Capacity Testing** (2573787): JMeter benchmarks for load characterization

### Next Steps (Planned)

- ✗ RDS PostgreSQL integration (structured user data)
- ✗ ElastiCache (managed Redis)
- ✗ SQS (async job queue for horizontal scaling)
- ✗ Cognito (enterprise authentication)
- ✗ CloudFront + WAF (CDN + security)
- ✗ Advanced analytics and learning path personalization

---

## Quick Start

### Local Development

```bash
# Clone repository
git clone https://github.com/bkumind/capstone.git
cd Phase_2_FE_AI_Merge

# Backend setup
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
python run_api.py

# Frontend setup (in another terminal)
cd frontend
npm install
npm run dev

# GPU Services (separate machine with GPU)
cd gpu_server
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Cloud Deployment

```bash
# Build and push images
docker build -t rag-pipeline-backend:latest ./backend
docker build -t rag-pipeline-frontend:latest ./frontend
aws ecr get-login-password | docker login --username AWS ...

# Terraform deployment
cd terraform
terraform init
terraform apply
```

---

## Contact & Support

For questions or issues, refer to:
- **Architecture Documentation**: `docs/diagram/`
- **Configuration**: `backend/config/default.yaml`
- **API Documentation**: FastAPI Swagger at `http://localhost:5000/docs`
- **Git Commits**: Recent commits document latest changes and optimizations

---

**Document Generated**: April 23, 2026
**System Version**: Phase 2 FE AI Merge (with async job-based indexing)
**Last Major Update**: Async job-based indexing with 3.6x performance improvement (fbe2906)
