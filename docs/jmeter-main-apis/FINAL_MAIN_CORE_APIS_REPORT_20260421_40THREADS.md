# Final Consolidated Report - Main Core APIs (Max Accepted 40 Threads)

- Date: 2026-04-21 02:31:02
- Scope: Pipeline core APIs only (upload/process/index + auth/me + processing-stats)
- Input PDF: docs/jmeter-main-apis/data/Text_mining_by_using_Python2025_5pages.pdf
- Decision: 40 threads is accepted; 50-thread validation intentionally skipped per user request.

## Source Artifacts
- Label CSV (threads=10): report-ready/main_apis_labels_20260421_014916.csv
- Dashboard (threads=10): reports/main_apis_focus_20260421_014916/index.html
- Label CSV (threads=20): report-ready/main_apis_labels_20260421_015255.csv
- Dashboard (threads=20): reports/main_apis_focus_20260421_015255/index.html
- Label CSV (threads=30): report-ready/main_apis_labels_20260421_020003.csv
- Dashboard (threads=30): reports/main_apis_focus_20260421_020003/index.html
- Label CSV (threads=40): report-ready/main_apis_labels_20260421_021040.csv
- Dashboard (threads=40): reports/main_apis_focus_20260421_021040/index.html
- Preflight: report-ready/pipeline_endpoint_preflight_20260421014728713.csv

## Thread-Level Pass Summary

| Threads | Total Requests | Failed Requests | Max Error % Across APIs | Worst P95 (ms) | Pass |
|---|---:|---:|---:|---:|---|
| 10 | 60 | 0 | 0 | 7904.35 | True |
| 20 | 120 | 0 | 0 | 7890.85 | True |
| 30 | 180 | 0 | 0 | 7988.4 | True |
| 40 | 240 | 0 | 0 | 8324.8 | True |

## 40-Thread API Metrics (Final Accepted Level)

| API Label | Total | Failed | Error % | Avg (ms) | P95 (ms) | P99 (ms) |
|---|---:|---:|---:|---:|---:|---:|
| GET /api/processing-stats (core) | 40 | 0 | 0 | 232.98 | 304.35 | 371.39 |
| GET /api/users/me | 40 | 0 | 0 | 254.2 | 279.05 | 286.71 |
| POST /api/auth/login-local | 40 | 0 | 0 | 828.82 | 934.3 | 1344.11 |
| POST /api/index (core) | 40 | 0 | 0 | 7956.15 | 8324.8 | 10410.78 |
| POST /api/process (core) | 40 | 0 | 0 | 2203.48 | 2394.5 | 2606.79 |
| POST /api/upload (core) | 40 | 0 | 0 | 1156.05 | 1400.35 | 1997.05 |

## Core Latency Trend (P95 ms)

| API Label | T10 | T20 | T30 | T40 |
|---|---:|---:|---:|---:|
| POST /api/upload (core) | 2023.55 | 2172.85 | 2427.2 | 1400.35 |
| POST /api/process (core) | 2436.45 | 2444 | 2401.05 | 2394.5 |
| POST /api/index (core) | 7904.35 | 7890.85 | 7988.4 | 8324.8 |

## Conclusion

- Validated successful at 10, 20, 30, and 40 concurrent users with 0 failures on all tested core APIs.
- Final accepted concurrency for this campaign: 40 users.
- Primary latency hotspot remains POST /api/index (core) (~8.3s P95 at 40 threads).

## Consolidated Data File

- main_core_apis_consolidated_20260421_10_20_30_40.csv
