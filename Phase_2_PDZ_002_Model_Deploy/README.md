# Phase 2 PDZ 002 - SageMaker Inference Deployment

## Decision Summary

This folder is now aligned to a SageMaker-first deployment model.

Latest consolidated verification and sizing notes:

- See `SAGEMAKER_DEPLOYMENT_VERIFICATION_AND_CAPACITY.md`

Key decisions:

- Managed service target: AWS SageMaker Real-Time Inference
- Target traffic tier for now: 5 to 10 concurrent users
- No Lambda path for core model inference
- Primary deployed model in this folder: ColQwen endpoint
- Docling and Whisper are documented in architecture decisions but are not yet implemented as separate API services in this folder

## Why SageMaker for this phase

This direction was chosen to match your requirement and to reduce operational risk during early production rollout.

Reasons:

1. Managed endpoint lifecycle
- Endpoint creation, update, rollback, and health are managed by SageMaker APIs.
- Fewer moving pieces than self-managed infrastructure orchestration for this stage.

2. Native autoscaling controls
- Application Auto Scaling can scale endpoint instance count based on invocations per instance.
- This is enough for 5 to 10 concurrent users without building custom ASG plus ALB logic first.

3. Better operational baseline for team handoff
- IAM role based access and endpoint metadata are easier to standardize for team operations.
- This keeps the operational model consistent around SageMaker-managed endpoints.

4. Lambda is not suitable for this model mix
- ColQwen and Docling workloads are GPU-centric and large-memory.
- Lambda does not provide a stable fit for this workload shape at your required throughput.

## Current Implemented Scope in this folder

Implemented now:

- SageMaker-compatible FastAPI server with:
  - /ping
  - /invocations
  - /health
  - embedding and scoring operations mapped via operation in /invocations
- Quantization controls for ColQwen: none, 4bit, 8bit
- Concurrency guard for GPU operations
- ECR build and push script
- SageMaker deploy and delete scripts
- SageMaker endpoint test script

Not implemented yet in this folder:

- Dedicated Docling service API
- Dedicated Whisper service API
- Full remote integration wiring in Phase_2 backend to call all services by endpoint name

## 5 to 10 Concurrent Users - Recommended Configuration

This is the baseline profile for now.

Endpoint configuration:

- Instance type: ml.g4dn.xlarge
- Initial instance count: 1
- Autoscaling min capacity: 1
- Autoscaling max capacity: 2
- Target invocations per instance: 6

Model runtime settings:

- COLQWEN_MODEL: vidore/colqwen2-v1.0
- COLQWEN_QUANTIZATION: 8bit
- COLQWEN_MAX_CONCURRENT_INFERENCES: 2
- Uvicorn workers: 1

Why this profile was chosen:

- Single instance keeps cost low at low steady-state traffic.
- Max capacity 2 gives headroom when user requests overlap.
- Concurrency=2 inside one model process prevents uncontrolled VRAM spikes while still allowing overlapping calls.
- 8bit is the stability and memory balance point on T4-class GPU.

## Folder Map

- server.py
  - SageMaker-compatible inference server
- Dockerfile
  - Container image definition for endpoint deployment
- sagemaker_entrypoint.sh
  - Container startup command for SageMaker runtime mode
- build_push_ecr.ps1
  - Build and push image to ECR from PowerShell
- build_push_ecr.sh
  - Build and push image to ECR
- deploy_sagemaker_endpoint.py
  - Create or update endpoint and configure autoscaling
- delete_sagemaker_endpoint.py
  - Delete endpoint resources
- test_sagemaker_endpoint.py
  - Invoke endpoint and run concurrency test
- RUNBOOK.md
  - Step-by-step operational guide
- FINDINGS_AND_REASONING.md
  - Deep findings and architecture rationale

## Fast Start

1. Build and push image (PowerShell)

```powershell
$env:AWS_REGION = "us-west-2"
$env:REPO_NAME = "phase2-colqwen-sagemaker"
$env:IMAGE_TAG = "v1"
.\build_push_ecr.ps1
```

2. Deploy endpoint

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
  --quantization 8bit `
  --max-concurrent-inferences 2 `
  --wait
```

3. Validate endpoint

```powershell
python .\test_sagemaker_endpoint.py --region us-west-2 --endpoint-name phase2-colqwen-rt --concurrent-users 5
```

## Cleanup

```powershell
python .\delete_sagemaker_endpoint.py --region us-west-2 --endpoint-name phase2-colqwen-rt --delete-config-and-models
```

For full deployment operations, use RUNBOOK.md.

