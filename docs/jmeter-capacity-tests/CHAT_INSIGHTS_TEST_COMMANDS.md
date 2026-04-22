# Chat & Insights APIs - Capacity Test Commands
**Windows PowerShell - Run from `docs/jmeter-capacity-tests/` directory**

---

## Chat Stream API (09_chat_stream_mapped.jmx)

### Chat - 10 Threads (Baseline)
```powershell
jmeter -n -t 09_chat_stream_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jchat_query="What are the main topics in my documents?" -l "results/09-chat_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### Chat - 15 Threads (Scale-up)
```powershell
jmeter -n -t 09_chat_stream_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=15 -Jramp_up=5 -Jduration=60 -Jchat_query="What are the main topics in my documents?" -l "results/09-chat_15threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### Chat - 20 Threads (Aggressive)
```powershell
jmeter -n -t 09_chat_stream_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=20 -Jramp_up=5 -Jduration=60 -Jchat_query="What are the main topics in my documents?" -l "results/09-chat_20threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## Insights Summary API (10_insights_summary_mapped.jmx)

### Summary - 10 Threads (Baseline - Detailed)
```powershell
jmeter -n -t 10_insights_summary_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jdepth="detailed" -l "results/10-summary_detailed_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### Summary - 15 Threads (Detailed)
```powershell
jmeter -n -t 10_insights_summary_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=15 -Jramp_up=5 -Jduration=60 -Jdepth="detailed" -l "results/10-summary_detailed_15threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### Summary - 10 Threads (Brief - Lighter Load)
```powershell
jmeter -n -t 10_insights_summary_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jdepth="brief" -l "results/10-summary_brief_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## Insights MCQ API (11_insights_mcq_mapped.jmx)

### MCQ - 10 Threads (Baseline - Text Mining)
```powershell
jmeter -n -t 11_insights_mcq_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jtopic="text mining" -l "results/11-mcq_mining_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### MCQ - 15 Threads (Scale-up)
```powershell
jmeter -n -t 11_insights_mcq_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=15 -Jramp_up=5 -Jduration=60 -Jtopic="text mining" -l "results/11-mcq_mining_15threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### MCQ - 10 Threads (Python)
```powershell
jmeter -n -t 11_insights_mcq_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jtopic="python programming" -l "results/11-mcq_python_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## Insights Learning Roadmap API (12_insights_roadmap_mapped.jmx)

### Roadmap - 10 Threads (Baseline)
```powershell
jmeter -n -t 12_insights_roadmap_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jgoals="Learn data mining and NLP techniques" -l "results/12-roadmap_mining_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### Roadmap - 15 Threads (Scale-up)
```powershell
jmeter -n -t 12_insights_roadmap_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=15 -Jramp_up=5 -Jduration=60 -Jgoals="Learn data mining and NLP techniques" -l "results/12-roadmap_mining_15threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### Roadmap - 10 Threads (Data Science)
```powershell
jmeter -n -t 12_insights_roadmap_mapped.jmx -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=10 -Jramp_up=5 -Jduration=60 -Jgoals="Master data science and machine learning" -l "results/12-roadmap_datascience_10threads_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

---

## Recommended Test Sequence

Run in this order to identify capacity bottlenecks:

### Phase 1: Baselines (10 threads each)
1. Chat Stream - 10 threads
2. Summary (detailed) - 10 threads
3. MCQ - 10 threads
4. Roadmap - 10 threads

### Phase 2: Scale-up (15 threads)
5. Chat Stream - 15 threads
6. Summary (detailed) - 15 threads
7. MCQ - 15 threads
8. Roadmap - 15 threads

### Phase 3: Aggressive (20 threads - Chat only, if Phase 2 passes)
9. Chat Stream - 20 threads

---

## Parameter Reference

| Parameter | Example | Meaning |
|-----------|---------|---------|
| `-t FILE` | `09_chat_stream_mapped.jmx` | Test plan file |
| `-Jthreads=N` | `10` | Concurrent users |
| `-Jramp_up=N` | `5` | Seconds to spawn all threads |
| `-Jduration=N` | `60` | Seconds to hold load |
| `-Jchat_query=` | `"What are the main topics?"` | Chat query text |
| `-Jdepth=` | `detailed\|brief\|comprehensive` | Summary depth level |
| `-Jtopic=` | `"text mining"` | MCQ topic |
| `-Jgoals=` | `"Learn data mining..."` | Roadmap learning goal |
| `-l "results/..."` | Output file | Where to save results |

---

## Expected Outcomes

| API | 10 Threads | 15 Threads | 20 Threads |
|-----|-----------|-----------|-----------|
| Chat | 0-5% errors | 5-15% errors | 15-30% errors |
| Summary (detailed) | 0-3% errors | 5-10% errors | 10-25% errors |
| MCQ | 0-2% errors | 3-8% errors | 8-20% errors |
| Roadmap | 0-2% errors | 2-5% errors | 5-15% errors |

---

## Success Criteria

✓ **0-2% error rate** = API handles load reliably
⚠️ **2-10% error rate** = Acceptable but at capacity edge
❌ **>10% error rate** = Needs optimization or load shedding

---

## Notes

- Each test takes ~70 seconds (5s ramp-up + 60s load + JMeter overhead)
- All tests authenticate per-user using CSV data
- Tests are read-only (no data modification)
- AgentCore/Bedrock APIs may be rate-limited on concurrent calls
