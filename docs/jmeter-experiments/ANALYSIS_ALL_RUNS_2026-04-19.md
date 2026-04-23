# JMeter Experiments All-Runs Analysis (2026-04-19)

## Scope
This report consolidates all available run artifacts under `docs/jmeter-experiments/reports` and `docs/jmeter-experiments/report-ready`.

## Data Sources
- `report-ready/all_jtl_run_rollup_20260419.csv`
- `report-ready/all_jtl_label_rollup_20260419.csv`
- `report-ready/all_jtl_failure_code_rollup_20260419.csv`
- `report-ready/all_scenarios_rollup_clean_20260419.csv`

## Run Inventory and Totals
- Total JTL runs analyzed: `23`
- Total requests: `11708`
- Total failed requests: `1551`
- Global weighted error rate: `13.2474%`
- Mean per-run error rate: `10.9576%`

## Scenario Trend (Canonical Battery Runs)
From scenario summaries (`summary_*.csv`, excluding label files):

| Scenario | Runs | Requests | Failed | Weighted Error % |
|---|---:|---:|---:|---:|
| S01_smoke | 3 | 303 | 36 | 11.8812 |
| S02_load | 3 | 2738 | 368 | 13.4405 |
| S03_concurrency | 1 | 1176 | 167 | 14.2007 |
| S04_stress | 1 | 784 | 108 | 13.7755 |

Observation: error rate increases from smoke into load/concurrency/stress, with the worst in concurrency.

## Highest-Error Run Files (Across 23 JTLs)
Top runs by error rate:

1. `20260419_221347_S03_concurrency.jtl`: `14.2007%` (167/1176)
2. `20260419_211802_S02_load.jtl`: `13.9031%` (109/784)
3. `20260419_221347_S04_stress.jtl`: `13.7755%` (108/784)
4. `diag_t30_l2.jtl`: `13.7755%` (162/1176)
5. `diag_t35_l2.jtl`: `13.7655%` (189/1373)

## Global Failure Concentration by API Label
Top labels by failed request count:

1. `Essential Authenticated API Journey`: `512/596` failed (`85.906%`)
2. `POST /api/search (retrieval_generation both)`: `511/596` failed (`85.7383%`)
3. `POST /api/search (retrieval_generation text)`: `511/596` failed (`85.7383%`)

All other labels are low-failure (mostly near zero).

## Global Failure Signature by HTTP Code/Message
Most frequent failure groups:

1. `POST /api/search (retrieval_generation text)` -> `500 Internal Server Error` (`510`)
2. `POST /api/search (retrieval_generation both)` -> `500 Internal Server Error` (`509`)
3. Transaction aggregate failures for `Essential Authenticated API Journey` driven by failing inner samples
4. Smaller side cluster of `502 Bad Gateway` across multiple labels

## Root-Cause Direction from All-Runs Evidence
1. The dominant system issue is concentrated in search-generation endpoints (`/api/search` text and both), not across all APIs uniformly.
2. Because `text` and `both` fail at nearly identical rates, the primary fault is likely in shared search-generation path (or common dependencies), not only image-specific branch.
3. Intermittent `502` errors indicate transient upstream instability under load.

## SageMaker Relation
Current runtime probe (`GET /api/system/inference`) shows:
- `use_aws_sagemaker_inference=true`
- `sagemaker_endpoint_name=phase2-multimodal-rt`
- `generation_provider=bedrock`
- `qdrant_mode=cloud`

Therefore, `/api/search` failures can be linked to cloud dependencies that include SageMaker-inference path, but cannot be attributed to SageMaker alone from these JMeter outputs. Bedrock generation and Qdrant cloud are also in the same critical path.

## Immediate Next Isolations
1. Run text-only search with image disabled and generation disabled to isolate retrieval path.
2. Run text-only search with generation enabled to isolate generation provider faults.
3. Capture full error response body and backend exception trace for search `500` samples.
4. Correlate failure timestamps with SageMaker endpoint metrics and Bedrock throttling/errors.