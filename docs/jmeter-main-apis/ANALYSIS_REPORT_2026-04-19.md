# JMeter Main APIs Analysis Report (Updated 2026-04-20)

## 1) Scope and Goal
This report analyzes the focused main-APIs test package under `docs/jmeter-main-apis` using the latest results in `report-ready`.

Primary objective in this update:
- Determine why the previous mixed-user concurrency runs failed.
- Re-validate actual concurrency capacity after preserving full SageMaker model environment variables.
- Provide an operational conclusion for low-peak and high-peak periods.

## 2) What We Used To Run Tests

### Toolchain and execution mode
- Apache JMeter `5.6.3` test plan format (`BKMind_Main_APIs_Focus.jmx` header).
- Non-GUI execution through `run_main_apis_focus_tests.ps1`.
- Java headless launch path used by runner:
  - `java -Djava.awt.headless=true -jar ApacheJMeter.jar`
- Runner stabilization:
  - Runtime overrides are generated into `reports/main_apis_focus_<timestamp>.runtime.properties`.
  - JMeter receives properties through `-q` files instead of long `-J` command chains.
  - Bounded retry policy: `-MaxRetries` (default `2`).

### Infrastructure context during this phase
- Backend target: `https://k2p-bkmind-learning-platform.com`.
- Runtime in use: AWS SageMaker inference path enabled (from prior runtime probe flow).
- Endpoint under test: `phase2-multimodal-rt`.

### SageMaker model environment preserved for redeploy
The redeploy used full previous model environment plus concurrency controls, including:
- `AWS_REGION=us-west-2`
- `COLQWEN_MODEL=vidore/colqwen2-v1.0`
- `COLQWEN_QUANTIZATION=8bit`
- `DOCLING_ENABLE_VLM=false`
- `DOCLING_EXPORT_IMAGES=false`
- `DOCLING_EXPORT_TABLES=false`
- `DOCLING_OCR_ENGINE=rapidocr`
- `WHISPER_CONDITION_ON_PREVIOUS_TEXT=false`
- `WHISPER_MODEL=base`
- `WHISPER_TEMPERATURE_SCHEDULE=0.0`
- `WHISPER_WORD_TIMESTAMPS=false`
- `UNIFIED_MAX_CONCURRENT_GPU_OPS=10`
- `COLQWEN_MAX_CONCURRENT_INFERENCES=10`

## 3) What Was Used In Tests

### Input data and users
- User source: `docs/jmeter-main-apis/data/users.csv`.
- Query source: `docs/jmeter-main-apis/data/main_queries.csv`.
- For diagnosis, an explicit user-readiness check was performed via:
  - `GET /api/status?fresh=false`
  - `GET /api/files-with-metadata`

Observed readiness state:
- `admin@local.dev`: `ready=true`, files present (`25`), processed files present (`25`).
- `perfuser01@local.dev`: `ready=false`, files `0`, processed files `0`.

This is the decisive evidence behind mixed-user failures.

### Test profile used for concurrency verdict
- Enabled APIs:
  - `POST /api/auth/login-local`
  - `GET /api/users/me`
  - `POST /api/search (retrieval_generation both)`
- Disabled APIs:
  - `upload/process/index` pipeline calls
- Loops: `1`

### Coverage gap for process/index semantics
- Current concurrency verdict does not cover `POST /api/process (core)` and `POST /api/index (core)` behavior.
- In the JMX test plan, pipeline APIs run in a separate path: first thread only + once-only controller.
- Correctness of this path is stateful and must follow strict order per user data state:
  - `process` is valid for files that are new and not yet processed.
  - `index` is valid for files already processed and not yet indexed.
- Because of this dependency chain, a dedicated run with a fresh user is required for reliable process/index validation.

## 4) What The Tests Include

### Mixed-user sweep (existing production-like user mix)
- Artifact: `report-ready/concurrency_3mainapis_20260420_012856.csv`
- Threads tested: `1..10`

### Admin-only counterfactual sweep (single ready user)
- Artifact: `report-ready/concurrency_adminonly_max_20260420_021539.csv`
- Threads tested: `10,15,20,25,30,35,40`

## 5) Detailed Results

### A. Mixed-user sweep (1..10)
From `concurrency_3mainapis_20260420_012856.csv`:
- `login_err=0` at all tested thread levels.
- `me_err=0` at all tested thread levels.
- `search_err` remains extremely high:
  - `1 thread`: `100%` (`1/1` failed)
  - `10 threads`: `90%` (`9/10` failed)

Interpretation:
- Failure is isolated to search path, not auth endpoints.
- Because one or more users are not ready/indexed, search fails immediately for those users.

### B. Admin-only sweep (10..40)
From `concurrency_adminonly_max_20260420_021539.csv`:
- `run_exit_code=0` for all runs.
- `search_err=0` for all tested thread levels through `40`.
- Maximum zero-error threads tested: `40`.

Latency behavior (search endpoint):
- `P95` range: `23122.15 ms` to `61526.55 ms`.
- Average P95 across tested levels: `44420.24 ms`.

This means capacity improved for correctness (error-free) but latency is still very high under load.

### C. Why previous verdict looked contradictory
Earlier run (`concurrency_adminonly_max_20260420_014740.csv`) showed errors at `20` threads.
Latest rerun with corrected environment and stabilized setup (`...021539.csv`) shows `0%` error through `40` threads.

Current best evidence should prioritize the latest validated run set.

## 6) Performance Analysis

### Root cause of mixed-user failures
The dominant cause is user data readiness, not immediate endpoint crash:
- Ready user (`admin`) succeeds under high concurrency.
- Not-ready user (`perfuser01`) has no files/index and fails search.

So the previous "search cannot handle concurrency" conclusion was incomplete. The correct statement is:
- Search cannot succeed for users that are not indexed/ready.
- For ready/indexed users, search can handle at least `40` concurrent requests in this one-shot test profile.

### Quality of service under load
Even with `0%` error in admin-only runs, search P95 reaches `61.5s` at 40 threads.

Therefore:
- Reliability improved.
- User-perceived responsiveness is still weak at higher concurrency.

## 7) Conclusion and Current Application Status

### Current practical capacity (based on measured evidence now)
1. Ready/indexed users:
- At least `40` concurrent users tested with `0%` search error in the focused profile.

2. Not-ready users:
- Search can fail immediately even at very low concurrency.
- Effective concurrent capacity for those users is not meaningful until readiness is fixed.

### What is good now
- Authentication and `/api/users/me` are stable in all sweeps.
- Main search path is error-free for ready user profile through 40 threads.

### What is still bad now
- Search latency tail is high (`P95` tens of seconds) as concurrency increases.
- Readiness contract is not enforced clearly enough before search, causing hard failures for unprepared users.

## 8) Operational Guidance

### Low peak time
- Keep current architecture.
- Prioritize onboarding flow quality:
  - Ensure upload/process/index completion before allowing search-heavy actions.

### High peak time
- Enforce readiness gating before search (return clear 4xx/business response instead of backend 500-style failure behavior).
- Keep autoscaling enabled and monitor:
  - `SageMakerVariantInvocationsPerInstance`
  - model latency metrics
- Consider separating heavy generation path from normal user path if peak tail latency remains high.

## 9) Immediate Next Actions
1. Add explicit pre-search readiness checks in backend/API contract.
2. Run mixed-profile test matrix with fixed user cohorts:
   - all ready users,
   - mixed ready/unready users,
   - all unready users.
3. Run a dedicated pipeline correctness test with a fresh user:
  - upload a brand-new file,
  - process with `force=false`,
  - index with `force=false`,
  - verify processing/index stats and no duplicate-state failures.
4. Add latency SLO gates (not only error-rate gates), for example:
   - pass: error `<= 1%` and search `P95 <= target`.
