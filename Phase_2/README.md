# Phase 2 Maintained Application

This folder is the **integrated production stack**: React UI with Firebase auth, FastAPI RAG backend (Qdrant, S3, optional SageMaker for ColQwen / Docling / Whisper paths), unified **SageMaker** hosting assets, and **Terraform** for AWS (ECS Fargate, ALB, ECR, ElastiCache Serverless search cache, optional HTTPS).

Legacy prototype folders were merged into this maintained `Phase_2/` tree and removed from the repo. Current source lives under `code/`; large datasets and generated artifacts live under ignored `data/`.

## Scope

Use this README for Phase 2 setup and navigation only. For the whole repository, use [`../README.md`](../README.md). For technical docs and reports, use [`../docs/README.md`](../docs/README.md).

Detailed backend feature notes, including chat history/runtime behavior, live in [`code/backend/docs/CHAT_ASSISTANT_HISTORY_AND_RUNTIME.md`](code/backend/docs/CHAT_ASSISTANT_HISTORY_AND_RUNTIME.md).

---

## Layout

| Path | Purpose |
|------|---------|
| [`code/frontend/`](code/frontend/) | Vite + React app, Firebase Google login, API client |
| [`code/backend/`](code/backend/) | FastAPI app (`app/`), processing pipeline (`src/`), tests, Docker |
| [`code/sagemaker/`](code/sagemaker/) | Unified + split containers (Docling, Whisper, ColQwen), deploy/delete/test scripts |
| [`code/terraform/`](code/terraform/) | ECR, IAM, ALB (HTTP + optional ACM HTTPS), ECS, autoscaling, ElastiCache Serverless (search cache), optional SageMaker endpoint |
| [`code/scripts/`](code/scripts/) | Helper scripts (e.g. local setup) |
| [`data/`](data/) | Local-only raw inputs, outputs, eval artifacts, indexes, and model files; ignored by Git |

---

## Prerequisites (local dev)

- Python 3.10+ (see `code/backend/requirements.txt`)
- Node.js 18+ (see `code/frontend/package.json`)
- GPU optional locally; heavy models can run on **AWS SageMaker** instead (see `code/sagemaker/README.md`)

---

## Quick start (local)

Commands use **Windows PowerShell** from the repository root.

**Backend**

```powershell
Set-Location Phase_2\code\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env: keys, Firebase, AWS.
# For admin observability endpoints, set DYNAMODB_APP_USAGE_TABLE.
python run_api.py
```

**Frontend**

```powershell
Set-Location Phase_2\code\frontend
npm install
Copy-Item .env.example .env
# Default dev proxy: VITE_API_BASE_URL=/api and API_PROXY_TARGET=http://localhost:5001
npm run dev
```

**Backend tests**

```powershell
Set-Location Phase_2\code\backend
pytest
```

---

## AWS: Terraform (infrastructure as code)

Infra for this merge lives in [`code/terraform/`](code/terraform/). It provisions ECR repos, ECS Fargate services behind an ALB, optional **HTTPS** (ACM certificate ARN), ElastiCache Serverless wiring for backend search cache, and optionally a **SageMaker real-time endpoint** for the unified multimodal image.

- Full reference: [`code/terraform/README.md`](code/terraform/README.md) (variables, safe `fmt`/`validate`, warnings about `plan`/`apply`)

**Local checks only (no resource changes):**

```powershell
Set-Location Phase_2\code\terraform
terraform init -backend=false
terraform fmt -recursive
terraform validate
```

Do not run `terraform apply` against a live account until you intend to provision resources and accept cost.

---

## AWS: SageMaker (unified endpoint)

Build, push to ECR, create/update endpoint, smoke tests, backend `.env` wiring:

- [`code/sagemaker/README.md`](code/sagemaker/README.md)

---

## Related repo docs

- Root [`README.md`](../README.md)   full capstone overview and phase components
- [`docs/README.md`](../docs/README.md)   documentation hub
- [`docs/technical/APPLICATION_OVERVIEW.md`](../docs/technical/APPLICATION_OVERVIEW.md)   maintained application overview
- [`docs/technical/API_REFERENCE.md`](../docs/technical/API_REFERENCE.md)   maintained API reference
- [`docs/technical/DOCS_deployment-alb-acm-custom-domain.md`](../docs/technical/DOCS_deployment-alb-acm-custom-domain.md)   ALB + ACM + custom domain checklist (when using HTTPS)
- [`docs/testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md`](../docs/testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md)   final performance test report

---

## Status

Maintained entry points are `code/backend`, `code/frontend`, `code/sagemaker`, `code/terraform`, and `code/scripts`.
