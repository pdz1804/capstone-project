# Capstone Project - HCMUT CS252

> **Educational Content Processing & Retrieval-Augmented Generation System**
> A comprehensive research platform for multimodal lecture processing, intelligent retrieval, and RAG pipeline development.

---

## Repository Layout

The repo is organized around tracked code/docs and local-only data:

- `docs/` - project documentation, references, architecture notes, and report-ready supporting material.
- `Phase_1/code/` - Phase 1 experiments and prototypes.
- `Phase_1/data/` - Phase 1 raw inputs and generated outputs; ignored by Git and stored in Drive.
- `Phase_1/Report/` - Phase 1 report PDF and report source; tracked.
- `Phase_2/code/` - Phase 2 backend, frontend, deployment, Terraform, SageMaker, and scripts.
- `Phase_2/data/` - Phase 2 raw inputs, pipeline outputs, evaluation data, indexes, model artifacts, and third-party local checkouts; ignored by Git and stored in Drive.
- `Phase_2/Report/` and `Phase_2/Manuscript/` - final report/manuscript PDFs and sources; tracked.

See [`docs/04_PROJECT_REFERENCE/data_manifest.md`](docs/04_PROJECT_REFERENCE/data_manifest.md) for Drive restore locations.

---

## README Map

Use this root README as the project entry point. Other README files are scoped to their folder:

| README | Use it for |
|---|---|
| [`README.md`](README.md) | Project overview, repo layout, high-level architecture, and where to go next |
| [`Phase_1/code/README.md`](Phase_1/code/README.md) | Phase 1 experiment/code map after the week-folder cleanup |
| [`Phase_2/README.md`](Phase_2/README.md) | Phase 2 app runbook: backend, frontend, SageMaker, Terraform, scripts |
| `Phase_2/code/*/README.md` | Component-specific instructions for backend, frontend-related scripts, SageMaker, Terraform |

If two README files disagree, treat the more specific folder README as authoritative for commands inside that folder, and treat this root README as authoritative for repository structure.

---

## 🎯 Project Overview

This capstone builds an **educational content processing and Retrieval-Augmented Generation (RAG)** system: ingest multimodal lecture materials, align and structure them, index them for **text and visual** retrieval, and support **question answering with citations**, **lecture-aware summaries**, and **personalized learning** features behind a **modern web UI** and **production-style deployment** options.

The authoritative requirements baseline is **[`docs/requirements.md`](docs/requirements.md)** (Software Requirements Specification): **37** requirements in total **22** functional (FR-001–FR-022 and extended FRs in that doc), **8** non-functional (NFR-001–NFR-008), and **7** technical (TR-001–TR-007). Highlights from the SRS scope:

- **Content processing**: ASR and timed exports (**FR-001**); documents, OCR, dual outputs (**FR-002**); spreadsheet merged cells and Markdown (**FR-003**, **FR-004**); images / VLM (**FR-005**); deduplication (**FR-006**); audio–slide alignment and temporal navigation (**FR-007**, **FR-008**).
- **Retrieval & QA**: BM25, dense, hybrid (**FR-009**); vision–language retrieval (**FR-010**); query handling (**FR-011**); grounded answers (**FR-012**, **FR-013**); chat decomposition, strategy, and multi-search aggregation (**FR-014**).
- **Product features**: file management and search UI (**FR-021**, **FR-022**); automated summaries and summary navigation (**FR-023**, **FR-024**); learning paths, assessment, and analytics (**FR-025–FR-027**).
- **Non-functional**: latency and scale targets (**NFR-001–NFR-002**); availability, integrity, UX, accessibility, security, and privacy (**NFR-003–NFR-008**).
- **Technical**: FastAPI + async APIs, React 18 + Vite + Tailwind, vector and metadata stores, external LLM/embedding services, Docker, and **cloud-ready** infrastructure (**TR-001–TR-007**).

Phase 1 research milestones now live under `Phase_1/code/`; **`Phase_2`** is the maintained integrated app (Firebase UI, Qdrant/S3, optional **SageMaker**, **Terraform** for ECS/ALB/ECR).

---

## 🏗️ System Architecture

BK-MInD follows a **six-tier Clean Architecture** pattern that separates concerns across distinct layers, enabling maintainability, testability, and independent scaling. The system is designed to achieve: **(1) multimodal data ingestion** from diverse educational materials, **(2) asynchronous processing** to support concurrent operations without bottlenecks, and **(3) production-grade security and scalability** on AWS infrastructure.

### High-Level System Architecture

The following diagram shows the complete system topology aligning with the SRS: multimodal **ingest → process → index → retrieve → generate**, organized across six architectural tiers plus cross-cutting concerns for auth, security, and persistence.

![BK-MInD High-Level Architecture - Six-Tier Clean Architecture](Phase_2/Report/img/pdz/Report%20252%20Diagram-High%20Level%20Architecture.png)

**Layer summary**

| Layer                  | Role                                           | SRS touchpoints                                  |
| ---------------------- | ---------------------------------------------- | ------------------------------------------------ |
| Client                 | Uploads, search, summaries, dashboards, auth   | FR-021–FR-022, FR-023–FR-027, NFR-005–NFR-008 |
| API                    | Orchestration, RBAC hooks, integration         | TR-001, NFR-003–NFR-004                         |
| Processing             | ASR, OCR/VLM, spreadsheets, sync, corpus       | FR-001–FR-008                                   |
| Storage                | Vectors, sparse index, blobs, metadata         | TR-003, TR-004, NFR-004                          |
| Retrieval & generation | Hybrid + visual search, RAG, chat, LLM         | FR-009–FR-014, TR-004                           |
| Deployment             | Containers, cloud LB TLS, optional managed GPU | TR-006–TR-007, NFR-002–NFR-003                 |

For HTTPS and custom domains on AWS, see [`docs/technical/DOCS_deployment-alb-acm-custom-domain.md`](docs/technical/DOCS_deployment-alb-acm-custom-domain.md).

---

### AWS Deployment Architecture

The latest deployment architecture (v4) shows production-grade cloud infrastructure on AWS with ECS Fargate, ALB, ElastiCache, vector databases, and auto-scaling:

![AWS Deployment Architecture Diagram](docs/diagram/Deployment%20Diagram_v4.png)

**For capstone presentations / documentation review:** open [`docs/report/`](docs/report/) for Phase 2 reports and presentation material.

**For development setup:** follow [`docs/requirements.md`](docs/requirements.md) for the baseline environment. The main pieces are Python 3.9+ for the backend, React 18 + Vite + Tailwind for the frontend, and FFmpeg / Tesseract / Poppler for media and OCR. GPU use is optional locally if you offload heavy inference to APIs or SageMaker ([`Phase_2/code/sagemaker/README.md`](Phase_2/code/sagemaker/README.md)).

**Additional Diagrams:**
- [`docs/diagram/`](docs/diagram/)   Complete diagram collection including document processing flows and system documentation

## Complete Environment Setup Guide

**Last Updated**: July 4, 2026
**For**: Phase 2 maintained application stack
**Duration**: 20-40 minutes for a local backend/frontend setup

This guide matches the current codebase structure documented in [`../README.md`](../README.md), [`../Phase_2/README.md`](../Phase_2/README.md), [`../Phase_2/code/backend/README.md`](../Phase_2/code/backend/README.md), and [`../Phase_2/code/terraform/README.md`](../Phase_2/code/terraform/README.md).

### What You Need

- Python 3.10+ for the backend
- Node.js 18+ for the frontend
- Git
- Docker and Docker Compose for local Qdrant and Redis
- Optional system binaries: FFmpeg, Tesseract, and Poppler if you run the document-processing paths locally

### 1. Clone the Repository

```bash
git clone https://github.com/pdz1804/capstone-project.git
cd capstone-project
```

The maintained app lives in `Phase_2/`.

### 2. Start Local Infrastructure

From the backend folder, start the local service dependencies:

```bash
cd Phase_2/code/backend
docker compose up -d
```

This starts Redis and Qdrant from [`docker-compose.yml`](../Phase_2/code/backend/docker-compose.yml); it does not start the FastAPI backend itself.

Useful checks:

```bash
curl http://localhost:6333/health
docker compose ps
```

### 3. Configure and Run the Backend

Create the backend environment file and fill in the values you need:

```bash
cd Phase_2/code/backend
cp .env.example .env
```

Start the backend with the maintained entrypoint:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python run_api.py
```

Activate the virtual environment with the equivalent command for your shell before installing packages if you prefer not to use the system interpreter.

The API runs on port 5001 by default. The runner accepts `--host`, `--port`, `--workers`, `--reload`, and `--no-reload` if you need to override the defaults.

Common backend env values to review:

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `QDRANT_MODE`, `QDRANT_HOST`, `QDRANT_PORT`, or `QDRANT_URL`
- `REDIS_URL`
- `FILE_STORAGE_BACKEND`
- `USE_AWS_SAGEMAKER_INFERENCE`
- `DYNAMODB_USERS_TABLE`, `DYNAMODB_APP_USAGE_TABLE`, `DYNAMODB_JOBS_TABLE`

### 4. Configure and Run the Frontend

In a separate terminal:

```bash
cd Phase_2/code/frontend
cp .env.example .env
npm install
npm run dev
```

The current frontend dev script is `tsx server.ts`, and the default local URL is `http://localhost:5173`. The template in [`../Phase_2/code/frontend/.env.example`](../Phase_2/code/frontend/.env.example) uses `VITE_API_BASE_URL=/api` and `API_PROXY_TARGET=http://localhost:5001`.

### 5. Verify the Stack

Backend health:

```bash
curl http://localhost:5001/health
curl http://localhost:5001/api/health
```

Frontend should be reachable at `http://localhost:5173`.

If you want to smoke-test search after indexing data, use the current API contract from [`../Phase_2/code/backend/README.md`](../Phase_2/code/backend/README.md) and send requests with the `X-User-Id` header.

### 6. Optional Local Validation

Backend tests:

```bash
cd Phase_2/code/backend
python -m pytest tests -v
```

Terraform validation only:

```bash
cd Phase_2/code/terraform
terraform init -backend=false
terraform fmt -recursive
terraform validate
```

### 7. Common Failure Points

- If Qdrant is unreachable, confirm `docker compose up -d` completed and that port 6333 is free.
- If Redis is unreachable, confirm the same compose stack is running and that the backend `REDIS_URL` points at `redis://localhost:6379/0` or your configured instance.
- If the frontend cannot reach the API, confirm `API_PROXY_TARGET=http://localhost:5001` and that the backend is running on port 5001.
- If `pip install` fails on large wheels, clear the pip cache or use a drive with more free space before retrying.

### 8. Where To Read Next

- [`Phase_2/README.md`](../Phase_2/README.md) for the maintained Phase 2 setup summary
- [`Phase_2/code/backend/README.md`](../Phase_2/code/backend/README.md) for backend runtime, API routes, and indexing workflow
- [`Phase_2/code/terraform/README.md`](../Phase_2/code/terraform/README.md) for infrastructure validation and deployment notes


---
<!--
## 📄 Academic Publication - Phase_2/Manuscript

### BK-MInD Academic Manuscript (Ready for Conference Submission)

The project includes a **complete, publication-ready academic manuscript** for submission to top-tier conferences:

📜 **Folder**: [`Phase_2/Manuscript/`](Phase_2/Manuscript/)

**What's Included**:
- ✅ **main.pdf** (804 KB, 14 pages) - 2-column IEEE/ACM format paper with BibTeX references
- ✅ **main.tex** (418 lines) - LaTeX source with proper `\cite{}` commands and all elements
- ✅ **references.bib** (23 academic sources) - Comprehensive BibTeX bibliography
- ✅ **Figures** (3 professional diagrams) - System architecture, technology rationale, related work
- ✅ **Tables** (5 comprehensive tables) - RAG alternatives, parsing, retrieval, end-to-end eval, appendix comparison
- ✅ **Complete Documentation** - Submission guides, compilation instructions, writing standards
- ✅ **Fact-Checked Metrics** - All 40+ performance metrics verified against Phase_2/Report

**Manuscript Title**: *BK-MInD: Multimodal Retrieval-Augmented Generation for Institutional Educational Content*

**Key Contributions**:
1. Dual-pathway multimodal architecture with reciprocal rank fusion
2. 7-stage document processing pipeline with conditional routing
3. Multi-tier security architecture (FERPA-compliant)
4. Production deployment validation (50 concurrent users, $683.72/month)

**Evaluation Results**:
- Document parsing: 58.91% OmniDocBench score
- Retrieval effectiveness: 84.84% nDCG@10 for text, 67.14% for images
- System accuracy: 72.7% correctness, 99.5% faithfulness (zero hallucinations)
- Production ready: Stable 30-45 second response times at 50 concurrent users

**Target Conferences**:
- ACL 2027 (Deadline: January 2027) - EXCELLENT FIT
- EMNLP 2027 (Deadline: May 2027) - EXCELLENT FIT
- Learning@Scale 2027 (Deadline: October 2026) - EXCELLENT FIT

**Quick Start**: Download `main.pdf` from `Phase_2/Manuscript/` folder and submit to target conference!

See [`Phase_2/Manuscript/README.md`](Phase_2/Manuscript/README.md) for detailed submission instructions. -->
<!--
---

## 📦 Project Components

### 🔧 **Utility: Research Paper Downloader** (`downloads/`)

A robust batch downloader for academic PDFs from major venues (arXiv, ACL, CVPR, AAAI, ACM). Features intelligent metadata extraction, automatic retries, and comprehensive logging.

**Key Features**:

- Multi-venue support with site-specific heuristics
- Semantic filename generation from paper metadata
- PDF validation and deduplication
- Exponential backoff retry mechanism

---

### 📅 **Week 03-04: Foundation Development**

#### **MKhoi: ASR & OCR Pipeline** (`Phase_1/code/asr_ocr/baseline_ocr_asr/`)

Baseline implementation for extracting text from lecture videos and slides.

**Technologies**:

- **ASR**: PhoWhisper (OpenAI Whisper variant optimized for Vietnamese)
- **OCR**: Tesseract with adaptive preprocessing
- **Audio Processing**: FFmpeg extraction, 16kHz WAV conversion
- **Batch Processing**: Multi-file support with structured outputs

**Output**: Timestamped transcripts (TXT/JSON) + extracted slide text

---

#### **NKhoi: Retrieval Systems Evaluation** (`Phase_1/code/retrieval/baseline_bm25_dense_hybrid/`)

Comprehensive comparison of retrieval methods on MS MARCO dataset.

**Methods Evaluated**:

- **BM25**: Sparse keyword-based retrieval (baseline)
- **Dense**: Sentence-BERT embeddings with cosine similarity
- **Hybrid**: Weighted Sum + Reciprocal Rank Fusion (RRF)

**Key Findings**:

- Dense retrieval achieves 3.6× higher nDCG@10 than BM25 on MS MARCO
- Hybrid methods provide marginal improvements but add complexity
- Vocabulary mismatch severely impacts BM25 on natural language queries

**Metrics**: nDCG@10, Recall@10, latency analysis

---

#### **QPhu: RAG Framework Comparison** (`Phase_1/code/processing_rag_pipeline/rag_framework_comparison/`)

Systematic evaluation of three RAG implementation approaches.

**Frameworks**:

1. **LangChain**: High-level abstractions, extensive integrations
2. **LlamaIndex**: Python-native, data-centric design
3. **Manual**: Custom implementation for full control

**Configuration Options**:

- **Vector Stores**: FAISS (in-memory), Chroma (persistent)
- **LLMs**: OpenAI GPT-4o-mini, Azure OpenAI, Google Gemini, Ollama
- **Benchmarking**: Automated metrics collection and reporting

**Use Case**: Comparative analysis for selecting optimal RAG stack

---

### 📅 **Week 05-06: Advanced Enhancements**

#### **MKhoi: Multi-Model ASR/OCR** (`Phase_1/code/asr_ocr/multi_model_benchmark/`)

Expanded processing pipeline with multiple AI backends and detailed benchmarking.

**ASR Models**:

- **OpenAI Whisper**: Variants from `tiny` to `large-v3`
- **Google Gemini**: API-based with 2.0/2.5 Flash models
- **DeepSeek**: Alternative API provider

**OCR Enhancements**:

- Advanced preprocessing (OTSU, adaptive thresholding)
- Multi-language support (Vietnamese + English)
- PDF batch processing with Poppler integration

**Deliverables**: Model comparison reports (`asr rank.md`, `ocr rank.md`, `model comparison.md`)

---

#### **NKhoi: Production Retrieval Systems** (`Phase_1/code/retrieval/production_retrieval/`)

Industrial-grade retrieval implementations using specialized tools.

**Upgrades**:

- **Milvus**: Vector database for billion-scale dense retrieval
- **Pyserini**: Lucene-based BM25 with advanced linguistic processing
- **ColPali**: Vision-language retrieval for document images (no OCR needed)

**Performance Improvements**:

- 44 minutes → ~10 seconds for BM25 (Pyserini)
- 6 seconds → <1 second for Dense (Milvus)
- Better tokenization, stemming, and query optimization

**Novel Approach**: ColPali for end-to-end visual retrieval (bypassing OCR errors)

---

### 📅 **Week 07-09: Production Pipeline**

#### **QPhu: Unified Processing Pipeline** (`Phase_1/code/processing_rag_pipeline/unified_processor/`)

Complete overhaul into production-ready 4-stage pipeline with enterprise features and intelligent processing.

**Architecture Overview**:

- **Stage 1 (Normalizer)**: Format conversion with consistent filename truncation for Windows compatibility
- **Stage 2 (Media Processor)**: Audio/video transcription with multiple export formats (JSON/SRT/VTT/MD)
- **Stage 3 (Docling Processor)**: Smart deduplication avoiding duplicate processing, VLM-powered understanding
- **Stage 4 (Consolidator)**: RAG-ready unified structure with dual-mode outputs

**Core Features**:

- **Smart Deduplication**: Process each file only once, optimal quality source selection
- **Dual RAG Outputs**: Normalized PDFs for image retrieval + Markdown for semantic search
- **Universal Format Support**: 15+ formats (DOCX, PPTX, HTML, Images, Video, Audio, PDF, Excel, CSV, AsciiDoc, WebVTT)

**Advanced Capabilities**:

- **Visual Understanding**: SmolVLM-256M integration for image descriptions and layout analysis
- **Processing Modes**:
  - Full Mode (default): VLM-enabled, highest quality, ~1× speed
  - Balanced Mode (`--no-vlm`): OCR-only with exports, ~2× faster
  - Fast Mode (`--fast-mode`): OCR-only minimal exports, 3-5× faster
- **Intelligent Caching**: MD5-based skip system with `--force` flag to bypass
- **Windows Optimization**: Automatic filename truncation (50 chars + MD5 hash) for 260-char path limit
- **Multi-OCR Support**: RapidOCR (primary), Tesseract, EasyOCR
- **ASR Integration**: Whisper-based transcription for audio/video with configurable models

**Performance Optimizations**:

- GPU acceleration (CUDA support)
- Batch processing with progress tracking
- Exponential backoff retry mechanism
- Comprehensive error handling and logging
- Graceful degradation for unsupported formats

**Output Structure**:

```
stage4_rag_ready/
├── document_name.pdf                    # Image-based RAG (preserved layout)
├── document_name.md                     # Text-based RAG (semantic search)
└── document_name_docling_additional/    # Extracted images/tables
    ├── images/
    └── tables/
```

--- -->

## **Phase 2 Integrated Application: FE + AI + AWS (`Phase_2/`)**

Single tree that combines the production-style **FastAPI** backend (Qdrant, S3, optional SageMaker inference), the **React + Firebase** frontend from the FE track, **SageMaker** hosting packs (unified Docling + Whisper + ColQwen container and optional split endpoints), and **Terraform** for AWS: **ECR**, **ECS Fargate**, **Application Load Balancer** with optional **HTTPS** (ACM), auto scaling, and an optional **SageMaker endpoint** aligned with `sagemaker/unified`.

| Area                                 | Path                                                        | Documentation                                                                       |
| ------------------------------------ | ----------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Folder overview                      | `Phase_2/`                                    | [`Phase_2/README.md`](Phase_2/README.md)                     |
| Terraform (ALB, ECS, ECR, SageMaker) | `Phase_2/code/terraform/`                          | [`Phase_2/code/terraform/README.md`](Phase_2/code/terraform/README.md) |
| SageMaker build / deploy             | `Phase_2/code/sagemaker/`                                 | [`Phase_2/code/sagemaker/README.md`](Phase_2/code/sagemaker/README.md) |
| HTTPS + custom domain runbook        | `docs/technical/DOCS_deployment-alb-acm-custom-domain.md` | ACM validation, DNS, ALB listeners                                                  |

Use **`Phase_2`** as the maintained application tree for local development, technical review, deployment, and testing.

---

## 🚀 Quick Start

**📚 For capstone presentations / documentation review:**
Start with **[`docs/report/`](docs/report/)** folder for Phase 2 reports and presentation guides.

**👨‍💻 For development setup:**
Prerequisites follow **[`docs/requirements.md`](docs/requirements.md)** (TR-001–TR-005, NFR-005–NFR-006): **Python 3.9+**, **FastAPI** backend; **React 18+**, **Vite**, **Tailwind** frontend; **FFmpeg**, **Tesseract**, **Poppler** for media; **GPU** optional locally if you offload heavy inference to APIs or **SageMaker** ([`Phase_2/code/sagemaker/README.md`](Phase_2/code/sagemaker/README.md)). **Docker** and **Terraform** are for packaging and cloud layout (TR-006–TR-007).

### Clone and base setup

```bash
git clone https://github.com/pdz1804/capstone-project.git
cd capstone-project
python -m venv venv
```

Activate the virtual environment with the equivalent command for your shell.

### Recommended: merged app (`Phase_2/`)

Full UI (Firebase), Qdrant/S3-aware API, tests, **Terraform** and **SageMaker** docs see [**`Phase_2/README.md`**](Phase_2/README.md).

Backend:

```bash
cd Phase_2/code/backend
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env with keys, Qdrant, S3, and SageMaker settings.
python run_api.py
```

Frontend:

```bash
cd Phase_2/code/frontend
npm install
cp .env.example .env
npm run dev
```

**URLs (typical):** UI `http://localhost:5173` (or your Vite default), API `http://localhost:5001`, docs `http://localhost:5001/docs`.

**Terraform (local validation only, no apply):**

```bash
cd Phase_2/code/terraform
terraform init -backend=false
terraform fmt -recursive
terraform validate
```

### Research and pipeline folders (optional)

```bash
cd Phase_1/code/asr_ocr/multi_model_benchmark/src
python main.py asr --output-dir results/asr <list-of-video-files>

cd Phase_1/code/retrieval/baseline_bm25_dense_hybrid
jupyter notebook manual_bm25_dense_hybrid.ipynb

cd Phase_1/code/processing_rag_pipeline/rag_framework_comparison
python setup_and_run.py

cd Phase_1/code/processing_rag_pipeline/unified_processor
python src/pipeline.py input/ output/
# Optional: add --fast-mode where that script supports it
```

Use `cd <repoRoot>` first if you are not already at the repository root.

---

## 🎓 Academic Context

**Course**: CS252 - Capstone Project
**Institution**: Ho Chi Minh City University of Technology (HCMUT)
**Focus**: Applied AI for Educational Content Processing
**Domain**: Information Retrieval, NLP, Multimodal Learning, RAG Systems

**Research Contributions**:

1. Vietnamese-optimized ASR/OCR pipeline for lecture processing
2. Comprehensive retrieval method comparison on MS MARCO
3. RAG framework selection guide for educational Q&A
4. Production-grade retrieval system implementations
5. Multimodal document understanding with Docling
6. Dual-mode RAG processing pipeline (text + image retrieval)
7. Intelligent document deduplication and caching system
8. Performance-quality tradeoff framework (Fast vs Full modes)

---

## 📚 Documentation

**📖 Start Here:** **[`docs/requirements.md`](docs/requirements.md)** ⭐   Software Requirements Specification: functional, non-functional, technical constraints (37 requirements total).

**Authoritative Technical Documents**

- **[`docs/technical/APPLICATION_OVERVIEW.md`](docs/technical/APPLICATION_OVERVIEW.md)** ⭐   Product scope, user workflows, architecture summary, features, quality attributes, and engineering assessment.
- **[`docs/technical/API_REFERENCE.md`](docs/technical/API_REFERENCE.md)**   Maintainer-level API reference covering authentication, files, processing, indexing, search, chat, insights, feedback, and operational guidance.
- **[`docs/technical/DOCS_TECHNICAL_GUARDRAIL_CONFIGURATION.md`](docs/technical/DOCS_TECHNICAL_GUARDRAIL_CONFIGURATION.md)**   AWS Bedrock guardrails configuration, content safety filters, PII protection, implementation details.

**Testing and Performance Evidence**

- **[`docs/report/FRESH_EVALUATION_REPORT_2026_05_07.md`](docs/report/FRESH_EVALUATION_REPORT_2026_05_07.md)**   Final evaluation report with component testing, performance benchmarks, and production readiness assessment.
- **[`docs/jmeter-capacity-tests/runs/README_MAIN_APIS.md`](docs/jmeter-capacity-tests/runs/README_MAIN_APIS.md)**   JMeter runbook and result exports for Process, Index, and Search APIs.
- **[`docs/jmeter-capacity-tests/runs/README_NON_MAIN_APIS.md`](docs/jmeter-capacity-tests/runs/README_NON_MAIN_APIS.md)**   JMeter runbook and result exports for Auth, User, Stats, Upload, Chat, and Insights APIs.

**Architecture and Deployment**

- **[`docs/technical/DOCS_deployment-alb-acm-custom-domain.md`](docs/technical/DOCS_deployment-alb-acm-custom-domain.md)**   ACM certificates, DNS validation, ALB HTTP→HTTPS, and custom domain setup.
- **[`docs/technical/DOCS_search-cache-redis-setup.md`](docs/technical/DOCS_search-cache-redis-setup.md)**   Redis/ElastiCache search cache setup and operational notes.
- **[`docs/technical/DOCS_REDIS_ASYNC_JOB_SYSTEM_GUIDE.md`](docs/technical/DOCS_REDIS_ASYNC_JOB_SYSTEM_GUIDE.md)**   Async job tracking system (Redis-based), job lifecycle, and monitoring.

**Security and WAF Configuration**

- **[`docs/technical/DOCS_TECHNICAL_WAF_CONFIGURATION.md`](docs/technical/DOCS_TECHNICAL_WAF_CONFIGURATION.md)**   AWS WAF rules, IP whitelisting, DDoS protection, and security group configuration.
- **[`docs/technical/SECURITY_SECTION_CAPSTONE_REPORT.md`](docs/technical/SECURITY_SECTION_CAPSTONE_REPORT.md)**   Security architecture, threat modeling, and compliance considerations.

**Cost Estimation**

- **[`docs/others/AWS_Cost_Estimation_50_Users_Professional.xlsx`](docs/others/AWS_Cost_Estimation_50_Users_Professional.xlsx)**   Detailed cost analysis and scalability projections for 50 concurrent users.

**Merged Production Application (`Phase_2/`)**

- **[`Phase_2/README.md`](Phase_2/README.md)**   Top-level map: frontend, backend, SageMaker pack, Terraform; local quick paths.
- **[`Phase_2/code/backend/README.md`](Phase_2/code/backend/README.md)**   FastAPI layout, Qdrant/BM25/hybrid/image retrieval, S3 vs local storage.
- **[`Phase_2/code/terraform/README.md`](Phase_2/code/terraform/README.md)**   AWS resources (ECR, ECS, ALB, optional HTTPS, optional SageMaker) and Terraform checks.
- **[`Phase_2/code/sagemaker/README.md`](Phase_2/code/sagemaker/README.md)**   Unified container, ECR push, deploy/delete scripts, and backend environment variables.

**Research Milestones and Utilities**

- READMEs inside **`Phase_1/code/asr_ocr/`**, **`Phase_1/code/retrieval/`**, **`Phase_1/code/processing_rag_pipeline/`**, and **`downloads/`** directories (datasets and paper references).
- **`Phase_1/code/processing_rag_pipeline/rag_framework_comparison/DETAILED_PIPELINE_FLOWS.md`** — Detailed RAG pipeline flow diagrams and explanations.

---

## 🔬 Research Papers & References

The `downloads/` directory contains a curated collection of research papers covering:

- Retrieval-Augmented Generation (RAG) architectures
- Dense retrieval methods (DPR, ColBERT, ANCE)
- Multimodal learning (CLIP, LayoutLM, Docling)
- Speech recognition (Whisper, Wav2Vec 2.0)
- OCR and document understanding

---

## 🤝 Contributing

This is an academic capstone project. For collaboration or questions:

- **Repository**: [github.com/pdz1804/capstone-project](https://github.com/pdz1804/capstone-project)
- **Issues**: Use GitHub Issues for bug reports or feature requests
- **Contact**: See individual weekly READMEs for team member information

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Quang Phu, Ngoc Khoi, and Minh Khoi

---

## 🙏 Acknowledgments

Open-source models, APIs, and platforms that this codebase builds on (see also TR-004–TR-005 and integration notes in [`docs/requirements.md`](docs/requirements.md)):

- **OpenAI**   Whisper and LLM APIs used in ASR and generation experiments.
- **Google**   Gemini (multimodal/API), **Firebase** (authentication in the merged frontend stack), and embedding-related tooling referenced in weekly work.
- **Hugging Face**   `transformers`, model hubs, and pretrained checkpoints (e.g. ColQwen, sentence encoders).
- **IBM**   **Docling** and related document-understanding components.
- **Qdrant**   Vector Database used in the Phase 2 AI service and merge backend.
- **Amazon Web Services**   **S3**, **SageMaker** real-time inference, and (via Terraform) **ECS**, **ECR**, **ALB**, **ACM** for optional cloud deployment.
- **HashiCorp**   **Terraform** for infrastructure as code in `Phase_2/code/terraform/`.
- **Pyserini / Anserini & Milvus**   retrieval stacks explored in research-week milestones.
- **LangChain & LlamaIndex**   RAG framework comparisons (early-phase notebooks and prototypes).
- **FFmpeg, Tesseract, Poppler**   media, OCR, and PDF tooling (TR-005).
- **React, Vite, Tailwind CSS**   frontend stack (TR-002).

---

**Version:** 1.0
**Last Updated:** May 10, 2026

**Team:** MKhoi, NKhoi, QPhu.
