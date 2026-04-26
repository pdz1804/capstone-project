# BK-MInD Performance Testing Final Release Report

Version: 1.1  
Date: 2026-04-21  
Scope: Consolidated findings from both JMeter test packages under docs

Repository-safe evidence policy:
- This report references only commit-safe artifacts under docs.
- Metrics from transient local-run artifacts are embedded directly in this document and not linked.

## 1) Executive Summary

This report consolidates all major analysis outputs from:
- non-main API battery testing in [docs/jmeter-experiments](docs/jmeter-experiments)
- main API focused testing in [docs/jmeter-main-apis](docs/jmeter-main-apis)

Final outcome:
- Non-main APIs are highly reliable by error rate, but several generation-heavy endpoints show high tail latency.
- Main search API failures were strongly tied to user readiness/data state, not login/me endpoint instability.
- Main core pipeline APIs (upload, process, index, plus login/me/stats) were validated successfully at 10, 20, 30, and 40 concurrent users with 0 failures.
- Final accepted concurrency boundary for this campaign: 40 users.

Release recommendation:
- Conditional Go for performance release, with readiness-gating and latency-SLO controls applied.

## 2) Source Evidence Included

Primary analysis reports (commit-safe):
- [docs/jmeter-experiments/ANALYSIS_NON_MAIN_APIS_2026-04-20.md](docs/jmeter-experiments/ANALYSIS_NON_MAIN_APIS_2026-04-20.md)
- [docs/jmeter-main-apis/ANALYSIS_REPORT_2026-04-19.md](docs/jmeter-main-apis/ANALYSIS_REPORT_2026-04-19.md)
- [docs/jmeter-main-apis/FINAL_MAIN_CORE_APIS_REPORT_20260421_40THREADS.md](docs/jmeter-main-apis/FINAL_MAIN_CORE_APIS_REPORT_20260421_40THREADS.md)
- [docs/jmeter-main-apis/main_core_apis_consolidated_20260421_10_20_30_40.csv](docs/jmeter-main-apis/main_core_apis_consolidated_20260421_10_20_30_40.csv)

Embedded evidence in this report:
- Ready-user search validation is summarized in Section 4 with full KPI numbers.
- Core pipeline thread-level pass matrix is consolidated in Section 5.

## 3) Workstream A: Non-Main APIs (docs/jmeter-experiments)

### 3.1 Workload and Coverage Summary

Non-main workload coverage used in this report:
- Non-main scoped requests analyzed: 8,436

Canonical battery scenario traffic in non-main scope:
- S01_smoke: 213 requests
- S02_load: 1,978 requests
- S03_concurrency: 846 requests
- S04_stress: 564 requests

Covered endpoint families in non-main scope include:
- platform/status and file-discovery endpoints
- chat and insights endpoints
- quiz and feedback endpoints

Interpretation:
- Coverage is broad across smoke, load, concurrency, and stress profiles.
- Traffic volume is sufficient to characterize response-time behavior on non-main APIs.

### 3.2 Latency Findings

Non-main latency hotspots (weighted/peak indicators from analysis):
- POST /api/chat/stream: weighted avg 18,280.13 ms, max P95 32,650.95 ms
- POST /api/insights/summary: weighted avg 3,256.96 ms, max P95 20,189.2 ms
- POST /api/insights/learning-roadmap: weighted avg 3,122.72 ms, max P95 18,548.55 ms
- POST /api/insights/mcq: weighted avg 1,669.69 ms, max P95 7,671.4 ms

Interpretation:
- Generation-heavy endpoints still present the primary responsiveness risk due to high tail latency.

## 4) Workstream B: Main Search Path Diagnosis (docs/jmeter-main-apis)

### 4.1 Ready-User Validation Profile

Validation scope in this section:
- Cohort: ready/indexed user profile only
- Concurrency levels: 10, 15, 20, 25, 30, 35, 40 threads
- Search label: POST /api/search (retrieval_generation both)
- Data source used for this table: measured values consolidated from the ready-user validation campaign

### 4.2 Ready-User Behavior (Measured)

| Threads | Search Requests | Successful Requests | Success Rate % | Avg Latency (ms) | P95 (ms) | P99 (ms) | Throughput (req/s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 10 | 10 | 10 | 100 | 19,991.30 | 23,122.15 | 23,429.23 | 1.6343 |
| 15 | 15 | 15 | 100 | 26,226.33 | 30,763.30 | 34,605.46 | 9.8168 |
| 20 | 20 | 20 | 100 | 32,789.60 | 51,399.50 | 60,207.90 | 6.2598 |
| 25 | 25 | 25 | 100 | 35,740.60 | 42,409.80 | 50,262.64 | 25.0000 |
| 30 | 30 | 30 | 100 | 37,851.40 | 47,870.10 | 48,483.66 | 1.7777 |
| 35 | 35 | 35 | 100 | 43,426.40 | 53,850.30 | 55,066.84 | 1.5187 |
| 40 | 40 | 40 | 100 | 46,680.18 | 61,526.55 | 62,113.53 | 1.4815 |

### 4.3 Ready-User Latency Characterization

Search P95 summary across ready-user runs:
- Minimum P95: 23,122.15 ms
- Average P95: 44,420.24 ms
- Maximum P95: 61,526.55 ms

Latency trend interpretation:
- Behavior remains stable in terms of successful completion through 40 threads.
- Tail latency increases with concurrency and remains the main optimization priority for this path.

### 4.4 Ready-User Conclusion

- Ready-user search behavior is validated through 40 concurrent users with 100% success in this test profile.
- Next improvement focus for this path should target P95/P99 reduction and tail control at higher concurrency.

## 5) Workstream C: Main Core Pipeline Validation (Upload/Process/Index)

Validation profile:
- Input artifact: Text_mining_by_using_Python2025_5pages.pdf
- Fresh user strategy and preflight gate enabled
- Accepted test levels: 10, 20, 30, 40 threads
- 50-thread validation intentionally skipped in final acceptance decision

Pass summary:
- 10 threads: pass, 0 failed requests across all tested core APIs
- 20 threads: pass, 0 failed requests
- 30 threads: pass, 0 failed requests
- 40 threads: pass, 0 failed requests

Thread-level pass matrix:

| Threads | Total Requests | Failed Requests | Max Error % Across APIs | Worst P95 (ms) | Verdict |
|---|---:|---:|---:|---:|---|
| 10 | 60 | 0 | 0 | 7904.35 | Pass |
| 20 | 120 | 0 | 0 | 7890.85 | Pass |
| 30 | 180 | 0 | 0 | 7988.4 | Pass |
| 40 | 240 | 0 | 0 | 8324.8 | Pass |

40-thread metrics:

| API | Total | Failed | Error % | Avg (ms) | P95 (ms) | P99 (ms) |
|---|---:|---:|---:|---:|---:|---:|
| GET /api/processing-stats (core) | 40 | 0 | 0 | 232.98 | 304.35 | 371.39 |
| GET /api/users/me | 40 | 0 | 0 | 254.2 | 279.05 | 286.71 |
| POST /api/auth/login-local | 40 | 0 | 0 | 828.82 | 934.3 | 1,344.11 |
| POST /api/upload (core) | 40 | 0 | 0 | 1,156.05 | 1,400.35 | 1,997.05 |
| POST /api/process (core) | 40 | 0 | 0 | 2,203.48 | 2,394.5 | 2,606.79 |
| POST /api/index (core) | 40 | 0 | 0 | 7,956.15 | 8,324.8 | 10,410.78 |

Interpretation:
- Core pipeline reliability at 40 concurrent users is validated.
- Primary remaining latency hotspot is indexing.

Core latency trend (P95 ms):

| API | T10 | T20 | T30 | T40 |
|---|---:|---:|---:|---:|
| POST /api/upload (core) | 2023.55 | 2172.85 | 2427.2 | 1400.35 |
| POST /api/process (core) | 2436.45 | 2444 | 2401.05 | 2394.5 |
| POST /api/index (core) | 7904.35 | 7890.85 | 7988.4 | 8324.8 |

## 6) Consolidated Risks and Production Impact

| Risk ID | Risk | Evidence | Severity | Impact |
|---|---|---|---|---|
| R1 | Search failure for unready users | Mixed-user search failures up to 100% at low concurrency; ready-user sweep stable | High | Hard failure in user journey if readiness is not enforced |
| R2 | High tail latency on generation/search | Search P95 up to 61.5s; non-main generation endpoints with high P95/P99 | High | Poor UX and timeout pressure at peak |
| R3 | Index endpoint remains slow under load | Core index P95 ~8.3s at 40 threads | Medium | Slower ingestion/index refresh during busy windows |
| R4 | Sparse transient upstream 502 events | Non-main failures are low but dominated by 502 signatures | Medium | Intermittent instability spikes without proactive monitoring |
| R5 | Limited infra-correlation closure | Need tighter correlation against model and gateway metrics | Medium | Slower incident triage and uncertain root-cause proof |

## 7) Release Readiness Decision

Decision: Conditional Go

Rationale:
- Reliability gates are met for non-main APIs and core pipeline at accepted concurrency level 40.
- Search and generation-heavy tails require operational controls before declaring full performance maturity.

Mandatory release conditions:
1. Enforce readiness gating before search to prevent not-ready user flows from entering heavy retrieval-generation paths.
2. Apply explicit latency and error SLO alerting on search/chat/insights/index endpoints.
3. Maintain autoscaling and endpoint health monitoring for SageMaker and upstream dependencies.

Go-live gate checklist:
- G1: Readiness guard enabled on search path with clear business-response behavior.
- G2: Alerting configured for error-rate and tail latency (P95, P99) on critical endpoints.
- G3: Peak-hour runbook available for generation-path degradation.
- G4: Capacity/health dashboards reviewed for model-inference and gateway layers.
- G5: Post-release canary window planned with rollback criteria.

## 8) Recommended SLO Baseline for Next Cycle

Proposed service objectives:
- Reliability:
  - Search/core critical APIs: error rate <= 1%
  - Non-main APIs: error rate <= 1%
- Latency:
  - search generation path: define staged targets for P95 and P99 by load tier
  - chat/insights endpoints: enforce P95 and P99 budgets with alert thresholds
  - index endpoint: dedicated latency target and monitoring due to highest tail

Recommended initial gate values for next campaign:
- Search generation path: start with P95 <= 20s, P99 <= 30s, then tighten by release cycle.
- Chat stream path: start with P95 <= 25s, P99 <= 35s.
- Insights endpoints: start with P95 <= 12s, P99 <= 20s.
- Core index path: start with P95 <= 9s, P99 <= 12s.

## 9) Next Test Plan (Release Follow-Up)

1. Mixed profile matrix with fixed cohorts:
- all ready users
- mixed ready/unready users
- all unready users

2. Non-main concurrency saturation sweep:
- recommended levels: 20, 40, 60
- measure error, P95, P99, and queue behavior

3. Search latency deep dive:
- correlate request windows with SageMaker model latency, invocation pressure, and gateway metrics

4. Pipeline stress extension:
- extend accepted boundary beyond 40 only after index latency mitigation actions are validated

5. Production-like soak test:
- hold mixed workload for at least 30 to 60 minutes
- evaluate sustained P95/P99 drift, not only short-burst behavior

## 10) Artifact Index

Consolidated final references:
- [docs/PERFORMANCE_TESTING_FINAL_RELEASE_REPORT_2026-04-21.md](docs/PERFORMANCE_TESTING_FINAL_RELEASE_REPORT_2026-04-21.md)
- [docs/jmeter-experiments/ANALYSIS_NON_MAIN_APIS_2026-04-20.md](docs/jmeter-experiments/ANALYSIS_NON_MAIN_APIS_2026-04-20.md)
- [docs/jmeter-main-apis/ANALYSIS_REPORT_2026-04-19.md](docs/jmeter-main-apis/ANALYSIS_REPORT_2026-04-19.md)
- [docs/jmeter-main-apis/FINAL_MAIN_CORE_APIS_REPORT_20260421_40THREADS.md](docs/jmeter-main-apis/FINAL_MAIN_CORE_APIS_REPORT_20260421_40THREADS.md)
- [docs/jmeter-main-apis/main_core_apis_consolidated_20260421_10_20_30_40.csv](docs/jmeter-main-apis/main_core_apis_consolidated_20260421_10_20_30_40.csv)
