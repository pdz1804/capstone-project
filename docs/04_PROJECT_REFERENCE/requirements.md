# Software Requirements Specification

## Educational Content Processing & Retrieval-Augmented Generation System

**Document Version**: 2.0  
**Last Updated**: May 14, 2026  
**Status**: Active

---

## Requirements Overview

### Summary Statistics

| Metric | Value |
|--------|-------|
| **Total Requirements** | 43 |
| Functional Requirements | 26 |
| Non-Functional Requirements | 10 |
| Technical Requirements | 7 |
| **AI-Heavy Requirements** | 17 (40%) |
| **Software-Heavy Requirements** | 26 (60%) |

### Functional Requirements by Category

| Category | Count | Examples |
|----------|-------|----------|
| Content Processing | 8 | Audio, Document, Spreadsheet processing |
| Information Retrieval | 3 | Text, Visual, Query processing |
| Question Answering | 4 | Answer generation, Results, Chat, History |
| User Interface | 2 | File management, Search interface |
| Lecture Summary | 2 | Summary generation, Interactive navigation |
| Personalization | 3 | Learning paths, Assessments, Analytics |

### Critical & High-Risk Requirements

**Most Critical** (Must Have): FR-001, FR-002, FR-009, FR-012, NFR-001  
**Highest Risk** (Monitor closely): FR-005, FR-010, FR-018, FR-019, NFR-002

---

### 1. Introduction

#### 1.1 Purpose

This document outlines the comprehensive requirements for an Educational Content Processing & Retrieval-Augmented Generation (RAG) System designed to process, index, and enable intelligent querying of educational multimedia content from lectures.

#### 1.2 Scope

The system encompasses:

- Multimodal content processing (audio, video, documents, images)
- Audio-slide temporal synchronization and alignment
- Advanced spreadsheet parsing with merged cell support to markdown
- Intelligent information retrieval across multiple modalities
- Question-answering capabilities with citation support
- Automated lecture summary generation
- Personalized learning paths and roadmaps
- Web-based user interface for interaction
- Production-ready deployment architecture (Local and Cloud modes)
- S3-based canonical storage with local workspace synchronization
- Qdrant-based vector search with payload-level multitenancy

#### 1.3 Key Definitions

| Term | Definition |
|------|-----------|
| **ASR** | Automatic Speech Recognition - converting speech to text using AI models |
| **OCR** | Optical Character Recognition - extracting text from images/scanned documents |
| **RAG** | Retrieval-Augmented Generation - combining document retrieval with LLM generation |
| **VLM** | Vision Language Model - AI model understanding both text and images |
| **BM25** | Best Match 25 - statistical ranking function for full-text search (sparse retrieval) |
| **Dense Retrieval** | Semantic similarity-based retrieval using vector embeddings |
| **Multitenancy** | Architecture strategy isolating data between different users/tenants |
| **Qdrant** | Vector database for efficient semantic search at scale |
| **Docling** | Advanced document processing framework for layout-aware PDF/doc conversion |

---

### 2. Functional Requirements

#### 2.1 Content Processing Requirements

**FR-001: Audio Processing**

- Extract audio from video files (MP4, AVI, MOV) using FFmpeg.
- Transcribe audio to text using **Whisper Large-v3** (Standard mode) or **Whisper Tiny** (Fast mode).
- Generate timestamped transcripts in multiple formats (JSON, SRT, VTT, MD).

**FR-002: Document Processing**

- Process PDF documents with layout preservation
- Extract text from images using OCR
- Support multiple document formats (DOCX, PPTX, HTML, TXT, CSV, Excel)
- Generate dual outputs: normalized PDFs and Markdown files

**FR-003: Advanced Spreadsheet Parsing (Stage 3b)**

- Parse Excel/CSV files using specialized Stage 3b logic (local XML parsing).
- Preserve merged cell structure and hierarchy in parsing.
- Extract merged cell content with proper semantic interpretation.
- Generate hierarchical markdown representation (nested lists, tables with row/column groups).
- Support complex multi-level merged cell layouts.
- Handle merged cells in headers (column groups, row groups).
- Detect and preserve data relationships across merged ranges.
- Support conditional preservation of formatting (colors, fonts, borders).

**FR-004: Markdown Export from Spreadsheets**

- Convert spreadsheet data to hierarchical markdown structure
- Generate markdown tables with header grouping notation
- Support visualization hints in markdown (comments for formatting)
- Create section-based markdown from spreadsheet tabs
- Preserve calculated values and formulas as comments

**FR-005: Image Processing**

- Extract and process images from documents using Docling.
- Generate image descriptions using **SmolVLM-256M**.
- Support visual retrieval capabilities via ColQwen multivectors.

**FR-007: Audio-Slide Synchronization**

- Detect slide transitions and timestamps in video lectures
- Correlate slide changes with audio transcript timestamps
- Build temporal alignment map between audio segments and slide content
- Store alignment metadata in video processing database
- Generate aligned transcript with slide references

**FR-008: Temporal Navigation and Retrieval**

- Display current slide alongside transcript during playback
- Generate slide-indexed summaries (one summary per slide change)
- Support alignment-based chunking for content retrieval
- Enable cross-referencing questions to specific slides and timestamps

**FR-006: Content Deduplication**

- Implement file hashing
- Skip already processed files based on content hash and processing cache

**FR-028: Multi-Mode Processing (Standard vs Fast)**

- Support **Standard mode**: Full quality (Whisper Large-v3, Docling VLM enabled, table/image export, word timestamps).
- Support **Fast mode**: Optimized speed (Whisper Tiny, Docling VLM disabled, increased frame intervals, simplified ASR schedule).

**FR-033: Processing Cache & Deduplication**

- Implement idempotent processing using content-based hashing.
- Maintain a processing cache (`.processing_cache.json`) to skip already processed files.
- Support `force` flag to bypass cache and re-process entire library.

#### 2.2 Information Retrieval Requirements

**FR-009: Text Retrieval**

- Implement BM25 sparse retrieval
- Implement dense semantic retrieval using embeddings
- Support hybrid retrieval combining both methods

**FR-010: Visual Retrieval**

- Implement vision-language retrieval for document images
- Support ColQwen/ColPali models for visual retrieval

**FR-011: Query Processing**

- Accept natural language queries
- Provide relevance scoring for results
- Support query expansion and optimization
- **Enforce tenant isolation via `user_id` filtering in all retrieval operations**

#### 2.3 Question Answering Requirements

**FR-012: Answer Generation**

- Generate responses using LLMs
- Include citations from source documents
- Provide configurable answer generation parameters

**FR-013: Result Presentation**

- Display text chunks with relevance scores
- Show image results with page numbers
- Present generated answers with citations
- Support result filtering and sorting

**FR-014: Chat Assistant**

- Provide a natural language interface for querying educational content.
- Retrieve relevant documents from multiple search methods (Dense, Sparse, Hybrid).
- Generate comprehensive answers using retrieved context across multiple modalities.
- Provide citations from all relevant sources used in answer generation.

**FR-030: Persistent Chat History**

- Persist chat sessions and messages using DynamoDB.
- Enable users to retrieve history across different devices/sessions.
- Support paged loading of chat history to optimize performance.

**FR-031: Chat Session Management**

- Allow users to rename, pin/unpin, and delete chat sessions.
- Provide a compact chat history panel for easy navigation.
- Support "History Sync" toggle for session data privacy.

**FR-032: Runtime Mode Switch**

- Support dynamic switching between local agent runtime and remote Bedrock AgentCore runtime.
- Enable configuration-driven runtime selection via environment variables.

**FR-029: Cloud-Native Storage & Processing**

- Support S3 as the canonical storage for original and processed artifacts.
- Implement automatic synchronization between cloud storage and local processing workspace.
- Support remote inference for heavy tasks (SageMaker for Docling/Whisper/ColQwen).

#### 2.4 User Interface Requirements

**FR-021: File Management**

- Drag-and-drop file upload interface
- Display uploaded, processed, and indexed files
- Show processing progress and status

**FR-022: Search Interface**

- Natural language query input
- Display multimodal search results
- Support result refinement and filtering

#### 2.5 Lecture Summary Requirements

**FR-023: Automated Lecture Summary Generation**

- Generate concise summaries from lecture transcripts and documents
- Extract key concepts and learning objectives
- Create multi-level summaries (brief, detailed, comprehensive)
- Highlight important definitions and formulas
- Preserve original timestamps and source references
- Support customizable summary length and focus areas

**FR-024: Interactive Summary Navigation**

- Clickable summary sections with links to source material
- Timeline view of lecture flow with key milestones
- Visual outline generation from summary structure
- Search within generated summaries
- Annotation and note-taking on summaries

**FR-025: Learning Path Generation**

- Generate customized "learning roadmaps" based on student profile and goals.
- Suggest prerequisites and ordered topics based on processed document content.

**FR-026: Knowledge Assessment Generation**

- Generate multiple-choice questions (MCQs) from lecture content.
- Support different difficulty levels and question styles.
- Provide instant feedback with correct answers and explanations.
- Track basic quiz results and scores per user.

---

### 3. Non-Functional Requirements

#### 3.1 Performance Requirements

**NFR-001: Response Time**

- Text retrieval: <1 second for 1000+ documents.
- Image retrieval: <2 seconds for visual queries.
- Answer generation: <10 seconds for typical queries.
- Document processing: <2 minutes for standard 10MB document (DOC/PPT/PDF) in Standard Mode; <30 seconds in Fast Mode.

**NFR-002: Scalability**

- Support 10,000+ documents in corpus.
- Handle concurrent users (10+ simultaneous) with horizontal scaling.
- Efficient memory usage via `on_disk=true` vector storage and quantization.
- Support multi-tenant isolation at scale via payload-based filtering.

#### 3.2 Reliability Requirements

**NFR-003: System Availability**

- 99% uptime during business hours.
- Graceful recovery via **Local <=> Cloud failover** for inference and storage backends.
- Automatic retry mechanisms for SageMaker/Bedrock transient failures.

**NFR-004: Data Integrity & Consistency**

- Maintain atomicity between file storage (S3) and vector index states.
- Ensure processed markdown accuracy against original hashes.
- Idempotent re-runs using `.processing_cache.json`.
- Automatic pruning of orphan artifacts in the processing pipeline.

#### 3.3 Usability Requirements

**NFR-005: User Experience**

- Intuitive web interface with minimal training
- Responsive design for desktop and mobile
- Clear error messages and guidance
- Progress indicators for long operations

**NFR-006: Accessibility**

- Support screen readers and assistive technologies
- Keyboard navigation support
- High contrast mode availability
- Multi-language support (Vietnamese, English)

#### 3.4 Security Requirements

**NFR-007: Data Protection**

- Secure file upload with backend validation.
- **Firebase Authentication** for user-level access control and session management.
- **Payload-level tenant isolation** in shared Qdrant collections using `user_id` filters.
- Data encryption in transit (HTTPS/TLS) and at rest (S3/DynamoDB encryption).

**NFR-008: Privacy Compliance**

- Multi-tenant isolation ensuring no leakage between user-isolated prefixes in S3.
- Anonymous usage analytics.
- GDPR/FERPA compliance readiness for educational records.
- Clear data usage policies.
- Support for session-only history persistence option.

#### 3.5 Operational & Quality Requirements

**NFR-009: Observability & Lifecycle Management**

- Detailed structured logging for pipeline stages and API errors.
- Real-time monitoring of SageMaker/Bedrock inference costs and latency.
- Automated lifecycle management for temporary processing workspaces (pruning and cleanup).

**NFR-010: RAG Accuracy & Trust**

- **Citation Precision**: 100% accuracy in mapping citations to source document pages/timestamps.
- **Hallucination Mitigation**: Enforced groundedness via prompt engineering and multi-stage verification.
- **Retrieval Recall**: Optimized dense/sparse hybrid search to ensure top-relevant chunks are within top-5 results.

---

### 4. Technical Requirements

#### 4.1 System Architecture

**TR-001: Backend Requirements**

- Python 3.11+ runtime environment
- FastAPI web framework for all microservices
- Asynchronous orchestration with Pydantic v2 data models
- Production-grade Uvicorn/Gunicorn server

**TR-002: Frontend Requirements**

- React 19+ (Single Page Application)
- Vite build tool and dev server
- TailwindCSS 4.1+ for advanced styling and modern aesthetics
- Lucide-React and Framer Motion for premium UX/UI
- TypeScript for full-stack type safety

**TR-003: Database Requirements**

- Vector database for dense retrieval
- Document store for processed content
- Metadata storage for file management
- Search index for efficient querying

#### 4.2 Integration Requirements

**TR-004: External Service Integration**

- OpenAI API for primary LLM generation (GPT-4o)
- Google Gemini API for multimodal 1.5 Pro processing
- AWS SageMaker for remote ColQwen and Docling inference
- Google Firebase for Identity and Authentication
- AWS DynamoDB for user profiles and persistent chat history storage
- AWS S3 for canonical object storage (Originals & Processed)
- Hugging Face Hub for model weights and configuration

**TR-005: AI and Processing Pipeline Stack**

- **Docling 2.0+**: Primary document understanding and layout analysis
- **Whisper**: High-accuracy spear-to-text (transcribe)
- **ColQwen/ColPali**: Vision-Language-Model for direct image retrieval
- **SmolVLM (256M)**: Lightweight VLM for image captioning and OCR
- **FFmpeg**: Media stream extraction and frame management
- **Sentence-Transformers**: Dense text embeddings (Local and Cloud)
- **CUDA 12.8**: GPU acceleration for inference stages

#### 4.3 Deployment Requirements

**TR-006: Containerization**

- Docker support for consistent deployment
- Docker Compose for multi-service orchestration
- Environment-specific configurations
- Health check endpoints

**TR-007: Infrastructure**

- Support for cloud deployment (AWS, GCP, Azure).
- On-premises deployment capability.
- Load balancing for high availability.
- Monitoring and logging infrastructure.
- **AWS S3** for original and processed artifact persistence.
- **Qdrant Cloud** with shared collections and payload-level tenant isolation (Deprecated per-user collections).

---

### 5. Constraints and Assumptions

#### 5.1 Technical Constraints

- Windows filename length limitation (260 characters)
- GPU memory limitations for large models
- API rate limits for external services
- Network bandwidth for file uploads

#### 5.2 Business Constraints

- Academic project timeline limitations
- Budget constraints for API usage
- Open source licensing requirements
- Educational institution policies

#### 5.3 Assumptions

- Users have basic computer literacy
- Stable internet connection available
- Sufficient computational resources
- Content primarily in Vietnamese and English

---

### 6. Verification Criteria

#### 6.1 Functional Testing

- Unit tests for all core components
- Integration tests for API endpoints
- End-to-end tests for user workflows
- Performance benchmarks for retrieval accuracy

#### 6.2 Acceptance Criteria

- Successful processing of supported file formats
- Accurate transcription and extraction
- Relevant search results for test queries
- Generated answers with proper citations

#### 6.3 Quality Metrics

- ASR Word Error Rate (WER) < 15%
- OCR accuracy > 90% for clear text
- Retrieval nDCG@10 > 0.2
- User satisfaction score > 4.0/5.0
