# BK-MInD Application Overview

BK-MInD is an AI learning platform that transforms videos, slides, PDFs, and documents into searchable learning knowledge. The system supports grounded question answering, source citations, document processing, hybrid retrieval, chat assistance, quiz generation, summaries, learning roadmaps, and performance-aware cloud deployment.

## Mission

BK-MInD helps students and educators convert unstructured learning materials into an interactive knowledge base. Instead of manually searching through slides, videos, and documents, learners can upload materials, process them into structured content, index them, search across them, and interact with them through AI-assisted workflows.

## Core Capabilities

| Capability | Description |
|---|---|
| File upload | Users upload learning materials into isolated per-user storage prefixes |
| Document processing | Pipeline converts source files into normalized, processed, and RAG-ready artifacts |
| Search and retrieval | Supports text, image, hybrid, BM25, dense vector, and multimodal retrieval flows |
| Grounded Q&A | Answers are generated from retrieved learning materials with source references |
| Chat assistant | Streamed AI assistant with tool usage, session persistence, and learning-material context |
| Learning insights | Summary, MCQ, roadmap, analytics, and visualization-oriented workflows |
| Performance testing | JMeter plans and reports validate behavior under concurrent-user workloads |
| Cloud deployment | AWS-oriented deployment with ECS, ALB, S3, DynamoDB, Qdrant, Redis/ElastiCache, and optional SageMaker components |

## User-Facing Workflows

1. **Upload materials:** a learner uploads PDFs, slides, or media files.
2. **Process materials:** the backend converts files into normalized content and markdown-like artifacts.
3. **Index knowledge:** processed content is indexed into text/image/vector stores.
4. **Search:** users query the indexed knowledge base with retrieval and citation support.
5. **Chat:** users ask learning questions through a streamed assistant that can use tools and session history.
6. **Learn:** users generate summaries, quizzes, roadmaps, and visual learning aids.

## High-Level Architecture

| Layer | Responsibilities |
|---|---|
| Frontend | React/Vite user interface for upload, library, lecture view, search, chat, insights, and feedback |
| API backend | FastAPI service exposing auth-aware application APIs and orchestration endpoints |
| Processing pipeline | Converts raw learning materials into structured assets for retrieval and generation |
| Retrieval services | BM25, dense vector, hybrid retrieval, image retrieval, Qdrant, and cache-backed result reuse |
| AI services | LLM/agent workflows, summaries, MCQs, roadmap generation, chat, and visualization generation |
| Persistence | S3 for source/processed artifacts, DynamoDB for jobs/chat state, Redis for cache, and Qdrant for vector search |
| Infrastructure | AWS ECS/ALB/ECR/Terraform with environment-driven deployment configuration |

## Quality Attributes

| Attribute | Current approach |
|---|---|
| User isolation | `X-User-Id`, per-user S3 prefixes, scoped processing roots, and scoped retrieval/index behavior |
| Reliability | Job tracking in DynamoDB, explicit status polling, error-aware runbooks, and retry-ready architecture |
| Performance | Redis-backed search cache, JMeter performance testing, and separation of synchronous vs asynchronous workloads |
| Scalability | ECS deployment model, queue-oriented recommendations for processing/indexing, and independent service scaling path |
| Observability | Timing logs, performance CSV exports, DynamoDB job metrics, and test reports |
| Security | Tenant-aware storage, controlled API headers, minimized sensitive logging, and deployment-focused infrastructure docs |

## Current Engineering Assessment

The platform is strongest for learner-facing workflows: upload, search, chat, and learning insight generation. The current performance evidence shows stable behavior through the tested concurrency levels for user-facing APIs. The main scaling boundary is the processing/indexing pipeline, especially full indexing at higher concurrent job counts.

This is a healthy system profile for an AI learning platform: interactive features are usable, while heavy ingestion workloads require controlled background execution. The next maturity step is to isolate and autoscale process/index workers, strengthen job queue policy, and improve retrieval/chat latency through caching and model-routing strategies.

## Documentation Map

- API surface: [`API_REFERENCE.md`](API_REFERENCE.md)
- Performance report: [`../testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md`](../testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md)
- JMeter runbooks: [`../jmeter-capacity-tests/runs/`](../jmeter-capacity-tests/runs/)
- Deployment references: [`../../Phase_2_FE_AI_Merge/terraform/README.md`](../../Phase_2_FE_AI_Merge/terraform/README.md)
