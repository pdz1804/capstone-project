# BK-MInD API Capacity Testing Suite

## Overview

This directory contains JMeter test plans to discover concurrent user capacity for all BK-MInD platform APIs. The test suite is designed for **quick capacity discovery** (~1 minute per API) to identify breaking points and maximum safe concurrency levels.

## Directory Structure

```
jmeter-capacity-tests/
├── Core APIs (01-04)
│   ├── 01_auth_login.jmx                      # POST /api/auth/login-local
│   ├── 02_user_me.jmx                         # GET /api/users/me
│   ├── 03_stats.jmx                           # GET /api/processing-stats
│   └── 04_upload.jmx                          # POST /api/upload
│
├── Pipeline APIs (05-06 Mapped)
│   ├── 05_process_mapped.jmx                  # POST /api/process (per-user with locks)
│   └── 06_index_mapped.jmx                    # POST /api/index (per-user with locks)
│
├── Search & Chat APIs (08-09 Mapped)
│   ├── 08_search_mapped.jmx                   # POST /api/search (retrieval_generation mode)
│   └── 09_chat_stream_mapped.jmx              # POST /api/chat/stream
│
├── Insights APIs (10-12 Mapped)
│   ├── 10_insights_summary_mapped.jmx         # POST /api/summary
│   ├── 11_insights_mcq_mapped.jmx             # POST /api/mcq
│   └── 12_insights_roadmap_mapped.jmx         # POST /api/learning-roadmap
│
├── Test Command Files
│   ├── COMMANDS_WINDOWS.md                    # Search/Index/Process test commands
│   ├── runs/README_MAIN_APIS.md               # 05/06/08: JMeter + JTL + Dynamo + search CSV
│   ├── runs/README_NON_MAIN_APIS.md           # 01–04, 09–12: JMeter + jtl_metrics_csv
│   ├── runs/README.md                         # Short index → links above
│   └── CHAT_INSIGHTS_TEST_COMMANDS.md         # Chat & Insights API test commands (NEW)
│
├── Result Files
│   ├── 05_RESULTS_SUMMARY.md                  # Process API results
│   ├── 06_SEARCH_API_RESULTS.md               # Search API results (NEW)
│   └── CAPACITY_RESULTS.md                    # Historical results summary
│
├── data/
│   ├── user_file_mapping_with_passwords.csv  # 50 test users with S3 file paths
│   └── Text_mining_by_using_Python2025_5pages.pdf  # PDF for processing/indexing
│
└── results/                                    # Output directory for .jtl test files
    ├── 05-process_*.jtl                       # Process API results
    ├── 07-index_*.jtl                         # Index API results
    ├── 08-search_*.jtl                        # Search API results
    ├── 09-chat_*.jtl                          # Chat API results (NEW)
    ├── 10-summary_*.jtl                       # Summary API results (NEW)
    ├── 11-mcq_*.jtl                           # MCQ API results (NEW)
    └── 12-roadmap_*.jtl                       # Roadmap API results (NEW)
```

## APIs Tested

| #  | API Endpoint | Test File | Type | Status | Purpose |
|----|---|---|---|---|---|
| 1  | `POST /api/auth/login-local` | 01_auth_login.jmx | Auth | ✓ | User authentication |
| 2  | `GET /api/users/me` | 02_user_me.jmx | GET | ✓ | User profile retrieval |
| 3  | `GET /api/processing-stats` | 03_stats.jmx | GET | ✓ | Statistics endpoint |
| 4  | `POST /api/upload` | 04_upload.jmx | Upload | ✓ | File upload |
| 5  | `POST /api/process` | 05_process_mapped.jmx | Process | ✓ DONE | File processing (per-user) |
| 6  | `POST /api/index` | 06_index_mapped.jmx | Index | ✓ DONE | Document indexing (per-user) |
| 7  | `POST /api/search` | 08_search_mapped.jmx | Search | ✓ DONE | Search with retrieval_generation |
| 8  | `POST /api/chat/stream` | 09_chat_stream_mapped.jmx | Chat | 🆕 NEW | Chat streaming (per-user) |
| 9  | `POST /api/summary` | 10_insights_summary_mapped.jmx | Insights | 🆕 NEW | Summary generation |
| 10 | `POST /api/learning-roadmap` | 12_insights_roadmap_mapped.jmx | Insights | 🆕 NEW | Learning roadmap generation |
| 11 | `POST /api/mcq` | 11_insights_mcq_mapped.jmx | Insights | 🆕 NEW | MCQ generation |

## Test Strategy

### Quick Capacity Discovery Mode

Each API is tested at increasing concurrency levels until error rates exceed 5%:

- **Thread Levels:** 5, 10, 20, 30, 40, 50 concurrent users
- **Ramp-up Time:** 5 seconds (gradual thread spawning)
- **Sustained Load:** 15 seconds per level
- **Total per level:** ~20 seconds
- **Time per API:** ~120 seconds (6 levels)
- **Total Suite:** ~22-30 minutes (all APIs)

### Test Parameters

```
Threads:      Concurrent users to simulate
Ramp-up:      Time to spawn all threads gradually (prevents thundering herd)
Duration:     Time to maintain load after ramp-up completes
```

## Prerequisites

1. **JMeter 5.6.3+**
   ```bash
   # Verify installation
   jmeter --version
   ```

2. **Running API Server**
   - Host: k2p-bkmind-learning-platform.com (default)
   - Port: 443 (default)
   - HTTPS available

3. **Test Data**
   - Valid user credentials in `data/users.csv`
   - Search queries in `data/search_queries.csv`
   - File IDs in `data/file_ids.csv`

4. **PowerShell 5.1+**
   - Windows environment
   - Execution policy allows script execution

## Usage

### Quick Start: Test Chat & Insights APIs

```powershell
cd .\docs\jmeter-capacity-tests
# Run baseline tests (10 threads each)
jmeter -n -t 09_chat_stream_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jchat_query="What are the main topics?" -l "results/09-chat_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

See **CHAT_INSIGHTS_TEST_COMMANDS.md** for all Chat & Insights API commands.

### Test Search API

```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_mining_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

See **runs/README_MAIN_APIS.md** for Search, Index, and Process (JTL, Dynamo CSV, `jtl_metrics_csv`). **COMMANDS_WINDOWS.md** has additional Windows-oriented snippets.

### Manual Test Command Template

```powershell
jmeter -n -t FILE.jmx `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" `
  -Jthreads=10 `
  -Jramp_up=5 `
  -Jduration=60 `
  -l "results/FILE_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**Parameters:**
- `-t FILE.jmx` = Test plan file
- `-Jmapping_csv=` = User data CSV (required for mapped tests)
- `-Jthreads=` = Concurrent users to simulate
- `-Jramp_up=` = Seconds to gradually spawn all threads
- `-Jduration=` = Seconds to hold load after ramp-up
- `-l results/...` = Output file path

## Output & Results

### Console Output

The script displays results in real-time:

```
================================================================================
Testing: POST /api/search (Retrieval Only)
================================================================================
ℹ  Running: POST /api/search (Retrieval Only) | Threads: 5 | Ramp-up: 5s | Duration: 15s
✓ Completed | Success: 95 | Failed: 2 | Error Rate: 2.06% | Avg: 4523.45ms | P95: 8901ms

ℹ  Running: POST /api/search (Retrieval Only) | Threads: 10 | Ramp-up: 5s | Duration: 15s
✓ Completed | Success: 180 | Failed: 5 | Error Rate: 2.7% | Avg: 5234.12ms | P95: 9456ms

ℹ  Running: POST /api/search (Retrieval Only) | Threads: 20 | Ramp-up: 5s | Duration: 15s
✗ Completed | Success: 280 | Failed: 42 | Error Rate: 13.04% | Avg: 7890.34ms | P95: 14523ms
```

### Summary Report

```
================================================================================
CAPACITY TEST SUMMARY REPORT
================================================================================

API                             Max Concurrent Status
─────────────────────────────────────────────────────────
POST /api/auth/login-local            20 ✓ PASS
GET /api/users/me                     20 ✓ PASS
GET /api/processing-stats             20 ✓ PASS
POST /api/upload                      10 ⚠ WARN
POST /api/process                     20 ✓ PASS
POST /api/index                       10 ⚠ WARN
POST /api/search (Retrieval Only)     10 ⚠ WARN
POST /api/chat/stream                  5 ✗ FAIL
POST /api/insights/summary            10 ⚠ WARN
POST /api/insights/learning-roadmap    5 ✗ FAIL
POST /api/insights/mcq                20 ✓ PASS
```

### Detailed Results Table

```
API: POST /api/search (Retrieval Only)
Max Recommended Capacity: 10 concurrent users

Threads Requests Success Failed Error %  Avg (ms) P95 (ms) P99 (ms)
───────────────────────────────────────────────────────────────────
5         95       95      2      2.06%    4523      8901     9345
10       185      180      5      2.7%     5234      9456     10234
20       322      280     42     13.04%    7890     14523     15678
```

### CSV Export

Results are automatically exported to: `results/capacity_summary_YYYYMMDD_HHMMSS.csv`

```csv
API,MaxCapacity,Threads,Requests,Success,Failed,ErrorRate,AvgTime,P95,P99
POST /api/auth/login-local,20,5,150,150,0,0%,1234.5,1456,1678
POST /api/auth/login-local,20,10,300,300,0,0%,1345.2,1567,1789
POST /api/auth/login-local,20,20,600,600,0,0%,1456.8,1678,1901
POST /api/search (Retrieval Only),10,5,95,95,2,2.06%,4523.45,8901,9345
POST /api/search (Retrieval Only),10,10,185,180,5,2.7%,5234.12,9456,10234
POST /api/search (Retrieval Only),10,20,322,280,42,13.04%,7890.34,14523,15678
...
```

## Interpreting Results

### Status Indicators

| Status | Error Rate | Interpretation |
|--------|-----------|---|
| ✓ PASS | ≤ 1% | **Recommended capacity** - stable and reliable |
| ⚠ WARN | 1-5% | **Acceptable but monitor** - approaching limits |
| ✗ FAIL | > 5% | **Exceeded capacity** - increase infrastructure |

### Key Metrics

- **Threads:** Concurrent users simulated
- **Requests:** Total API calls made
- **Success:** Successful responses (HTTP 200)
- **Failed:** Failed/error responses
- **Error %:** Failure rate percentage
- **Avg (ms):** Average response time
- **P95 (ms):** 95th percentile response time (tail latency)
- **P99 (ms):** 99th percentile response time (extreme tail)

### Max Capacity Determination

The `MaxCapacity` field indicates the **highest thread level** tested with error rate ≤ 5%. This represents:
- Safe recommended concurrent user count
- Baseline for your infrastructure's capacity
- Starting point for load balancing decisions

## Test Data Files

### user_file_mapping_with_passwords.csv (NEW)
Contains 50 test users with S3 file paths and credentials:
```csv
email,password,user_id,file_path
testuser1@loadtest.io,TestPassword123!,user_001,s3://bucket/users/user_001/...
testuser2@loadtest.io,TestPassword123!,user_002,s3://bucket/users/user_002/...
...
```

**Fields:**
- `email` - Login email
- `password` - Account password
- `user_id` - Unique user ID (used in X-User-Id header)
- `file_path` - S3 path to user's processed files

### Text_mining_by_using_Python2025_5pages.pdf
5-page PDF document used for:
- **Process API** tests - file processing
- **Index API** tests - document indexing
- **Search API** tests - retrieval queries
- **Insights API** tests - content analysis

## Troubleshooting

### JMeter Not Found
```powershell
# Add JMeter to PATH or specify full path
$JmeterPath = "C:\jmeter\bin\jmeter.bat"
.\run_capacity_finder.ps1 -JmeterPath $JmeterPath
```

### Connection Timeout
```powershell
# Verify server is running and accessible
Test-NetConnection -ComputerName k2p-bkmind-learning-platform.com -Port 443
```

### CSV Data File Not Found
```powershell
# Ensure you're in the correct directory
cd .\docs\jmeter-capacity-tests
Get-ChildItem .\data\
```

### Script Execution Policy
```powershell
# Allow script execution (if needed)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### No Results Generated
1. Check JMeter logs: `.\results\*.log`
2. Verify network connectivity to API server
3. Check user credentials in `data/users.csv`
4. Ensure test data files exist

## Performance Baselines (Reference)

Based on PERFORMANCE_TESTING_FINAL_RELEASE_REPORT_2026-04-21:

| API | Tested Concurrency | Success Rate | Status |
|-----|---|---|---|
| Core Pipeline (auth/users/stats/upload/process/index) | 40 users | 100% | ✓ PASS |
| Search (Retrieval Only) | 40 users | 100% | ✓ PASS |
| Chat/Stream | ~18s P95 | High latency | ⚠ Needs optimization |
| Insights (Generation) | High tail | P95: 7-20s | ⚠ Needs optimization |

## Next Steps

### After Capacity Testing

1. **Review Results:** Identify bottleneck APIs
2. **Scale Infrastructure:** Increase capacity for failing APIs
3. **Load Balancing:** Distribute traffic across instances
4. **Caching:** Implement caching for frequently accessed endpoints
5. **Optimization:** Profile and optimize slow endpoints
6. **Re-test:** Verify improvements after changes

### Recommended Thresholds

Based on test results, set up alerting for:

```yaml
Error Rate:
  - Critical: > 5%
  - Warning: > 2%

P95 Latency:
  - Auth/Stats: > 2s
  - Upload/Process: > 3s
  - Index: > 10s
  - Search: > 20s
  - Chat/Insights: > 30s

Throughput:
  - Monitor requests/second
  - Alert if < 50% of expected
```

## Test Results

### Completed Tests

- **Process API:** ✓ 5.26% error @ 10 threads (acceptable)
- **Search API:** 🔄 Testing in progress (64.8% error @ 30 threads)
- **Chat API:** 🆕 Ready to test (09_chat_stream_mapped.jmx)
- **Insights Summary:** 🆕 Ready to test (10_insights_summary_mapped.jmx)
- **Insights MCQ:** 🆕 Ready to test (11_insights_mcq_mapped.jmx)
- **Insights Roadmap:** 🆕 Ready to test (12_insights_roadmap_mapped.jmx)

### Result Files

- [Process API Results](results/05_RESULTS_SUMMARY.md)
- [Search API Results](results/06_SEARCH_API_RESULTS.md)
- [Capacity Summary](results/CAPACITY_RESULTS.md)

## Additional Resources

- [JMeter Documentation](https://jmeter.apache.org/usermanual/)
- [Chat & Insights API Commands](CHAT_INSIGHTS_TEST_COMMANDS.md)
- [Main APIs runbook — 05 / 06 / 08](runs/README_MAIN_APIS.md)
- [Non-main APIs runbook — 01–04, 09–12](runs/README_NON_MAIN_APIS.md)
- [Search/Index/Process Commands](COMMANDS_WINDOWS.md)
- [Performance Testing Report](../PERFORMANCE_TESTING_FINAL_RELEASE_REPORT_2026-04-21.md)
- [API Documentation](../API_SCHEMA.md)

## Support

For issues or questions:
1. Check troubleshooting section
2. Review JMeter logs in `results/`
3. Verify test data files
4. Check server connectivity

---

## Changelog

### 2026-04-22 (Current)
- ✓ Fixed Search API bug: `NameError: requested_model not defined`
- ✓ Created 09_chat_stream_mapped.jmx (Chat API tests)
- ✓ Created 10_insights_summary_mapped.jmx (Summary API tests)
- ✓ Created 11_insights_mcq_mapped.jmx (MCQ API tests)
- ✓ Created 12_insights_roadmap_mapped.jmx (Roadmap API tests)
- ✓ Created CHAT_INSIGHTS_TEST_COMMANDS.md with all test commands
- ✓ Cleaned up old unmapped test files (kept 01-04, removed old 05-11)
- ✓ Updated README with new file structure and test commands
- 🔄 Completed Search API baseline testing (30 threads @ 64.8% error rate)

### 2026-04-21
- ✓ Created Search API test plan (08_search_mapped.jmx)
- ✓ Completed Process API capacity tests (5.26% error @ 10 threads)
- ✓ Analyzed Index API bottlenecks (per-user mutual exclusion locks)

---

**Last Updated:** 2026-04-22
**JMeter Version:** 5.6.3+
**Test Suite:** Comprehensive API Capacity Testing
**Status:** Chat & Insights APIs ready for testing
