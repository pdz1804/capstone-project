# BK-MInD JMeter Experiments (Authenticated Core APIs)

This folder contains the authenticated JMeter test package for BK-MInD core APIs, including:
- essential run,
- multi-scenario performance battery,
- detailed result extraction,
- optional Bedrock analysis of result files,
- API max-concurrency sweep.

For focused validation of high-error APIs plus `upload/process/index`, use:
- `docs/jmeter-main-apis/README.md`

## Folder

`docs/jmeter-experiments`

## Package Contents

- `BKMind_Essential_APIs_Auth.jmx`: main authenticated JMeter test plan.
- `setup_test_accounts.ps1`: creates/verifies admin + test users and writes `data/users.csv`.
- `run_auth_essential_tests.ps1`: single-run authenticated test (non-GUI) with detailed JTL capture.
- `run_auth_performance_battery.ps1`: scenario battery with summary exports and optional Bedrock analysis.
- `run_api_concurrency_sweep.ps1`: thread-level sweep to estimate max supported concurrency per API label.
- `cleanup_test_outputs.ps1`: cleanup utility for raw outputs.
- `data/queries.csv`: rotating test prompts.
- `data/sample_upload.md`: optional upload payload.
- `report-ready/`: report-ready summary outputs.
- `reports/`: raw JMeter artifacts (JTL + HTML dashboards).

## API Coverage (Core Left Navigation)

| Left nav feature | Covered APIs |
|---|---|
| Dashboard | `GET /api/status`, `GET /api/health` |
| Knowledge Management - Upload Files | `GET /api/files?quick=true`, `GET /api/files-with-metadata`, optional `POST /api/upload` |
| Knowledge Management - Run Pipeline | `GET /api/processing-stats`, optional `POST /api/process` |
| Knowledge Management - Build Index | optional `POST /api/index` |
| Knowledge Management - Knowledge Explorer | `POST /api/search` (text + both), `GET /api/search/generation-models` |
| Knowledge Management - Knowledge Dashboard | `GET /api/files-with-metadata`, `GET /api/status` |
| Lecture Viewer | conditional `GET /api/input-file-url` |
| Learning Path | `POST /api/insights/summary`, `POST /api/insights/learning-roadmap`, `POST /api/insights/mcq`, `GET /api/quiz-results`, `POST /api/quiz-results` |
| Chat Assistant | `POST /api/chat/stream`, `GET /api/chat/sessions?limit=20` |
| Feedbacks | `GET /api/feedback?limit=20`, `POST /api/feedback` |
| Profile/Auth | `POST /api/auth/login-local`, `GET /api/users/me` |

## Standard Test Flow

1. Go to folder and clear stale JVM override (important)

```powershell
cd docs/jmeter-experiments
Remove-Item Env:JVM_ARGS -ErrorAction SilentlyContinue
Remove-Item Env:HEAP -ErrorAction SilentlyContinue
```

2. Prepare users

```powershell
.\setup_test_accounts.ps1
```

3. Run performance battery and keep detailed + summary outputs

```powershell
.\run_auth_performance_battery.ps1 -Profile standard
```

4. Optional: include mutation endpoints (`/api/upload`, `/api/process`, `/api/index`)

```powershell
.\run_auth_performance_battery.ps1 -Profile standard -EnableMutationApis
```

### Resume a stopped battery run (no re-run of completed scenarios)

If a run stops at mid-scenarios, resume with the same run ID. The script reuses existing non-empty `reports/<runid>_Sxx_*.jtl` files and runs only missing scenarios.

```powershell
cd docs/jmeter-experiments
Remove-Item Env:JVM_ARGS -ErrorAction SilentlyContinue
Remove-Item Env:HEAP -ErrorAction SilentlyContinue
.\run_auth_performance_battery.ps1 -Profile standard -SkipAccountSetup -RunId 20260419_221347
```

To force re-running completed scenarios for that run ID, add `-RerunCompletedScenarios`.

### Quick smoke check before long runs

```powershell
cd docs/jmeter-experiments
Remove-Item Env:JVM_ARGS -ErrorAction SilentlyContinue
Remove-Item Env:HEAP -ErrorAction SilentlyContinue
.\run_auth_essential_tests.ps1 -Threads 5 -RampUp 20 -Loops 1
```

## Detailed and Summary Outputs

### Detailed outputs (for later deep check)

Generated in `reports/`:
- scenario JTL files (`*.jtl`) with per-sample details,
- JMeter HTML dashboards per scenario.

The scripts force detailed JTL fields, including latency/connect-time/thread counts/bytes/hostname and response payload on error.

### Summary outputs (report-ready)

Generated in `report-ready/`:
- `summary_<timestamp>.csv`: scenario-level KPI summary.
- `summary_labels_<timestamp>.csv`: API-label-level KPI summary.
- `summary_<timestamp>.md`: markdown summary table.

## Bedrock Analysis Step

You can add an analysis step using an Amazon Bedrock model directly after KPI export.

```powershell
cd docs/jmeter-experiments
Remove-Item Env:JVM_ARGS -ErrorAction SilentlyContinue
Remove-Item Env:HEAP -ErrorAction SilentlyContinue
.\run_auth_performance_battery.ps1 `
  -Profile standard `
  -AnalyzeWithBedrock `
  -BedrockRegion us-west-2 `
  -BedrockModelId us.anthropic.claude-haiku-4-5-20251001-v1:0
```

Output:
- `report-ready/bedrock_analysis_<timestamp>.md`

If Bedrock fails, the run still keeps JMeter outputs and KPI summaries (unless `-FailIfBedrockAnalysisFails` is set).

## API Maximum Concurrency Test

Run the dedicated concurrency sweep to estimate maximum sustainable concurrency per API label.

```powershell
cd docs/jmeter-experiments
Remove-Item Env:JVM_ARGS -ErrorAction SilentlyContinue
Remove-Item Env:HEAP -ErrorAction SilentlyContinue
.\run_api_concurrency_sweep.ps1 `
  -ConcurrencyLevels "5,10,20,30,40,50,60,80" `
  -Loops 1 `
  -MaxErrorRatePct 5 `
  -MaxP95LatencyMs 15000
```

Outputs:
- `report-ready/concurrency_labels_<timestamp>.csv`: per-label metrics at each thread level.
- `report-ready/concurrency_max_supported_<timestamp>.csv`: inferred max supported threads per API label.
- `report-ready/concurrency_summary_<timestamp>.md`: concise report.
- `reports/concurrency/*`: JTL + HTML dashboards for each thread level.

## Why Avg vs P95/P99 Can Be Very Different

Your sample:
- `POST /api/insights/summary`
- `POST /api/insights/learning-roadmap`
- `POST /api/insights/mcq`

can show large gaps because:
- these APIs are generation-heavy and tail latency is naturally high,
- with very small sample size (example: only `5` requests), p95/p99 are strongly influenced by the slowest response,
- one or two slow responses can keep average moderate while pushing p95/p99 high.

Tracking implementation in scripts:
- p95/p99 are computed from JTL `elapsed` values using interpolated percentile calculation,
- min/max are also exported to improve interpretation of tail behavior,
- per-label totals are kept so you can validate sample size before trusting percentiles.

## Cleanup (Optional)

Only run cleanup when you no longer need raw JTL/HTML files.

```powershell
cd docs/jmeter-experiments
.\cleanup_test_outputs.ps1
```

## Notes

- For serious load testing, keep non-GUI mode only.
- If JMeter is not in PATH, pass `-JMeterBin "C:\path\to\apache-jmeter\bin\jmeter.bat"`.
- On Windows PowerShell, always clear both `JVM_ARGS` and `HEAP` before running these scripts.
- Recommended pre-run guard:

```powershell
Remove-Item Env:JVM_ARGS -ErrorAction SilentlyContinue
Remove-Item Env:HEAP -ErrorAction SilentlyContinue
```
- If your prompt already shows `...\docs\jmeter-experiments>`, do not run `cd docs/jmeter-experiments` again.
- If a run fails with transient cloud/runtime behavior, resume with the same `-RunId` so completed scenarios are reused and only missing scenarios run.
