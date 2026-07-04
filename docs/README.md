## Complete Environment Setup Guide

**Last Updated**: July 4, 2026
**For**: Phase 2 maintained application stack
**Duration**: 20-40 minutes for a local backend/frontend setup

This guide matches the current codebase structure documented in [`../README.md`](../README.md), [`../Phase_2/README.md`](../Phase_2/README.md), [`../Phase_2/code/backend/README.md`](../Phase_2/code/backend/README.md), and [`../Phase_2/code/terraform/README.md`](../Phase_2/code/terraform/README.md).

## What You Need

- Python 3.10+ for the backend
- Node.js 18+ for the frontend
- Git
- Docker and Docker Compose for local Qdrant and Redis
- Optional system binaries: FFmpeg, Tesseract, and Poppler if you run the document-processing paths locally

## 1. Clone the Repository

```bash
git clone https://github.com/pdz1804/capstone-project.git
cd capstone-project
```

The maintained app lives in `Phase_2/`.

## 2. Start Local Infrastructure

From the backend folder, start the local service dependencies:

```bash
cd Phase_2/code/backend
docker compose up -d
```

This starts Redis and Qdrant from [`docker-compose.yml`](../Phase_2/code/backend/docker-compose.yml); it does not start the FastAPI backend itself.

Useful checks:

```bash
curl http://localhost:6333/health
docker compose ps
```

## 3. Configure and Run the Backend

Create the backend environment file and fill in the values you need:

```bash
cd Phase_2/code/backend
cp .env.example .env
```

Start the backend with the maintained entrypoint:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python run_api.py
```

Activate the virtual environment with the equivalent command for your shell before installing packages if you prefer not to use the system interpreter.

The API runs on port 5001 by default. The runner accepts `--host`, `--port`, `--workers`, `--reload`, and `--no-reload` if you need to override the defaults.

Common backend env values to review:

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `QDRANT_MODE`, `QDRANT_HOST`, `QDRANT_PORT`, or `QDRANT_URL`
- `REDIS_URL`
- `FILE_STORAGE_BACKEND`
- `USE_AWS_SAGEMAKER_INFERENCE`
- `DYNAMODB_USERS_TABLE`, `DYNAMODB_APP_USAGE_TABLE`, `DYNAMODB_JOBS_TABLE`

## 4. Configure and Run the Frontend

In a separate terminal:

```bash
cd Phase_2/code/frontend
cp .env.example .env
npm install
npm run dev
```

The current frontend dev script is `tsx server.ts`, and the default local URL is `http://localhost:5173`. The template in [`../Phase_2/code/frontend/.env.example`](../Phase_2/code/frontend/.env.example) uses `VITE_API_BASE_URL=/api` and `API_PROXY_TARGET=http://localhost:5001`.

## 5. Verify the Stack

Backend health:

```bash
curl http://localhost:5001/health
curl http://localhost:5001/api/health
```

Frontend should be reachable at `http://localhost:5173`.

If you want to smoke-test search after indexing data, use the current API contract from [`../Phase_2/code/backend/README.md`](../Phase_2/code/backend/README.md) and send requests with the `X-User-Id` header.

## 6. Optional Local Validation

Backend tests:

```bash
cd Phase_2/code/backend
python -m pytest tests -v
```

Terraform validation only:

```bash
cd Phase_2/code/terraform
terraform init -backend=false
terraform fmt -recursive
terraform validate
```

## 7. Common Failure Points

- If Qdrant is unreachable, confirm `docker compose up -d` completed and that port 6333 is free.
- If Redis is unreachable, confirm the same compose stack is running and that the backend `REDIS_URL` points at `redis://localhost:6379/0` or your configured instance.
- If the frontend cannot reach the API, confirm `API_PROXY_TARGET=http://localhost:5001` and that the backend is running on port 5001.
- If `pip install` fails on large wheels, clear the pip cache or use a drive with more free space before retrying.

## 8. Where To Read Next

- [`Phase_2/README.md`](../Phase_2/README.md) for the maintained Phase 2 setup summary
- [`Phase_2/code/backend/README.md`](../Phase_2/code/backend/README.md) for backend runtime, API routes, and indexing workflow
- [`Phase_2/code/terraform/README.md`](../Phase_2/code/terraform/README.md) for infrastructure validation and deployment notes
