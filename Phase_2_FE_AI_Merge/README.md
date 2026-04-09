# Phase 2 — Frontend + AI service (merged)

This folder is the **integrated production stack**: React UI with Firebase auth, FastAPI RAG backend (Qdrant, S3, optional SageMaker for ColQwen / Docling / Whisper paths), unified **SageMaker** hosting assets, and **Terraform** for AWS (ECS Fargate, ALB, ECR, optional HTTPS).

For a detailed list of what was merged from earlier branches, see [`MERGE_SUMMARY.md`](MERGE_SUMMARY.md).

---

## Layout

| Path | Purpose |
|------|---------|
| [`frontend/`](frontend/) | Vite + React app, Firebase Google login, API client |
| [`backend/`](backend/) | FastAPI app (`app/`), processing pipeline (`src/`), tests, Docker |
| [`sagemaker/`](sagemaker/) | Unified + split containers (Docling, Whisper, ColQwen), deploy/delete/test scripts |
| [`terraform/`](terraform/) | ECR, IAM, ALB (HTTP + optional ACM HTTPS), ECS, autoscaling, optional SageMaker endpoint |
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
# Edit .env: keys, Firebase, AWS. Run API: see backend README, run_api.bat, or uvicorn.
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

Infra for this merge lives in [`terraform/`](terraform/). It provisions ECR repos, ECS Fargate services behind an ALB, optional **HTTPS** (ACM certificate ARN), and optionally a **SageMaker real-time endpoint** for the unified multimodal image.

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
- [`docs/deployment-alb-acm-custom-domain.md`](../docs/deployment-alb-acm-custom-domain.md) — ALB + ACM + custom domain checklist (when using HTTPS)

---

## Status

Integration summary and completion notes: [`MERGE_SUMMARY.md`](MERGE_SUMMARY.md).
