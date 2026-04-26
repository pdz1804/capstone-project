# BK-MInD API Reference

This document summarizes the main BK-MInD HTTP API surface at a reviewer and maintainer level. It is not a replacement for the FastAPI OpenAPI schema, but it provides a stable conceptual map for the platform.

## Authentication And Identity

| Method | Endpoint | Purpose | Notes |
|---|---|---|---|
| `POST` | `/api/auth/login-local` | Authenticate a local test/platform user | Returns an access token used by JMeter and frontend clients |
| `GET` | `/api/users/me` | Return current authenticated user profile | Used by UI and performance tests to verify identity |

Most tenant-scoped learning APIs use `X-User-Id` to determine the logical storage/index user. This is required for correct S3 prefixes and per-user retrieval scope. Without this header, backend dependencies fall back to the configured default storage user.

## File And Library APIs

| Method | Endpoint | Purpose | Notes |
|---|---|---|---|
| `POST` | `/api/upload` | Upload one or more files | Multipart form field is `files`; uses user-scoped storage |
| `GET` | `/api/files` | List uploaded files | Used by library and knowledge management views |
| `GET` | `/api/files/metadata` | List files with processing/index metadata | Powers UI state and document selection |
| `DELETE` | `/api/files` | Delete an uploaded/processed file | Requires a path returned by the API |

## Processing And Indexing APIs

| Method | Endpoint | Purpose | Behavior |
|---|---|---|---|
| `GET` | `/api/processing-stats` | Return processing/index status summary | Lightweight operational read |
| `POST` | `/api/process` | Start document processing | Asynchronous job; returns/polls job status |
| `POST` | `/api/index` | Start full indexing | Asynchronous job; writes searchable vectors/text indexes |
| `POST` | `/api/index/text` | Start text-only indexing | Useful for faster text-first workflows |
| `POST` | `/api/index/image` | Start image/visual indexing | Heavier multimodal path |
| `GET` | `/api/index/status/{job_id}` | Poll background job status | Used by JMeter extractors and frontend progress UI |

Processing and indexing should be treated as controlled background workloads. Performance evidence shows full indexing is the most capacity-sensitive operation.

## Search And Retrieval APIs

| Method | Endpoint | Purpose | Notes |
|---|---|---|---|
| `POST` | `/api/search` | Search indexed learning materials | Supports retrieval mode, generation mode, text/image/both scope, top-k, and retriever selection |
| `GET` | `/api/image` | Resolve image assets for display | Used by search and citation rendering |
| `GET` | `/api/pdf-page-image` | Render or retrieve PDF page images | Supports lecture and citation previews |

Search can involve BM25, dense vector retrieval, hybrid merge logic, Qdrant, and optional generation. Tail latency should be monitored separately from average latency.

## Chat APIs

| Method | Endpoint | Purpose | Notes |
|---|---|---|---|
| `POST` | `/api/chat/stream` | Stream assistant response through SSE | Uses retrieval/tools/session context; full elapsed time includes complete stream duration |
| `GET` | `/api/chat/sessions` | List chat sessions | Backed by chat history persistence when configured |
| `POST` | `/api/chat/sessions` | Create or ensure a chat session | JMeter chat test creates a fresh session before streaming |
| `PATCH` | `/api/chat/sessions/{session_id}` | Update session metadata | Used for title/pin updates |
| `DELETE` | `/api/chat/sessions/{session_id}` | Delete a session and messages | Removes persisted history for the user |
| `GET` | `/api/chat/sessions/{session_id}/messages` | List messages for a session | Supports paged history retrieval |
| `GET` | `/api/chat/attachment` | Retrieve persisted chat image attachments | Used for generated visualization images |

For performance analysis, distinguish first-byte latency from full stream duration. A fast first byte means the user sees progress quickly even if complete reasoning takes longer.

## Insight APIs

| Method | Endpoint | Purpose | Notes |
|---|---|---|---|
| `POST` | `/api/summary` | Generate a document/course summary | Uses processed learning materials |
| `POST` | `/api/mcq` | Generate multiple-choice questions | Strong candidate for high-concurrency learning workflows |
| `POST` | `/api/learning-roadmap` | Generate a personalized learning roadmap | Low-latency insight path in current performance tests |
| `POST` | `/insights/visualization` | Generate a learning visualization/infographic | Uses processed markdown and image generation model |
| `GET` | `/api/analytics` | Return learning analytics where configured | Supports insight dashboards |

## Feedback APIs

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/feedback` | List feedback items |
| `POST` | `/api/feedback` | Submit message or general feedback |
| `PATCH` | `/api/feedback/{feedback_id}` | Update feedback status/classification |

Feedback APIs support product quality review, answer-rating workflows, and operational triage.

## Operational Guidance

- Always send `Authorization` where the endpoint requires authentication.
- Always send `X-User-Id` for storage/retrieval scoped JMeter tests.
- Separate synchronous API latency from asynchronous job duration in reports.
- For high-volume process/index workloads, prefer queue-based execution and concurrency limits.
- Use the JMeter runbooks in `../jmeter-capacity-tests/runs/` for repeatable performance validation.
