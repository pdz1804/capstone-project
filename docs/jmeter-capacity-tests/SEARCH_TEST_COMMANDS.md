# Search API - Capacity Test Commands

**Status:** Search endpoint is typically FAST (read-only, no locking)

Search should handle **higher concurrency** than Index API since there's:
- No per-user lock
- No ML inference (just database query)
- No file I/O

---

## BASELINE: Search 5 Threads (Conservative)

```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=5 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_5threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**Expected:**
- Error rate: 0-2% ✓ (search is fast)
- Avg response: 200-500ms
- Success: 200 OK

---

## SCALE UP: Search 10 Threads

```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**Decision:**
- If < 5% errors → try 20 threads
- If > 5% errors → stay at 10

---

## PUSH LIMIT: Search 20 Threads

```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=20 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_20threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## AGGRESSIVE: Search 30 Threads

```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=30 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_30threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## DIFFERENT SEARCH QUERIES

### Test "python" keyword:
```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jsearch_query="python" -l "results/08-search_python_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### Test "data" keyword:
```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jsearch_query="data" -l "results/08-search_data_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### Test "text" keyword:
```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jsearch_query="text" -l "results/08-search_text_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## QUICK TEST SEQUENCE

Run these in order (each ~1.5 minutes):

**1. Verify search works (5 threads):**
```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=5 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_5threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**2. Scale to 10 threads:**
```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**3. Push to 20 threads:**
```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=20 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_20threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## WHAT TO EXPECT

**Search is Read-Only:**
- No locking (unlike index)
- Fast database queries
- Should handle 20-30+ concurrent users

**If errors occur:**
- 400: Bad query syntax
- 404: No results found (expected, not an error)
- 500: Backend crash (unlikely)

---

## AFTER SEARCH TESTS

**Summarize results:**
```
Process API capacity:  ~10-15 threads (5% error threshold)
Index API capacity:    ~1-2 concurrent users (per-user lock)
Search API capacity:   ~20-30+ threads (estimated)
```

Then decide: do you want to come back to **optimize indexing** or move to other features?

