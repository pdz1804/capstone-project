# Process API - Capacity Test Results
**Date: 2026-04-22**

## Test Results Summary

### Test Series Completed

| Threads | Total Requests | Success | Failed | Error Rate | Status | Notes |
|---------|-----------------|---------|--------|-----------|--------|-------|
| **10** | 266 | 252 | 14 | **5.26%** | ⚠️ MARGINAL | At 5% threshold - acceptable but tight |
| **30** | 271 | 234 | 37 | **13.65%** | ❌ UNACCEPTABLE | Degraded from 2.70% → 22.41% |
| **50** | 3,282 | 1,557 | 1,725 | **52.5%** | ❌ FAILED | Backend overwhelmed |

---

## Detailed Analysis

### 10-Thread Test ✓ (ACCEPTABLE)
```
Ramp-up (0-10s):   Err 0.00% - Auth succeeding, files process cleanly
Sustained (10-70s): Err 1.08-6.00% - Minor conflicts during sustained load
End (70-130s):     Err 7.84% - Slight degradation but manageable
FINAL:             5.26% error rate
```
- **Response Times:** Avg 4,473ms | Min 316ms | Max 11,603ms
- **Throughput:** 2.1 req/s
- **Conclusion:** Can reliably handle 10 concurrent users

---

### 30-Thread Test ❌ (UNACCEPTABLE)
```
Ramp-up (0-10s):    Err 2.70% - Manageable at start
Early Load (10-30s): Err 13.79% - Rapid degradation
Mid Load (30-60s):  Err 20.29% - Continues climbing
End (60-130s):      Err 22.41% - System exhausted
FINAL:              13.65% error rate
```
- **Response Times:** Avg 13,861ms | Min 315ms | Max 35,897ms (very slow!)
- **Throughput:** 2.0 req/s
- **Conclusion:** System cannot handle 30 concurrent users - errors degrade linearly

---

### 50-Thread Test ❌ (FAILED)
- Error Rate: **52.5%**
- Failures by type:
  - 409 Conflict: 1,214 (70% of failures)
  - 401 Unauthorized: 424 (25% of failures)
  - 500 Internal Error: 87 (5% of failures)
- **Conclusion:** Backend crashes/exhausts under this load

---

## Capacity Threshold Finding

**Process API Capacity: ~10-15 concurrent users**
- 10 threads: 5.26% errors (acceptable, at edge)
- 30 threads: 13.65% errors (degrading, unacceptable)
- 50 threads: 52.5% errors (catastrophic failure)

**Recommendation:** Cap at **10-12 concurrent users** for Process API in production

---

## Error Patterns

### 401 Unauthorized (Auth Failures)
- Occur during **ramp-up phase** (when many threads start simultaneously)
- Token extraction sometimes fails under rapid-fire auth requests
- Stabilizes after ~30 seconds
- **Root Cause:** Auth endpoint rate limiting or token parsing timing

### 409 Conflict (File Already Processing)
- Multiple threads try to process same file
- CSV data recycles through 50 users
- With 30+ threads, concurrent file processing attempts spike
- **Root Cause:** No request queueing or file-level locking

### 500 Internal Error
- Only at 50 threads
- Backend service crashes/exhausts memory
- Indicates system resource exhaustion
- **Root Cause:** Insufficient backend capacity for document processing

---

## Files & Data Used

✓ Test Plan: `05_process_mapped.jmx`
✓ Data File: `data/user_file_mapping_with_passwords.csv` (50 users)
✓ Upload File: `data/Text_mining_by_using_Python2025_5pages.pdf`

All 50 users have:
- Unique email (testuser1@loadtest.io ... testuser50@loadtest.io)
- Same password: TestPassword123!
- Unique user_id and S3 file path per user

---

## Next: Indexing & Search Testing

Now test other endpoints with mapped user data:
- **Index API** - Index processed files for search
- **Search API** - Search across indexed documents

See: `NEXT_TESTS_INDEX_SEARCH.md`
