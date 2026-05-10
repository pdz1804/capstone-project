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

## 9) Raw Successful Logs from Chat History

This section appends the successful testing and verification logs captured in our chat.

### 9.1 Endpoint status and config check (success)

```text
{
    "UserId": "381492273521",
    "Account": "381492273521",
    "Arn": "arn:aws:iam::381492273521:root"
}

DescribeEndpoint:
- CreationTime: 2026-03-21T19:26:07.843000+07:00
- EndpointStatus: InService
- FailureReason: None
- LastModifiedTime: 2026-03-21T19:30:34.966000+07:00

DescribeEndpoint ProductionVariants:
- VariantName: AllTraffic
- CurrentInstanceCount: 1
- DesiredInstanceCount: 1
- CurrentWeight: 1.0
- ResolvedImage: 381492273521.dkr.ecr.us-west-2.amazonaws.com/phase2-colqwen-sagemaker@sha256:123f00c942328ede932adcd065d6a6dbdefe557b40d46471cb9ab998aed4aa31

EndpointConfigName:
- phase2-colqwen-rt-cfg-20260321122605

DescribeEndpointConfig ProductionVariants:
- VariantName: AllTraffic
- InstanceType: ml.g5.xlarge
- InitialInstanceCount: 1
- ModelName: phase2-colqwen-rt-model-20260321122605

ListEndpoints:
- phase2-colqwen-rt | InService | 2026-03-21T19:30:34.966000+07:00
```

### 9.2 Basic invoke and concurrency test script (success)

Command:

```powershell
python Phase_2_PDZ_002_Model_Deploy_Not_Start/test_sagemaker_endpoint.py --region us-west-2 --endpoint-name phase2-colqwen-rt --concurrent-users 3
```

Output:

```text
Testing endpoint: phase2-colqwen-rt
Single invoke latency: 2193.3 ms
Running concurrent invoke test with 3 users
Concurrent latency p50: 1667.1 ms
Concurrent latency p95: 1667.1 ms
SageMaker endpoint tests passed
```

### 9.3 Real pipeline end-to-end test script (success)

Command:

```powershell
python Phase_2_PDZ_002_Model_Deploy_Not_Start/test_real_pipeline.py --region us-west-2 --endpoint-name phase2-colqwen-rt --query "What is the main topic of this document?"
```

Output:

```text
============================================================
Endpoint : phase2-colqwen-rt  (us-west-2)
Images   : 5 file(s)
Query    : What is the main topic of this document?
============================================================
[Pre-flight] Endpoint health
  model       : vidore/colqwen2-v1.0
  quantization: 8bit
  load_time_s : 68.8
  GPU         : NVIDIA A10G  (22.2 GB)
  VRAM used   : 2.45 GB allocated  /  2.57 GB reserved  /  19.62 GB free
  GPU util    : 0%

[Step 1/3] embed-query   'What is the main topic of this document?' ...
  ✓ Query embedded in 425 ms
    n_tokens  : 19
    embed_dim : 128

[Step 2/3] embed-images + score   processing 5 image(s) ...
  [1/5] page_001_full.png  (649 KB) ...  embed=3033 ms  score=865 ms  (patches=755, score=16.886)
  [2/5] page_002_full.png  (884 KB) ...  embed=936 ms  score=1526 ms  (patches=755, score=16.895)
  [3/5] page_003_full.png  (823 KB) ...  embed=2382 ms  score=723 ms  (patches=755, score=16.854)
  [4/5] page_004_full.png  (857 KB) ...  embed=1141 ms  score=924 ms  (patches=755, score=16.891)
  [5/5] page_005_full.png  (762 KB) ...  embed=1148 ms  score=1041 ms  (patches=755, score=16.892)
  ✓ 5 images processed
    embed_dim     : 128
    patches/image : [755, 755, 755, 755, 755]
    embed total   : 8640 ms
    score total   : 5078 ms

Total pipeline time: 27264 ms

[Step 3/3] ranking

Ranked retrieval results (highest relevance first)
  # 1  score=  16.895  page_002_full.png
  # 2  score=  16.892  page_005_full.png
  # 3  score=  16.891  page_004_full.png
  # 4  score=  16.886  page_001_full.png
  # 5  score=  16.854  page_003_full.png

Real pipeline test passed ✓
```

### 9.4 Endpoint stop validation (success)

Command summary:

```powershell
python .\delete_sagemaker_endpoint.py --region $REGION --endpoint-name $ENDPOINT_NAME
```

Output:

```text
Deleting endpoint: phase2-colqwen-rt
Endpoint deletion requested. Config and model resources were kept.
```

Follow-up verification output:

```text
DescribeEndpoint error:
- ValidationException: Could not find endpoint "phase2-colqwen-rt".

Endpoint configs kept:
- phase2-colqwen-rt-cfg-20260321115450
- phase2-colqwen-rt-cfg-20260321122605

Models kept:
- phase2-colqwen-rt-model-20260321122605
```
