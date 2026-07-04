# Phase 2 SageMaker Hosting Pack

This folder is the maintained SageMaker deployment pack for Phase 2 model inference. It replaces the older ColQwen-only deployment pack.

Use this folder for current AWS SageMaker work:

- Unified endpoint: one SageMaker real-time endpoint serving Docling, Whisper, and ColQwen.
- Split endpoints: optional one-endpoint-per-model layout for independent scaling.
- Ops scripts: build, deploy/update, test, and delete endpoint resources.
- Backend integration: the maintained backend reads SageMaker settings from `Phase_2/code/backend/config/default.yaml`, `.env`, or process environment.

## Folder Layout

```text
Phase_2/code/sagemaker/
  README.md
  SAGEMAKER_ANALYSIS_CORRECTED.md
  SUMMARY_CORRECTED.md
  unified/
    server.py
    Dockerfile
    requirements.txt
    sagemaker_entrypoint.sh
    build_push_ecr.ps1
    build_push_ecr.sh
  colqwen/
    server.py
    Dockerfile
    requirements.txt
    sagemaker_entrypoint.sh
  docling/
    server.py
    Dockerfile
    requirements.txt
    sagemaker_entrypoint.sh
  whisper/
    server.py
    Dockerfile
    requirements.txt
    sagemaker_entrypoint.sh
  ops/
    deploy_sagemaker_endpoint.py
    delete_sagemaker_endpoint.py
    test_sagemaker_endpoint.py
```

## Which Endpoint Pattern To Use

| Pattern | Path | When to use |
| --- | --- | --- |
| Unified endpoint | `unified/` | Recommended default. Lower ops overhead and one endpoint for Docling, Whisper, and ColQwen. |
| ColQwen split endpoint | `colqwen/` | Use when visual retrieval needs independent scaling or rollout. |
| Docling split endpoint | `docling/` | Use when document parsing load dominates. |
| Whisper split endpoint | `whisper/` | Use when audio/video transcription load dominates. |

For this project, prefer the unified endpoint unless you have a clear scaling reason to split services.

## Runtime Contract

All SageMaker containers expose SageMaker-compatible endpoints:

- `GET /ping`
- `POST /invocations`

Unified endpoint operations:

```json
{"operation":"health"}
{"operation":"embed-query","query":"What is multimodal retrieval?"}
{"operation":"embed-images","images_base64":["<base64-image>"]}
{"operation":"score","query_embedding":[...],"doc_embeddings":[...]}
{"operation":"process-document","filename":"file.pdf","content_base64":"<base64-file>"}
{"operation":"transcribe-audio","filename":"audio.wav","audio_base64":"<base64-audio>","language":null}
```

## Defaults

These defaults are aligned with the backend config and are chosen for stable first deployment.

| Setting | Default | Override env |
| --- | --- | --- |
| AWS region | `us-west-2` | `AWS_REGION` |
| Unified GPU concurrency | `10` | `UNIFIED_MAX_CONCURRENT_GPU_OPS` |
| ColQwen model | `vidore/colqwen2-v1.0` | `COLQWEN_MODEL` |
| ColQwen quantization | `8bit` | `COLQWEN_QUANTIZATION` |
| ColQwen concurrency | `10` | `COLQWEN_MAX_CONCURRENT_INFERENCES` |
| Whisper model | `base` | `WHISPER_MODEL` |
| Whisper language | auto-detect | `WHISPER_LANGUAGE` |
| Docling OCR | `true` | `DOCLING_ENABLE_OCR` |
| Docling OCR engine | `rapidocr` | `DOCLING_OCR_ENGINE` |
| Docling VLM picture description | `false` | `DOCLING_ENABLE_VLM` |
| Docling image export | `false` | `DOCLING_EXPORT_IMAGES` |
| Docling table export | `false` | `DOCLING_EXPORT_TABLES` |

Keep VLM and image/table export off unless you need richer parsing output. Those options are slower and increase response size.

## Prerequisites

- Docker running locally.
- AWS CLI configured.
- AWS account with ECR, SageMaker, IAM pass role, CloudWatch logs, and Application Auto Scaling permissions.
- SageMaker execution role ARN.
- Python environment with `boto3` installed for ops scripts.

Set variables in PowerShell:

```powershell
$env:AWS_REGION     = "us-west-2"
$env:AWS_ACCOUNT_ID = "<account-id>"
$env:ROLE_ARN       = "arn:aws:iam::<account-id>:role/<sagemaker-execution-role>"
$env:REPO_NAME      = "phase2-multimodal-unified"
$env:IMAGE_TAG      = "v1"
$env:ENDPOINT_NAME  = "phase2-multimodal-rt"
$env:IMAGE_URI      = "$($env:AWS_ACCOUNT_ID).dkr.ecr.$($env:AWS_REGION).amazonaws.com/$($env:REPO_NAME):$($env:IMAGE_TAG)"
```

## Build And Push Unified Image

Run from the repository root:

```powershell
docker build `
  -f "Phase_2/code/sagemaker/unified/Dockerfile" `
  -t "$($env:REPO_NAME):$($env:IMAGE_TAG)" `
  .
```

Create the ECR repository if needed:

```powershell
aws ecr describe-repositories `
  --repository-names $env:REPO_NAME `
  --region $env:AWS_REGION

if ($LASTEXITCODE -ne 0) {
  aws ecr create-repository `
    --repository-name $env:REPO_NAME `
    --region $env:AWS_REGION
}
```

Login, tag, and push:

```powershell
aws ecr get-login-password --region $env:AWS_REGION | `
  docker login --username AWS --password-stdin `
  "$($env:AWS_ACCOUNT_ID).dkr.ecr.$($env:AWS_REGION).amazonaws.com"

docker tag "$($env:REPO_NAME):$($env:IMAGE_TAG)" $env:IMAGE_URI
docker push $env:IMAGE_URI
```

You can also use:

```powershell
cd Phase_2/code/sagemaker/unified
.\build_push_ecr.ps1
```

or:

```bash
cd Phase_2/code/sagemaker/unified
./build_push_ecr.sh
```

## Deploy Or Update Endpoint

Run from `Phase_2/code/sagemaker`:

```powershell
python .\ops\deploy_sagemaker_endpoint.py `
  --region $env:AWS_REGION `
  --role-arn $env:ROLE_ARN `
  --image-uri $env:IMAGE_URI `
  --endpoint-name $env:ENDPOINT_NAME `
  --instance-type ml.g4dn.xlarge `
  --initial-instance-count 1 `
  --min-capacity 1 `
  --max-capacity 10 `
  --target-invocations-per-instance 10 `
  --env AWS_REGION=$env:AWS_REGION `
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

The deploy script creates a timestamped SageMaker model and endpoint config. If the endpoint already exists, it calls `update_endpoint`; otherwise it creates the endpoint.

## Check Endpoint Status

```powershell
aws sagemaker describe-endpoint `
  --endpoint-name $env:ENDPOINT_NAME `
  --region $env:AWS_REGION `
  --query "{Status:EndpointStatus,LastModified:LastModifiedTime,Failure:FailureReason}" `
  --output table
```

Wait until `EndpointStatus` is `InService`.

## Smoke Tests

Run from `Phase_2/code/sagemaker`:

```powershell
python .\ops\test_sagemaker_endpoint.py `
  --region $env:AWS_REGION `
  --endpoint-name $env:ENDPOINT_NAME `
  --service colqwen
```

```powershell
python .\ops\test_sagemaker_endpoint.py `
  --region $env:AWS_REGION `
  --endpoint-name $env:ENDPOINT_NAME `
  --service docling
```

```powershell
python .\ops\test_sagemaker_endpoint.py `
  --region $env:AWS_REGION `
  --endpoint-name $env:ENDPOINT_NAME `
  --service whisper `
  --audio-file ".\sample.wav"
```

Concurrency smoke test, merged from the old PDZ 002 guide:

```powershell
python .\ops\test_sagemaker_endpoint.py `
  --region $env:AWS_REGION `
  --endpoint-name $env:ENDPOINT_NAME `
  --service colqwen `
  --concurrent-users 5
```

Start with 1, then 3, then 5 users before trying higher load.

## Point Backend At SageMaker

Set these in `Phase_2/code/backend/.env` or in process environment:

```dotenv
USE_AWS_SAGEMAKER_INFERENCE=true
SAGEMAKER_ENDPOINT_NAME=phase2-multimodal-rt

USE_AWS_SAGEMAKER_DOCLING=true
SAGEMAKER_DOCLING_ENDPOINT_NAME=

USE_AWS_SAGEMAKER_WHISPER=true
SAGEMAKER_WHISPER_ENDPOINT_NAME=

AWS_REGION=us-west-2
```

Leaving `SAGEMAKER_DOCLING_ENDPOINT_NAME` and `SAGEMAKER_WHISPER_ENDPOINT_NAME` empty makes the backend reuse `SAGEMAKER_ENDPOINT_NAME`.

To return to local inference:

```dotenv
USE_AWS_SAGEMAKER_INFERENCE=false
USE_AWS_SAGEMAKER_DOCLING=false
USE_AWS_SAGEMAKER_WHISPER=false
```

## Turn Endpoint Off And On

This section is preserved from the useful part of the older ColQwen-only deployment notes.

Important billing behavior:

- A real-time endpoint that exists and is `InService` keeps billing instance compute.
- To stop endpoint compute billing, delete the endpoint.
- You can keep the model and endpoint config for easier restart.
- Keeping model/config does not bill endpoint compute, but ECR, S3, and CloudWatch storage can still have small charges.

Turn off compute billing but keep model/config:

```powershell
python .\ops\delete_sagemaker_endpoint.py `
  --region $env:AWS_REGION `
  --endpoint-name $env:ENDPOINT_NAME
```

Turn off fully:

```powershell
python .\ops\delete_sagemaker_endpoint.py `
  --region $env:AWS_REGION `
  --endpoint-name $env:ENDPOINT_NAME `
  --delete-config-and-models
```

Turn on later from the latest endpoint config:

```powershell
$ENDPOINT_CONFIG = aws sagemaker list-endpoint-configs `
  --region $env:AWS_REGION `
  --name-contains "$($env:ENDPOINT_NAME)-cfg-" `
  --query "sort_by(EndpointConfigs,&CreationTime)[-1].EndpointConfigName" `
  --output text

aws sagemaker create-endpoint `
  --region $env:AWS_REGION `
  --endpoint-name $env:ENDPOINT_NAME `
  --endpoint-config-name $ENDPOINT_CONFIG
```

## Capacity Notes

Historical PDZ 002 evidence showed a ColQwen-only endpoint successfully running on `ml.g5.xlarge` with NVIDIA A10G:

- Query embedding succeeded.
- Five image embeddings and scoring succeeded.
- A 3-user concurrency smoke test passed.
- A real pipeline test completed in roughly 27 seconds for 5 images.

Treat those numbers as historical evidence only. Current maintained deployment is the unified endpoint in this folder, so re-benchmark before using the numbers in reports.

Practical tuning rules:

- Start with `ml.g4dn.xlarge`, `initial=1`, `min=1`, `max=10`.
- Keep `COLQWEN_QUANTIZATION=8bit` first.
- Increase endpoint instance count before increasing process workers.
- If you see GPU OOM, reduce `UNIFIED_MAX_CONCURRENT_GPU_OPS` or `COLQWEN_MAX_CONCURRENT_INFERENCES`.
- For under-100-user demos, compare `ml.g4dn.xlarge` and `ml.g5.xlarge` using the same smoke/load tests.

## Real-Time Endpoint Metric Note

`InvocationsPerInstance` is a rate metric for SageMaker real-time endpoints, not a hard concurrent-request limit. The Console can show async concurrency fields as empty for real-time endpoints. Verify actual behavior with endpoint health payloads and smoke/load tests.

## Related Docs

- `Phase_2/code/backend/README.md` - backend local/API workflow.
- `Phase_2/code/terraform/README.md` - AWS infrastructure around ECS/ECR/ALB/SageMaker.
- `Phase_2/docs/evaluation/README.md` - evaluation summaries.
- `Phase_2/code/sagemaker/SAGEMAKER_ANALYSIS_CORRECTED.md` - architecture/capacity analysis notes.
- `Phase_2/code/sagemaker/SUMMARY_CORRECTED.md` - short corrected SageMaker summary.
