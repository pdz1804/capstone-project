# Process API - Capacity Test Results
**Date: 2026-04-22**

## Test Results Summary

### 50-Thread Test
- **Threads:** 50 concurrent users
- **Ramp-up:** 10 seconds
- **Duration:** 120 seconds  
- **Total Test Time:** ~130 seconds
- **Total Requests:** 3,282
- **Success (200 OK):** 1,557 (47.5%)
- **Failed Requests:** 1,725 (52.5%)
  - **409 Conflict:** 1,214 (70.4% of failures)
  - **401 Unauthorized:** 424 (24.6% of failures)
  - **500 Internal Server Error:** 87 (5.0% of failures)

**Status:** ❌ UNACCEPTABLE - Error rate 52.5% exceeds 5% threshold

---

## Detailed Error Analysis

### 409 Conflict (1,214 failures)
- **Cause:** Multiple threads attempting to process same files concurrently
- **Issue:** CSV file recycles through 50 users, but all 50 threads hit within the same 10-second ramp-up and 120-second duration window
- **Severity:** HIGH - System overloaded with file processing requests

### 401 Unauthorized (424 failures)  
- **Cause:** Auth token extraction failures during concurrent ramp-up
- **Timing:** Most at start of test when threads spawn rapidly
- **Severity:** MEDIUM - Improves after ramp-up phase

### 500 Internal Server Error (87 failures)
- **Cause:** Backend service overload/crashes
- **Severity:** CRITICAL - Indicates system exhaustion

---

## Capacity Test Series

Based on error rate degradation pattern observed:
- **30 threads:** ~22% error rate (PREVIOUS TEST)
- **50 threads:** ~52% error rate (CURRENT TEST)

**Binary Search Strategy:**
Need to find sweet spot between acceptable (5% errors) and unacceptable

### Next Tests Recommended:

**Test 1: 10 threads** (Conservative)
```bash
jmeter -n -t 05_process_mapped.jmx \
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" \
  -Jthreads=10 \
  -Jramp_up=10 \
  -Jduration=120 \
  -l "results/05-process_10threads_$(date +%Y%m%d_%H%M%S).jtl"
```
Expected: ~2-3% error rate

**Test 2: 15 threads** (If 10 passes)
```bash
jmeter -n -t 05_process_mapped.jmx \
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" \
  -Jthreads=15 \
  -Jramp_up=10 \
  -Jduration=120 \
  -l "results/05-process_15threads_$(date +%Y%m%d_%H%M%S).jtl"
```
Expected: ~3-4% error rate

**Test 3: 20 threads** (If 15 passes)
```bash
jmeter -n -t 05_process_mapped.jmx \
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" \
  -Jthreads=20 \
  -Jramp_up=10 \
  -Jduration=120 \
  -l "results/05-process_20threads_$(date +%Y%m%d_%H%M%S).jtl"
```
Expected: ~5-8% error rate

---

## Analysis Key Points

✓ CSV data structure is valid (50 unique users with passwords/file paths)
✓ Test data loads correctly from file
✓ Some requests succeed (200 OK responses)

✗ System cannot handle 50 concurrent threads
✗ 409 conflicts indicate inadequate file locking/queueing
✗ 500 errors indicate backend resource exhaustion

## Recommendations

1. **Immediate:** Test with 10, 15, 20 threads to find capacity threshold
2. **Short-term:** Investigate why 50 threads causes backend crashes (500 errors)
3. **Long-term:** 
   - Implement request queueing for file processing
   - Add rate limiting to auth endpoint
   - Consider async processing with job queue

---

## File Locations
- Test Plan: `05_process_mapped.jmx`
- Data: `data/user_file_mapping_with_passwords.csv` (50 users)
- Results: `results/*.jtl`

