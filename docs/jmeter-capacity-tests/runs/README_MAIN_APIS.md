# Main APIs   JMeter runs, JTL extract, Dynamo & search metrics

This document covers **capacity testing for the core knowledge pipeline**: **05 Process**, **06 Index**, and **08 Search** (mapped plans, one job or one search per user unless noted).

Auto-generated CSVs from `d:\PDZ\BKU\Learning\LVTN\GD1\Code\docs\jmeter-capacity-tests\scripts\dynamo_job_metrics.py --out-csv-auto` land in **this folder** as `05_YYYYMMDD_HHMMSS_dynamo_metrics.csv` or `06_...` (local PC time in the filename). Search summaries from `jtl_metrics_csv.py --out-csv-auto 08` become `08_YYYYMMDD_HHMMSS_jtl_metrics.csv`.

**Other JMeter plans** (chat, insights, auth, upload, …) are documented in [README_NON_MAIN_APIS.md](README_NON_MAIN_APIS.md).

---

## Capacity snapshot (April 2026 sample runs)

Mapped CSV users; **05/06**: `Jramp_up=0`, **1 loop** per thread; **08**: `08_search_mapped_1loop.jmx`, `-Jsearch_query="mining"`, `Jramp_up=0`. Dynamo table `**bk_mind_app_jobs`**, region `**us-west-2**`.

### Process (`05`)   Dynamo job duration (seconds)


| Threads | CSV in `runs/`                          | Jobs (summary) | avg  | p95 | p99 | Notes                                                          |
| ------- | --------------------------------------- | -------------- | ---- | --- | --- | -------------------------------------------------------------- |
| 20      | `05_20260425_162810_dynamo_metrics.csv` | n_ok=20        | 36.2 | 38  | 39  | Mix of `completed` / `failed` rows; all rows present in Dynamo |
| 30      | `05_20260426_192020_dynamo_metrics.csv` | n_ok=30        | 41.5 | 44  | 44  | Some `failed` jobs still have `duration_sec`                   |
| 40      | `05_20260426_193738_dynamo_metrics.csv` | n_ok=40        | 50.8 | 56  | 56  | Higher contention; more `failed`                               |


### Index (`06`)   Dynamo job duration (seconds)


| Threads | CSV in `runs/`                          | Jobs (summary) | avg   | p95 | p99 | Notes                                                               |
| ------- | --------------------------------------- | -------------- | ----- | --- | --- | ------------------------------------------------------------------- |
| 20      | `06_20260425_162052_dynamo_metrics.csv` | n_ok=20        | 98.1  | 106 | 107 | All `index_all` **completed** in this sample                        |
| 30      | `06_20260426_191438_dynamo_metrics.csv` | n_ok=30        | 161.7 | 187 | 190 | All **completed**                                                   |
| 40      | `06_20260426_193133_dynamo_metrics.csv` | n_ok=40        | 274.6 | 329 | 331 | All `**failed`** in this sample   treat as overload / tuning signal |


### Search (`08`)   `POST /api/search` only (`jtl_metrics_csv.py --search-only`)


| Threads | CSV in `runs/`                       | samples | errors | elapsed mean (ms) | elapsed p95 (ms) |
| ------- | ------------------------------------ | ------- | ------ | ----------------- | ---------------- |
| 20      | `08_20260426_195014_jtl_metrics.csv` | 20      | 0      | 16 163            | 18 040           |
| 30      | `08_20260426_195346_jtl_metrics.csv` | 30      | 0      | 20 503            | 24 751           |
| 40      | `08_20260426_195521_jtl_metrics.csv` | 40      | 0      | 21 091            | 27 725           |
| 50      | `08_20260426_195619_jtl_metrics.csv` | 50      | 0      | 21 895            | 30 119           |


Interpretation: search latency grows with concurrency; index at **40** simultaneous **full** index jobs exceeded healthy completion in this environment validate workers, Qdrant, and job timeouts before relying on that tier.

---

## Shared variables (optional)

```powershell
$BASE   = "D:\PDZ\BKU\Learning\LVTN\GD1\Code\docs\jmeter-capacity-tests"
$MYENV  = "D:\PDZ\BKU\Learning\LVTN\GD1\Code\Phase_2_FE_AI_Merge\backend\myenv\Scripts\python.exe"
$MAP    = "data/user_file_mapping_with_passwords.csv"

$env:AWS_REGION          = "us-west-2"
$env:DYNAMODB_JOBS_TABLE = "bk_mind_app_jobs"

cd $BASE
```

If you already activated `myenv`, you can use `python` instead of `$MYENV`.

**PowerShell:** If you use `-Jmapping_csv=$MAP` but **never set** `$MAP`, it expands to nothing, JMeter gets an **empty** CSV path (overriding the JMX default), the CSV data set fails, and you can see **0 samples**. Either run the “Shared variables” block first or pass the path literally:  
`-Jmapping_csv="data/user_file_mapping_with_passwords.csv"`.

Set **AWS** as you usually do (`AWS_PROFILE`, keys, or SSO). Python needs **boto3** for Dynamo export.

---

## Index API   3 steps (JMeter → JTL → job ids → Dynamo)

Use the **1-loop** plan so each user runs **one** index job; `job_id` values appear in JTL on `GET /api/index/status/{uuid}` URLs (response bodies are not saved in the default CSV JTL).

`data/user_file_mapping_with_passwords.csv` has **50** user rows   use **at most 50** threads (`-Jthreads`).

**Primary matrix (April 2026):** 20 / 30 / 40 threads, `Jramp_up=0`, `Jpoll_max_checks=90`, `Jpoll_interval_ms=2000`.

### 1) Run JMeter

**20 threads**

```powershell
jmeter -n -t "06_index_mapped_1loop.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=20 -Jramp_up=0 `
  -Jpoll_max_checks=90 -Jpoll_interval_ms=2000 `
  -l "results\06_index_1loop_20t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**30 threads**

```powershell
jmeter -n -t "06_index_mapped_1loop.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=30 -Jramp_up=0 `
  -Jpoll_max_checks=90 -Jpoll_interval_ms=2000 `
  -l "results\06_index_1loop_30t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**40 threads**

```powershell
jmeter -n -t "06_index_mapped_1loop.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=40 -Jramp_up=0 `
  -Jpoll_max_checks=90 -Jpoll_interval_ms=2000 `
  -l "results\06_index_1loop_40t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**50 threads (optional)**

```powershell
jmeter -n -t "06_index_mapped_1loop.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=50 -Jramp_up=0 `
  -Jpoll_max_checks=90 -Jpoll_interval_ms=2000 `
  -l "results\06_index_1loop_50t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### 2) Extract `job_id` list from the latest JTL

```powershell
$jtl = Get-ChildItem "results\06_index_1loop_*.jtl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
& $MYENV "scripts\jtl_extract_job_ids.py" $jtl.FullName -o "job_ids_06_index.txt"
```

### 3) Read Dynamo and write CSV under `runs/`

```powershell
& $MYENV "scripts\dynamo_job_metrics.py" `
  --ids-file "job_ids_06_index.txt" `
  --region $env:AWS_REGION --table $env:DYNAMODB_JOBS_TABLE --out-csv-auto 06
```

**Output:** `runs\06_YYYYMMDD_HHMMSS_dynamo_metrics.csv`

---

## Process API   3 steps (same pattern as index)

Same **50**-row mapping CSV   **at most 50** threads.

**Primary matrix:** 20 / 30 / 40 threads; `Jprocess_timeout=180000`, `Jpoll_max_checks=90`, `Jpoll_interval_ms=2000`, `Jramp_up=0`.

### 1) Run JMeter

**20 threads**

```powershell
jmeter -n -t "05_process_mapped_1loop.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=20 -Jramp_up=0 -Jprocess_timeout=180000 `
  -Jpoll_max_checks=90 -Jpoll_interval_ms=2000 `
  -l "results\05_process_1loop_20t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**30 threads**

```powershell
jmeter -n -t "05_process_mapped_1loop.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=30 -Jramp_up=0 -Jprocess_timeout=180000 `
  -Jpoll_max_checks=90 -Jpoll_interval_ms=2000 `
  -l "results\05_process_1loop_30t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**40 threads**

```powershell
jmeter -n -t "05_process_mapped_1loop.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=40 -Jramp_up=0 -Jprocess_timeout=180000 `
  -Jpoll_max_checks=90 -Jpoll_interval_ms=2000 `
  -l "results\05_process_1loop_40t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**50 threads (optional)**

```powershell
jmeter -n -t "05_process_mapped_1loop.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=50 -Jramp_up=0 -Jprocess_timeout=180000 `
  -Jpoll_max_checks=90 -Jpoll_interval_ms=2000 `
  -l "results\05_process_1loop_50t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### 2) Extract `job_id` list from the latest JTL

(Polling still uses `GET /api/index/status/{uuid}`; the extractor matches that path.)

```powershell
$jtl = Get-ChildItem "results\05_process_1loop_*.jtl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
& $MYENV "scripts\jtl_extract_job_ids.py" $jtl.FullName -o "job_ids_05_process.txt"
```

### 3) Dynamo metrics

```powershell
& $MYENV "scripts\dynamo_job_metrics.py" `
  --ids-file "job_ids_05_process.txt" `
  --region $env:AWS_REGION --table $env:DYNAMODB_JOBS_TABLE --out-csv-auto 05
```

**Output:** `runs\05_YYYYMMDD_HHMMSS_dynamo_metrics.csv`

---

## Search API   JMeter + JTL metrics CSV (no `job_id`, no Dynamo)

Search is synchronous; there is **no** job table step. `data/user_file_mapping_with_passwords.csv` has **50** rows. For **1-loop** plans, use **at most 50** threads.

### A) One search per user (primary   matches April 2026 runs)

`08_search_mapped_1loop.jmx`, `Jramp_up=0`, `-Jsearch_query="mining"` (change as needed).

**20 threads**

```powershell
jmeter -n -t "08_search_mapped_1loop.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=20 -Jramp_up=0 `
  -Jsearch_query="mining" `
  -l "results\08_search_1loop_20t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**30 threads**

```powershell
jmeter -n -t "08_search_mapped_1loop.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=30 -Jramp_up=0 `
  -Jsearch_query="mining" `
  -l "results\08_search_1loop_30t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**40 threads**

```powershell
jmeter -n -t "08_search_mapped_1loop.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=40 -Jramp_up=0 `
  -Jsearch_query="mining" `
  -l "results\08_search_1loop_40t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**50 threads**

```powershell
jmeter -n -t "08_search_mapped_1loop.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=50 -Jramp_up=0 `
  -Jsearch_query="mining" `
  -l "results\08_search_1loop_50t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

### B) Export latency / elapsed to CSV (`jtl_metrics_csv.py`)

Summarises the JTL **per `label`**: sample count, errors, `elapsed` (full response, ms) and `**Latency**` (TTFB, ms) when the JTL includes a `Latency` column   plus a `**TOTAL_ALL_LABELS**` row when multiple labels match.

- `**--search-only**`   only samples whose `label` or `URL` contains `/api/search` (drops login, etc.).
- `**--out-csv-auto 08**`   writes `runs\08_YYYYMMDD_HHMMSS_jtl_metrics.csv`.

**Latest `08_*.jtl` → CSV (search samples only, auto name under `runs/`):**

Use `**python`** from your activated venv (e.g. `myenv`). Do **not** use `& $MYENV` unless you set `$MYENV` to the full path of `python.exe` (from the Shared variables block); an **unset** `$MYENV` makes `&` fail with “expression … was not valid”.

```powershell
$jtl = Get-ChildItem "results\08_search*.jtl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python "scripts\jtl_metrics_csv.py" $jtl.FullName --search-only --out-csv-auto 08
```

**Explicit files:**

```powershell
python "scripts\jtl_metrics_csv.py" "results\08_search_1loop_20t_20260426_195014.jtl" --search-only -o "runs\search_run_metrics.csv"
```

If you need **all** labels (e.g. login + search), omit `--search-only` or set `--label-regex` (see `python scripts\jtl_metrics_csv.py -h`).

### C) Sustained load (alternative)

`08_search_mapped.jmx`   `duration` seconds, many searches per thread. Example: `Jramp_up=5`, `Jduration=60`.

**20 threads**

```powershell
jmeter -n -t "08_search_mapped.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" -Jthreads=20 -Jramp_up=5 -Jduration=60 `
  -Jsearch_query="mining" `
  -l "results\08_search_20t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

(Repeat for 30 / 40 / 50 threads by changing `-Jthreads` and the JTL filename.)

Then export with the same `jtl_metrics_csv.py` command as in section B.

### Optional: HTML report from a `.jtl`

```powershell
$jtl = Get-ChildItem "results\08_search*.jtl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$out = "results\report_08_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
jmeter -g $jtl.FullName -o $out   # folder $out must not exist
Start-Process "$out\index.html"
```

Override host if needed: add e.g. `-Japihost=your.api.host` to any `jmeter -n` command.

---

## CSV columns (Dynamo exports)

- **duration_sec**: `completed_at - started_at` when `started_at` is set and `> 0`, otherwise `completed_at - created_at`.
- **dynamo_presence**: `ok` or `missing` (id requested but no row in Dynamo).
- Last row **SUMMARY**: counts, `avg` / `p95` / `p99` of durations, and region.

---

## Scripts


| Script                           | Role                                                                     |
| -------------------------------- | ------------------------------------------------------------------------ |
| `scripts/jtl_extract_job_ids.py` | Pull unique UUIDs from `/api/index/status/...` in a CSV JTL              |
| `scripts/dynamo_job_metrics.py`  | `GetItem` per `job_id`, print table + optional CSV                       |
| `scripts/jtl_metrics_csv.py`     | JTL → per-label `elapsed` / `Latency` percentiles, CSV (search, any API) |


## Reference notes

- Snapshot write-up for an index run: `06_index_reference_2026-04-25_1608.md` (if present in this folder).

