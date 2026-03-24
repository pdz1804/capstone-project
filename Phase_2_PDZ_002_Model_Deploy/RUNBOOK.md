# Runbook - SageMaker Deployment and Operations

## Scope

This runbook provides practical steps to deploy and operate the ColQwen endpoint on SageMaker for the current 5 to 10 concurrent user target.

It includes both Console and CLI flows.

## Prerequisites

- AWS account with SageMaker and ECR permissions
- SageMaker execution role ARN
- Docker available on your build machine
- AWS CLI configured with valid credentials
- Python environment with boto3 installed
- PowerShell 5.1+ (commands in this runbook are PowerShell-first)

## Baseline Target Configuration

Use this baseline first:

- Endpoint name: phase2-colqwen-rt
- Instance type: ml.g4dn.xlarge
- Initial instances: 1
- Autoscaling: min 1, max 2
- Target invocations per instance: 6
- Quantization: 8bit
- Max concurrent inferences in container: 2

Do not optimize until this baseline is stable.

## Path A - CLI (recommended)

### 1. Build and push image to ECR

From this folder:

```powershell
$env:AWS_REGION = "us-west-2"
$env:REPO_NAME = "phase2-colqwen-sagemaker"
$env:IMAGE_TAG = "v1"
.\build_push_ecr.ps1
```

Record the printed image URI.

### 2. Deploy endpoint

```powershell
python .\deploy_sagemaker_endpoint.py `
  --region us-west-2 `
  --role-arn arn:aws:iam::<account-id>:role/<sagemaker-execution-role> `
  --image-uri <account-id>.dkr.ecr.us-west-2.amazonaws.com/phase2-colqwen-sagemaker:v1 `
  --endpoint-name phase2-colqwen-rt `
  --instance-type ml.g4dn.xlarge `
  --initial-instance-count 1 `
  --min-capacity 1 `
  --max-capacity 2 `
  --target-invocations-per-instance 6 `
  --model-name vidore/colqwen2-v1.0 `
  --quantization 8bit `
  --max-concurrent-inferences 2 `
  --wait
```

### 3. Validate endpoint behavior

```powershell
python .\test_sagemaker_endpoint.py --region us-west-2 --endpoint-name phase2-colqwen-rt --concurrent-users 5
```

Optional higher-load check:

```powershell
python .\test_sagemaker_endpoint.py --region us-west-2 --endpoint-name phase2-colqwen-rt --concurrent-users 10
```

### 4. Update endpoint safely

When you have a new image tag:

- Push new image tag to ECR
- Re-run deploy_sagemaker_endpoint.py with same endpoint name and new image URI
- Script will update endpoint config and endpoint in place

### 5. Cleanup resources

```powershell
python .\delete_sagemaker_endpoint.py --region us-west-2 --endpoint-name phase2-colqwen-rt --delete-config-and-models
```

## Path B - Console

### 1. Build image and push to ECR

Use build_push_ecr.ps1 from CLI path first.

### 2. Create model in SageMaker Console

- Open SageMaker Console
- Inference > Models > Create model
- Container image: your ECR image URI
- Environment variables:
  - COLQWEN_MODEL=vidore/colqwen2-v1.0
  - COLQWEN_QUANTIZATION=8bit
  - COLQWEN_MAX_CONCURRENT_INFERENCES=2
  - SAGEMAKER_SERVICE_MODE=true
- Execution role: your SageMaker role

### 3. Create endpoint configuration

- Inference > Endpoint configurations > Create
- Variant name: AllTraffic
- Instance type: ml.g4dn.xlarge
- Initial instance count: 1
- Weight: 1.0

### 4. Create endpoint

- Inference > Endpoints > Create
- Endpoint name: phase2-colqwen-rt
- Select the endpoint configuration created above

### 5. Configure autoscaling

Use Application Auto Scaling for resource:

- endpoint/phase2-colqwen-rt/variant/AllTraffic
- Min capacity: 1
- Max capacity: 2
- Target tracking metric: SageMakerVariantInvocationsPerInstance
- Target value: 6

## SageMaker Request Shape

This container supports native SageMaker endpoints:

- GET /ping
- POST /invocations

Invoke payload for query embedding:

```json
{
  "operation": "embed-query",
  "query": "What is multimodal retrieval?"
}
```

Invoke payload for scoring:

```json
{
  "operation": "score",
  "query_embedding": [[0.1, 0.2]],
  "doc_embeddings": [[[0.1, 0.2], [0.2, 0.3]]]
}
```

Invoke payload for image embedding:

```json
{
  "operation": "embed-images",
  "images_base64": ["<base64-image-1>", "<base64-image-2>"]
}
```

## Tuning Rules for this phase

For your current target, apply these constraints:

1. Keep max_concurrent_inferences at 2 initially.
2. Keep uvicorn workers at 1.
3. Scale by endpoint instance count first, not by workers.
4. Prefer quantization 8bit first, test 4bit only after baseline is stable.

## Troubleshooting

- Symptom: endpoint is slow at 8 to 10 users
  - Action: verify autoscaling policy attached and endpoint scaled to 2 instances.

- Symptom: GPU OOM errors
  - Action: reduce max_concurrent_inferences to 1 or reduce batch size in caller.

- Symptom: model load timeout
  - Action: keep initial instance count at 1 and use wait mode on deployment script.

- Symptom: test script fails with non-200 response
  - Action: check CloudWatch logs for model container and validate operation payload.

## Important Boundaries

- This folder currently deploys ColQwen serving only.
- Docling and Whisper service deployment are architecture recommendations and next steps, not completed API services in this folder yet.
- Lambda is intentionally not used for this model-serving path.


