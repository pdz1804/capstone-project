# Search API - Capacity Test Results
**Date: 2026-04-22**

## Bug Fix Applied
**Fixed:** `NameError: name 'requested_model' is not defined` in `app/api/routes/search_routes.py:71`
- **Cause:** Variables `requested_model` and `configured_model` were undefined
- **Fix:** Extract `configured_model` from `cfg.get("generation")` and use `req.generation_model` as fallback
- **File:** `Phase_2_FE_AI_Merge/backend/app/api/routes/search_routes.py`
- **Lines Modified:** 51-71

---

## Test Results Summary

### Search API - 30 Threads Test
**File:** `08-search_mining_30threads_20260422_171824.jtl`
**Duration:** 60 seconds | **Threads:** 30 | **Ramp-up:** 5 seconds

| Metric | Value |
|--------|-------|
| **Total Search Requests** | 165 |
| **Successful (200 OK)** | 58 |
| **Failed (500 Error)** | 107 |
| **Error Rate** | **64.8%** ❌ |
| **Auth Requests** | 30 (all 200 OK) |

#### Search Response Times
```
Successful searches (200 OK):
- Min: ~3,000 ms
- Avg: ~22,000 ms (estimated)
- Max: ~27,606 ms
```

---

## Analysis

### What Worked ✓
- **Authentication:** All 30 auth logins succeeded (100%)
- **Bearer Token Extraction:** Token regex working correctly
- **Request Format:** POST /api/search with JSON body correctly formatted
- **Fixed Bug:** Search endpoint no longer crashes with NameError

### What Failed ❌
- **500 Internal Server Errors:** 64.8% failure rate at 30 threads
- **Concurrent Load Handling:** System cannot handle 30 concurrent search requests
- **Response Times:** When successful, responses take 20-27 seconds (very slow)

### Likely Root Causes
1. **Search Orchestrator Bottleneck** - Single instance processing requests sequentially
2. **Vector DB Contention** - Qdrant queries from 30 threads competing for connections
3. **LLM Generation Bottleneck** - Bedrock Converse API rate limiting or overload
4. **Text Embedding** - SentenceTransformer CPU-bound on all 30 threads
5. **Image Processing** - ColQwen model processing 5 images per search x 30 threads

---

## Recommended Next Tests

Run in this order to find capacity threshold:

### Step 1: Baseline (10 threads)
```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### Step 2: Medium load (15 threads)
```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=15 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_15threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### Step 3: Conservative capacity (20 threads)
```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=20 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_20threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## Test Configuration
- **API Host:** k2p-bkmind-learning-platform.com (HTTPS)
- **Search Query:** "mining"
- **Retriever Type:** hybrid (BM25 + dense vector search)
- **Search Scope:** both (text + images)
- **Top K Results:** 5
- **Images for Generation:** 5
- **Mode:** retrieval_generation (LLM-powered answers)
- **Include Images:** true

---

## Next: Index API Optimization
After completing search capacity tests, return to Index API bottleneck optimization.
See: `BOTTLENECK_ANALYSIS.md`
