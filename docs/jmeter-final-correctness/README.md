
# Final JMeter Performance Testing - Correctness Focus

## Overview

This package implements **correct concurrent user testing** with proper thread spawning strategy:

- **Thread Ramp-Up:** Threads are spawned gradually over a time period (e.g., 10 threads over 60 seconds = 1 thread every 6 seconds)
- **Concurrent Load Testing:** Tests APIs under sustained concurrent load to measure latency and throughput metrics
- **Error Boundary Testing:** Monitors response times and errors to identify the optimal concurrent user count
- **Retrieval-Only Search:** Tests `/api/search` with both retrieval modes (`retrieval_generation` and `retrieval_only`) - NO generation mode

## Test Structure

### APIs Tested

1. **Authentication:**
   - `POST /api/auth/login-local` - Baseline auth (1 thread only)

2. **Search APIs (Concurrent Load):**
   - `POST /api/search (retrieval_generation)` - Text mode with retrieval + generation
   - `POST /api/search (retrieval_only)` - Text mode with retrieval only
   - Testing at: 5, 10, 20, 30 concurrent users with ramp-up

3. **Core Pipeline APIs (Single thread initialization):**
   - `POST /api/upload` - File upload (1 thread for setup)
   - `POST /api/process` - Document processing (1 thread)
   - `POST /api/index` - Index operation (1 thread)
   - `GET /api/processing-stats` - Stats polling

### Test Scenarios

**Scenario 1: Baseline (5 Concurrent Users)**
- Duration: 120 seconds
- Threads: 5
- Ramp-up: 30 seconds (1 thread every 6 seconds)
- Loops: 5 per thread
- Metrics: Response time, throughput, error rate

**Scenario 2: Moderate Load (10 Concurrent Users)**
- Duration: 180 seconds
- Threads: 10
- Ramp-up: 60 seconds (1 thread every 6 seconds)
- Loops: 5 per thread
- Metrics: p50, p95, p99 latency, concurrent success rate

**Scenario 3: Higher Load (20 Concurrent Users)**
- Duration: 240 seconds
- Threads: 20
- Ramp-up: 120 seconds (1 thread every 6 seconds)
- Loops: 3 per thread
- Metrics: Monitor for degradation, error emergence

**Scenario 4: Peak Load (30 Concurrent Users)**
- Duration: 300 seconds
- Threads: 30
- Ramp-up: 180 seconds (1 thread every 6 seconds)
- Loops: 2 per thread
- Metrics: Identify breaking point, max sustainable throughput

## Files

- `BKMind_Final_Correctness_Search.jmx` - JMeter test plan with proper thread spawning
- `run_final_correctness_tests.ps1` - PowerShell runner for all scenarios
- `data/users.csv` - Pre-generated test user credentials
- `data/search_queries.csv` - Diverse search queries
- `reports/` - Output reports and metrics

## How to Run

```powershell
# Run all test scenarios with proper reporting
.\run_final_correctness_tests.ps1 -Threads 5,10,20,30 -RampUpSeconds 30,60,120,180

# Run single scenario
.\run_final_correctness_tests.ps1 -Threads 10 -RampUpSeconds 60 -Duration 180

# Run with custom host
.\run_final_correctness_tests.ps1 -Host "localhost" -Port "8080" -Protocol "http" -Threads 5
```

## Key Testing Principles

1. **Gradual Thread Spawning:** Threads spawn evenly over ramp-up period (avoids thundering herd)
2. **Sustained Load:** Once ramped up, threads stay active for full duration
3. **Realistic Think Time:** Small random delays between requests
4. **Error Tracking:** Failures are tracked separately from latency
5. **Both Retrieval Modes:** Search API tests with and without generation
6. **No Mode Generation:** Focused on retrieval performance, not generation speed

## Expected Outcomes

- Identify concurrent user capacity before SLA breach
- Measure latency distribution (p50, p95, p99)
- Confirm search APIs handle retrieval-only mode correctly
- Generate performance baseline for monitoring
