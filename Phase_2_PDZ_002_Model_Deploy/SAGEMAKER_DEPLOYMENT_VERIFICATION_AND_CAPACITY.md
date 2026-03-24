# SageMaker Deployment Verification and Capacity Notes

## Purpose

This is the single consolidated record from our chat history for:

- deployment status
- local invoke/test confirmation
- current instance type used
- capacity fit discussion for your use case
- pricing-driven cleanup actions

## 1) Deployment and Endpoint Status Confirmation

From the verified CLI outputs in chat:

- AWS identity call succeeded (`aws sts get-caller-identity`).
- Endpoint `phase2-colqwen-rt` reached `InService`.
- Endpoint config existed and was attached successfully.
- Model existed and was referenced by endpoint config.

Observed endpoint config details from chat output:

- Endpoint name: `phase2-colqwen-rt`
- Endpoint config: `phase2-colqwen-rt-cfg-20260321122605`
- Model: `phase2-colqwen-rt-model-20260321122605`
- Instance type actually used in that successful deployment: `ml.g5.xlarge`

## 2) Local Code Invocation Confirmation (Successful)

Yes, we successfully invoked the deployed SageMaker model from local code.

### Basic endpoint test (successful)

Command used:

```powershell
python Phase_2_PDZ_002_Model_Deploy_Not_Start/test_sagemaker_endpoint.py --region us-west-2 --endpoint-name phase2-colqwen-rt --concurrent-users 3
```

Observed result from chat:

- Single invoke latency: ~2193 ms
- Concurrent test (3 users): passed
- p50: ~1667 ms
- p95: ~1667 ms
- Final status: `SageMaker endpoint tests passed`

### Real pipeline test (successful)

Command used:

```powershell
python Phase_2_PDZ_002_Model_Deploy_Not_Start/test_real_pipeline.py --region us-west-2 --endpoint-name phase2-colqwen-rt --query "What is the main topic of this document?"
```

Observed result from chat:

- Pre-flight health succeeded
- GPU detected: NVIDIA A10G
- Query embedding step succeeded
- Image embedding and scoring succeeded on 5 images
- Ranking output produced
- Total pipeline time: ~27.3 s
- Final status: `Real pipeline test passed`

## 3) How Local Invocation Works in This Folder

The local scripts invoke the hosted SageMaker endpoint via `boto3` runtime client.

- Runtime client creation:
  - `boto3.client("sagemaker-runtime", region_name=...)`
- Inference call:
  - `runtime.invoke_endpoint(...)`
- Payload format:
  - JSON body with `operation` field (`embed-query`, `embed-images`, `score`, `health`)

Practical files used:

- `test_sagemaker_endpoint.py`
- `test_real_pipeline.py`

This confirms your flow: deploy to SageMaker -> call from local Python code -> receive inference results.

## 4) Current Instance Type and Capability

### Current (confirmed from chat output)

- Instance type: `ml.g5.xlarge`
- GPU family seen in health output: NVIDIA A10G

### Capability summary (practical)

- `ml.g5.xlarge` is a strong single-GPU option for ColQwen-style inference.
- It is suitable for stable low-latency retrieval and moderate concurrency.
- For a target under 100 concurrent users, one instance is usually not enough by itself; you need autoscaling and/or queueing depending on latency SLO.

## 5) Is `ml.g5.xlarge` Too Much for <100 Concurrent Users?

Short answer: it can be over-provisioned for low traffic periods, but not necessarily overkill for bursts if latency targets are strict.

Interpretation for your case:

- Your measured tests succeeded with good behavior at low concurrency.
- If average traffic is small and burst tolerance is acceptable, you can reduce cost by:
  - turning endpoint off when idle (already done), or
  - testing downsize options (for example `ml.g4dn.xlarge`) and comparing latency + OOM risk.
- If you expect true near-simultaneous high concurrency with low latency, keep `g5` and scale instance count.

## 6) Pricing-Driven Cleanup Status (Confirmed)

From our later checks in chat:

- Endpoint was deleted successfully (`phase2-colqwen-rt` not found).
- Endpoint configs and model remained initially.
- ECR repository and images remained.
- CloudWatch endpoint log group remained.

This is the expected state when deleting endpoint only to stop compute charges while keeping restart artifacts.

## 7) Cost Confirmation

Confirmed behavior:

- If endpoint is deleted, endpoint compute billing stops.
- Keeping model and endpoint config does not keep endpoint compute running.
- Small storage/registry/log charges can still remain (S3, ECR, CloudWatch).

## 8) Recommended Next Capacity Step (if you redeploy)

For your "under 100 users" scenario, do an A/B benchmark before locking instance type:

1. Deploy `ml.g4dn.xlarge` with same model settings.
2. Run the same tests (`test_sagemaker_endpoint.py`, `test_real_pipeline.py`) at increasing concurrency.
3. Compare p50/p95 latency, failure rate, and GPU memory stability.
4. Keep the cheapest profile that satisfies your latency and reliability target.
