# Environment & external dependencies

Configure the backend with **`backend/.env`** (see `backend/.env.example`) plus **`backend/config/default.yaml`**. Environment variables override YAML where noted in `app/core/paths.py` (`merged_runtime_settings`).

## 1. LLM generation (answer, insights)

| Variable | Required | Notes |
|----------|----------|--------|
| `OPENAI_API_KEY` | Yes, for OpenAI provider | Used by `src/generation/generator.py` and insights |

Other providers (Azure, Ollama) follow the same YAML keys as Phase 2 under `generation:`.

## 2. Qdrant (vector database)

**Primary reference:** `Phase_2_PDZ_003_Test_Qdrant_Cloud` (connection modes, collection creation, multivec ColQwen).

| Variable | Meaning |
|----------|---------|
| `QDRANT_MODE` | `docker` or `cloud` |
| `QDRANT_HOST`, `QDRANT_PORT` | Local Docker (`localhost:6333`) |
| `QDRANT_URL`, `QDRANT_API_KEY` | Qdrant Cloud |
| `QDRANT_TEXT_COLLECTION`, `QDRANT_IMAGE_COLLECTION` | Optional overrides (defaults in `default.yaml`) |

Local Docker (example):

```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
```

## 3. ColQwen inference — local vs AWS SageMaker

**Primary reference:** `Phase_2_PDZ_002_Model_Deploy` — `server.py` exposes `/invocations` with `operation`: `embed-query`, `embed-images` (JSON body matches `test_sagemaker_endpoint.py`).

| Variable | Meaning |
|----------|---------|
| `USE_AWS_SAGEMAKER_INFERENCE` | `true` / `1` / `yes` → use **SageMaker Runtime** for embeddings (no local ColQwen load for inference path) |
| `AWS_REGION` | e.g. `us-west-2` |
| `SAGEMAKER_ENDPOINT_NAME` | Deployed endpoint name |

**AWS credentials:** standard IAM (e.g. `~/.aws/credentials` or instance role) for `boto3` `sagemaker-runtime`.

When **not** using SageMaker, install GPU/CPU PyTorch and `colpali-engine` per `requirements.txt`; first load may download Hugging Face weights.

## 4. System tools (unchanged from Phase 2)

Document/media processing still depends on **FFmpeg**, **Poppler** (pdf2image), **Tesseract**, and **LibreOffice** (see this service's `backend/requirements.txt` and the maintained `Phase_2_FE_AI_Merge/backend/requirements.txt` notes). These are **not** Terraform-managed in this refactor.

## 5. Terraform

For maintained infrastructure-as-code, use **`Phase_2_FE_AI_Merge/terraform`**.
