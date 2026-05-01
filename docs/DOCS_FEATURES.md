# BK-MInD Feature Documentation

**Last Updated:** April 28, 2026  
**Version:** 1.0  
**Status:** Production

---

## 📑 Feature Index

| Feature | Category | Status | Documentation |
|---------|----------|--------|-----------------|
| 1. [User Authentication](#1-user-authentication) | Core | ✅ Active | Firebase + Local |
| 2. [File Upload & Management](#2-file-upload--management) | Content | ✅ Active | S3/Local Storage |
| 3. [Document Processing](#3-document-processing) | Pipeline | ✅ Active | Multi-stage normalization |
| 4. [Full-Text Search (BM25)](#4-full-text-search-bm25) | Retrieval | ✅ Active | Sparse indexing |
| 5. [Semantic Search (Dense)](#5-semantic-search-dense) | Retrieval | ✅ Active | Vector embeddings |
| 6. [Hybrid Search](#6-hybrid-search) | Retrieval | ✅ Active | Combined BM25+Dense |
| 7. [Image/Visual Retrieval](#7-imagevision-retrieval) | Retrieval | ✅ Active | Vision-language models |
| 8. [Chat Assistant](#8-chat-assistant) | Interaction | ✅ Active | Strands Agent + Tools |
| 9. [Quiz Generation](#9-quiz-generation) | Learning | ✅ Active | MCQ creation |
| 10. [Lecture Summaries](#10-lecture-summaries) | Learning | ✅ Active | Automated abstracts |
| 11. [Learning Roadmaps](#11-learning-roadmaps) | Learning | ✅ Active | Personalized paths |
| 12. [Performance Analytics](#12-performance-analytics) | Analytics | ✅ Active | Quiz tracking |
| 13. [Learning Visualizations](#13-learning-visualizations) | Learning | ✅ Active | Infographics + mind maps |
| 14. [Feedback System](#14-feedback-system) | Interaction | ✅ Active | User feedback triage |
| 15. [Session Management](#15-session-management) | Core | ✅ Active | Chat history |
| 16. [Content Safety (Guardrails)](#16-content-safety-guardrails) | Security | ✅ Active | AWS Bedrock Guardrails |
| 17. [Search Result Caching](#17-search-result-caching) | Performance | ✅ Active | Redis cache |
| 18. [Admin Dashboard](#18-admin-dashboard) | Admin | ✅ Active | Usage tracking |

---

## 1. User Authentication

**Purpose:** Secure tenant isolation and user identity management

**Implementation:**
- **Local Mode:** Username/password (dev/testing) → DynamoDB user table
- **Firebase Mode:** Google OAuth 2.0 → Firebase Auth → DynamoDB users table
- **Session Handling:** JWT tokens via header or secure cookies
- **Default Admin:** Built-in bootstrap user for initial setup

**API Endpoints:**
- `POST /api/auth/login-local` — Local credential authentication
- `GET /api/users/me` — Retrieve current user profile
- `POST /api/auth/logout` — Invalidate session

**Database Table:** `phase2-merge-users` (DynamoDB)
- Partition Key: `uid` (String)
- Attributes: `email`, `displayName`, `role`, `photoURL`, `createdAt`, `lastLogin`

**Configuration:**
```env
ENABLE_DEFAULT_ADMIN_BOOTSTRAP=true
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_EMAIL=admin@local.dev
DEFAULT_ADMIN_PASSWORD=quangphu1804
FIREBASE_SERVICE_ACCOUNT_PATH=firebase-service-account.json
LOCAL_AUTH_SECRET=PHUDEPZAI
```

**Security:** ✅ NFR-007 (Identity & access control)

**Links:**
- API Reference: [`API_REFERENCE.md#authentication-and-identity`](API_REFERENCE.md#authentication-and-identity)
- Code: `app/api/routes/auth_routes.py`

---

## 2. File Upload & Management

**Purpose:** Enable learners to ingest diverse learning materials

**Supported Formats:** PDF, DOCX, PPTX, XLSX, CSV, PNG, JPG, MP4, MP3, VTT, HTML, etc.

**Storage Backends:**
- **S3 Mode** (Production): User-scoped buckets with prefix isolation
  - Originals: `s3://ai-service-originals-dev/<user_id>/<file_name>`
  - Processed: `s3://ai-service-processed-dev/<user_id>/<file_name>`
- **Local Mode** (Dev): File system storage

**API Endpoints:**
- `POST /api/upload` — Upload one or more files (multipart form)
- `GET /api/files` — List uploaded files
- `GET /api/files/metadata` — List files with processing status
- `DELETE /api/files` — Delete file and cleanup processed artifacts
- `GET /api/image` — Retrieve image assets
- `GET /api/pdf-page-image` — Render PDF page images

**Database Tables:**
- `bk_mind_app_jobs` — Processing job tracking
- S3/local filesystem — Actual file storage

**Configuration:**
```env
FILE_STORAGE_BACKEND=s3  # or "local"
S3_ORIGINALS_BUCKET=ai-service-originals-dev
S3_PROCESSED_BUCKET=ai-service-processed-dev
```

**Security:** ✅ NFR-006 (User isolation via prefixes)

**Links:**
- API Reference: [`API_REFERENCE.md#file-and-library-apis`](API_REFERENCE.md#file-and-library-apis)
- Code: `app/api/routes/file_routes.py`, `app/services/file_service.py`

---

## 3. Document Processing

**Purpose:** Convert raw learning materials into structured, retrieval-ready content

**Pipeline Stages:**

### Stage 1: Normalization
- Format conversion (DOCX → PDF, etc.)
- Filename sanitization for Windows compatibility (260-char limit)
- Deduplication check (MD5-based)

### Stage 2: Media Processing
- **Audio/Video:** Whisper transcription with timestamped exports
- **Output Formats:** JSON, SRT, VTT, Markdown
- **Language:** Auto-detected via Whisper

### Stage 3: Document Understanding (Docling)
- **Smart OCR:** RapidOCR with fallbacks (Tesseract, EasyOCR)
- **VLM Analysis:** SmolVLM-256M for image descriptions (optional, toggled via `--no-vlm`)
- **Table Extraction:** Markdown-formatted tables
- **Layout Preservation:** PDFs maintain visual structure

### Stage 4: Consolidation
- **Dual Outputs:**
  - Normalized PDF (for image-based retrieval)
  - Markdown (for semantic/text retrieval)
- **Deduplication:** One file processed once, best-quality source selected

**API Endpoints:**
- `POST /api/process` — Start processing job (async)
- `GET /api/processing-stats` — View processing status
- `GET /api/index/status/{job_id}` — Poll background job

**Supported Formats:** 15+ (DOCX, PPTX, HTML, Images, Video, Audio, PDF, Excel, CSV, AsciiDoc, WebVTT, etc.)

**Performance Modes:**
- **Full Mode:** VLM-enabled, ~1× speed
- **Balanced Mode:** OCR-only with exports, ~2× faster
- **Fast Mode:** OCR minimal exports, 3-5× faster

**Features:**
- ✅ Windows path truncation (50 chars + MD5 hash)
- ✅ GPU acceleration (CUDA support)
- ✅ Batch processing with progress tracking
- ✅ Exponential backoff retry mechanism
- ✅ Comprehensive error handling

**Configuration:**
```env
USE_AWS_SAGEMAKER_DOCLING=false  # or true for remote processing
SAGEMAKER_DOCLING_ENDPOINT_NAME=phase2-multimodal-rt
OFFICE_PDF_CONVERTER_MODE=lambda  # or "local"
```

**Implementation:** [`Week070809_QPhu_Processor/`](../../Week070809_QPhu_Processor/)

**Links:**
- Code: `src/generation/providers/`, pipeline modules
- API Reference: [`API_REFERENCE.md#processing-and-indexing-apis`](API_REFERENCE.md#processing-and-indexing-apis)

---

## 4. Full-Text Search (BM25)

**Purpose:** Fast keyword-based retrieval for text queries

**Technology:** Sparse inverted index (BM25 ranking algorithm)

**Features:**
- ✅ Stemming and tokenization
- ✅ Relevance ranking via BM25 formula
- ✅ Wildcard and phrase queries
- ✅ Sub-second latency

**Integration:** Qdrant sparse index

**API Usage:**
```python
POST /api/search
{
  "query": "machine learning",
  "retriever_type": "sparse",  # BM25
  "top_k": 10,
  "search_scope": "text"
}
```

**Performance:** Typical 50-200ms for 10-50k documents

**Links:**
- Code: `src/generation/retrievers/`
- API Reference: [`API_REFERENCE.md#search-and-retrieval-apis`](API_REFERENCE.md#search-and-retrieval-apis)

---

## 5. Semantic Search (Dense)

**Purpose:** Meaning-based retrieval using vector embeddings

**Technology:** 
- **Embeddings:** Sentence-BERT or API-based (OpenAI, Gemini)
- **Vector DB:** Qdrant cloud or local
- **Distance Metric:** Cosine similarity

**Features:**
- ✅ Semantic understanding (synonyms, paraphrases)
- ✅ Multi-language support
- ✅ 3.6× higher nDCG@10 than BM25 (MS MARCO benchmark)

**Configuration:**
```env
QDRANT_MODE=cloud  # or "docker"
QDRANT_URL=https://22df1f46-c59a-4877-a754-a819e4a95eac.us-west-2-0.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Performance:** Typical 200-500ms for 10-50k documents

**Research:** Week 05 retrieval comparison shows dense outperforms sparse on natural language queries

**Links:**
- Code: `src/generation/retrievers/dense_retriever.py`
- Research: [`Week0506_NKhoi_Retrieval/`](../../Week0506_NKhoi_Retrieval/)

---

## 6. Hybrid Search

**Purpose:** Combine BM25 (precision) + Dense (recall) for balanced results

**Strategy:**
- Run both BM25 and dense retrieval in parallel
- Merge rankings via Reciprocal Rank Fusion (RRF)
- Deduplicate and re-rank by combined score

**Benefits:**
- Better coverage than BM25 alone
- More relevant than dense alone
- Vocabulary-mismatch resilient

**API Usage:**
```python
POST /api/search
{
  "query": "student learning outcomes",
  "retriever_type": "hybrid",
  "top_k": 10
}
```

**Research Finding:** Marginal improvement over dense alone but adds slight latency overhead

**Links:**
- Code: `src/generation/search_orchestrator.py`
- Research: [`Week0304_NKhoi_Retrieval/manual_bm25_dense_hybrid.ipynb`](../../Week0304_NKhoi_Retrieval/manual_bm25_dense_hybrid.ipynb)

---

## 7. Image/Vision Retrieval

**Purpose:** Retrieve lecture slides, diagrams, and visual content without OCR errors

**Technology:** Vision-Language Models (ColQwen via optional SageMaker)

**Features:**
- ✅ End-to-end visual retrieval (bypasses OCR)
- ✅ Handles handwritten text, complex layouts
- ✅ Multi-page document support

**API Usage:**
```python
POST /api/search
{
  "query": "algorithm flowchart",
  "search_scope": "image",
  "top_k": 5,
  "retriever_type": "hybrid"
}
```

**Backend:**
- Local: ColQwen embeddings
- Remote: SageMaker endpoint (optional)

**Configuration:**
```env
USE_AWS_SAGEMAKER_INFERENCE=false  # or true
SAGEMAKER_ENDPOINT_NAME=phase2-multimodal-rt
```

**Performance:** 1-2 second latency for image search (includes S3 retrieval)

**Research:** [`Week0506_NKhoi_Retrieval/`](../../Week0506_NKhoi_Retrieval/) — ColPali for superior document image retrieval

**Links:**
- Code: `src/generation/retrievers/image_retriever.py`
- API Reference: [`API_REFERENCE.md#search-and-retrieval-apis`](API_REFERENCE.md#search-and-retrieval-apis)

---

## 8. Chat Assistant

**Purpose:** Conversational learning interaction with tool-using agent

**Technology:** Strands Agent Framework + AWS Bedrock LLM

**Features:**
- ✅ Tool-using agent (search, quiz, visualization, etc.)
- ✅ Session memory (AgentCore optional)
- ✅ Server-sent events (SSE) streaming
- ✅ Follow-up suggestions
- ✅ Structured output (JSON schema)

**Available Tools:**
1. `text_rag` — Search lecture notes (hybrid text retrieval)
2. `image_rag` — Search slide images (vision-language)
3. `get_quiz_performance` — Retrieve quiz analytics
4. `list_my_documents` — List uploaded files
5. `get_processed_markdown` — Get markdown content
6. `get_document_summary` — Generate summary
7. `generate_quiz` — Create quiz
8. `generate_learning_visualization` — Create infographic

**System Prompt:** Educated assistant with direct responses for greetings, farewell, identity, capability questions; tool usage for academic queries

**Session Storage:** DynamoDB
- `DYNAMODB_CHATBOT_SESSIONS_TABLE=chatbot-session`
- `DYNAMODB_CHATBOT_MESSAGES_TABLE=chatbot-messages`

**LLM Model:** Bedrock (Claude 3.5 Sonnet or configured model)

**API Endpoints:**
- `POST /api/chat/stream` — Stream response with tools

**Safety:** ✅ AWS Bedrock Guardrails (see Feature #16)

**Configuration:**
```env
CHAT_AGENT_RUNTIME=local  # or "agentcore-runtime"
AGENTCORE_REGION=us-west-2
```

**Performance:** 50-500ms for tool invocation + streaming response

**Links:**
- Code: `agent/strands_chat_runtime.py`, `app/api/routes/chat_routes.py`
- API Reference: [`API_REFERENCE.md#chat-apis`](API_REFERENCE.md#chat-apis)
- Guardrail Config: [`GUARDRAIL_CONFIGURATION.md`](GUARDRAIL_CONFIGURATION.md)

---

## 9. Quiz Generation

**Purpose:** Create practice questions from lecture materials

**Features:**
- ✅ Multiple-choice questions (MCQs)
- ✅ Configurable difficulty
- ✅ Source citation
- ✅ Topic-focused

**API Endpoint:**
```python
POST /api/insights/mcq-quiz
{
  "document_id": "lecture_01.pdf",
  "num_questions": 5,
  "difficulty": "medium"
}
```

**Generation Model:** Bedrock Claude + RAG pipeline

**Storage:** DynamoDB `bk_mind_quiz_results`
- Tracks quiz attempts per user
- Stores scores, answers, timestamps

**Performance Tracking:**
- Accuracy by topic
- Improvement over time
- Strength/weakness breakdown

**Links:**
- Code: `app/services/insights_service.py`
- API Reference: [`API_REFERENCE.md`](API_REFERENCE.md)

---

## 10. Lecture Summaries

**Purpose:** Generate concise abstracts of lecture content

**Features:**
- ✅ Multi-document summarization
- ✅ Key concepts extraction
- ✅ Markdown formatting
- ✅ Navigation support (timestamps for videos)

**API Endpoint:**
```python
POST /api/insights/lecture-summary
{
  "document_id": "lecture_01.pdf",
  "summary_length": "medium"  # short, medium, long
}
```

**Generation Process:**
1. Retrieve full lecture content via `get_processed_markdown()`
2. Send to Bedrock Claude with RAG-aware prompt
3. Return formatted summary with section headers

**Performance:** 2-5 seconds (including LLM inference)

**Links:**
- Code: `app/services/insights_service.py`
- API Reference: [`API_REFERENCE.md`](API_REFERENCE.md)

---

## 11. Learning Roadmaps

**Purpose:** Generate personalized learning paths based on student profile and goals

**Features:**
- ✅ Topic sequencing
- ✅ Difficulty progression
- ✅ Prerequisite identification
- ✅ Timeline estimation

**API Endpoint:**
```python
POST /api/insights/learning-roadmap
{
  "learning_goal": "Master machine learning basics",
  "current_knowledge": "Basic Python programming",
  "available_hours": 20
}
```

**Generation:** Bedrock Claude using course materials + student profile

**Output:** Structured learning plan with milestones, estimated hours, recommended resources

**Links:**
- Code: `app/services/insights_service.py`
- API Reference: [`API_REFERENCE.md`](API_REFERENCE.md)

---

## 12. Performance Analytics

**Purpose:** Track student learning progress and identify strengths/weaknesses

**Features:**
- ✅ Quiz score tracking
- ✅ Topic-level breakdown
- ✅ Longitudinal progress
- ✅ Comparative analytics (vs. class average)

**API Endpoint:**
```python
GET /api/stats/quiz-performance
```

**Stored Data:** DynamoDB `bk_mind_quiz_results`
- `quiz_id`, `user_id`, `score`, `total`, `quiz_topic`, `timestamp`

**Dashboard:** React component showing charts, metrics, progress

**Links:**
- Code: `app/services/quiz_results_service.py`
- Frontend: `frontend/src/components/AnalyticsDashboard.tsx`

---

## 13. Learning Visualizations

**Purpose:** Create infographics, mind maps, and visual summaries

**Features:**
- ✅ Concept map generation
- ✅ Topic hierarchy visualization
- ✅ Relationship diagrams
- ✅ PNG/SVG output

**API Endpoint:**
```python
POST /api/insights/learning-visualization
{
  "document_id": "lecture_01.pdf",
  "topic": "Neural Networks",
  "visualization_type": "mindmap"  # or "infographic", "flowchart"
}
```

**Generation:**
1. Retrieve document markdown
2. Extract key concepts
3. Generate visualization description (Claude)
4. Render via visualization library

**Output:** Base64-encoded PNG embedded in response

**Storage:** DynamoDB with S3 backup

**Performance:** 3-10 seconds (includes rendering)

**Links:**
- Code: `app/services/insights_service.py`
- API Reference: [`API_REFERENCE.md`](API_REFERENCE.md)

---

## 14. Feedback System

**Purpose:** Collect and categorize user feedback for improvement

**Features:**
- ✅ Free-form feedback input
- ✅ Automated categorization (bug, feature request, general)
- ✅ PII masking via guardrails
- ✅ Admin review interface

**API Endpoint:**
```python
POST /api/feedback
{
  "message": "The search is slow when I upload 50 documents",
  "feedback_type": "bug"  # or "feature", "general"
}
```

**Processing:**
1. User submits feedback
2. Guardrails mask PII (phone, email, etc.)
3. Claude classifier determines category
4. Stored in DynamoDB `bk_mind_feedback`

**Admin Interface:** View/export feedback, respond to users

**Storage:** DynamoDB `bk_mind_feedback`

**Links:**
- Code: `app/services/feedback_service.py`
- API Reference: [`API_REFERENCE.md`](API_REFERENCE.md)

---

## 15. Session Management

**Purpose:** Maintain conversational context across chat turns

**Features:**
- ✅ Message history storage
- ✅ User-scoped sessions
- ✅ Session listing/deletion
- ✅ Timestamp tracking

**Storage:** DynamoDB
- `DYNAMODB_CHATBOT_SESSIONS_TABLE=chatbot-session`
- `DYNAMODB_CHATBOT_MESSAGES_TABLE=chatbot-messages`

**Session Data:**
```python
{
  "session_id": "uuid",
  "user_id": "uid",
  "created_at": "2026-04-28T10:00:00Z",
  "last_message_at": "2026-04-28T10:30:00Z",
  "message_count": 12
}
```

**Message Format:**
```python
{
  "message_id": "uuid",
  "session_id": "uuid",
  "role": "user|assistant",
  "content": "...",
  "timestamp": "2026-04-28T10:00:00Z",
  "attachments": []
}
```

**API Endpoints:**
- `POST /api/chat/session` — Create session
- `GET /api/chat/sessions` — List user's sessions
- `GET /api/chat/messages/{session_id}` — Retrieve messages
- `DELETE /api/chat/session/{session_id}` — Delete session

**Links:**
- Code: `app/services/chat_history_service.py`
- API Reference: [`API_REFERENCE.md#chat-apis`](API_REFERENCE.md#chat-apis)

---

## 16. Content Safety (Guardrails)

**Purpose:** Prevent harmful, offensive, or unsafe AI responses

**Technology:** AWS Bedrock Guardrails

**Protections:**
- ✅ Hate speech, insults, sexual, violence, misconduct blocking
- ✅ Prompt attack detection (injection, jailbreak, etc.)
- ✅ PII masking (27 types: phone, email, credit cards, etc.)
- ✅ Profanity filtering
- ✅ Configurable message for blocked content

**Guardrail ID:** `42ay3u3pr8vr` (DRAFT version)

**Integration:** All Bedrock API calls include guardrailConfig parameter

**Features Protected:**
- Chat assistant
- Quiz generation
- Summary generation
- Roadmap generation
- Feedback triage

**Configuration:**
```env
GUARDRAIL_ENABLED=true
GUARDRAIL_ID=42ay3u3pr8vr
GUARDRAIL_VERSION=DRAFT
```

**Blocked Message:**
```
Sorry, the we cannot answer this question because it violates our policies.
```

**Monitoring:** Track block rate, filter triggers, false positives

**Links:**
- Documentation: [`GUARDRAIL_CONFIGURATION.md`](GUARDRAIL_CONFIGURATION.md)
- Code: `agent/bedrock_guardrail_integration.py`
- Implementation: `src/generation/provider/bedrock_provider.py`, `src/generation/generator.py`, `app/services/feedback_service.py`

---

## 17. Search Result Caching

**Purpose:** Improve performance and reduce redundant processing

**Technology:** Redis (local) or AWS ElastiCache (cloud)

**Features:**
- ✅ Text result caching (10 min TTL default)
- ✅ Image result caching
- ✅ Query-based keys with hashing
- ✅ Per-user cache isolation

**Configuration:**
```env
SEARCH_CACHE_ENABLED=true
SEARCH_CACHE_BACKEND=redis
SEARCH_CACHE_TTL_SECONDS=600
SEARCH_CACHE_REDIS_URL=redis://localhost:6379/0
SEARCH_CACHE_KEY_PREFIX=phase2:search:v1
```

**ElastiCache Setup (AWS):**
```env
SEARCH_CACHE_REDIS_URL=rediss://rag-pipeline-cache-jx9fd6.serverless.usw2.cache.amazonaws.com:6379/0
```

**Performance Impact:**
- Cache hit: 5-50ms
- Cache miss: Full retrieval (200-500ms)
- Typical hit rate: 40-60% for repeated queries

**Links:**
- Code: `app/services/search_cache_service.py`
- Documentation: [`DOCS_search-cache-redis-setup.md`](DOCS_search-cache-redis-setup.md)

---

## 18. Admin Dashboard

**Purpose:** Monitor usage, system health, and operational metrics

**Features:**
- ✅ User activity tracking
- ✅ Feature usage breakdown
- ✅ Processing job status
- ✅ Cost estimation

**Tracked Metrics:** DynamoDB `bk_mind_app_usage`
```python
{
  "usage_id": "uuid",
  "user_id": "uid",
  "feature": "chat_assistant|search|quiz|...",
  "method": "POST",
  "path": "/api/chat/stream",
  "status": 200,
  "elapsed_ms": 1250,
  "timestamp": "2026-04-28T10:00:00Z"
}
```

**Cost Tracking:** AWS Cost Estimation spreadsheet
- Per-user active costs
- Feature-level breakdown
- Scaling projections

**Admin Endpoints:**
- `GET /api/stats/usage` — View usage metrics
- `GET /api/processing-stats` — View processing status

**Links:**
- Code: `app/services/usage_service.py`
- AWS Cost: [`docs/others/AWS_Cost_Estimation_50_Users_Professional.xlsx`](../others/AWS_Cost_Estimation_50_Users_Professional.xlsx)

---

## 📊 Feature Compliance with SRS

| Requirement | Feature | Status |
|-------------|---------|--------|
| FR-001 | ASR + timed exports | ✅ Document Processing |
| FR-002 | Documents + OCR | ✅ Document Processing |
| FR-003/004 | Spreadsheet + Markdown | ✅ Document Processing |
| FR-005 | Images/VLM | ✅ Document Processing + Image Retrieval |
| FR-006 | Deduplication | ✅ Document Processing |
| FR-007/008 | Audio-slide alignment | ✅ Document Processing |
| FR-009 | BM25, dense, hybrid | ✅ Full/Semantic/Hybrid Search |
| FR-010 | Vision-language retrieval | ✅ Image Retrieval |
| FR-011 | Query handling | ✅ All Search endpoints |
| FR-012/013 | Grounded answers + citations | ✅ Chat + RAG pipeline |
| FR-014 | Chat decomposition | ✅ Chat Assistant (Strands Agent) |
| FR-021/022 | File management + search UI | ✅ Upload + Search |
| FR-023/024 | Summaries + navigation | ✅ Lecture Summaries |
| FR-025/026/027 | Learning paths, quiz, analytics | ✅ Roadmap, Quiz, Analytics |
| NFR-007 | Identity & access | ✅ Authentication |
| TR-001/002/003/004 | FastAPI, React, Vectors, LLMs | ✅ Full stack |

---

**Version:** 1.0  
**Last Updated:** April 28, 2026  
**Maintained By:** AI Service Team
