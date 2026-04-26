# Ingestion Job Capacity Report (Process / Index / Search)

Date: 2026-04-20  
Scope: 20 concurrent users, 1 main request per user, 60-second test window profile

## 1) Test Profile Used

- Threads: `20`
- Ramp-up: `5s`
- Process/Index polling profile: `poll_max_checks=30`, `poll_interval_ms=2000` (~60s polling window)
- Search profile: no async polling (synchronous main API path)
- Success criterion for main API acceptance: response code `2xx`

Executed JMeter files:
- `docs/jmeter-capacity-tests/05_process_mapped_1loop.jmx`
- `docs/jmeter-capacity-tests/06_index_mapped_1loop.jmx`
- `docs/jmeter-capacity-tests/08_search_mapped_1loop.jmx`

Result artifacts:
- `docs/jmeter-capacity-tests/results_05_process_poll_60s.jtl`
- `docs/jmeter-capacity-tests/results_06_index_poll_60s.jtl`
- `docs/jmeter-capacity-tests/results_08_search_20.jtl`

## 2) Main API Acceptance Results (JMeter)

All three main APIs reached `20/20` accepted requests (`2xx`):

- Process accepted (`POST /api/process (force=true)`): `20/20`
- Index accepted (`POST /api/index`): `20/20`
- Search accepted (`POST /api/search`): `20/20`

## 3) API Request Latency Metrics (JMeter Sampler Latency)

These values are request-level latency from JMeter for the main sampler only.

| API | Threads | Requests | Successful Requests | Success Rate % | Avg Latency (ms) | P95 (ms) | P99 (ms) | Throughput (req/s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| POST /api/process (force=true) | 20 | 20 | 20 | 100.00 | 204.95 | 218 | 219 | 4.70 |
| POST /api/index | 20 | 20 | 20 | 100.00 | 1161.85 | 1991 | 2140 | 3.45 |
| POST /api/search | 20 | 20 | 20 | 100.00 | 17374.15 | 18853 | 19612 | 3.46 |

## 4) Correct Latency Definition for Ingestion Jobs

For `process` and `index`, the correct end-to-end latency is **job start -> job done**.

Use backend completion logs:
- start: job accepted/created
- end: `... job completed ... elapsed_sec=...`

Therefore:
- **Process true latency** = backend `elapsed_sec` from process completion log
- **Index true latency** = backend `elapsed_sec` from index completion log

Important:
- JMeter sampler latency (`POST /api/process`, `POST /api/index`) is only API acceptance time.
- It is **not** job completion latency.

## 5) Why Some JMeter Errors Appeared in Polling Runs

When run duration is shorter than actual job completion time, final status assertions can fail:
- status sampler may still see `queued/running`
- final assertion expects `completed`

This does not necessarily mean main API acceptance failed.

## 6) Required Final Step for True Job Latency Table

To finalize true ingestion latency metrics (Avg/P95/P99 from start->done), export ECS/CloudWatch logs for the same run window and parse `elapsed_sec` values.

### 6.1 Known Values Already Available

From JMeter accepted-request results:

| API | Jobs Accepted |
|---|---:|
| PROCESS | 20 |
| INDEX | 20 |

### 6.2 Run This Now (PowerShell)

1) Export ECS logs to:
- `docs/jmeter-capacity-tests/ecs_run_2026-04-20.log`

2) Run this command block:

```powershell
$log = "docs/jmeter-capacity-tests/ecs_run_2026-04-20.log"
if (!(Test-Path $log)) { Write-Host "Missing log file: $log"; exit 1 }

# Accepted counts (from JMeter)
$procAccepted = (Import-Csv "docs/jmeter-capacity-tests/results_05_process_poll_60s.jtl" |
  Where-Object { $_.label -eq "POST /api/process (force=true)" -and $_.responseCode -like "20*" }).Count
$idxAccepted = (Import-Csv "docs/jmeter-capacity-tests/results_06_index_poll_60s.jtl" |
  Where-Object { $_.label -eq "POST /api/index" -and $_.responseCode -like "20*" }).Count

function Pct($arr,$p){
  if($arr.Count -eq 0){ return 0 }
  $i=[math]::Ceiling($p*$arr.Count)-1
  if($i -lt 0){$i=0}
  if($i -ge $arr.Count){$i=$arr.Count-1}
  [math]::Round($arr[$i],3)
}

# Adjust PROCESS regex if your completion phrase differs.
$proc = Get-Content $log | ForEach-Object {
  if ($_ -match '(?i)process.*job completed:.*elapsed_sec=([0-9]+(?:\.[0-9]+)?)') { [double]$matches[1] }
}
$idx = Get-Content $log | ForEach-Object {
  if ($_ -match 'Index_all job completed:.*elapsed_sec=([0-9]+(?:\.[0-9]+)?)') { [double]$matches[1] }
}

$proc = @($proc | Sort-Object)
$idx = @($idx | Sort-Object)

$rows = @(
  [pscustomobject]@{
    API = "PROCESS"
    JobsAccepted = $procAccepted
    JobsCompleted = $proc.Count
    CompletionRatePct = if($procAccepted){ [math]::Round(($proc.Count*100.0)/$procAccepted,2) } else { 0 }
    AvgJobLatencySec = if($proc.Count){ [math]::Round((($proc|Measure-Object -Average).Average),3) } else { 0 }
    P95Sec = Pct $proc 0.95
    P99Sec = Pct $proc 0.99
  }
  [pscustomobject]@{
    API = "INDEX"
    JobsAccepted = $idxAccepted
    JobsCompleted = $idx.Count
    CompletionRatePct = if($idxAccepted){ [math]::Round(($idx.Count*100.0)/$idxAccepted,2) } else { 0 }
    AvgJobLatencySec = if($idx.Count){ [math]::Round((($idx|Measure-Object -Average).Average),3) } else { 0 }
    P95Sec = Pct $idx 0.95
    P99Sec = Pct $idx 0.99
  }
)

$rows | Format-Table -AutoSize
$rows | Export-Csv -NoTypeInformation "docs/jmeter-capacity-tests/true_job_latency_2026-04-20.csv"
Write-Host "Exported: docs/jmeter-capacity-tests/true_job_latency_2026-04-20.csv"
```

### 6.3 Final Reporting Table (Computed from Current Artifacts)

Current measurable completion outcome within 60-second polling window:

| API | Jobs Accepted | Jobs Completed (within 60s) | Completion Rate % (within 60s) |
|---|---:|---:|---:|
| PROCESS | 20 | 15 | 75.00 |
| INDEX | 20 | 0 | 0.00 |

True job latency (start->done) from backend `elapsed_sec` lines currently captured:

| API | Completed Jobs with `elapsed_sec` evidence | Avg Job Latency (s) | P95 (s) | P99 (s) |
|---|---:|---:|---:|---:|
| PROCESS | 0 | N/A | N/A | N/A |
| INDEX | 5 | 112.18 | 112.70 | 112.70 |

Index `elapsed_sec` values used: `112.7, 111.5, 112.5, 111.8, 112.4`.

Notes:
- `PROCESS` completion count above is derived from JMeter final status assertions in `results_05_process_poll_60s.jtl`.
- `INDEX` completion count above is derived from JMeter final status assertions in `results_06_index_poll_60s.jtl`.
- True latency requires backend `elapsed_sec`; current captured logs contain index completion values but no process completion `elapsed_sec` lines.

## 7) Current Conclusion

- Concurrency acceptance target at 20 users succeeded for all main APIs (`20/20` accepted).
- Search latency is synchronous and fully represented by JMeter request latency.
- Process/Index must use backend `elapsed_sec` for true end-to-end latency; this is the correct method for ingestion-job architecture.
