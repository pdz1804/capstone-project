# Non-main APIs — JMeter commands and JTL → CSV export

This document covers JMeter plans **outside** the core **05 Process / 06 Index / 08 Search** flow. Those three are documented in [README_MAIN_APIS.md](README_MAIN_APIS.md).

**Pattern (same idea as search in the main doc):**

1. `cd` to `docs/jmeter-capacity-tests`.
2. Run `jmeter -n -t ... -l results\NN_....jtl`.
3. Summarise with `scripts/jtl_metrics_csv.py` → `runs/NN_YYYYMMDD_HHMMSS_jtl_metrics.csv` via `--out-csv-auto NN`.

There is **no** Dynamo `job_id` export for these calls (no `dynamo_job_metrics.py` step).

---

## Shared variables (optional)

```powershell
$BASE   = "D:\PDZ\BKU\Learning\LVTN\GD1\Code\docs\jmeter-capacity-tests"
$MYENV  = "D:\PDZ\BKU\Learning\LVTN\GD1\Code\Phase_2_FE_AI_Merge\backend\myenv\Scripts\python.exe"

cd $BASE
```

Use `python` instead of `& $MYENV` if your venv is already activated.

---

## Export helper (after any run)

Pick the JTL you care about, then either **filter to the API under test** (recommended) or export **all** labels.

**Filter by sampler label** (regex, case-insensitive):

```powershell
$jtl = Get-ChildItem "results\09_chat*.jtl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python "scripts\jtl_metrics_csv.py" $jtl.FullName --label-regex "POST /api/chat/stream" --out-csv-auto 09
```

**All labels** in that JTL (includes login, etc.):

```powershell
python "scripts\jtl_metrics_csv.py" $jtl.FullName --out-csv-auto 09
```

**Output:** `runs\09_YYYYMMDD_HHMMSS_jtl_metrics.csv` (prefix `09` matches the example; use `01`…`04`, `10`, `11`, `12` consistently for your plan).

**CLI help:** `python scripts\jtl_metrics_csv.py -h`

---

## 01 — `POST /api/auth/login-local` (`01_auth_login.jmx`)

Default user list: `data/users.csv`. Override with `-Jusers_csv=...`.

**Example (50 threads, 15 s duration):**

```powershell
jmeter -n -t "01_auth_login.jmx" `
  -Jusers_csv="data/users.csv" -Jthreads=50 -Jramp_up=5 -Jduration=15 `
  -l "results\01_auth_login_20t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**CSV export (login sampler only):**

```powershell
$jtl = Get-ChildItem "results\01_auth_login*.jtl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python "scripts\jtl_metrics_csv.py" $jtl.FullName --label-regex "POST /api/auth/login-local" --out-csv-auto 01
```

---

## 02 — `GET /api/users/me` (`02_user_me.jmx`)

**Example:**

```powershell
jmeter -n -t "02_user_me.jmx" `
  -Jusers_csv="data/users.csv" -Jthreads=50 -Jramp_up=5 -Jduration=15 `
  -l "results\02_user_me_20t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**CSV export:**

```powershell
$jtl = Get-ChildItem "results\02_user_me*.jtl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python "scripts\jtl_metrics_csv.py" $jtl.FullName --label-regex "GET /api/users/me" --out-csv-auto 02
```

---

## 03 — `GET /api/processing-stats` (`03_stats.jmx`)

**Example:**

```powershell
jmeter -n -t "03_stats.jmx" `
  -Jusers_csv="data/users.csv" -Jthreads=50 -Jramp_up=5 -Jduration=15 `
  -l "results\03_stats_20t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**CSV export:**

```powershell
$jtl = Get-ChildItem "results\03_stats*.jtl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python "scripts\jtl_metrics_csv.py" $jtl.FullName --label-regex "GET /api/processing-stats" --out-csv-auto 03
```

---

## 04 — `POST /api/upload` (`04_upload.jmx`)

**Semantics:** default `loops=1`, scheduler off. Each thread runs once: `POST /api/auth/login-local` then `POST /api/upload`.

- `#(POST /api/upload)` = `threads x loops` (e.g. 30 threads -> **30** upload samples).
- `#(login)` matches that same count.
- CSV `recycle=false`: you need at least as many data rows as threads (header excluded). Use `data/user_file_mapping_with_passwords.csv` because it includes `email`, `password`, and `user_id`.
- The upload request sends `X-User-Id: ${user_id}`. Without this header, the backend intentionally falls back to `DEFAULT_STORAGE_USER_ID` / `default`, which writes to `s3://.../users/default/...`.
- Upload body file: `-Jupload_file_path` (default `data/Text_mining_by_using_Python2025_5pages.pdf`). Paths are relative to the directory where you run JMeter (run from `docs/jmeter-capacity-tests`).

**Optional:** `-Jloops=3` -> each user performs 3 uploads in sequence (`threads x 3` upload samples).

**Timeouts:** the plan sets `response_timeout_ms` default `600000` (10 min). The old **120 s** limit often shows up as `Err` with `Max` elapsed around `120000-122000 ms` when many uploads hit the API at once (ALB/API/S3 queueing). Override if needed: `-Jresponse_timeout_ms=900000`. Connect timeout default **60 s**: `-Jconnect_timeout_ms=...`.

**If many errors remain:** open the `.jtl` and check `responseCode` / `responseMessage` on failed rows (`POST /api/upload` vs login). Tune ECS concurrency, ALB `idle_timeout_seconds`, or reduce `threads`.

**Example (30 concurrent users, 30 uploads, ramp 0):**

```powershell
jmeter -n -t "04_upload.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" `
  -Jupload_file_path="data/Text_mining_by_using_Python2025_5pages.pdf" `
  -Jupload_mime_type="application/pdf" `
  -Jthreads=30 -Jramp_up=0 -Jloops=1 `
  -l "results\04_upload_30t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**CSV export:**

```powershell
$jtl = Get-ChildItem "results\04_upload*.jtl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python "scripts\jtl_metrics_csv.py" $jtl.FullName --label-regex "POST /api/upload" --out-csv-auto 04
```

---

## 09 — `POST /api/chat/stream` (`09_chat_stream_mapped.jmx`)

Uses the **mapped** user/file CSV (same family as 05/06/08). See also [CHAT_INSIGHTS_TEST_COMMANDS.md](../CHAT_INSIGHTS_TEST_COMMANDS.md).

**Semantics:** these chat/insights mapped plans are **sustained-load** tests (`loops=-1`, scheduler duration enabled). `threads` means concurrent users, but total endpoint samples are based on how many request cycles complete during `Jduration`. This is different from 04 upload, where `threads=uploads` because `loops=1`.

All 09–12 plans already send `X-User-Id: ${user_id}`, so backend storage/retrieval is scoped to the mapped user instead of `default`.

For 09 specifically, the plan now explicitly calls `POST /api/chat/sessions` before `POST /api/chat/stream`. A Groovy preprocessor generates a fresh `chat_session_id` for each loop, the session create request persists it for that user, and the chat stream request sends the same `session_id`.

**Example:**

```powershell
jmeter -n -t "09_chat_stream_mapped.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" `
  -Jthreads=50 -Jramp_up=5 -Jduration=60 `
  -Jchat_query="Hi" `
  -l "results\09_chat_50t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**CSV export (stream endpoint only, excludes login row):**

```powershell
$jtl = Get-ChildItem "results\09_chat*.jtl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python "scripts\jtl_metrics_csv.py" $jtl.FullName --label-regex "POST /api/chat/stream" --out-csv-auto 09
```

---

## 10 — `POST /api/summary` (`10_insights_summary_mapped.jmx`)

Sustained-load plan, same CSV and identity behavior as 09.

**Example (detailed):**

```powershell
jmeter -n -t "10_insights_summary_mapped.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" `
  -Jthreads=50 -Jramp_up=5 -Jduration=60 -Jdepth="detailed" `
  -l "results\10_summary_detailed_50t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**CSV export:**

```powershell
$jtl = Get-ChildItem "results\10_summary*.jtl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python "scripts\jtl_metrics_csv.py" $jtl.FullName --label-regex "POST /api/summary" --out-csv-auto 10
```

---

## 11 — `POST /api/mcq` (`11_insights_mcq_mapped.jmx`)

Sustained-load plan, same CSV and identity behavior as 09.

**Example:**

```powershell
jmeter -n -t "11_insights_mcq_mapped.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" `
  -Jthreads=50 -Jramp_up=5 -Jduration=60 -Jtopic="text mining" `
  -l "results\11_mcq_50t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**CSV export:**

```powershell
$jtl = Get-ChildItem "results\11_mcq*.jtl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python "scripts\jtl_metrics_csv.py" $jtl.FullName --label-regex "POST /api/mcq" --out-csv-auto 11
```

---

## 12 — `POST /api/learning-roadmap` (`12_insights_roadmap_mapped.jmx`)

Sustained-load plan, same CSV and identity behavior as 09.

**Example:**

```powershell
jmeter -n -t "12_insights_roadmap_mapped.jmx" `
  -Jmapping_csv="data/user_file_mapping_with_passwords.csv" `
  -Jthreads=50 -Jramp_up=5 -Jduration=60 `
  -Jgoals="Learn data mining and NLP techniques" `
  -l "results\12_roadmap_50t_$(Get-Date -Format 'yyyyMMdd_HHmmss').jtl"
```

**CSV export:**

```powershell
$jtl = Get-ChildItem "results\12_roadmap*.jtl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python "scripts\jtl_metrics_csv.py" $jtl.FullName --label-regex "POST /api/learning-roadmap" --out-csv-auto 12
```

---

## Optional: HTML report

```powershell
$jtl = Get-ChildItem "results\09_chat*.jtl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$out = "results\report_09_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
jmeter -g $jtl.FullName -o $out
Start-Process "$out\index.html"
```

---

## Script reference


| Script                       | Role                                                                       |
| ---------------------------- | -------------------------------------------------------------------------- |
| `scripts/jtl_metrics_csv.py` | JTL → per-label `elapsed` / `Latency` percentiles, UTF-8 CSV under `runs/` |


See [README_MAIN_APIS.md](README_MAIN_APIS.md) for `jtl_extract_job_ids.py` and `dynamo_job_metrics.py` (Process/Index only).