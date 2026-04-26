# Testing Documentation

This folder contains final testing documents prepared for technical review, project defense, and release-quality evidence.

## Final Reports

| Document | Description |
|---|---|
| [`FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md`](FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md) | Final application performance report covering JMeter methodology, API results, DynamoDB job metrics, analysis, risks, and scaling plan |

## Related Test Assets

| Location | Description |
|---|---|
| [`../jmeter-capacity-tests/`](../jmeter-capacity-tests/) | JMeter `.jmx` plans, helper scripts, user mappings, runbooks, and raw test exports |
| [`../jmeter-capacity-tests/runs/README_MAIN_APIS.md`](../jmeter-capacity-tests/runs/README_MAIN_APIS.md) | Main API performance runbook for Process, Index, and Search |
| [`../jmeter-capacity-tests/runs/README_NON_MAIN_APIS.md`](../jmeter-capacity-tests/runs/README_NON_MAIN_APIS.md) | Non-main API performance runbook for Auth, User, Stats, Upload, Chat, and Insights |

## Review Notes

- Final conclusions should reference exported CSV evidence under `../jmeter-capacity-tests/runs/`.
- Raw JMeter `.jtl` files and HTML reports are generated artifacts and should remain outside Git tracking.
- Performance claims should distinguish synchronous API latency from asynchronous background job duration.
