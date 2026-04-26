# Phase 2 — Frontend + AI service (merged)

This folder is the **integrated production stack**: React UI with Firebase auth, FastAPI RAG backend (Qdrant, S3, optional SageMaker for ColQwen / Docling / Whisper paths), unified **SageMaker** hosting assets, and **Terraform** for AWS (ECS Fargate, ALB, ECR, ElastiCache Serverless search cache, optional HTTPS).

For a detailed list of what was merged from earlier branches, see [`MERGE_SUMMARY.md`](MERGE_SUMMARY.md).

## April 2026 updates

### Chat assistant and runtime

- Chat assistant now supports persistent session history with rename, pin, delete, and paged session list UI.
- Backend exposes dedicated chat history APIs and stores data in DynamoDB session/message tables.
- Chat runtime supports environment-based switching between local Strands and deployed Bedrock AgentCore runtime using runtime ARN invocation.
- Frontend chat history panel supports sync on/off and a compact Gemini-like session rail.

### Admin observability and dashboard (implemented today)

- Admin dashboard now uses one unified time range selector (`1h`, `3h`, `6h`, `12h`, `1d`, `7d`, `30d`, `90d`) to drive both query scope and trend charts.
- Dashboard "Recent API Invocations" is intentionally compact (latest 8 rows) and includes a **Show all** action.
- Added dedicated admin page at `/admin/invocations` with clean filtering UX:
	- server-side filters: `days`, `limit`, `user_id`, `feature`, `model_id`
	- local filters: keyword search, HTTP method, status family (`2xx/4xx/5xx`), and path contains.
- Backend invocation telemetry pipeline was hardened for DynamoDB compatibility and reliability:
	- recursive float to `Decimal` conversion before persistence
	- async-safe background recorder to prevent unhandled task exceptions.
- Telemetry policy is now strict: records are saved only when a valid non-default `X-User-Id` is present.

See detailed backend notes in [`backend/docs/CHAT_ASSISTANT_HISTORY_AND_RUNTIME.md`](backend/docs/CHAT_ASSISTANT_HISTORY_AND_RUNTIME.md).

---

## Layout

| Path | Purpose |
|------|---------|
| [`frontend/`](frontend/) | Vite + React app, Firebase Google login, API client |
| [`backend/`](backend/) | FastAPI app (`app/`), processing pipeline (`src/`), tests, Docker |
| [`sagemaker/`](sagemaker/) | Unified + split containers (Docling, Whisper, ColQwen), deploy/delete/test scripts |
| [`terraform/`](terraform/) | ECR, IAM, ALB (HTTP + optional ACM HTTPS), ECS, autoscaling, ElastiCache Serverless (search cache), optional SageMaker endpoint |
| [`scripts/`](scripts/) | Helper scripts (e.g. local setup) |

---

## Prerequisites (local dev)

- Python 3.10+ (see `backend/requirements.txt`)
- Node.js 18+ (see `frontend/package.json`)
- GPU optional locally; heavy models can run on **AWS SageMaker** instead (see `sagemaker/README.md`)

---

## Quick start (local)

Commands use **Windows PowerShell**. Run `Set-Location` to this folder (`Phase_2_FE_AI_Merge`) first.

**Backend**

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env: keys, Firebase, AWS.
# For admin observability endpoints, set DYNAMODB_APP_USAGE_TABLE.
# Run API: see backend README, run_api.bat, or uvicorn.
```

**Frontend**

```powershell
Set-Location frontend
npm install
Copy-Item .env.example .env
# e.g. VITE_API_BASE_URL=http://localhost:8000/api
npm run dev
```

**Backend tests** (from `backend/`)

```powershell
Set-Location backend
pytest
# Or: .\run_tests.ps1
```

---

## AWS: Terraform (infrastructure as code)

Infra for this merge lives in [`terraform/`](terraform/). It provisions ECR repos, ECS Fargate services behind an ALB, optional **HTTPS** (ACM certificate ARN), ElastiCache Serverless wiring for backend search cache, and optionally a **SageMaker real-time endpoint** for the unified multimodal image.

- Full reference: [`terraform/README.md`](terraform/README.md) (variables, safe `fmt`/`validate`, warnings about `plan`/`apply`)

**Local checks only (no resource changes):**

```powershell
Set-Location terraform
terraform init -backend=false
terraform fmt -recursive
terraform validate
```

Do not run `terraform apply` against a live account until you intend to provision resources and accept cost.

---

## AWS: SageMaker (unified endpoint)

Build, push to ECR, create/update endpoint, smoke tests, backend `.env` wiring:

- [`sagemaker/README.md`](sagemaker/README.md)

---

## Related repo docs

- Root [`README.md`](../README.md) — full capstone overview and week-by-week components
- [`docs/README.md`](../docs/README.md) — documentation hub
- [`docs/technical/APPLICATION_OVERVIEW.md`](../docs/technical/APPLICATION_OVERVIEW.md) — maintained application overview
- [`docs/technical/API_REFERENCE.md`](../docs/technical/API_REFERENCE.md) — maintained API reference
- [`docs/technical/DOCS_deployment-alb-acm-custom-domain.md`](../docs/technical/DOCS_deployment-alb-acm-custom-domain.md) — ALB + ACM + custom domain checklist (when using HTTPS)
- [`docs/testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md`](../docs/testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md) — final performance test report

---

## Status

Integration summary and completion notes: [`MERGE_SUMMARY.md`](MERGE_SUMMARY.md).
