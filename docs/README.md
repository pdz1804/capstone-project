# BK-MInD Documentation Index

This README is only the index for `docs/`. For the project overview and repository layout, start at the root [`../README.md`](../README.md). For running the Phase 2 application, use [`../Phase_2/README.md`](../Phase_2/README.md).

Use this page for technical review, testing evidence, deployment references, diagrams, and project reports.

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

## Rubric-Based Documentation Improvements

**Current Progress**: Phase 1 ✅ COMPLETE + Phase 2 ✅ COMPLETE

**Rubric Score**: **76/100 (B+)** → Phase 1: **80/100** → Phase 2: **81.8/100** ✅

### Quick Navigation

**→ START HERE**: [`02_MASTER_DOCUMENTS/README_IMPROVEMENTS.md`](02_MASTER_DOCUMENTS/README_IMPROVEMENTS.md)

### Phase 1 Documentation (5 Critical Improvements)
- [`01_PHASE_1_IMPROVEMENTS/`](01_PHASE_1_IMPROVEMENTS/) — Core documentation:
  - BUILD_REPRODUCIBILITY.md — Dependency management & setup
  - EVALUATION_REPRODUCIBILITY.md — Metrics & benchmarking
  - TECHNICAL_DESIGN_DEEP_DIVE.md — 5 hard problems solved
  - ERROR_HANDLING_AND_FAILURES.md — Error recovery strategies
  - OPERATIONS_RUNBOOK.md — On-call troubleshooting guide

### Phase 2 Documentation (API & Setup)
- **[`API_DOCUMENTATION.md`](API_DOCUMENTATION.md)** ⭐ — Complete API reference with examples
- **[`SETUP_GUIDE.md`](SETUP_GUIDE.md)** ⭐ — Step-by-step environment setup for new developers
- **Backend Module Docstrings** ⭐ — 7 Python modules with comprehensive documentation

### Master Documents
- [`02_MASTER_DOCUMENTS/`](02_MASTER_DOCUMENTS/) — Rubric evaluation & improvement plan
- [`03_ARCHITECTURE_DESIGN/`](03_ARCHITECTURE_DESIGN/) — System architecture diagrams
- [`04_PROJECT_REFERENCE/`](04_PROJECT_REFERENCE/) — Requirements, use cases, statistics

## Recommended Reading Order

1. **For project orientation**: [`../README.md`](../README.md)
2. **For current Phase 2 setup**: [`../Phase_2/README.md`](../Phase_2/README.md)
3. **For maintained technical overview**: [`technical/APPLICATION_OVERVIEW.md`](technical/APPLICATION_OVERVIEW.md)
4. **For API behavior**: [`technical/API_REFERENCE.md`](technical/API_REFERENCE.md) and [`API_DOCUMENTATION.md`](API_DOCUMENTATION.md)
5. **For setup/reproducibility**: [`SETUP_GUIDE.md`](SETUP_GUIDE.md) and [`01_PHASE_1_IMPROVEMENTS/BUILD_REPRODUCIBILITY.md`](01_PHASE_1_IMPROVEMENTS/BUILD_REPRODUCIBILITY.md)

---

## Original Documentation Structure

1. [`technical/APPLICATION_OVERVIEW.md`](technical/APPLICATION_OVERVIEW.md)   product scope, feature set, architecture, and quality attributes.
2. [`technical/API_REFERENCE.md`](technical/API_REFERENCE.md)   API surface grouped by platform capability.
3. [`testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md`](testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md)   final performance evidence and scaling analysis.
4. [`jmeter-capacity-tests/runs/README_MAIN_APIS.md`](jmeter-capacity-tests/runs/README_MAIN_APIS.md)   main API capacity-test commands and result exports.
5. [`jmeter-capacity-tests/runs/README_NON_MAIN_APIS.md`](jmeter-capacity-tests/runs/README_NON_MAIN_APIS.md)   non-main API capacity-test commands and JTL export flow.

## Documentation Standards

- Keep generated or raw output files out of high-level documentation unless they are intentionally part of the test evidence.
- Prefer concise tables for API, performance, and operational matrices.
- Keep final reports in `docs/testing/`.
- Keep implementation and architecture reference material in `docs/technical/`.
- Keep historical notes in `docs/others/` unless they are promoted into a maintained document.
- Keep maintained deployment, backend, cache, API, and infrastructure notes in `docs/technical/`.
