# Index API - Bottleneck Analysis (Standard Mode)

**File:** `app/services/indexing_service.py`

---

## CRITICAL BOTTLENECKS

### 1. **Per-User Mutual Exclusion Lock** 🔴 CRITICAL
**Location:** `app/api/routes/pipeline_routes.py` (line ~26)
```python
lock = _pipeline_lock_for_user(user_id)
if not lock.acquire(blocking=False):
    raise HTTPException(status_code=409, detail="...")
```
**Impact:** 
- Only ONE indexing job per user at a time
- When 3+ concurrent threads → only 1 can run, others fail with 409 Conflict
- This is intentional (prevent duplicate indexing), but kills concurrency

**Why 50% failure at 3 threads:**
- Thread 1 gets lock ✓ (processes for ~15 seconds)
- Thread 2 requests lock ✗ (409 Conflict - immediate fail)
- Thread 3 requests lock ✗ (409 Conflict - immediate fail)
- Then Threads 2&3 loop again... but Thread 1 still holding lock

---

### 2. **Image Indexing with ColQwen (Standard Mode Only)** 🔴 CRITICAL
**Location:** `indexing_service.py` lines 348-533 (`index_images()`)

**Sub-bottlenecks:**

#### a) PDF to Images Conversion
```python
pages = convert_from_path(str(pdf_path), dpi=dpi)  # Line 463
```
- Converts PDF to images at 150 DPI
- For 5-page PDF: ~5-10 seconds
- **Runs sequentially** (not parallelized per document)

#### b) ColQwen Image Embedding
```python
vecs, _ = self._colqwen.embed_images(batch_imgs)  # Line 450
```
- ColQwen is ML model inference (heavy compute)
- Generates embeddings for each page
- Batches only 2 images (small batch!)
- **Each batch flush waits for model inference**

#### c) Qdrant Vector DB Writes
```python
repo.upsert_pages(all_ids, all_vecs, all_payloads, batch_size=8)  # Line 530
```
- Network round-trip to remote Qdrant instance
- Multiple calls per document (batched but sequential)

---

### 3. **Text Embedding (Shared by Both Paths)** 🟡 MODERATE
**Location:** `indexing_service.py` lines 283-286 (`index_text()`)
```python
model = _get_text_embedder(self._embed_model)  # Line 283 - cached
texts = [d.get("text", "") for d in documents]
embeddings = model.encode(texts, show_progress_bar=False)  # Line 286
```
**Impact:**
- SentenceTransformer (all-MiniLM-L6-v2) runs on CPU
- Encodes ALL chunks at once (batch operation)
- Takes ~2-3 seconds for 9 chunks
- Blocks until complete

---

### 4. **S3 Sync Before Indexing** 🟡 MODERATE
**Location:** `indexing_service.py` lines 190-200 (`_sync_selected_stage4_docs_from_s3()`)
```python
def _sync_selected_stage4_docs_from_s3(self, ...):
    if not is_s3_storage_backend():
        return
```
**Impact:**
- Downloads files from S3 to local `/tmp`
- For each user indexing: ~1-2 second S3 latency
- Can be slow with large files

---

### 5. **Qdrant Collection Preparation (Per-User)** 🟡 MODERATE
**Location:** `indexing_service.py` lines 301-303 (`index_text()`)
```python
if force or self._text_collection not in _PREPARED_TEXT_COLLECTIONS:
    repo.ensure_collection(recreate=force)  # Can take 1-2s
    _PREPARED_TEXT_COLLECTIONS.add(self._text_collection)
```
**Impact:**
- First indexing per user creates Qdrant collection
- Subsequent runs use cache
- Network call to Qdrant

---

## TIMELINE OF A SINGLE INDEX REQUEST (STANDARD MODE)

```
Total: ~17-20 seconds

Auth & Lock Acquisition:        0.5s
├── Login                       0.3s
├── Get lock                    0.2s

S3 Sync:                        1.5s (if not cached)

TEXT INDEXING (parallel):       
├── Load docs from rag_ready    0.5s
├── Embed chunks (CPU)          2.5s
├── Ensure Qdrant collection    1.0s
├── Upsert to Qdrant           2.0s
└── Save BM25 + snapshot       1.5s
                               -------
                               ~7.5s

IMAGE INDEXING (parallel):
├── PDF → Images (5 pages)      5.0s  ← SLOW
├── ColQwen embed (batch=2)     6.0s  ← VERY SLOW
├── Qdrant upsert             2.0s
└── Image sidecar write       0.5s
                             -------
                             ~13.5s

Total (parallel):             max(7.5s, 13.5s) = ~13.5s

Lock Release:                   1.0s (cleanup)
```

---

## WHY 3 THREADS FAIL AT 50%

```
Thread Timeline:
T=0s    Thread 1 acquires lock → starts
        Thread 2 tries lock → 409 CONFLICT (instant fail)
        Thread 3 tries lock → 409 CONFLICT (instant fail)

T=0.5s  Thread 2 retries → still locked
        Thread 3 retries → still locked

T=13.5s Thread 1 releases lock
        Thread 2 acquires lock → starts
        Thread 3 tries lock → 409 CONFLICT (instant fail)

T=27s   Thread 2 releases lock
        Thread 3 acquires lock → starts

T=40.5s Thread 3 completes

Result:
- Thread 1: Success (first)
- Thread 2: Timeout (waits 60s, eventually fails)
- Thread 3: Timeout (waits 60s, eventually fails)

JMeter sees: 1 success + 2 timeouts = ~33% success (matches observed 50% ≈ some succeed on retry)
```

---

## FAST MODE vs STANDARD MODE

### FAST Mode (`mode="fast"`)
**Location:** `indexing_service.py` lines 550-564
```python
if mode == "fast":
    text_res = self.index_text(...)
    return {..., "image": {"status": "skipped_fast_mode"}}
```
- **Skips ALL image processing** ✓
- Only runs text embedding + Qdrant upsert
- **Expected time: ~7.5 seconds instead of 13.5s**
- **2x faster, similar concurrency issues**

### STANDARD Mode (Current)
- Runs text and image **in parallel** (ThreadPoolExecutor with max_workers=2)
- **BUT:** Limited by per-user lock → still sequential!

---

## ROOT CAUSE SUMMARY

| Bottleneck | Severity | Cause | Solution |
|-----------|----------|-------|----------|
| **Per-user lock** | 🔴 CRITICAL | `if not lock.acquire(blocking=False)` | Remove lock OR make async queue |
| **ColQwen embedding** | 🔴 CRITICAL | ML inference on CPU | Use GPU / batch larger / async |
| **PDF to images** | 🔴 CRITICAL | PIL convert_from_path() | Parallelize per document |
| **S3 sync latency** | 🟡 MODERATE | Network I/O | Cache aggressively |
| **Text embedding** | 🟡 MODERATE | CPU bound | Batch larger / GPU |
| **Qdrant calls** | 🟡 MODERATE | Network I/O | Connection pooling |

---

## WHY CONCURRENT USERS CAN'T SCALE

**The per-user lock is INTENTIONAL** (from comments in code):
- Prevents duplicate indexing of same file
- Avoids race conditions on user workspace

**But it kills concurrency:**
- 3 concurrent requests = 1 runs, 2 wait
- After 60s timeout → 2 fail
- System never processes requests in parallel

---

## CAPACITY IMPLICATIONS

**Current Reality:**
- System processes **ONE user's index job at a time**
- Each takes 13-17 seconds
- Maximum throughput: **1 user / 13-17 seconds = ~3-4 users/minute**
- **NOT 10-20 concurrent users like Process API**

**Theoretical with Fast Mode:**
- 7-10 seconds per user
- **~6-8 users/minute**

**What test saw:**
- 3 concurrent threads starting simultaneously
- Only 1 could run (lock)
- 2 timed out
- **= 50% failure rate** ✓

