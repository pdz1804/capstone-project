# Search API Documentation

**Base URL**: `http://localhost:8000` (local) or deployment URL  
**Auth**: User ID required via `X-User-Id` header or query parameter  
**Content-Type**: `application/json` for all POST requests

---

## Main Endpoints

### POST /api/search - Multimodal Search & Generation

Execute a unified search query combining text and image retrieval with optional LLM generation.

**Request**:
```json
{
  "query": "explain machine learning algorithms",
  "top_k": 10,
  "retriever_type": "hybrid",
  "search_scope": "both",
  "mode": "retrieval_generation",
  "include_images": true,
  "images_for_generation": 5,
  "generation_model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
  "skip_reranker": true
}
```

**Request Fields**:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string (required) | — | Natural language search query (min 1 character) |
| `top_k` | integer | 10 | Number of results per retriever (1-100) |
| `retriever_type` | string | "hybrid" | One of: `bm25`, `dense`, `hybrid` |
| `search_scope` | string | "both" | Index to search: `text`, `image`, or `both` |
| `mode` | string | "retrieval_generation" | `retrieval_only` or `retrieval_generation` |
| `include_images` | boolean | true | Include image results in response |
| `images_for_generation` | integer | 5 | Max images to pass to LLM (0-20) |
| `generation_model` | string | None | Override configured LLM model ID |
| `skip_reranker` | boolean | true | Deprecated (always true for performance) |

**Response** (200 OK):
```json
{
  "query": "explain machine learning algorithms",
  "search_scope": "both",
  "mode": "retrieval_generation",
  "results": {
    "text": [
      {
        "rank": 1,
        "source": "/documents/chapter_5/section_2.md",
        "content": "Machine learning is a subset of artificial intelligence...",
        "metadata": {
          "document_id": "doc_123",
          "page": 42,
          "chunk_index": 5
        },
        "score": 0.856,
        "retriever": "hybrid"
      }
    ],
    "images": [
      {
        "rank": 1,
        "source": "s3://bucket/extracted/doc_123/page_42_img_1.png",
        "caption": "Decision tree visualization",
        "document_id": "doc_123",
        "page": 42,
        "preview_url": "/api/search/image-preview?storage_uri=s3%3A%2F%2F...",
        "score": 0.742,
        "retriever": "colqwen"
      }
    ]
  },
  "generation": {
    "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "answer": "Machine learning algorithms fall into three main categories...",
    "confidence": 0.92
  },
  "telemetry": {
    "steps_ms": {
      "retrieval_text": 45,
      "retrieval_image": 52,
      "retrieval_total": 97,
      "generation": 312,
      "total": 409
    },
    "tokens": {
      "input_total": 1250,
      "output_total": 342
    },
    "cache": {
      "retrieval": {
        "hit": false
      }
    }
  }
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `results.text[*]` | array | Text chunks ranked by relevance score |
| `results.text[*].source` | string | File path or chunk ID |
| `results.text[*].score` | float | Relevance score (0.0-1.0) |
| `results.text[*].retriever` | string | Which retriever returned: `bm25`, `dense`, `hybrid` |
| `results.images[*]` | array | Image results with preview URLs |
| `generation.answer` | string | LLM-generated answer from top results |
| `generation.confidence` | float | Model confidence (0.0-1.0) |
| `telemetry.steps_ms` | object | Per-component latency in milliseconds |
| `telemetry.tokens` | object | LLM token usage for billing |
| `telemetry.cache.retrieval.hit` | boolean | Whether result was from cache |

**Error Responses**:

| Status | Condition | Detail |
|--------|-----------|--------|
| 400 | Invalid query or validation error | Missing required field or value out of bounds |
| 503 | Qdrant vector DB offline | "Cannot connect to Qdrant. Check logs." |
| 429 | Bedrock rate limit exceeded | "Service busy, please retry in 60s" |
| 500 | Unexpected error | Server error (check application logs) |

**Examples**:

cURL:
```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -H "X-User-Id: user_123" \
  -d '{
    "query": "what is clustering?",
    "top_k": 5,
    "retriever_type": "hybrid"
  }'
```

Python:
```python
import requests

response = requests.post(
    "http://localhost:8000/api/search",
    json={
        "query": "what is clustering?",
        "top_k": 5,
        "retriever_type": "hybrid"
    },
    headers={"X-User-Id": "user_123"}
)
result = response.json()
for chunk in result["results"]["text"]:
    print(f"Score: {chunk['score']:.3f} - {chunk['content'][:100]}")
```

---

### GET /api/search/generation-models - List Available LLMs

Returns the list of available language models for generation based on current configuration.

**Query Parameters**: None (user_id required via header/query)

**Response** (200 OK):
```json
{
  "provider": "bedrock",
  "configured_model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
  "region": "us-east-1",
  "models": [
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "us.anthropic.claude-sonnet-4-6",
    "google.gemma-3-27b-it",
    "zai.glm-4.7-flash"
  ]
}
```

**Examples**:

cURL:
```bash
curl http://localhost:8000/api/search/generation-models \
  -H "X-User-Id: user_123"
```

Python:
```python
import requests

response = requests.get(
    "http://localhost:8000/api/search/generation-models",
    headers={"X-User-Id": "user_123"}
)
models = response.json()["models"]
print(f"Available models: {', '.join(models)}")
```

---

### GET /api/search/image-preview - Retrieve Image Preview

Fetch the actual image file or PDF page from indexed documents.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `storage_uri` | string | Conditional | S3 URI for image (e.g., `s3://bucket/path/image.png`) |
| `source_path` | string | Conditional | Local file path (fallback for local backend) |
| `page` | integer | No | 1-based page number for PDF sources (default: 1) |

**Response**: 

- **200 OK**: Binary image file with appropriate `Content-Type` header
  - PNG: `image/png`
  - JPG: `image/jpeg`
  - PDF rendered page: `image/png`

**Error Responses**:

| Status | Condition |
|--------|-----------|
| 400 | Invalid storage_uri format or missing both storage_uri and source_path |
| 404 | Image file not found in storage |
| 500 | Error processing PDF page |

**Examples**:

cURL (retrieve image):
```bash
curl "http://localhost:8000/api/search/image-preview?storage_uri=s3%3A%2F%2Fbucket%2Fpath%2Fimage.png" \
  -H "X-User-Id: user_123" \
  -o image.png
```

HTML (display in browser):
```html
<img src="http://localhost:8000/api/search/image-preview?storage_uri=s3%3A%2F%2Fbucket%2Fpath%2Fimage.png&user_id=user_123" />
```

---

## Health Check Endpoints

### GET /health - Basic Health Check

Simple liveness probe for load balancers and monitoring.

**Response** (200 OK):
```json
{
  "status": "healthy",
  "timestamp": "2026-05-14T10:30:45Z"
}
```

---

### GET /api/health - Detailed Health Check

Extended health check with component status.

**Response** (200 OK):
```json
{
  "status": "healthy",
  "components": {
    "qdrant_text": "healthy",
    "qdrant_image": "healthy",
    "cache": "healthy",
    "bedrock": "responsive"
  },
  "timestamp": "2026-05-14T10:30:45Z",
  "latency_ms": 145
}
```

---

## Retriever Types Explained

### BM25 (Keyword/Lexical Search)
- Uses Okapi BM25 algorithm for term matching
- Fast, no embedding computation required
- Good for technical terms and exact phrase matches
- Latency: ~45ms for 1000-doc corpus
- Use when: Documents contain specific terminology, fast response needed

### Dense (Semantic/Embedding Search)
- Uses Sentence-Transformers embeddings
- Captures semantic meaning beyond keywords
- Good for topic-based queries
- Latency: ~100ms (includes embedding lookup in FAISS)
- Use when: Semantic understanding needed, can tolerate slower response

### Hybrid (Reciprocal Rank Fusion)
- Combines BM25 + Dense retrieval
- Uses RRF algorithm for score fusion
- Expansion factor 130%: dense retriever returns 1.3*K results before fusion
- Min-max normalization for combining different score scales
- Latency: ~150ms (both retrievers + fusion)
- Use when: Best overall quality, semantic + keyword matching needed
- **Recommended for most use cases**

---

## Error Handling & Recovery

### Qdrant Offline (503 Service Unavailable)
**Error Message**: `"Cannot connect to Qdrant. Check service health."`

**Recovery Steps**:
1. Check Qdrant health: `curl http://localhost:6333/health`
2. Restart Qdrant service: `docker restart qdrant`
3. Verify collections exist: `curl http://localhost:6333/collections`
4. Retry search request

### Bedrock Throttling (429 Too Many Requests)
**Error Message**: `"Service busy, please retry in 60s"`

**Recovery Steps**:
1. Implement exponential backoff on client (1s, 2s, 4s, 8s max)
2. Batch requests to stay under rate limit (~10 req/sec)
3. Contact AWS support if limit insufficient

### Invalid Query (400 Bad Request)
**Error Message**: `"validation error for SearchRequest"`

**Common Issues**:
- Empty query: `"query": ""`
- top_k out of bounds: `"top_k": 101` (max 100)
- Invalid retriever_type: `"retriever_type": "invalid"`

### Unexpected Error (500 Internal Server Error)
**Recovery Steps**:
1. Check application logs: `docker logs backend`
2. Check resource usage: `nvidia-smi` (GPU), `free -h` (memory)
3. Check configuration: Verify environment variables, API keys
4. Contact support with request details and error timestamp

---

## Performance & Limits

### Rate Limits
- **Text Retrieval**: No hard limit per user (fair-use policy)
- **Image Retrieval**: No hard limit (bandwidth-limited)
- **LLM Generation**: Subject to model provider limits (Bedrock: ~10 req/sec)

### Request Size Limits
- **Query length**: Max 1000 characters
- **top_k**: Max 100 results
- **images_for_generation**: Max 20 images

### Latency Benchmarks
- **Text retrieval only**: 45-100ms (BM25-Dense)
- **Image retrieval only**: 50-150ms (ColQwen embedding)
- **Both + fusion**: 100-200ms
- **LLM generation**: 300-2000ms (depends on model & context length)
- **Total (search + gen)**: 400-2200ms

### Caching
- **Retrieval results**: Cached per (user, query) pair
- **Cache TTL**: 24 hours (configurable)
- **Cache hit latency**: <10ms

---

## Authentication

All endpoints require one of:

**Option 1: Header**
```bash
curl -H "X-User-Id: user_123" http://localhost:8000/api/search
```

**Option 2: Query Parameter**
```bash
curl "http://localhost:8000/api/search?user_id=user_123"
```

**Per-User Isolation**: Each user_id gets isolated document index, cache, and quota.

---

## Response Headers

All success responses include telemetry headers:

```
X-Usage-Feature: knowledge_explorer
X-Usage-Model-Id: us.anthropic.claude-haiku-4-5-20251001-v1:0
X-Usage-Token-In: 1250
X-Usage-Token-Out: 342
```

Use these for billing, monitoring, and model selection tracking.

---

## Common Workflows

### Single Question with Context
```python
# Retrieve documents, then generate answer with inline context
response = requests.post("http://localhost:8000/api/search", json={
    "query": "What is the capital of France?",
    "mode": "retrieval_generation",
    "top_k": 3
})
answer = response.json()["generation"]["answer"]
print(answer)
```

### Retrieval Only (No Generation)
```python
# Just get documents, process them yourself
response = requests.post("http://localhost:8000/api/search", json={
    "query": "solar energy applications",
    "mode": "retrieval_only",
    "search_scope": "text"
})
chunks = response.json()["results"]["text"]
for chunk in chunks:
    print(f"{chunk['score']:.2f}: {chunk['content']}")
```

### Image-Focused Search
```python
# Find images relevant to query
response = requests.post("http://localhost:8000/api/search", json={
    "query": "solar panel installation diagram",
    "search_scope": "image",
    "include_images": True,
    "mode": "retrieval_only"
})
images = response.json()["results"]["images"]
for img in images:
    print(f"Page {img['page']}: {img['caption']}")
```

### Model Comparison
```python
# Test multiple generation models
models = requests.get("http://localhost:8000/api/search/generation-models").json()["models"]
results = {}
for model in models[:3]:  # Test first 3 models
    resp = requests.post("http://localhost:8000/api/search", json={
        "query": "explain quantum computing",
        "generation_model": model
    })
    results[model] = resp.json()["generation"]["answer"]
```

---

**Generated**: May 14, 2026  
**API Version**: 1.0  
**Next**: See ERROR_HANDLING_AND_FAILURES.md for detailed error recovery procedures
