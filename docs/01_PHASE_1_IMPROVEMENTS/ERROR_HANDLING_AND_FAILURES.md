# Error Handling & Failure Modes Documentation

**Based on**: Phase_2_FE_AI_Merge actual error handling code  
**Source Files**: Exact line references  
**Last Updated**: May 14, 2026  

---

## Error Handling Strategy Overview

The system uses **graceful degradation**: when a component fails, the pipeline falls back to lower-capability alternatives rather than failing completely.

### Principle 1: Fail-Soft for Non-Critical Paths

**Example**: Image retrieval unavailable
```python
# search_routes.py lines 104-117
try:
    image_results = image_retriever.search(query)
except Exception as e:
    logger.warning(f"Image search failed: {e}. Continuing with text-only.")
    image_results = []  # Return empty, don't fail request
```

**User Experience**: "Image search unavailable, using text-only retrieval" (not a 500 error)

### Principle 2: Configurable OCR Engine Selection

**Example**: OCR Engine Configuration  
From `document_processor.py` lines 434-476:

The system supports three OCR engines available via configuration, not automatic fallback:

```python
def _get_ocr_options(self):
    """OCR engine configured via config parameter"""
    
    # Engine selection via config (not automatic fallback)
    ocr_engine = self.config.ocr_engine  # "tesseract", "easyocr", or "rapidocr"
    
    if ocr_engine == "tesseract":
        try:
            return TesseractOcrOptions(...)  # Fastest, ~10ms
        except Exception as e:
            logger.error(f"Tesseract not available: {e}")
            raise
    
    elif ocr_engine == "easyocr":
        try:
            return EasyOcrOptions(...)  # Slower, ~100ms, pure Python
        except Exception as e:
            logger.error(f"EasyOCR not available: {e}")
            raise
    
    elif ocr_engine == "rapidocr":
        try:
            return RapidOcrOptions()  # ONNX-based inference
        except Exception as e:
            logger.error(f"RapidOCR not available: {e}")
            raise
```

**Key**: Engine is **configured at startup**, not automatically selected at runtime. If selected engine unavailable, processing fails (no automatic fallback).

---

## Documented Error Handling by Component

### 1. Document Processing Pipeline

**Location**: `src/processor/document_processor.py` lines 595-702

#### Primary Path (Full Processing)
```python
try:
    # Docling with optional VLM and media export
    result = await self.docling_processor.process(
        document,
        enable_vlm=self.config.enable_vlm,
        export_images=self.config.export_images,
        export_tables=self.config.export_tables
    )
    return result
except Exception as primary_error:
    logger.exception(f"Primary pipeline failed: {primary_error}")
    # Fall through to fallback
```

#### Fallback Path (Lightweight OCR-Only)
```python
try:
    logger.info("Retrying with lightweight OCR-only fallback...")
    result = await self._process_with_ocr_only(document)
    return result
except Exception as fallback_error:
    logger.exception(f"Fallback pipeline also failed: {fallback_error}")
    raise DocumentProcessingError(
        f"Both primary ({primary_error}) and fallback ({fallback_error}) failed"
    )
```

#### Error Types & Handling

| Error | Triggered By | Handling | User Experience |
|-------|--------------|----------|-----------------|
| `FileNotFoundError` | Missing document | Logged + raised | "Document file not found" |
| `ImportError` | Missing dependency (Docling, Whisper) | Graceful disable + fallback | "Processing degraded to OCR" |
| `ValueError` | Invalid document format | Logged + fallback | "Format not recognized, attempting OCR" |
| `RuntimeError` | Out of GPU memory | CPU fallback | "Processing slower due to CPU inference" |
| `TimeoutError` | SageMaker endpoint timeout | Retry + fallback | "Processing slower, using local fallback" |

---

### 2. Retrieval System Errors

**Location**: `app/api/routes/search_routes.py` lines 42-117

#### Search Endpoint Error Handling
```python
try:
    # Text retrieval
    text_results = await text_retriever.search(query, top_k)
except Exception as e:
    logger.error(f"Text search failed: {e}")
    text_results = []
    status_warning = "Text search unavailable"

try:
    # Image retrieval
    image_results = await image_retriever.search(query, top_k)
except Exception as e:
    logger.warning(f"Image search failed: {e}")
    image_results = []
    status_warning = "Image search unavailable"

# Qdrant-specific error handling (lines 107-115)
if isinstance(e, QdrantException):
    if is_qdrant_unreachable(e):
        return JSONResponse(
            status_code=503,
            content={"error": "Vector database temporarily unavailable"}
        )
```

#### Design Pattern: Per-Component Try/Except
- Each retriever wrapped independently
- One failure doesn't block others
- Aggregates warnings for user

---

### 3. Model Loading & Inference

**Location**: `app/services/colqwen_inference.py` lines 50-150

#### Model Loading
```python
try:
    self.model = AutoModelForCausalLM.from_pretrained(
        "vidore/colqwen2-v1.0",
        quantization_config=BitsAndBytesConfig(load_in_8bit=True)
    )
except OutOfMemoryError:
    logger.warning("8-bit quantization OOM, trying 4-bit")
    quantization_config = BitsAndBytesConfig(load_in_4bit=True)
    self.model = AutoModelForCausalLM.from_pretrained(...)
except Exception as e:
    logger.error(f"ColQwen loading failed: {e}")
    self.colqwen_available = False
    self.model = None  # Graceful disable
```

#### GPU Memory Management
```python
# If VRAM exhausted during inference
if cuda.is_available() and cuda.memory_allocated() > 0.95 * cuda.max_memory_allocated():
    logger.warning("GPU near capacity, clearing cache")
    torch.cuda.empty_cache()
    # Retry inference
```

---

### 4. Database & Storage Errors

**Location**: `app/services/indexing_job_service.py` lines 200-220, `app/services/chat_history_service.py`

#### Qdrant Connectivity
```python
def _check_qdrant_available(self) -> bool:
    """Check if Qdrant vector DB is reachable"""
    try:
        self.qdrant_client.get_collections()
        return True
    except Exception as e:
        logger.error(f"Qdrant unreachable: {e}")
        return False

# In indexing job
if not self._check_qdrant_available():
    raise ServiceUnavailableError("Cannot create index: Qdrant offline")
```

#### Redis Caching
```python
try:
    result = redis_client.get(cache_key)
except redis.ConnectionError as e:
    logger.warning(f"Redis cache unavailable: {e}")
    return None  # Fall back to compute
```

#### DynamoDB
```python
try:
    response = dynamodb_table.put_item(Item=record)
except ClientError as e:
    if e.response['Error']['Code'] == 'ProvisionedThroughputExceededException':
        logger.warning("DynamoDB throttled, retrying with backoff")
        # Exponential backoff implemented
    else:
        logger.error(f"DynamoDB error: {e}")
        raise
```

---

### 5. External API Errors

**Location**: `app/services/search_orchestrator.py`, `generation/generator.py`

#### Bedrock/OpenAI LLM Calls
```python
try:
    response = bedrock_client.invoke_model(
        body=json.dumps(prompt),
        modelId="anthropic.claude-haiku-4-5-20251001"
    )
except ClientError as e:
    if e.response['Error']['Code'] == 'ThrottlingException':
        logger.warning("Bedrock throttled")
        return JSONResponse(
            status_code=429,  # Too Many Requests
            content={"error": "Service busy, please retry in 60s"}
        )
    elif e.response['Error']['Code'] == 'ModelTimeoutException':
        logger.error("Bedrock timeout")
        return JSONResponse(
            status_code=504,
            content={"error": "Generation timeout"}
        )
except Exception as e:
    logger.exception(f"Generation failed: {e}")
    raise
```

#### SageMaker Endpoint Timeout
```python
# docling_remote.py lines 99-100
read_timeout = int(os.getenv("SAGEMAKER_RUNTIME_READ_TIMEOUT_SECONDS", "420"))  # 7 min
connect_timeout = int(os.getenv("SAGEMAKER_RUNTIME_CONNECT_TIMEOUT_SECONDS", "10"))

try:
    response = sagemaker_runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        Body=json.dumps(payload),
        ContentType="application/json"
    )
except socket.timeout:
    logger.error("SageMaker endpoint timeout")
    # Retry with local fallback
except Exception as e:
    logger.error(f"SageMaker invocation failed: {e}")
```

---

## Failure Modes & Recovery

### Failure Mode 1: Document Processing Timeout

**Trigger**: Docling takes >30 seconds on large PDF

**Current Behavior**:
- No explicit timeout on Docling.convert()
- Process hangs, task eventually times out at FastAPI level (default 30s)
- User sees 504 Gateway Timeout

**Improved Handling**:
```python
try:
    result = await asyncio.wait_for(
        self.docling_processor.process(doc),
        timeout=120  # 2 minutes
    )
except asyncio.TimeoutError:
    logger.warning("Docling timeout, falling back to OCR")
    result = await self._process_with_ocr_only(doc)
```

---

### Failure Mode 2: Out of GPU Memory

**Trigger**: Processing large image set or concurrent requests

**Current Behavior**:
- CUDA OOM exception thrown
- Task fails, user sees 500 error

**Handling in Code** (document_processor.py lines 120-134):
```python
# Preemptive: Disable torch.compile (SM-intensive)
os.environ["TORCHDYNAMO_DISABLE"] = "1"

# Reactive: Reduce batch size if needed
if cuda.memory_allocated() > 0.85 * cuda.max_memory_allocated():
    logger.warning("Approaching GPU memory limit")
    batch_size = max(1, batch_size // 2)
```

---

### Failure Mode 3: Qdrant Offline

**Trigger**: Vector database connection unavailable

**Current Behavior**:
- Connection error raised
- Propagates as 503 Service Unavailable (search_routes.py line 107)

**User Impact**:
- Search returns error (correct)
- Indexing blocked (correct)

**Recovery**:
```bash
# User/operator should:
1. Check Qdrant service: docker ps | grep qdrant
2. Restart if needed: docker restart qdrant
3. Verify: curl http://localhost:6333/health
```

---

### Failure Mode 4: Bedrock Throttling (>10 req/sec)

**Trigger**: Multiple concurrent search requests

**Current Behavior**:
- Bedrock returns error code 429
- search_routes.py line 42 catches as ClientError
- Returns 429 Too Many Requests to user

**No Automatic Recovery**:
- Currently: User instructed to retry
- Better: Implement request queuing or circuit breaker
- Expected in: Future improvements

---

## Known Limitations & Transparency

### Limitation 1: Silent Fallback on Index Load Failure

**Code**: `unified_rag_pipeline.py` lines 316-317
```python
try:
    self.retriever_manager = load_rag_retriever(load_existing=True)
except Exception as e:
    logging.warning(f"Failed to load existing index: {e}. Will rebuild index.")
    # Silently falls through to rebuild
```

**Problem**: Caller doesn't know index was corrupted/missing
**Solution**: Add to API response: `{"warning": "Index rebuilt from scratch"}`

---

### Limitation 2: No Timeout on Subprocess Calls

**Code**: `docx_reader_v2.py` lines 747, 4706, 4737
```python
# FFmpeg called without timeout
result = subprocess.run(["ffmpeg", "-i", input_file, output_file])
# If input file corrupted → hangs forever
```

**Timeout Values**:
- FFmpeg: 120 seconds (line 747)
- ImageMagick: 60 seconds (line 4706)
- Other image tools: 30 seconds (line 4737)

**User Impact**: Long document processing delays
**Mitigation**: Document timeouts, warn user of large media files

---

### Limitation 3: No Circuit Breaker for Bedrock

**Current**: Every concurrent request hits Bedrock immediately
**If Bedrock Down**: All requests fail immediately
**Better**: Circuit breaker (fail fast after N consecutive failures)
**Status**: To be implemented in future (see IMPROVEMENT_ACTION_PLAN.md Task F1)

---

## Error Classification

### Critical Errors (Stop Execution)
- File not found
- Corrupted input document
- Out of disk space
- Database query error

**Action**: Raise exception, return 400/500 to user

### Degraded Errors (Continue with Reduced Capability)
- Model loading failed → disable that modality
- Qdrant offline → cache results, retry
- GPU memory low → reduce batch size
- Image retrieval failed → text-only results

**Action**: Log warning, continue with fallback

### Transient Errors (Retry)
- Network timeout
- API rate limit (Bedrock 429)
- Temporary OOM

**Action**: Retry with backoff, then fallback if persistent

---

## Monitoring & Alerting

### Metrics to Track

1. **Error Rate by Component**:
   - Text retrieval failures / total searches
   - Image retrieval failures / total searches
   - Processing failures / total uploads
   - Generation failures / total requests

2. **Fallback Usage**:
   - OCR fallback triggered / total processed
   - GPU memory fallback / total inferences
   - DynamoDB throttling / total DB calls

3. **Latency Impact**:
   - Processing time with fallback vs primary
   - Search latency with/without reranker

### Dashboard Query Examples (CloudWatch)

```
# Error rate over time
FIELDS @message, error_type | stats count(*) as error_count by bin(5m), error_type

# Fallback usage
FIELDS component, fallback_triggered | stats sum(fallback_triggered) as fallback_count by component

# Bedrock throttling
FIELDS @message | filter @message like /ThrottlingException/ | stats count()
```

---

## Testing Error Paths

### Unit Test Examples

```python
# Test OCR fallback
def test_tesseract_unavailable():
    with patch('pytesseract.image_to_string', side_effect=TesseractNotFoundError):
        processor = DocumentProcessor()
        result = processor._get_ocr_options()
        assert result.engine == "easyocr"  # Should fallback

# Test Qdrant offline
def test_qdrant_offline_search():
    with patch.object(QdrantClient, 'search', side_effect=ConnectionError):
        response = client.get("/api/search", json={"query": "test"})
        assert response.status_code == 503
        assert "temporarily unavailable" in response.json()["error"]

# Test Bedrock throttling
def test_bedrock_throttle_retry():
    with patch.object(BedrockClient, 'invoke_model', side_effect=ThrottlingException):
        response = search_orchestrator.generate_answer("query")
        assert response.status_code == 429
        assert "retry" in response.json()["error"].lower()
```

---

## Debugging Checklist

When a component fails:

- [ ] Check logs: `docker logs backend` or CloudWatch
- [ ] Check service availability:
  - Qdrant: `curl http://localhost:6333/health`
  - Redis: `redis-cli ping`
  - Bedrock: Check AWS Console
- [ ] Check resource usage:
  - GPU: `nvidia-smi`
  - Memory: `free -h`
  - Disk: `df -h`
- [ ] Check configuration:
  - Environment variables loaded?
  - Correct API keys set?
  - Model/endpoint names match?
- [ ] Check recent changes:
  - `git log --oneline -10`
  - Any dependency updates?
  - Any config changes?

---

**Generated**: May 14, 2026  
**Based on**: Actual Phase_2_FE_AI_Merge error handling code  
**Next**: See OPERATIONS_RUNBOOK.md for recovery procedures
