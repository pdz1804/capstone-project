# BK-MInD Documentation Hub

This folder is organized as a maintainable documentation system for the BK-MInD capstone project. Use this page as the entry point for technical review, testing evidence, deployment references, and project reports.

## Primary Sections

| Section | Purpose |
|---|---|
| [`technical/`](technical/) | Senior-level technical documentation: application overview, API reference, architecture notes, and operational guidance |
| [`testing/`](testing/) | Final testing and performance reports intended for review and presentation |
| [`jmeter-capacity-tests/`](jmeter-capacity-tests/) | JMeter plans, scripts, raw run exports, and performance-test runbooks |
| [`diagram/`](diagram/) | System diagrams and architecture visuals |
| [`report/`](report/) | Academic and progress reports |
| [`presentation/`](presentation/) | Presentation artifacts and visual materials |
| [`others/`](others/) | Historical implementation logs and miscellaneous archival notes |

## Recommended Reading Order

1. [`technical/APPLICATION_OVERVIEW.md`](technical/APPLICATION_OVERVIEW.md) — product scope, feature set, architecture, and quality attributes.
2. [`technical/API_REFERENCE.md`](technical/API_REFERENCE.md) — API surface grouped by platform capability.
3. [`testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md`](testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md) — final performance evidence and scaling analysis.
4. [`jmeter-capacity-tests/runs/README_MAIN_APIS.md`](jmeter-capacity-tests/runs/README_MAIN_APIS.md) — main API capacity-test commands and result exports.
5. [`jmeter-capacity-tests/runs/README_NON_MAIN_APIS.md`](jmeter-capacity-tests/runs/README_NON_MAIN_APIS.md) — non-main API capacity-test commands and JTL export flow.

## Documentation Standards

- Keep generated or raw output files out of high-level documentation unless they are intentionally part of the test evidence.
- Prefer concise tables for API, performance, and operational matrices.
- Keep final reports in `docs/testing/`.
- Keep implementation and architecture reference material in `docs/technical/`.
- Keep historical notes in `docs/others/` unless they are promoted into a maintained document.
- Keep maintained deployment, backend, cache, API, and infrastructure notes in `docs/technical/`.
