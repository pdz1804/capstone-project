# JMeter Experiments Analysis - Non-Main APIs Only (2026-04-20)

## 1) Scope and Objective
This report analyzes the authenticated JMeter experiments under `docs/jmeter-experiments`, while excluding the main API call group used in the focused package.

Objective:
- Keep all other APIs in scope.
- Quantify how stable the non-main API surface is.
- Separate platform-wide behavior from the known main-path failures.

## 2) What We Use To Run The Tests

### Toolchain and execution style
- Apache JMeter non-GUI execution (`-n`) through PowerShell wrappers.
- Main runner script: `run_auth_performance_battery.ps1`.
- Supporting scripts:
  - `setup_test_accounts.ps1`
  - `run_auth_essential_tests.ps1`
  - `run_api_concurrency_sweep.ps1`
- Artifacts generated:
  - Raw JTL and HTML dashboards in `reports/`
  - Summary CSV/MD in `report-ready/`

### Scenario profile used by the standard battery
From runner defaults in `run_auth_performance_battery.ps1`:
- `S01_smoke`: threads=5, ramp_up=20, loops=1
- `S02_load`: threads=20, ramp_up=90, loops=3
- `S03_concurrency`: threads=30, ramp_up=60, loops=2
- `S04_stress`: threads=20, ramp_up=90, loops=2

### Data and account preparation
- Account bootstrap performed by `setup_test_accounts.ps1`.
- Query data from `data/queries.csv`.
- Optional upload payload from `data/sample_upload.md`.

## 3) Data Used In This Analysis

### Data sources
- `report-ready/all_jtl_label_rollup_20260419.csv`
- `report-ready/all_jtl_failure_code_rollup_20260419.csv`
- `report-ready/summary_labels_20260419_193202.csv`
- `report-ready/summary_labels_20260419_211802.csv`
- `report-ready/summary_labels_20260419_221347.csv`

### Exclusion set (main APIs calls removed)
The following labels were excluded from KPI calculations in this report:
- `Essential Authenticated API Journey`
- `POST /api/auth/login-local`
- `GET /api/users/me`
- `POST /api/search (retrieval_generation text)`
- `POST /api/search (retrieval_generation both)`
- `GET /api/processing-stats`
- `POST /api/upload (core)`
- `POST /api/process (core)`
- `POST /api/index (core)`

## 4) What The Tests Include (After Exclusion)
Remaining non-main APIs include:
- `GET /api/status`
- `GET /api/files?quick=true`
- `GET /api/files-with-metadata`
- `GET /api/search/generation-models`
- `POST /api/insights/summary`
- `POST /api/insights/learning-roadmap`
- `POST /api/insights/mcq`
- `GET /api/quiz-results?limit=20`
- `POST /api/quiz-results`
- `POST /api/chat/stream`
- `GET /api/chat/sessions?limit=20`
- `GET /api/feedback?limit=20`
- `POST /api/feedback (general)`
- `GET /api/health`
- `GET /api/input-file-url` (conditional)

## 5) Detailed Results

### A. Portfolio-level split
From all label rollups:
- All labels combined:
  - total requests: `11708`
  - failed requests: `1551`
  - error rate: `13.2474%`
- Excluded main-call set only:
  - total requests: `3272`
  - failed requests: `1538`
  - error rate: `47.0049%`
- Non-main set only (this report scope):
  - total requests: `8436`
  - failed requests: `13`
  - error rate: `0.1541%`

Key interpretation:
- Almost all failures in the global experiments are concentrated in the excluded main-call set.
- The non-main API surface is broadly stable by error rate.

### B. Scenario trend for non-main APIs (canonical battery summaries)
Using `summary_labels_20260419_*.csv`:
- `S01_smoke`: 213 requests, 0 failed, 0%
- `S02_load`: 1978 requests, 0 failed, 0%
- `S03_concurrency`: 846 requests, 0 failed, 0%
- `S04_stress`: 564 requests, 0 failed, 0%

This indicates non-main endpoints stayed error-free in canonical standard runs.

### C. Non-main failure signatures across all available runs
From `all_jtl_failure_code_rollup_20260419.csv` after exclusion:
- `POST /api/chat/stream`: 3 failures, `502 Bad Gateway`
- `GET /api/quiz-results?limit=20`: 2 failures, `502 Bad Gateway`
- `POST /api/insights/learning-roadmap`: 2 failures, `502 Bad Gateway`
- `POST /api/insights/summary`: 2 failures, `502 Bad Gateway`
- `GET /api/chat/sessions?limit=20`: 2 failures, `502 Bad Gateway`
- `GET /api/status`: 1 failure, `502 Bad Gateway`
- `GET /api/feedback?limit=20`: 1 failure, `502 Bad Gateway`

Interpretation:
- Remaining failures are sparse and mostly transient upstream-style `502` events.

### C1. Hypothesis: ECS memory pressure and autoscaling churn
- A plausible explanation is ECS tasks hitting memory limits, causing task replacement/scale-out windows that surface as `502`.
- This is currently a hypothesis, not a proven root cause, because these runs do not yet correlate request timestamps with ECS and ALB metrics.
- To confirm or reject this hypothesis, correlate failure windows with:
  - ECS service metrics: `MemoryUtilization`, `MemoryReservation`, `RunningTaskCount`, `PendingTaskCount`
  - ALB metrics: `HTTPCode_Target_5XX_Count`, `TargetResponseTime`
  - Container/task logs for `OOMKilled`, restart, and health-check failure events

### D. Latency hotspots among non-main APIs
From weighted aggregation over canonical summary-label outputs:
- `POST /api/chat/stream`: weighted avg `18280.13 ms`, max P95 `32650.95 ms`
- `POST /api/insights/summary`: weighted avg `3256.96 ms`, max P95 `20189.2 ms`
- `POST /api/insights/learning-roadmap`: weighted avg `3122.72 ms`, max P95 `18548.55 ms`
- `POST /api/insights/mcq`: weighted avg `1669.69 ms`, max P95 `7671.4 ms`

Even with low error, generative endpoints still show heavy latency tails.

## 6) Performance Testing Analysis

### Reliability
- Non-main APIs are currently reliable by error rate (0.1541% across all runs, 0% in canonical standard battery).
- The observed non-main failures are small in absolute count and largely `502`-type transient events.

### Responsiveness
- Reliability is not equal to responsiveness.
- Chat and insights endpoints have high tail latency and can degrade user experience during heavier load even when error rate stays near zero.

## 7) Conclusion About Current Application Status (Non-Main API View)

### Current status
- Good:
  - Non-main API reliability is strong.
  - Core navigation/support endpoints are operationally stable.
- Bad:
  - Tail latency remains high for generation-heavy non-main endpoints.

### Practical user-capacity statement (non-main only)
- For non-main APIs, current evidence supports operational stability under tested smoke/load/concurrency/stress profiles.
- Capacity risk for this scope is latency inflation rather than immediate error bursts.

### What to do in low-peak time
1. Keep current architecture and monitor latency percentiles.
2. Focus on reducing tail latency of chat/insights endpoints.

### What to do in high-peak time
1. Apply stricter timeout and retry budgets for upstream dependencies.
2. Prioritize traffic shaping for generation-heavy endpoints.
3. Track P95/P99 alerts, not only error-rate alerts.
4. Add ECS memory pressure alarms and scale-protection thresholds to reduce replacement churn.

## 8) Recommended Next Tests
1. Run non-main-only concurrency sweep with larger thread levels (for example 20, 40, 60) to map latency saturation points.
2. Add correlation against cloud metrics (ModelLatency, InvocationsPerInstance, gateway metrics) for `502` periods.
3. Define non-main SLO gates combining:
   - error rate target
   - P95/P99 latency target
