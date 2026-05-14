# Edge Cases & Constraints Documentation

**Based on**: Phase_2_FE_AI_Merge actual implementation  
**Last Updated**: May 14, 2026

---

## Known Limitations & Edge Cases

### Document Processing

#### 1. Empty Documents
**Trigger**: User uploads empty PDF/DOCX file  
**Behavior**: Process completes with zero chunks  
**Handling**: Logged as warning, empty result returned (no error thrown)  
**Impact**: Retrieval results will be empty for this document

#### 2. Very Large Documents (>500 pages)
**Trigger**: Processing PDF > 500 pages  
**Behavior**: Memory usage increases exponentially, may hit GPU/CPU limits  
**Mitigation**: Document chunking reduces memory footprint but doesn't fully eliminate issue  
**Recommended**: Split large documents into smaller parts before processing

#### 3. Scanned PDFs with Low Quality
**Trigger**: PDF with very low-quality scans (< 100 DPI)  
**Behavior**: OCR accuracy drops below 50%  
**Current Handling**: No automatic quality check or rejection  
**Recommendation**: User should rescan at 300+ DPI for best results

#### 4. Corrupted Files
**Trigger**: Partially downloaded or corrupted file uploads  
**Behavior**: Docling/PDF reader throws exception  
**Current Handling**: Exception caught, gracefully skipped  
**Impact**: Document not indexed, warning logged

#### 5. Non-UTF8 Encoded Text
**Trigger**: DOCX/Office documents with non-UTF8 text encoding  
**Behavior**: UnicodeDecodeError during text extraction  
**Handling**: Catch exception, process with partial text  
**Impact**: Some characters lost, but document still indexed

#### 6. Mixed Language Documents
**Trigger**: Document with text in multiple languages (e.g., English + Vietnamese + Chinese)  
**Current**: Whisper ASR/OCR may struggle with language mixing  
**Recommendation**: Set OCR/ASR language explicitly in configuration

---

### Retrieval & Search

#### 1. Empty Query
**Trigger**: User submits empty query string  
**Handling**: Input validation catches empty query  
**Response**: 400 Bad Request with "query required" error

#### 2. Extremely Long Query (>1000 chars)
**Trigger**: Query exceeds 1000 character limit  
**Handling**: Input validation limits to 1000 chars  
**Impact**: Query truncated silently

#### 3. Special Characters in Query
**Trigger**: Query with regex special chars (*, +, ?, $, ^, etc.)  
**BM25 Handling**: Treated as literal characters (safe)  
**Dense Embedding Handling**: Passed to model as-is (model handles it)  
**Impact**: Minimal, both methods handle special chars gracefully

#### 4. Queries in Unsupported Languages
**Trigger**: Query in language not in document corpus  
**Behavior**: Dense embedding returns low-confidence matches  
**BM25**: Returns exact character matches only  
**Current**: No language validation or mismatch detection

#### 5. Empty Index
**Trigger**: Search executed before any documents indexed  
**Behavior**: Empty results returned (not an error)  
**Response**: HTTP 200 with empty results array

#### 6. Very High top_k (100)
**Trigger**: User requests top_k=100 from small corpus (10 docs)  
**Behavior**: Return all 10 docs, pad with zeros if needed  
**Impact**: Performance OK, dense retrieval slower with high k

---

### Model & Inference Limits

#### 1. GPU Memory Exhaustion
**Trigger**: Large batch processing on low-VRAM GPU (< 2GB)  
**Current Handling**: torch.cuda.empty_cache() called periodically  
**Preemptive**: Disable torch.compile, reduce batch size on detect  
**Fallback**: CPU inference as last resort (5x slower)

#### 2. OOM on Very Long Context
**Trigger**: Passing 100+ retrieved chunks to LLM for generation  
**Behavior**: Token count may exceed model context window  
**Current**: No context truncation implemented  
**Workaround**: Reduce top_k or max_tokens in generation

#### 3. Model Loading Timeout
**Trigger**: Model download interrupted or extremely slow network  
**Behavior**: Download hangs, eventually times out (default 300s)  
**Current**: No retry logic, task fails  
**Recommendation**: Increase timeout or pre-download models

#### 4. Quantization Compatibility
**Trigger**: Loading 8-bit quantized model on system without BitsAndBytes  
**Behavior**: ImportError or compatibility issue  
**Fix**: Install bitsandbytes or disable quantization  
**Fallback**: Use FP32 models (more VRAM required)

#### 5. Whisper Language Detection Failure
**Trigger**: Audio with heavy background noise or multiple languages  
**Behavior**: Language auto-detected incorrectly  
**Impact**: Transcription quality degrades significantly  
**Fix**: Explicitly set language parameter in config

---

### Database & Storage

#### 1. Qdrant Connection Timeout
**Trigger**: Qdrant service slow or unreachable  
**Behavior**: Connection hangs for 30 seconds, then fails  
**Error**: Propagated as 503 Service Unavailable  
**Recovery**: User must restart Qdrant or check network

#### 2. Collection Does Not Exist
**Trigger**: Index operation before collections created  
**Behavior**: Qdrant API returns collection_not_found error  
**Handling**: Index creation fails with clear error message  
**Fix**: Create collections explicitly or use auto-create flag

#### 3. Payload Filter Mismatch
**Trigger**: User_id filter doesn't match indexed payloads  
**Behavior**: Query returns empty results (correctly isolated)  
**Impact**: No security issue, expected isolation behavior

#### 4. S3 Upload Timeout
**Trigger**: Large file (>500MB) uploaded over slow connection  
**Behavior**: Upload times out after 15 minutes  
**Current**: No multipart upload or resume support  
**Recommendation**: Break into smaller files or increase timeout

#### 5. DynamoDB Throttling
**Trigger**: Chat history writes exceed provisioned throughput  
**Behavior**: Exponential backoff retry (up to 3 attempts)  
**If Exhausted**: Write fails, user sees error  
**Solution**: Increase DynamoDB provisioned capacity

---

### Concurrency & Performance

#### 1. Race Condition on Concurrent Index Updates
**Trigger**: Two simultaneous document processing for same file  
**Current**: No file-level locking implemented  
**Behavior**: Undefined - may create duplicate chunks or conflicting metadata  
**Recommended Fix**: Add file-level locking with unique IDs

#### 2. Cache Invalidation Delay
**Trigger**: Document reprocessed without changing ID/hash  
**Behavior**: Cached results returned even though content changed  
**TTL**: 24 hours (cache only expires after)  
**Workaround**: Manual cache clear or force flag in processing

#### 3. Memory Leak in Long-Running Process
**Trigger**: Server running for weeks without restart  
**Behavior**: Memory usage gradually increases  
**Root**: Loaded models not garbage collected  
**Current Mitigation**: Periodic `torch.cuda.empty_cache()`  
**Fix**: Implement periodic model reload or memory cleanup

#### 4. Dense Retrieval Slowdown at Scale
**Trigger**: Corpus grows to 100K+ documents  
**Behavior**: Embedding lookup FAISS performance degrades  
**Current**: Using CPU FAISS (not GPU-accelerated)  
**Option**: Switch to GPU FAISS or Qdrant-only retrieval

---

### Integration Points

#### 1. OpenAI API Timeout
**Trigger**: OpenAI API slow or overloaded  
**Behavior**: Request times out after 30s  
**Current Handling**: Exception caught, user sees error  
**Retry Logic**: None (user must retry)

#### 2. Bedrock Throttling (Rate Limit 429)
**Trigger**: > 10 concurrent requests to Bedrock  
**Behavior**: 429 Too Many Requests error  
**Current**: Returned to user with "retry in 60s" message  
**Future**: Implement request queuing or circuit breaker

#### 3. SageMaker Endpoint Timeout
**Trigger**: SageMaker endpoint unhealthy or overloaded  
**Behavior**: Request times out after 7 minutes  
**Fallback**: Local inference attempted (slow)  
**Log**: Error logged but not escalated

#### 4. Firebase Auth Token Expiry
**Trigger**: User session lasts > 1 hour  
**Behavior**: Token expires, user must re-authenticate  
**Current**: No automatic token refresh  
**Fix**: Implement refresh token logic

---

## Constraint Categories

### Temporal Constraints
- **Processing**: <2 min for standard 10MB doc (standard mode), <30s (fast mode)
- **Retrieval**: <1s for text, <2s for images
- **Generation**: <10s typical, can exceed with long context
- **Cache expiry**: 24 hours

### Capacity Constraints
- **Max documents**: 10,000+ supported
- **Max concurrent users**: 10+ (depends on infrastructure)
- **Max query length**: 1,000 characters
- **Max top_k**: 100 results
- **Max images per result**: 20

### Resource Constraints
- **GPU memory**: 2GB minimum (with quantization)
- **CPU memory**: 16GB minimum recommended
- **Disk space**: 50GB for installation, models, and cache
- **Network**: Stable internet required for cloud services

### Data Constraints
- **Document formats**: PDF, DOCX, XLSX, PPTX, TXT, CSV, HTML
- **Image formats**: JPG, PNG, BMP, GIF, TIFF
- **Audio formats**: MP4, MOV, AVI (via FFmpeg)
- **Text encoding**: UTF-8 preferred (non-UTF8 handled gracefully)

---

## Handling Strategy by Category

### Critical Failures (Stop Processing)
- File not found
- Corrupted input document
- Out of disk space
- Database connection lost permanently
- **Action**: Raise exception, return 400/500 error

### Degraded Mode (Continue with Reduced Capability)
- Model loading failed → disable that modality
- Qdrant offline → return cached results or text-only
- GPU OOM → switch to CPU inference
- Image retrieval failed → text-only results
- **Action**: Log warning, continue with fallback

### Transient Failures (Retry)
- Network timeout
- API rate limit (429)
- Temporary OOM
- **Action**: Retry with backoff, then fallback if persistent

---

## Testing Edge Cases

### Recommended Test Cases
```python
# Empty document
test_pdf = create_empty_pdf("test.pdf")
result = processor.process(test_pdf)
assert len(result.chunks) == 0

# Very long query
long_query = "a" * 2000
response = client.search(long_query)
assert response.status_code == 400  # Should be truncated/rejected

# Empty index search
response = client.search("test query")
assert response["results"]["text"] == []

# Concurrent uploads
futures = [upload(doc) for doc in documents]
results = [f.result() for f in futures]
assert all(r.success for r in results)

# GPU memory exhaustion
with patch('torch.cuda.empty_cache'):
    result = processor.process(large_doc)
    # Should fallback to CPU
    assert result.used_fallback == True
```

---

**Generated**: May 14, 2026  
**Status**: Complete constraint documentation  
**Next**: See TROUBLESHOOTING_GUIDE.md for recovery procedures
