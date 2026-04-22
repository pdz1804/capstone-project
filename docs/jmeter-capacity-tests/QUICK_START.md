# BK-MInD Capacity Tests - Quick Start Guide

## 🚀 What You Just Got

11 separate JMeter test files for EACH API from the performance report, plus an automated test runner to find concurrent user capacity in ~1 minute per API.

## 📁 File Structure Created

```
docs/jmeter-capacity-tests/
├── 01_auth_login.jmx                 ← Test: POST /api/auth/login-local
├── 02_user_me.jmx                    ← Test: GET /api/users/me  
├── 03_stats.jmx                      ← Test: GET /api/processing-stats
├── 04_upload.jmx                     ← Test: POST /api/upload
├── 05_process.jmx                    ← Test: POST /api/process
├── 06_index.jmx                      ← Test: POST /api/index
├── 07_search_retrieval.jmx           ← Test: POST /api/search (Retrieval Only - NO Generation!)
├── 08_chat_stream.jmx                ← Test: POST /api/chat/stream
├── 09_insights_summary.jmx           ← Test: POST /api/insights/summary
├── 10_insights_roadmap.jmx           ← Test: POST /api/insights/learning-roadmap
├── 11_insights_mcq.jmx               ← Test: POST /api/insights/mcq
├── run_capacity_finder.ps1           ← Main test orchestrator script
├── README.md                          ← Full documentation
├── QUICK_START.md                     ← This file
│
└── data/
    ├── users.csv                     ← 30 test user accounts
    ├── search_queries.csv            ← 20 search queries
    ├── file_ids.csv                  ← 20 file IDs
    └── chat_messages.csv             ← 15 chat messages

results/
├── capacity_summary_*.csv            ← Auto-generated CSV reports
├── *.jtl                             ← Raw JMeter results
└── *.log                             ← JMeter execution logs
```

## ⚡ Quick Start (2 Minutes)

### 1. Navigate to Test Directory
```powershell
cd d:\PDZ\BKU\Learning\LVTN\GD1\Code\docs\jmeter-capacity-tests
```

### 2. Run All APIs (Automated Discovery)
```powershell
.\run_capacity_finder.ps1
```

**What happens:**
- Tests each of the 11 APIs
- Starts with 5, 10, 20, 30, 40, 50 concurrent users
- Stops when error rate exceeds 5%
- Auto-generates report with max capacity for each API
- Total time: ~24-30 minutes (6 levels × ~11 APIs)

### 3. Check Results
```powershell
# View summary in console (already shown)
# Or open CSV report:
Start-Process "results\capacity_summary_*.csv"
```

## 🎯 Example Output

```
================================================================================
CAPACITY TEST SUMMARY REPORT
================================================================================

API                             Max Concurrent Status
─────────────────────────────────────────────────────
POST /api/auth/login-local            20 ✓ PASS
GET /api/users/me                     20 ✓ PASS
GET /api/processing-stats             20 ✓ PASS
POST /api/upload                      10 ⚠ WARN
POST /api/process                     20 ✓ PASS
POST /api/index                       10 ⚠ WARN
POST /api/search (Retrieval Only)     10 ⚠ WARN    ← Retrieval ONLY (NO generation)
POST /api/chat/stream                  5 ✗ FAIL
POST /api/insights/summary            10 ⚠ WARN
POST /api/insights/learning-roadmap    5 ✗ FAIL
POST /api/insights/mcq                20 ✓ PASS
```

## 🔍 How It Works

### Test Strategy
- **Thread Levels:** 5, 10, 20, 30, 40, 50 concurrent users
- **Ramp-up:** 5 seconds (gradual spawning, not instant)
- **Duration:** 15 seconds sustained
- **Per level:** ~20 seconds total
- **Breakpoint:** Stops when error rate > 5%

### What "Max Concurrent" Means
The highest thread level where error rate stayed ≤ 5%

| Value | Meaning |
|-------|---------|
| 20 | Safe for 20 concurrent users |
| 10 | Safe for 10 concurrent users |
| 5 | Safe for 5 concurrent users |
| 0 | Failed at lowest level |

## 🛠️ Advanced Options

### Run Specific APIs Only
```powershell
.\run_capacity_finder.ps1 -APIs "07_search_retrieval,08_chat_stream"
```

### Custom Host/Port
```powershell
.\run_capacity_finder.ps1 -Host "your-server.com" -Port 8443
```

### Run Individual Test Manually
```bash
jmeter -n -t 07_search_retrieval.jmx `
  -Jhost=k2p-bkmind-learning-platform.com `
  -Jport=443 `
  -Jthreads=20 `
  -Jramp_up=10 `
  -Jduration=30 `
  -l results/search_custom.jtl
```

## 📊 Understanding Results

### Metrics
- **Threads:** How many concurrent users
- **Requests:** Total API calls made
- **Success:** How many got HTTP 200
- **Failed:** How many failed
- **Error %:** Failure percentage
- **Avg (ms):** Average response time
- **P95 (ms):** Worst 5% response time
- **P99 (ms):** Worst 1% response time

### Status Guide
- ✓ **PASS:** Error rate ≤ 1%, safe capacity
- ⚠ **WARN:** Error rate 1-5%, approaching limits  
- ✗ **FAIL:** Error rate > 5%, capacity exceeded

## 🎪 Key Features

✅ **11 Separate Test Files** - One for each API  
✅ **Search Retrieval Only** - NO generation mode tested  
✅ **Quick Testing** - ~1 minute per API  
✅ **Automated Discovery** - Finds breaking point automatically  
✅ **Real Data** - Uses actual user/query/file data  
✅ **Comprehensive Metrics** - P50, P95, P99, throughput  
✅ **CSV Reports** - Auto-exported for analysis  
✅ **PowerShell Orchestration** - Full automation  

## ⚠️ Important Notes

1. **Search Test = Retrieval Only**
   - No generation mode tested (as requested)
   - Only `retrieval_generation: false, retrieval_only: true`
   - Faster, focuses on retrieval bottlenecks

2. **All APIs Tested**
   - Auth, users, stats (core)
   - Upload, process, index (pipeline)
   - Search (retrieval only)
   - Chat, insights (generation-heavy)

3. **Gradual Thread Spawning**
   - Ramp-up: 5 seconds
   - Spawns threads gradually (not all at once)
   - More realistic than instant spawning

## 🐛 Troubleshooting

### "jmeter: command not found"
Add JMeter to PATH or specify path:
```powershell
$env:PATH += ";C:\jmeter\bin"
```

### "Connection refused"
Verify server is running:
```powershell
Test-NetConnection -ComputerName k2p-bkmind-learning-platform.com -Port 443
```

### "No results generated"
Check JMeter logs:
```bash
cd results
cat *.log  # Windows: type *.log
```

## 📚 Next Steps

1. **Run tests:** `.\run_capacity_finder.ps1`
2. **Review results:** Check CSV output and console summary
3. **Identify bottlenecks:** APIs with low max concurrent users
4. **Plan scaling:** Increase capacity for failing APIs
5. **Re-test:** Verify improvements after infrastructure changes

## 📖 Full Documentation

For detailed information, see [README.md](README.md):
- Detailed API list
- All parameters explained
- Advanced usage
- Performance baselines
- Optimization recommendations

---

**Ready to test?** Run this now:
```powershell
.\run_capacity_finder.ps1
```

**Questions?** See README.md for full documentation.
