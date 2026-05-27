# Troubleshooting Guide (G3)

**Based on**: Phase_2_FE_AI_Merge actual implementation  
**Last Updated**: May 14, 2026  
**Scope**: Extended troubleshooting beyond OPERATIONS_RUNBOOK.md

---

## 1. Document Processing Failures

### 1.1 "PDF Extraction Failed" Error

**Symptoms**:
- Error: `PDFException: Failed to extract pages from document`
- Document appears corrupted or uses unsupported PDF features
- OCR results are empty even for text-based PDFs

**Root Causes**:
1. PDF uses non-standard encoding (PDF/X, PDF/A variants)
2. Password-protected PDFs without password provided
3. PDF > 500 pages causing memory exhaustion
4. Corrupted PDF (incomplete download, transmission error)

**Debug Steps**:
```bash
# Check PDF structure
pdfinfo <file.pdf>  # Inspect PDF metadata

# Verify file integrity
md5sum <file.pdf>   # Compare with original

# Test with smaller chunk (first 10 pages)
# Modify ProcessingConfig.chunk_size = 10 in document_processor.py:85
```

**Resolution**:
- Re-download or rescan the PDF at original source
- Split large PDFs into smaller parts (< 500 pages)
- Verify PDF is not password-protected before upload
- For scanned PDFs, ensure quality is >= 150 DPI

**Implementation Reference**: document_processor.py:234-256 (error handling in `_extract_text_from_pdf`)

---

### 1.2 OCR Accuracy < 50%

**Symptoms**:
- OCR text contains gibberish, incorrect characters
- Confidence scores very low (< 0.3)
- Language-specific characters corrupted (Vietnamese diacritics lost)

**Root Causes**:
1. Scanned PDF quality too low (< 100 DPI)
2. OCR engine not configured for document language
3. Heavy background/noise in scans
4. Mixed language document (English + Vietnamese + Chinese)

**Debug Steps**:
```python
# Check OCR confidence scores
from document_processor import DocumentProcessor
processor = DocumentProcessor()
metadata = processor.process_document(file_path)
# Inspect metadata.ocr_confidence for each chunk

# Verify OCR engine in config
print(processor.config.ocr_engine)  # Should be "tesseract" or "easyocr"
```

**Resolution**:
- **For low-quality scans**: Rescan at 300+ DPI or use PDF enhancement tool (Ghostscript)
- **For language issues**: Set `ProcessingConfig.ocr_language = "vie+eng"` for Vietnamese+English mix
- **For background noise**: Use ImageMagick preprocess:
  ```bash
  convert input.pdf -quality 95 -density 300 output.pdf
  ```

**Implementation Reference**: document_processor.py:434-476 (`_get_ocr_options`)

---

### 1.3 XLSX/Excel Processing Loses Table Structure

**Symptoms**:
- Merged cells flattened into individual cells
- Column headers not preserved in semantic context
- Row groupings lost during chunking

**Root Causes**:
1. Using standard Excel library (openpyxl) instead of custom OOXML parser
2. Merged cell relationships not tracked
3. Chunking algorithm doesn't understand table hierarchy

**Debug Steps**:
```python
from xlsx_reader_v2 import XLSXReader
reader = XLSXReader(file_path)
# Check if merged cells detected
print(reader.merged_cells_map)

# Verify chunking preserves structure
chunks = reader.generate_chunks()
for chunk in chunks:
    print(chunk.text[:100])  # First 100 chars should show hierarchy
```

**Resolution**:
- Ensure you're using `xlsx_reader_v2.py` (custom OOXML parser) not openpyxl
- Verify `ProcessingConfig.preserve_table_structure = True`
- Check that merged cell information is in metadata:
  ```python
  metadata = processor.process_document(excel_file)
  for chunk in metadata.chunks:
      assert "merged_cells" in chunk.metadata  # Should be present
  ```

**Implementation Reference**: xlsx_reader_v2.py (lines not specified in original - custom parsing logic)

---

### 1.4 Video/Audio Processing Hangs at Frame Extraction

**Symptoms**:
- Process stuck at "Extracting frames..." stage for 10+ minutes
- FFmpeg process running at 100% CPU but no progress
- Memory usage gradually increasing

**Root Causes**:
1. FFmpeg timeout (default 120s) too short for large videos
2. Frame_interval too small (trying to extract 1000+ frames)
3. Video codec not supported, FFmpeg retrying endlessly
4. GPU memory full, CUDA operations blocking

**Debug Steps**:
```bash
# Check FFmpeg version and codecs
ffmpeg -codecs | grep h264

# Test video directly
ffmpeg -i video.mp4 -f null -  # Should complete in seconds

# Monitor resource usage
top -p $(pgrep -f ffmpeg)  # Check CPU/memory of FFmpeg process
```

**Resolution**:
- **Increase timeout**: Modify `MediaProcessor.frame_extraction_timeout = 300` (5 minutes)
- **Reduce frame extraction**: Set `frame_interval = 5` (extract every 5 seconds instead of 1 second)
- **Verify codec support**: Re-encode video in H.264:
  ```bash
  ffmpeg -i input.mp4 -c:v libx264 -c:a aac output.mp4
  ```
- **Free GPU memory**: Restart document processing service or manually clear cache

**Implementation Reference**: media_processor_enhanced.py:120-180 (FFmpeg timeout, frame_interval configuration)

---

## 2. Retrieval Quality Issues

### 2.1 Search Returns Irrelevant Results

**Symptoms**:
- Top results have low semantic relevance despite high scores
- Text results good, but image results completely unrelated
- Same query gives different results on different days

**Root Causes**:
1. Hybrid retrieval weight imbalance (BM25 vs Dense mixing)
2. Stale embeddings (document re-indexed but embeddings not updated)
3. Collection payload filters blocking correct results
4. Cache returning old results (24-hour TTL)

**Debug Steps**:
```python
from rag_retrievers import SimpleHybridRetriever
from search_orchestrator import SearchOrchestrator

# Check individual retriever scores
bm25_results = retriever.bm25.search(query, top_k=10)
dense_results = retriever.dense.search(query, top_k=10)
hybrid_results = retriever.search(query, top_k=10)

# Compare scores - should be balanced
print("BM25 top score:", bm25_results[0].score)  # Usually [0, ∞)
print("Dense top score:", dense_results[0].score)  # Usually [0, 1]
print("Hybrid top score:", hybrid_results[0].score)  # After RRF fusion

# Verify user isolation filter working
results_with_filter = retriever.search(query, filters={"user_id": "user123"})
assert all(r.metadata.user_id == "user123" for r in results_with_filter)
```

**Resolution**:
- **For weight imbalance**: Check RRF constant in SimpleHybridRetriever.search() (line 380-400) - should be 60, empirically tuned
- **For stale embeddings**: Re-index document with `force_reindex=True` flag
- **For filter issues**: Verify payload schema matches indexed payloads:
  ```python
  # In Qdrant, list points and check their payloads
  points = qdrant_client.retrieve(collection_name="text_chunks", ids=[1, 2, 3])
  print(points[0].payload)  # Should contain 'user_id', 'document_id', etc.
  ```
- **For cache staleness**: Clear cache or wait 24 hours for TTL expiry

**Implementation Reference**: rag_retrievers.py:325-456 (SimpleHybridRetriever, RRF fusion)

---

### 2.2 "Dense Embedding Model Failed to Load"

**Symptoms**:
- Error: `RuntimeError: CUDA out of memory` or `ImportError: No module named 'sentence_transformers'`
- Dense retrieval unavailable, falling back to BM25-only
- Embedding inference takes 30+ seconds per query

**Root Causes**:
1. VRAM insufficient for embedding model (ColPali requires 2GB+)
2. Model not downloaded (first-time use)
3. Transformers/Torch version mismatch
4. GPU driver incompatible with CUDA 12.8

**Debug Steps**:
```python
import torch
import sentence_transformers

# Check CUDA availability
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0))
print(torch.cuda.get_device_properties(0))

# Check VRAM available
print(torch.cuda.memory_allocated())  # Current usage
print(torch.cuda.get_device_properties(0).total_memory)  # Total

# Test model loading
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
embeddings = model.encode(["test"])
print("Model loaded successfully")
```

**Resolution**:
- **For VRAM issues**: 
  - Reduce batch size: Modify DenseRetriever.batch_size = 16 (from 32)
  - Enable 8-bit quantization: Set `use_quantization = True` in config
  - Switch to CPU-only mode: `config.device = "cpu"` (5x slower)
- **For model download**: Model auto-downloads on first use from HuggingFace; ensure internet connection
- **For version mismatch**:
  ```bash
  pip install --upgrade torch sentence-transformers transformers
  # Or use specific versions from requirements.txt
  ```
- **For GPU driver**: Verify CUDA 12.8 compatibility and update drivers

**Implementation Reference**: document_processor.py:120-134 (GPU optimization, torch settings)

---

### 2.3 Image Retrieval Returns No Results

**Symptoms**:
- Text retrieval works fine, but image search returns empty results
- Error: `No results found for image query` or `ColQwen inference failed`
- Images indexed but not searchable

**Root Causes**:
1. ColQwen model failed to initialize (GPU memory, CUDA error)
2. Image collection not created in Qdrant
3. Images not processed into embeddings during document indexing
4. Image metadata missing from chunks (modality_type not set)

**Debug Steps**:
```python
from processor.media_processor_enhanced import MediaProcessor
from qdrant_client import QdrantClient

# Check if images extracted
media_proc = MediaProcessor()
images = media_proc.extract_images(document_path)
print(f"Extracted {len(images)} images")

# Verify image collection exists in Qdrant
client = QdrantClient("localhost", port=6333)
collections = client.get_collections()
image_collection_exists = any(c.name == "image_chunks" for c in collections.collections)
print(f"Image collection exists: {image_collection_exists}")

# Check if image embeddings generated
from qdrant_client.models import Filter, FieldCondition, MatchValue
filter = Filter(
    must=[FieldCondition(key="modality_type", match=MatchValue(value="image"))]
)
image_count = client.count("image_chunks", count_filter=filter).count
print(f"Image chunks in database: {image_count}")
```

**Resolution**:
- **For ColQwen initialization**: Check GPU memory, ensure VRAM >= 2GB, verify CUDA installation
- **For missing collection**: Create collection explicitly:
  ```python
  from qdrant_client.models import VectorParams, Distance
  client.create_collection(
      collection_name="image_chunks",
      vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
  )
  ```
- **For images not processed**: Re-process document with `include_images = True` in ProcessingConfig
- **For missing metadata**: Verify ProcessingMetadata has `modality_type = "image"` for image chunks

**Implementation Reference**: media_processor_enhanced.py:50-120 (image extraction, metadata)

---

## 3. Model & Inference Performance Issues

### 3.1 Generation Slow (10-30 seconds for 100 tokens)

**Symptoms**:
- User query → retrieval (fast, <1s) → generation (very slow, 20+ seconds)
- GPU utilization low (20-30%), even though generation is slow
- CPU usage high (60-80%)

**Root Causes**:
1. Model running on CPU instead of GPU (torch.device="cpu")
2. Batch size too large, causing memory swaps
3. Context length very long (100+ chunks passed to LLM)
4. Model quantization disabled, loading FP32 weights

**Debug Steps**:
```python
import torch
from generation_service import GenerationService

gen_service = GenerationService()

# Check device
print(f"Model device: {gen_service.model.device}")  # Should be cuda:0

# Check quantization status
print(f"Model dtype: {gen_service.model.dtype}")  # Should be float16 or int8

# Profile generation
import time
start = time.time()
result = gen_service.generate(query="test", context="...")
end = time.time()
print(f"Generation took {end - start:.2f}s")
```

**Resolution**:
- **For CPU inference**: Force GPU with `torch.device("cuda:0")` in generation_service.py (check if model is loaded correctly)
- **For long context**: Reduce top_k in search query or truncate context to first N chunks:
  ```python
  max_context_tokens = 2048
  chunks = chunks[:max_context_tokens // avg_chunk_tokens]
  ```
- **For FP32 overhead**: Enable TensorFloat32:
  ```python
  torch.set_float32_matmul_precision('high')  # Should be in document_processor.py:172
  ```
- **For memory swaps**: Reduce batch_size in quantization config

**Implementation Reference**: document_processor.py:120-134 (torch settings), generation_service.py (device handling)

---

### 3.2 "Model Context Length Exceeded"

**Symptoms**:
- Error: `Input length (2500 tokens) exceeds max_tokens (2048)`
- Generation fails completely
- Works fine with small queries, fails with large document uploads

**Root Causes**:
1. Too many retrieved chunks passed to LLM
2. Chunk size too large (ProcessingConfig.chunk_size_tokens > 512)
3. System prompt + instructions consume tokens
4. Model has limited context (e.g., GPT-3.5 = 4K tokens)

**Debug Steps**:
```python
from generation_service import GenerationService
from transformers import AutoTokenizer

gen_service = GenerationService()
tokenizer = AutoTokenizer.from_pretrained(gen_service.model_name)

# Count tokens in context
context = "..." # Your retrieved chunks concatenated
token_count = len(tokenizer.encode(context))
print(f"Context tokens: {token_count}")

# Check model max
print(f"Model max context: {gen_service.model.config.max_position_embeddings}")
```

**Resolution**:
- **Reduce retrieved chunks**: In search_routes.py, reduce top_k from 10 to 5
- **Truncate context**: Keep only top 3-5 most relevant chunks, discard rest
- **Reduce chunk size**: Set ProcessingConfig.chunk_size_tokens = 256 (smaller chunks)
- **Use summarization**: Summarize retrieved context before passing to LLM (adds latency)
- **Switch model**: Use longer-context model (e.g., Claude 100K vs GPT-4 8K)

**Implementation Reference**: search_routes.py:search endpoint, search_orchestrator.py:orchestrate_search (context assembly)

---

## 4. Database & Storage Issues

### 4.1 Qdrant Connection Timeout

**Symptoms**:
- Error: `TimeoutError: Connection to localhost:6333 failed after 30s`
- All search requests fail with 503 Service Unavailable
- Qdrant process might be running but unresponsive

**Root Causes**:
1. Qdrant service not running or crashed
2. Port 6333 blocked by firewall
3. Qdrant database corrupted, slow recovery
4. Network connectivity issue (if using remote Qdrant)

**Debug Steps**:
```bash
# Check if Qdrant is running
curl http://localhost:6333/health

# If using Docker
docker ps | grep qdrant

# Test network connectivity (if remote)
telnet <qdrant-host> 6333

# Check Qdrant logs
docker logs qdrant  # Or check local logs
```

**Resolution**:
- **Restart Qdrant**:
  ```bash
  docker restart qdrant
  # Or if local installation: systemctl restart qdrant
  ```
- **Check firewall**: Ensure port 6333 is open
- **Clear corrupted data**: (WARNING: deletes all data)
  ```bash
  docker rm qdrant  # Remove container
  docker run -d -p 6333:6333 qdrant/qdrant  # Restart fresh
  ```
- **For slow recovery**: Check disk space, ensure SSD for Qdrant storage
- **For remote Qdrant**: Verify network latency with `ping <host>`

**Implementation Reference**: QdrantClient configuration in search_orchestrator.py

---

### 4.2 "Collection Does Not Exist" on Indexing

**Symptoms**:
- Error: `CollectionNotFound: Collection 'text_chunks' not found` during document indexing
- Works on some deployments but not others
- Error appears randomly, not consistently

**Root Causes**:
1. Collections not created during initialization
2. Wrong Qdrant instance (multiple Qdrant servers, indexing to one, searching another)
3. Collection deleted but code still tries to use it
4. Race condition: multiple processes trying to create collection simultaneously

**Debug Steps**:
```python
from qdrant_client import QdrantClient

client = QdrantClient("localhost", port=6333)

# List all collections
collections = client.get_collections()
for c in collections.collections:
    print(c.name)

# Check if expected collection exists
expected_collections = ["text_chunks", "image_chunks", "video_chunks"]
for name in expected_collections:
    exists = any(c.name == name for c in collections.collections)
    print(f"{name}: {exists}")
```

**Resolution**:
- **Create collections on startup**: Add initialization script that runs before indexing:
  ```python
  from qdrant_client.models import VectorParams, Distance
  
  def initialize_collections(client):
      for name, size in [("text_chunks", 384), ("image_chunks", 1024)]:
          try:
              client.create_collection(
                  collection_name=name,
                  vectors_config=VectorParams(size=size, distance=Distance.COSINE)
              )
          except:
              pass  # Collection already exists
  ```
- **Verify Qdrant connection**: Check `QdrantClient.get_collections()` before indexing
- **Use auto-create flag**: Check if indexing code has `auto_create=True` parameter
- **Add retry logic**: Retry collection creation with exponential backoff

**Implementation Reference**: Check initialization code path in main application startup

---

### 4.3 S3 Upload Timeout for Large Files

**Symptoms**:
- Error: `ClientError: An error occurred (RequestTimeout) when calling the PutObject operation`
- Works for files < 100MB, fails for > 500MB
- Upload stops at ~15 minutes with no progress

**Root Causes**:
1. Default AWS timeout too short (300 seconds) for large uploads
2. Network slow (< 1 Mbps), causing timeout before upload complete
3. S3 bucket permissions missing
4. No multipart upload for large files (uploading whole file at once)

**Debug Steps**:
```bash
# Check file size
ls -lh large_file.pdf

# Test S3 connectivity
aws s3 ls s3://your-bucket/

# Check network speed
speedtest-cli

# Monitor upload progress
aws s3 cp large_file.pdf s3://your-bucket/ --no-progress
```

**Resolution**:
- **Enable multipart upload**: Use boto3 with TransferConfig:
  ```python
  from boto3.s3.transfer import TransferConfig
  config = TransferConfig(multipart_threshold=100*1024*1024)  # 100MB threshold
  s3.upload_file(filename, bucket, key, Config=config)
  ```
- **Increase timeout**: Set `Config.connect_timeout = 30` and `read_timeout = 300`
- **For network issues**: Use S3 Transfer Acceleration or upload via S3 Direct endpoint
- **Check permissions**: Ensure IAM role has `s3:PutObject` permission

**Implementation Reference**: Check document upload service in backend

---

## 5. Concurrency & Race Conditions

### 5.1 Race Condition: Concurrent Document Uploads for Same File

**Symptoms**:
- Two simultaneous uploads of same document create duplicate chunks
- One upload fails with "file locked" error
- Metadata conflicts in database

**Root Causes**:
1. No document-level locking
2. Both processes write to same Qdrant collection simultaneously
3. No deduplication check (should detect if file already indexed)

**Debug Steps**:
```python
# Check for duplicate chunks with same document_id
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

client = QdrantClient("localhost", port=6333)

# Count chunks per document
document_id = "doc123"
filter = Filter(
    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
)
count = client.count("text_chunks", count_filter=filter).count
print(f"Chunks for {document_id}: {count}")

# Should be single peak, not multiple spikes indicating duplicates
```

**Resolution**:
- **Add file lock**: Use filesystem lock or database lock before indexing:
  ```python
  import fcntl
  with open(f"/tmp/{document_id}.lock", "w") as lock_file:
      fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
      try:
          # Process document
          pass
      finally:
          fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
  ```
- **Check if already indexed**: Before processing, query `document_metadata` table for document hash
- **Use idempotent indexing**: Mark chunks with unique (document_id, chunk_id) key, use upsert instead of insert

**Implementation Reference**: document_processor.py (add locking in process method)

---

### 5.2 Memory Leak in Long-Running Server

**Symptoms**:
- Server memory usage increases from 2GB to 8GB+ over 24-48 hours
- Performance degrades gradually (queries get slower)
- Restarting server fixes issue temporarily

**Root Causes**:
1. Models not garbage collected after inference
2. Cache not expiring (infinite accumulation)
3. GPU memory fragmentation from repeated allocations
4. Memory profiler not detecting leaks (background accumulation)

**Debug Steps**:
```python
import psutil
import gc
import torch

# Monitor memory over time
process = psutil.Process()
print(f"RSS memory: {process.memory_info().rss / 1024 / 1024:.2f} MB")

# Check GPU memory
print(f"GPU allocated: {torch.cuda.memory_allocated() / 1024 / 1024:.2f} MB")
print(f"GPU cached: {torch.cuda.memory_reserved() / 1024 / 1024:.2f} MB")

# Run garbage collection
gc.collect()
torch.cuda.empty_cache()
```

**Resolution**:
- **Periodic memory cleanup**: Add scheduled cleanup (every 1 hour):
  ```python
  import asyncio
  
  async def cleanup_memory():
      while True:
          await asyncio.sleep(3600)  # 1 hour
          gc.collect()
          torch.cuda.empty_cache()
  ```
- **Cap cache size**: Use LRU cache with max_size instead of unbounded dict
- **Monitor with APM**: Use DataDog or New Relic to track memory growth and identify culprit functions
- **Restart gracefully**: Implement health check that triggers restart if memory > 7GB threshold

**Implementation Reference**: Add cleanup to main application event loop (FastAPI startup)

---

## 6. Performance Troubleshooting

### 6.1 Search Latency High (2-5 seconds instead of <1s)

**Expected Latencies**:
- Text retrieval (BM25): ~45ms
- Dense retrieval: ~100ms
- Hybrid (RRF fusion): ~150ms total
- Image retrieval: ~200-300ms (ColQwen inference)

**Actual Latencies > 500ms**: Indicates bottleneck

**Diagnosis Tools**:
```python
import time
from search_orchestrator import SearchOrchestrator

orchestrator = SearchOrchestrator()

# Add timing instrumentation
start = time.time()
results = orchestrator.orchestrate_search(
    query="test query",
    top_k=10,
    retriever_type="hybrid",
    include_images=True
)
total_time = time.time() - start

# Break down by component
print(f"Total: {total_time:.3f}s")
print(f"  BM25: {results.telemetry.bm25_time:.3f}s")
print(f"  Dense: {results.telemetry.dense_time:.3f}s")
print(f"  Fusion: {results.telemetry.fusion_time:.3f}s")
print(f"  Image: {results.telemetry.image_time:.3f}s")
```

**Common Causes**:
- **Qdrant slow**: Collection too large (100K+ chunks), index needs optimization
  - Fix: Partition collection by user, use pagination
- **Dense embedding slow**: Batch size too large, GPU memory swapping
  - Fix: Reduce batch_size to 16, enable TF32
- **BM25 slow**: Unusual term frequency distribution
  - Fix: Check if document indexed with proper tokenization
- **Fusion slow**: Large top_k (20+) causing many documents to score
  - Fix: Reduce top_k to 5-10

**Implementation Reference**: search_orchestrator.py (add telemetry timing)

---

### 6.2 Corpus Growth → Search Slowdown (N grows from 1K to 100K documents)

**Symptoms**:
- Search time: 0.1s with 1K docs → 2s with 100K docs
- Scaling factor worse than linear
- Memory usage spikes periodically during searches

**Root Causes**:
1. Dense retrieval uses CPU FAISS (linear scan), not GPU-accelerated
2. Qdrant collection not sharded or optimized for large scale
3. No indexing on payload filters (user_id) → must scan all points
4. Vector dimension inefficiency (too high dimension)

**Debug Steps**:
```python
from rag_retrievers import DenseRetriever
import time

# Profile dense retrieval at different corpus sizes
retriever = DenseRetriever()

for corpus_size in [1000, 10000, 100000]:
    # Subset corpus to corpus_size
    start = time.time()
    results = retriever.search("test query", top_k=10)
    elapsed = time.time() - start
    print(f"{corpus_size} docs: {elapsed:.3f}s")
```

**Resolution**:
- **Enable Qdrant indexing**: Add index on `user_id` payload field:
  ```python
  client.create_payload_index(
      collection_name="text_chunks",
      field_name="user_id",
      field_schema=PayloadSchemaType.KEYWORD
  )
  ```
- **Use GPU FAISS** (if available): Modify DenseRetriever to use `faiss.index_gpu_to_cpu` instead of CPU FAISS
- **Partition by user**: Create separate collections per user (or use sharding) if multi-tenant
- **Reduce vector dimension**: Use smaller embedding models (384-dim instead of 1024-dim)
- **Implement caching**: Cache frequent queries (same query within 1 hour)

**Implementation Reference**: rag_retrievers.py:DenseRetriever class

---

## Summary: Decision Tree

**Search fails?**
→ Check Qdrant health (`/health` endpoint)
→ Verify collection exists
→ Check user_id filter applied

**Search is slow?**
→ Check corpus size (> 50K docs?)
→ Profile each component (BM25 vs Dense vs Fusion)
→ Check FAISS index type

**Generation is slow?**
→ Verify GPU in use (not CPU)
→ Check context length (< 2048 tokens?)
→ Reduce top_k or chunk count

**Memory leak?**
→ Profile with `psutil` + `torch.cuda`
→ Add periodic `gc.collect()` + `torch.cuda.empty_cache()`
→ Implement health check with restart trigger

---

**Generated**: May 14, 2026  
**Scope**: Operational troubleshooting beyond OPERATIONS_RUNBOOK.md  
**Next**: See NAMING_CONVENTIONS.md for code patterns

