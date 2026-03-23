# Findings and Reasoning - Deployment Direction

## Objective

Re-align the deployment package to current requirements:

- Use SageMaker instead of Lambda
- Keep implementation practical for 5 to 10 concurrent users now
- Preserve upgrade path to larger traffic tiers

## Findings from current codebase

1. Current implemented model-serving code in this folder is ColQwen only.
- Docling and Whisper usage exists in Phase 2 broader codebase, but not as standalone inference APIs here.

2. GPU memory risk is the real bottleneck.
- Concurrency failure mode is VRAM pressure, not web server request parsing.
- Single-process model serving plus bounded in-flight GPU operations is safer than increasing worker count.

3. For near-term traffic, managed complexity matters.
- Building full self-managed fleet orchestration now would increase operational burden.
- SageMaker endpoint plus autoscaling covers this phase requirement with less platform code.

## Why SageMaker was chosen for this phase

1. Requirement alignment
- You explicitly requested SageMaker over Lambda.

2. Delivery risk
- SageMaker reduces infrastructure assembly work for endpoint lifecycle.

3. Operational control
- Autoscaling policy can be attached directly to variant invocations.

4. Cost and scale fit for target range
- At 5 to 10 concurrent users, one small GPU endpoint with controlled scaling is usually sufficient.
- Overbuilding fleet orchestration this early can cost team time without immediate throughput benefit.

## Configuration decision for 5 to 10 concurrent users

Chosen baseline:

- ml.g4dn.xlarge
- initial instance count: 1
- autoscaling min: 1
- autoscaling max: 2
- target invocations per instance: 6
- in-container max concurrent inferences: 2
- quantization: 8bit

Rationale:

- Keeps initial spend lower than larger instance families.
- Maintains bounded concurrency to avoid GPU instability.
- Allows endpoint to scale to second instance when overlap increases.

## Why not Lambda for this workload

- Core workloads are GPU and model-memory heavy.
- Lambda execution and packaging model is not a stable fit for this sustained inference pattern.
- Lambda can still be useful for control-plane tasks, but not chosen for ColQwen serving path.

## Risk register and mitigations

Risk: P95 latency spikes during overlap bursts
- Mitigation: autoscaling policy and in-container concurrency cap

Risk: OOM at high overlap
- Mitigation: keep max_concurrent_inferences at 2 first, reduce to 1 if needed

Risk: Throughput ceiling with one model endpoint
- Mitigation: split Docling and Whisper to dedicated endpoints in next phase

Risk: Cost drift with idle endpoint
- Mitigation: endpoint schedule controls and right-sized max capacity

## Next implementation boundaries

Immediate next boundary:
- Integrate Phase_2 backend to call SageMaker endpoint for ColQwen path.

Later boundary:
- Add dedicated Whisper endpoint and dedicated Docling endpoint.
- Keep each model service independently scalable.

## Final note

This package now provides an implementable SageMaker path for current user volume while keeping architecture open for future horizontal scaling.


