# SageMaker Hosting Pack (Docling + Whisper + ColQwen)

Two deployment patterns are supported:

1. **Recommended**: one unified endpoint hosting all 3 models (cost-saving, simpler ops)
2. **Split**: one endpoint per model (independent scaling, independent updates)

---

## Folder layout

```
unified/          ← single endpoint for all 3 models (recommended)
  server.py
  Dockerfile
  requirements.txt
  sagemaker_entrypoint.sh
  build_push_ecr.ps1 / build_push_ecr.sh
colqwen/          ← optional standalone ColQwen endpoint
docling/          ← optional standalone Docling endpoint
whisper/          ← optional standalone Whisper endpoint
ops/
  deploy_sagemaker_endpoint.py   ← create / update endpoint + autoscaling
  delete_sagemaker_endpoint.py   ← teardown
  test_sagemaker_endpoint.py     ← smoke tests
```

---

## Processing defaults (aligned with backend)

All server defaults now match `backend/config/default.yaml`:


| Setting                   | Default    | Override env                  |
| ------------------------- | ---------- | ----------------------------- |
| VLM (picture description) | **OFF**    | `DOCLING_ENABLE_VLM=true`     |
| Image export              | **OFF**    | `DOCLING_EXPORT_IMAGES=true`  |
| Table export              | **OFF**    | `DOCLING_EXPORT_TABLES=true`  |
| OCR                       | ON         | `DOCLING_ENABLE_OCR=false`    |
| OCR engine                | `rapidocr` | `DOCLING_OCR_ENGINE=tesseract |
| Whisper model             | `base`     | `WHISPER_MODEL=small          |
| ColQwen quantization      | `8bit`     | `COLQWEN_QUANTIZATION=4bit    |


Enable VLM+image export only when you need richer multimodal understanding.
Default (VLM off) gives 3-5× faster Docling processing.

---

## Multi-user concurrency: do you need SQS?

**Short answer: NO for this application. Keep the current architecture.**

### Why SQS is NOT needed here

- The **backend FastAPI** already has per-user pipeline locks (`_pipeline_lock_for_user`).
Two different users can process/index in parallel; the same user cannot double-submit.
- The **SageMaker endpoint** serializes GPU work via `asyncio.Lock` (Docling, Whisper) and
`asyncio.Semaphore` (ColQwen). Concurrent requests from multiple users queue inside the
endpoint process and are served in order   exactly what you want.
- SageMaker autoscaling creates more instances when `InvocationsPerInstance` exceeds the
target (default 10 in this repo), so truly concurrent heavy load gets its own GPU automatically.

### When SQS would make sense (for future reference)

Use SQS **only if** you need async job submission where the user submits a job and polls
for the result later (e.g., very large document batch jobs >5 min). That requires:

- Frontend: submit → receive job_id → poll status
- Backend: SQS producer → Lambda or worker consumer → SageMaker
- This adds significant complexity for this app's current use case.

### What to do for multi-user at scale instead

1. SageMaker auto-scaling (already configured in deploy script).
2. Backend: add multiple uvicorn workers (`--workers 4`) behind a load balancer.
3. Keep per-user pipeline locks in backend to prevent duplicate submissions.

---

## Runtime contract (`/invocations`)

### ColQwen operations

```json
{"operation":"embed-query","query":"..."}
{"operation":"embed-images","images_base64":["<base64>"]}
{"operation":"score","query_embedding":[...],"doc_embeddings":[...]}
```

### Docling operation

```json
{"operation":"process-document","filename":"file.pdf","content_base64":"<base64>"}
```

### Whisper operation

```json
{"operation":"transcribe-audio","filename":"audio.wav","audio_base64":"<base64>","language":null}
```

---

## Step-by-step: Build → Push → Deploy → Test

### Prerequisites

```powershell
# Verify Docker daemon is running
docker info

# Verify AWS identity and permissions
aws sts get-caller-identity

# Set common variables (edit these for your account)
$env:AWS_REGION        = "us-west-2"
$env:AWS_ACCOUNT_ID    = "381492273521"
$env:ROLE_ARN          = "arn:aws:iam::381492273521:role/SageMaker-ColQwen-Role"
$env:REPO_NAME         = "phase2-multimodal-unified"
$env:IMAGE_TAG         = "v5"    # bump tag on every new build
$env:ENDPOINT_NAME     = "phase2-multimodal-rt"
$env:IMAGE_URI         = "$($env:AWS_ACCOUNT_ID).dkr.ecr.$($env:AWS_REGION).amazonaws.com/$($env:REPO_NAME):$($env:IMAGE_TAG)"
```

---

### Step 1 – Build Docker image

Run from **repo root** (the Dockerfile copies `Phase_2_FE_AI_Merge/backend` as context):

```powershell
cd "D:\PDZ\BKU\Learning\LVTN\GD1\Code"

docker build `
  -f "Phase_2_FE_AI_Merge/sagemaker/unified/Dockerfile" `
  -t "$($env:REPO_NAME):$($env:IMAGE_TAG)" `
  .
```

Verify the image was built:

```powershell
docker images | Select-String $env:REPO_NAME
```

---

### Step 2 – Push image to ECR

```powershell
# Create ECR repository if it does not exist
aws ecr describe-repositories `
  --repository-names $env:REPO_NAME `
  --region $env:AWS_REGION 2>$null
if ($LASTEXITCODE -ne 0) {
    aws ecr create-repository `
      --repository-name $env:REPO_NAME `
      --region $env:AWS_REGION | Out-Null
    Write-Host "ECR repository created: $env:REPO_NAME"
}

# Login to ECR
aws ecr get-login-password --region $env:AWS_REGION | `
  docker login --username AWS --password-stdin `
  "$($env:AWS_ACCOUNT_ID).dkr.ecr.$($env:AWS_REGION).amazonaws.com"

# Tag and push
docker tag "$($env:REPO_NAME):$($env:IMAGE_TAG)" $env:IMAGE_URI
docker push $env:IMAGE_URI

Write-Host "Pushed: $($env:IMAGE_URI)"
```

---

### Step 3 – Deploy endpoint

Change directory to `sagemaker/ops`:

```powershell
cd "D:\PDZ\BKU\Learning\LVTN\GD1\Code\Phase_2_FE_AI_Merge\sagemaker"

python .\ops\deploy_sagemaker_endpoint.py `
  --region            $env:AWS_REGION `
  --role-arn          $env:ROLE_ARN `
  --image-uri         $env:IMAGE_URI `
  --endpoint-name     $env:ENDPOINT_NAME `
  --instance-type     ml.g4dn.xlarge `
  --initial-instance-count 1 `
  --min-capacity      1 `
  --max-capacity      10 `
  --target-invocations-per-instance 10 `
  --env AWS_REGION=us-west-2 `
  --env UNIFIED_MAX_CONCURRENT_GPU_OPS=10 `
  --env COLQWEN_MAX_CONCURRENT_INFERENCES=10 `
  --env COLQWEN_MODEL=vidore/colqwen2-v1.0 `
  --env COLQWEN_QUANTIZATION=8bit `
  --env WHISPER_MODEL=base `
  --env DOCLING_OCR_ENGINE=rapidocr `
  --env DOCLING_ENABLE_VLM=false `
  --env DOCLING_EXPORT_IMAGES=false `
  --env DOCLING_EXPORT_TABLES=false `
  --wait
```

The `--wait` flag blocks until the endpoint is `InService` (typically 5-15 min for first deploy).

---

### Step 4 – Check endpoint status

```powershell
# Quick status check
aws sagemaker describe-endpoint `
  --endpoint-name $env:ENDPOINT_NAME `
  --region $env:AWS_REGION `
  --query "EndpointStatus" `
  --output text

# Full details
aws sagemaker describe-endpoint `
  --endpoint-name $env:ENDPOINT_NAME `
  --region $env:AWS_REGION
```

Wait for `EndpointStatus = InService` before running smoke tests.

### Why `InvocationsPerInstance` often looks like `1`

For real-time endpoints, this is a throughput/rate metric over time, not an async-endpoint
"max concurrent invocations per instance" hard limit. In the Console, the async setting shows
`-` for real-time endpoints by design.

If model/container env misses concurrency variables, your service can still behave like near
single-flight execution under load. Keep these env vars explicitly set in model deployment:

- `UNIFIED_MAX_CONCURRENT_GPU_OPS=10`
- `COLQWEN_MAX_CONCURRENT_INFERENCES=10`

Then verify with health payload and load tests before increasing beyond 10.

---

### Step 5 – Smoke tests

```powershell
cd "D:\PDZ\BKU\Learning\LVTN\GD1\Code\Phase_2_FE_AI_Merge\sagemaker"

# ColQwen (embed-query round-trip)
python .\ops\test_sagemaker_endpoint.py `
  --region $env:AWS_REGION `
  --endpoint-name $env:ENDPOINT_NAME `
  --service colqwen

# Docling (process a small PDF)
python .\ops\test_sagemaker_endpoint.py `
  --region $env:AWS_REGION `
  --endpoint-name $env:ENDPOINT_NAME `
  --service docling

# Whisper (transcribe a wav file)
python .\ops\test_sagemaker_endpoint.py `
  --region $env:AWS_REGION `
  --endpoint-name $env:ENDPOINT_NAME `
  --service whisper `
  --audio-file ".\sample.wav"

# Health probe via curl / Invoke-RestMethod (optional)
aws sagemaker-runtime invoke-endpoint `
  --endpoint-name $env:ENDPOINT_NAME `
  --content-type application/json `
  --body '{"operation":"health"}' `
  --region $env:AWS_REGION `
  /tmp/health_out.json
Get-Content /tmp/health_out.json
```

---

### Step 6 – Point backend at the endpoint

Set these in `backend/.env` (or as OS env before starting the backend):

```dotenv
USE_AWS_SAGEMAKER_INFERENCE=true
SAGEMAKER_ENDPOINT_NAME=phase2-multimodal-rt

USE_AWS_SAGEMAKER_DOCLING=true
SAGEMAKER_DOCLING_ENDPOINT_NAME=    # empty = reuse SAGEMAKER_ENDPOINT_NAME

USE_AWS_SAGEMAKER_WHISPER=true
SAGEMAKER_WHISPER_ENDPOINT_NAME=    # empty = reuse SAGEMAKER_ENDPOINT_NAME

AWS_REGION=us-west-2
```

To revert to local GPU:

```dotenv
USE_AWS_SAGEMAKER_INFERENCE=false
USE_AWS_SAGEMAKER_DOCLING=false
USE_AWS_SAGEMAKER_WHISPER=false
```

---

### Step 7 – Update endpoint (new image)

Just re-run Step 1-3 with a new `IMAGE_TAG`. The deploy script detects an existing endpoint
and calls `update_endpoint` instead of `create_endpoint`.

---

### Step 8 – Cleanup

```powershell
python .\ops\delete_sagemaker_endpoint.py `
  --region $env:AWS_REGION `
  --endpoint-name $env:ENDPOINT_NAME `
  --delete-config-and-models
```

---

## Environment variable reference


| Variable                         | Default                | Description                                          |
| -------------------------------- | ---------------------- | ---------------------------------------------------- |
| `DOCLING_ENABLE_VLM`             | `false`                | Enable VLM picture description (slow, richer output) |
| `DOCLING_ENABLE_OCR`             | `true`                 | Enable OCR for scanned documents                     |
| `DOCLING_OCR_ENGINE`             | `rapidocr`             | `rapidocr` / `tesseract` / `easyocr`                 |
| `DOCLING_EXPORT_IMAGES`          | `false`                | Export extracted images as base64 in response        |
| `DOCLING_EXPORT_TABLES`          | `false`                | Export extracted tables                              |
| `DOCLING_EXPORT_METADATA`        | `true`                 | Export document metadata JSON                        |
| `DOCLING_VLM_MODEL`              | `granite_docling`      | VLM model name (used only when VLM is ON)            |
| `WHISPER_MODEL`                  | `base`                 | `tiny` / `base` / `small` / `medium` / `large`       |
| `WHISPER_LANGUAGE`               | *(auto-detect)*        | Force language code e.g. `en`, `vi`                  |
| `COLQWEN_MODEL`                  | `vidore/colqwen2-v1.0` | ColQwen HuggingFace model id                         |
| `COLQWEN_QUANTIZATION`           | `8bit`                 | `4bit` / `8bit` / *(empty = bfloat16)*               |
| `UNIFIED_MAX_CONCURRENT_GPU_OPS` | `10`                   | Max parallel GPU operations in one container         |
| `COLQWEN_MAX_CONCURRENT_INFERENCES` | `10`                | ColQwen in-flight inference budget (when supported by server image) |
| `AWS_REGION`                     | `us-west-2`            | AWS region for boto3 clients inside container        |

---

## Related Maintained Docs

- [`../README.md`](../README.md)   maintained merged application overview.
- [`../../docs/technical/APPLICATION_OVERVIEW.md`](../../docs/technical/APPLICATION_OVERVIEW.md)   system capabilities and architecture summary.
- [`../../docs/technical/API_REFERENCE.md`](../../docs/technical/API_REFERENCE.md)   API map and operational guidance.
- [`../../docs/testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md`](../../docs/testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md)   performance evidence and scaling plan.


