# Quick Start Commands - Chat & Insights APIs
**Run from `docs/jmeter-capacity-tests/` directory in PowerShell**

---

## Baseline Tests (10 threads each)

### 1. Chat Stream API
```powershell
jmeter -n -t 09_chat_stream_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jchat_query="What are the main topics in my documents?" -l "results/09-chat_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### 2. Insights Summary API (Detailed)
```powershell
jmeter -n -t 10_insights_summary_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jdepth="detailed" -l "results/10-summary_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### 3. Insights MCQ API
```powershell
jmeter -n -t 11_insights_mcq_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jtopic="text mining" -l "results/11-mcq_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### 4. Insights Roadmap API
```powershell
jmeter -n -t 12_insights_roadmap_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jgoals="Learn data mining and NLP techniques" -l "results/12-roadmap_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## Scale-up Tests (15 threads)

### Chat - 15 threads
```powershell
jmeter -n -t 09_chat_stream_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=15 -Jramp_up=5 -Jduration=60 -Jchat_query="What are the main topics in my documents?" -l "results/09-chat_15threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### Summary - 15 threads
```powershell
jmeter -n -t 10_insights_summary_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=15 -Jramp_up=5 -Jduration=60 -Jdepth="detailed" -l "results/10-summary_15threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### MCQ - 15 threads
```powershell
jmeter -n -t 11_insights_mcq_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=15 -Jramp_up=5 -Jduration=60 -Jtopic="text mining" -l "results/11-mcq_15threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### Roadmap - 15 threads
```powershell
jmeter -n -t 12_insights_roadmap_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=15 -Jramp_up=5 -Jduration=60 -Jgoals="Learn data mining and NLP techniques" -l "results/12-roadmap_15threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## Aggressive Tests (20 threads - if Phase 2 passes)

### Chat - 20 threads
```powershell
jmeter -n -t 09_chat_stream_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=20 -Jramp_up=5 -Jduration=60 -Jchat_query="What are the main topics in my documents?" -l "results/09-chat_20threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## Existing Test Files (Already Completed)

### Search API (10 threads)
```powershell
jmeter -n -t 08_search_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jsearch_query="mining" -l "results/08-search_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### Index API (10 threads)
```powershell
jmeter -n -t 06_index_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=10 -Jduration=60 -l "results/07-index_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### Process API (10 threads)
```powershell
jmeter -n -t 05_process_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=10 -Jduration=120 -l "results/05-process_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## Check Results

**After each test completes, view results:**

```powershell
# Count lines (requests)
Get-Content "results/09-chat_10threads_*.jtl" | Measure-Object -Line

# View last lines (check status)
Get-Content "results/09-chat_10threads_*.jtl" -Tail 5

# Parse errors
Select-String "500|409|401" "results/09-chat_10threads_*.jtl" | Measure-Object
```

---

## Test Files Reference

| File | API | Endpoint |
|------|-----|----------|
| 09_chat_stream_mapped.jmx | Chat | POST /api/chat/stream |
| 10_insights_summary_mapped.jmx | Insights | POST /api/summary |
| 11_insights_mcq_mapped.jmx | Insights | POST /api/mcq |
| 12_insights_roadmap_mapped.jmx | Insights | POST /api/learning-roadmap |
| 08_search_mapped.jmx | Search | POST /api/search |
| 06_index_mapped.jmx | Index | POST /api/index |
| 05_process_mapped.jmx | Process | POST /api/process |

---

**Expected Duration:** ~70 seconds per test
**Total Baseline Phase:** ~280 seconds (~5 minutes)
**Total Phase 1+2:** ~560 seconds (~10 minutes)

