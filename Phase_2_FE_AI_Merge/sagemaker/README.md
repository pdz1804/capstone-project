# SageMaker Hosting Pack (Docling + Whisper + ColQwen)

This folder supports two deployment patterns:

1. **Recommended now**: one unified endpoint hosting all 3 operations (cost-saving test mode)
2. Split endpoints per model (legacy/flexible mode)

## Folder layout

- `unified/` (**single endpoint for all 3**)
  - `server.py`
  - `Dockerfile`
  - `requirements.txt`
  - `sagemaker_entrypoint.sh`
  - `build_push_ecr.ps1`
  - `build_push_ecr.sh`
- `colqwen/` (optional split service)
  - `server.py`
  - `Dockerfile`
  - `requirements.txt`
  - `sagemaker_entrypoint.sh`
- `docling/` (optional split service)
  - `server.py`
  - `Dockerfile`
  - `requirements.txt`
  - `sagemaker_entrypoint.sh`
- `whisper/` (optional split service)
  - `server.py`
  - `Dockerfile`
  - `requirements.txt`
  - `sagemaker_entrypoint.sh`
- `ops/`
  - `deploy_sagemaker_endpoint.py`
  - `delete_sagemaker_endpoint.py`
  - `test_sagemaker_endpoint.py`

## Unified Runtime Contract (`/invocations`)

Unified endpoint supports:

- `GET /ping` (health probe)
- `POST /invocations` with an `operation` field
- `GET /health`

### ColQwen operations

- `{"operation":"embed-query","query":"..."}`
- `{"operation":"embed-images","images_base64":["..."]}`
- `{"operation":"score","query_embedding":[...],"doc_embeddings":[...]}`

### Docling operation

- `{"operation":"process-document","filename":"file.pdf","content_base64":"..."}`

### Whisper operation

- `{"operation":"transcribe-audio","filename":"audio.wav","audio_base64":"...","language":null}`

## Build and Deploy (single endpoint, us-west-2 default)

### 1) Build and push unified image

Build from repo root (Docker context must include backend source):

```powershell
cd D:\PDZ\BKU\Learning\LVTN\GD1\Code

$env:AWS_REGION = "us-west-2"
$env:ACCOUNT_ID = "<your-account-id>"
$env:REPO_NAME = "phase2-multimodal-unified"
$env:IMAGE_TAG = "v1"

aws ecr describe-repositories --repository-names $env:REPO_NAME --region $env:AWS_REGION 2>$null
if ($LASTEXITCODE -ne 0) {
  aws ecr create-repository --repository-name $env:REPO_NAME --region $env:AWS_REGION | Out-Null
}

aws ecr get-login-password --region $env:AWS_REGION | docker login --username AWS --password-stdin "$($env:ACCOUNT_ID).dkr.ecr.$($env:AWS_REGION).amazonaws.com"

docker build -f "Phase_2_FE_AI_Merge/sagemaker/unified/Dockerfile" -t "$($env:REPO_NAME):$($env:IMAGE_TAG)" .
docker tag "$($env:REPO_NAME):$($env:IMAGE_TAG)" "$($env:ACCOUNT_ID).dkr.ecr.$($env:AWS_REGION).amazonaws.com/$($env:REPO_NAME):$($env:IMAGE_TAG)"
docker push "$($env:ACCOUNT_ID).dkr.ecr.$($env:AWS_REGION).amazonaws.com/$($env:REPO_NAME):$($env:IMAGE_TAG)"
```

### 2) Deploy endpoint (`ml.g4dn.xlarge` for cost-saving tests)

```powershell
python .\ops\deploy_sagemaker_endpoint.py `
  --region us-west-2 `
  --role-arn arn:aws:iam::<account-id>:role/<sagemaker-execution-role> `
  --image-uri <account-id>.dkr.ecr.us-west-2.amazonaws.com/phase2-multimodal-unified:v1 `
  --endpoint-name phase2-multimodal-rt `
  --instance-type ml.g4dn.xlarge `
  --initial-instance-count 1 `
  --min-capacity 1 `
  --max-capacity 2 `
  --target-invocations-per-instance 2 `
  --env AWS_REGION=us-west-2 `
  --env UNIFIED_MAX_CONCURRENT_GPU_OPS=1 `
  --env COLQWEN_MODEL=vidore/colqwen2-v1.0 `
  --env COLQWEN_QUANTIZATION=8bit `
  --env WHISPER_MODEL=base `
  --env DOCLING_OCR_ENGINE=rapidocr `
  --env DOCLING_ENABLE_VLM=true `
  --env DOCLING_VLM_MODEL=granite_docling `
  --wait
```

### 3) Smoke test endpoint

```powershell
python .\ops\test_sagemaker_endpoint.py --region us-west-2 --endpoint-name phase2-multimodal-rt --service colqwen
python .\ops\test_sagemaker_endpoint.py --region us-west-2 --endpoint-name phase2-multimodal-rt --service docling
python .\ops\test_sagemaker_endpoint.py --region us-west-2 --endpoint-name phase2-multimodal-rt --service whisper --audio-file .\sample.wav
```

### 4) Backend env switch (single endpoint for all 3)

```powershell
$env:AWS_REGION = "us-west-2"

$env:USE_AWS_SAGEMAKER_INFERENCE = "true"
$env:SAGEMAKER_ENDPOINT_NAME = "phase2-multimodal-rt"

$env:USE_AWS_SAGEMAKER_DOCLING = "true"
# Optional: leave empty to reuse SAGEMAKER_ENDPOINT_NAME
$env:SAGEMAKER_DOCLING_ENDPOINT_NAME = ""

$env:USE_AWS_SAGEMAKER_WHISPER = "true"
# Optional: leave empty to reuse SAGEMAKER_ENDPOINT_NAME
$env:SAGEMAKER_WHISPER_ENDPOINT_NAME = ""
```

### 5) Cleanup

```powershell
python .\ops\delete_sagemaker_endpoint.py --region us-west-2 --endpoint-name phase2-multimodal-rt --delete-config-and-models
```

## PowerShell Commands (Run List - Final)

Use this exact sequence from repo root.

```powershell
# 0) Repo root
cd "D:\PDZ\BKU\Learning\LVTN\GD1\Code"

# 1) Verify Docker daemon first (fixes: //./pipe/dockerDesktopLinuxEngine not found)
docker info
# If this fails, start Docker Desktop and wait until it is fully running.

# 2) Verify AWS identity
aws sts get-caller-identity

# 3) Set variables (validated account + region)
$env:AWS_REGION = "us-west-2"
$env:AWS_ACCOUNT_ID = "381492273521"
$env:ROLE_ARN = "arn:aws:iam::381492273521:role/SageMaker-ColQwen-Role"
$env:REPO_NAME = "phase2-multimodal-unified"
$env:IMAGE_TAG = "v1"
$env:ENDPOINT_NAME = "phase2-multimodal-rt"

# 4) Build + push image (uses robust script)
powershell -ExecutionPolicy Bypass -File ".\Phase_2_FE_AI_Merge\sagemaker\unified\build_push_ecr.ps1"

# 5) Deploy endpoint (g4 test size)
cd "D:\PDZ\BKU\Learning\LVTN\GD1\Code\Phase_2_FE_AI_Merge\sagemaker"

python .\ops\deploy_sagemaker_endpoint.py `
  --region us-west-2 `
  --role-arn $env:ROLE_ARN `
  --image-uri "$($env:AWS_ACCOUNT_ID).dkr.ecr.us-west-2.amazonaws.com/$($env:REPO_NAME):$($env:IMAGE_TAG)" `
  --endpoint-name $env:ENDPOINT_NAME `
  --instance-type ml.g4dn.xlarge `
  --initial-instance-count 1 `
  --min-capacity 1 `
  --max-capacity 2 `
  --target-invocations-per-instance 2 `
  --env AWS_REGION=us-west-2 `
  --env UNIFIED_MAX_CONCURRENT_GPU_OPS=1 `
  --env COLQWEN_MODEL=vidore/colqwen2-v1.0 `
  --env COLQWEN_QUANTIZATION=8bit `
  --env WHISPER_MODEL=base `
  --env DOCLING_OCR_ENGINE=rapidocr `
  --env DOCLING_ENABLE_VLM=true `
  --env DOCLING_VLM_MODEL=granite_docling `
  --wait

# 6) Smoke tests
python .\ops\test_sagemaker_endpoint.py --region us-west-2 --endpoint-name $env:ENDPOINT_NAME --service colqwen
python .\ops\test_sagemaker_endpoint.py --region us-west-2 --endpoint-name $env:ENDPOINT_NAME --service docling
# Prepare one local wav file first:
python .\ops\test_sagemaker_endpoint.py --region us-west-2 --endpoint-name $env:ENDPOINT_NAME --service whisper --audio-file ".\sample.wav"

# 7) Backend switch to single shared endpoint
$env:AWS_REGION = "us-west-2"
$env:USE_AWS_SAGEMAKER_INFERENCE = "true"
$env:USE_AWS_SAGEMAKER_DOCLING = "true"
$env:USE_AWS_SAGEMAKER_WHISPER = "true"
$env:SAGEMAKER_ENDPOINT_NAME = $env:ENDPOINT_NAME
$env:SAGEMAKER_DOCLING_ENDPOINT_NAME = ""
$env:SAGEMAKER_WHISPER_ENDPOINT_NAME = ""

# 8) Cleanup (when needed)
python .\ops\delete_sagemaker_endpoint.py --region us-west-2 --endpoint-name $env:ENDPOINT_NAME --delete-config-and-models
```
