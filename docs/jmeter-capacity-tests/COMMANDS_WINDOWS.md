# JMeter Capacity Tests - Windows PowerShell Commands

**For Windows PowerShell - use these commands, not the bash versions!**

---

## Process API Tests (Already Done)

### 10 Threads (Baseline - ACCEPTABLE ✓)
```powershell
jmeter -n -t 05_process_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=10 -Jduration=120 -l "results/05-process_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```
**Result:** 5.26% error rate ⚠️ (at threshold)

### 30 Threads (UNACCEPTABLE ❌)
```powershell
jmeter -n -t 05_process_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=30 -Jramp_up=10 -Jduration=120 -l "results/05-process_30threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```
**Result:** 13.65% error rate ❌

---

## Index API Tests (NEW)

### Index - 10 Threads (Baseline)

```powershell
jmeter -n -t 07_index_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=10 -Jduration=60 -l "results/07-index_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**What it does:**
- 10 concurrent users (from CSV data)
- Each user logs in → gets Bearer token → indexes their file
- Authorization: `Bearer ${token}` + `X-User-Id: ${user_id}`
- Expected: 0-2% errors (indexing is fast)

---

### Index - 15 Threads

```powershell
jmeter -n -t 07_index_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=15 -Jramp_up=10 -Jduration=60 -l "results/07-index_15threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

### Index - 20 Threads (Push Limit)

```powershell
jmeter -n -t 07_index_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=20 -Jramp_up=10 -Jduration=60 -l "results/07-index_20threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## Search API Tests (NEW)

### Search - 10 Threads with "mining" query

```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**What it does:**
- 10 concurrent users (from CSV data)
- Each user logs in → gets Bearer token → searches for "mining"
- Authorization: `Bearer ${token}` + `X-User-Id: ${user_id}`
- Expected: 0-2% errors (search is fast)

---

### Search - 20 Threads with "mining" query

```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=20 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_20threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

### Search - 30 Threads with "mining" query

```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=30 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_30threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

### Search - Alternative Queries

**Search for "python":**
```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jsearch_query="python" -l "results/08-search_python_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**Search for "data":**
```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jsearch_query="data" -l "results/08-search_data_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## Test Sequence (Recommended)

**Step 1: Verify indexing works (10 threads)**
```powershell
jmeter -n -t 07_index_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=10 -Jduration=60 -l "results/07-index_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**Step 2: Test search on indexed data (10 threads)**
```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**Step 3: Push index capacity (20 threads)**
```powershell
jmeter -n -t 07_index_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=20 -Jramp_up=10 -Jduration=60 -l "results/07-index_20threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**Step 4: Push search capacity (20 threads)**
```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=20 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_20threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## One-Liner Quick Templates

### Index N threads:
```powershell
jmeter -n -t 07_index_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=10 -Jduration=60 -l "results/07-index_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```
**Edit:** Change `10` in `-Jthreads=10` to desired number

### Search N threads:
```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```
**Edit:** Change `10` in `-Jthreads=10` and `"mining"` in `-Jsearch_query="mining"` as needed

---

## Key Parameters Explained

| Parameter | Example | Meaning |
|-----------|---------|---------|
| `-t 07_index_mapped.jmx` | Test plan file | Which API to test |
| `-Jthreads=10` | Number | Concurrent users |
| `-Jramp_up=10` | Seconds | Time to spawn all threads |
| `-Jduration=60` | Seconds | How long to hold load |
| `-Jsearch_query="mining"` | Search term | What to search for |
| `-l "results/..."` | Output file | Where to save results |
| `Get-Date -Format 'yyyyMMdd_HHmmss'` | Timestamp | Unique filename |

---

## Windows PowerShell Notes

✓ Use `Get-Date -Format 'yyyyMMdd_HHmmss'` for timestamps (not `date +%Y%m%d_%H%M%S`)
✓ Copy entire line at once (no line continuation with `\`)
✓ Parameter order doesn't matter for `-J` flags
✓ All paths use forward slashes (`/`) or backslashes (`\`) both work

---

## Check Results

After test completes, check the results file:

```powershell
Get-Content "results/07-index_10threads_*.jtl" | Measure-Object -Line | Select-Object Lines
```

Or view last few lines:

```powershell
Get-Content "results/07-index_10threads_*.jtl" -Tail 5
```

---

## Expected Success Codes

| Endpoint | Success Code | Meaning |
|----------|-------------|---------|
| Index | 200, 201 | File indexed successfully |
| Search | 200 | Search completed |
| Auth (failed) | 401 | Token extraction failed |

---

## Files Structure

```
docs/jmeter-capacity-tests/
├── 05_process_mapped.jmx       ← Process API test (already done)
├── 07_index_mapped.jmx         ← Index API test (NEW)
├── 08_search_mapped.jmx        ← Search API test (NEW)
├── data/
│   ├── user_file_mapping_with_passwords.csv  ← 50 users
│   └── Text_mining_by_using_Python2025_5pages.pdf
├── results/
│   ├── 05-process_10threads_*.jtl
│   ├── 05-process_30threads_*.jtl
│   ├── 07-index_10threads_*.jtl              ← (NEW - from next tests)
│   ├── 08-search_mining_10threads_*.jtl      ← (NEW - from next tests)
│   └── ...
└── CAPACITY_RESULTS.md         ← Summary of all tests
```

---

## Summary

### Completed Tests:
✓ Process API: 10 threads = 5.26% errors (acceptable)
✓ Process API: 30 threads = 13.65% errors (too high)
✓ Process API: 50 threads = 52.5% errors (failed)

### Next Tests:
→ Index API: 10, 15, 20 threads (find capacity)
→ Search API: 10, 20, 30 threads (find capacity)

### Key Feature:
✓ All tests use **per-user authentication** with Bearer tokens
✓ Each thread logs in, gets unique token, and accesses their own files
✓ Tests real-world multi-user concurrent scenarios
