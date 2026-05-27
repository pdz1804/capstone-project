# Operations Runbook

**For**: Phase_2_FE_AI_Merge deployed system  
**Version**: 1.0  
**Last Updated**: May 14, 2026  
**Target Audience**: DevOps, SRE, On-Call Engineers  

---

## Quick Reference - Common Issues

| Issue | Symptom | Fix Time | Severity |
|-------|---------|----------|----------|
| ECS task unhealthy | ALB returns 502 | 2-5 min | 🔴 Critical |
| Search endpoint timeout | 13% error rate under load | 5-10 min | 🔴 Critical |
| Qdrant offline | All search fails (503) | 1-2 min | 🔴 Critical |
| Bedrock throttling | 429 Too Many Requests | 1 min (retry) | 🟠 High |
| Document processing slow | Processing >5 min | 5 min (investigation) | 🟡 Medium |
| GPU memory error | OOM exception in logs | 2 min (restart) | 🟡 Medium |

---

## CRITICAL: ECS Task Unhealthy (502 Bad Gateway)

### Diagnosis

**Symptom**: ALB health check failing, auto-refresh shows 502 Bad Gateway

**Step 1: Check CloudWatch Logs**
```bash
# Option A: AWS CLI
aws logs tail /ecs/bk-mind-backend --follow --since 5m

# Option B: AWS Console
# CloudWatch → Log Groups → /ecs/bk-mind-backend → Real-time logs
```

**Step 2: Look for error patterns**
```
Common errors:
✗ "Connection refused" → Port 5000 not listening
✗ "OutOfMemory" / "MemoryError" → Container OOMKilled
✗ "Exception" / "Traceback" → Application crash
✓ "Healthy" / "Started successfully" → Task is OK
```

### Root Cause & Recovery

#### Root Cause A: Port Not Listening

**Symptoms**:
```
Connection refused on port 5000
HTTPException: Cannot connect to uvicorn server
```

**Recovery** (2-3 minutes):
```bash
# Option 1: Force new deployment
aws ecs update-service \
  --cluster bk-mind \
  --service bk-mind-backend \
  --force-new-deployment

# Wait for new task to start (~60 seconds)
# Verify: curl http://<ALB-DNS>/health should return 200
```

#### Root Cause B: Out of Memory (OOMKilled)

**Symptoms**:
```
Memory exhausted
Task terminated due to OOMKilled
Cannot allocate memory
```

**Recovery** (5-10 minutes):
```bash
# Step 1: Increase task memory in Terraform
# terraform/main.tf, search for: memory_soft_limit / memory_hard_limit

# Current: memory_hard_limit = 512  # MB
# Change:  memory_hard_limit = 1024 # MB

terraform apply -target=aws_ecs_task_definition.backend

# Step 2: Redeploy with new task definition
aws ecs update-service \
  --cluster bk-mind \
  --service bk-mind-backend \
  --force-new-deployment

# Wait for new task (will use larger memory)
```

**Why OOM Happens**:
- ColQwen model (6-24 GB depending on quantization)
- FAISS index (can grow large with 10k+ documents)
- Concurrent requests (each holds memory)

#### Root Cause C: Application Crash

**Symptoms**:
```
Traceback (most recent call last):
ImportError: No module named 'transformers'
AttributeError: 'NoneType' object has no attribute ...
```

**Recovery** (5-15 minutes):

**Option A: Check recent deployments**
```bash
# View last 5 deployments
aws ecs describe-services \
  --cluster bk-mind \
  --services bk-mind-backend \
  --query 'services[0].deployments[0:5]' \
  --output table

# Note the task definition of last working deployment (CreatedAt)
```

**Option B: Revert to previous task definition**
```bash
# Get previous task definition ARN
PREV_TASK_DEF=$(aws ecs describe-services \
  --cluster bk-mind \
  --services bk-mind-backend \
  --query 'services[0].taskDefinition' \
  --output text | rev | cut -d: -f2- | rev):$(($(echo $CURRENT | rev | cut -d: -f1 | rev) - 1))

# Rollback service to previous task definition
aws ecs update-service \
  --cluster bk-mind \
  --service bk-mind-backend \
  --task-definition $PREV_TASK_DEF

# Verify new task starts
aws ecs wait services-stable \
  --cluster bk-mind \
  --services bk-mind-backend
```

**Option C: Investigate crash cause**
```bash
# Read full logs (CloudWatch → /ecs/bk-mind-backend)
# Look for:
- Missing dependency: pip install -r requirements-frozen.txt
- Module import error: check sys.path in startup
- Configuration error: verify .env variables

# Common fixes:
- pip install <missing-module>
- git pull latest code
- Redeploy
```

---

## Search Endpoint Timeout (13.25% Error Rate Under Load)

### Diagnosis

**Symptom**: JMeter concurrency test returns 502 Bad Gateway, error rate ~14%

**Step 1: Identify bottleneck**
```bash
# Check latency breakdown
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name TargetResponseTime \
  --statistics Average \
  --start-time 2026-05-14T10:00:00Z \
  --end-time 2026-05-14T10:05:00Z \
  --period 60

# Check error count
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_Target_5XX_Count \
  --statistics Sum \
  --start-time 2026-05-14T10:00:00Z \
  --end-time 2026-05-14T10:05:00Z \
  --period 60
```

**Step 2: Check specific endpoints**
```bash
# Search endpoint (most heavy)
curl -X POST http://<ALB-DNS>/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"test"}' \
  -w "HTTP %{http_code}, Time: %{time_total}s\n"

# Index endpoint
curl -X POST http://<ALB-DNS>/api/index \
  -H "Content-Type: application/json" \
  -d '{}' \
  -w "HTTP %{http_code}, Time: %{time_total}s\n"
```

### Root Cause & Recovery

#### Root Cause A: Bedrock Throttling (429 Too Many Requests)

**Symptom**:
```
Bedrock returned error code 429: ThrottlingException
Too many concurrent requests to anthropic.claude-haiku-4-5-20251001
```

**Current Status** (from code analysis):
- No circuit breaker implemented
- No request queuing
- Every request hits Bedrock immediately

**Recovery** (1-5 minutes):

**Option 1: Increase Bedrock quota** (AWS Console)
```
Bedrock → Model Access → Anthropic Claude
Look for "Inference quota" section
Increase: "Max tokens per minute" or "Concurrent requests"
```

**Option 2: Enable request queuing** (Code improvement)
```python
# This is in IMPROVEMENT_ACTION_PLAN.md Task F2
# Add to api/main.py
from asyncio import Semaphore

max_concurrent_searches = Semaphore(10)

@app.post("/api/search")
async def search(request: SearchRequest):
    async with max_concurrent_searches:
        return await search_orchestrator.search(request)
```

**Option 3: Implement circuit breaker** (Code improvement)
```python
# Wrap Bedrock calls with circuit breaker
from pybreaker import CircuitBreaker

bedrock_breaker = CircuitBreaker(fail_max=5, reset_timeout=60)

try:
    response = await bedrock_breaker.call(
        bedrock_client.invoke_model(...)
    )
except CircuitBreakerListener:
    # Fall back to cached results or simpler model
    return cache_result(query)
```

#### Root Cause B: Qdrant Overloaded

**Symptom**:
```
Qdrant search latency >1000ms
Qdrant returns 429 (too many requests)
```

**Recovery**:
```bash
# Check Qdrant health
curl http://localhost:6333/health

# Check Qdrant metrics
curl http://localhost:6333/metrics

# If overloaded:
# Option 1: Scale up Qdrant pod
#   - Increase pod memory/CPU
#   - Restart pod
# Option 2: Enable caching layer (Redis)
#   - Already configured (redis cache for search results)
#   - Verify: redis-cli INFO stats
```

#### Root Cause C: Database Throttling

**Symptom**:
```
DynamoDB ProvisionedThroughputExceededException
```

**Recovery** (2-5 minutes):
```bash
# Increase DynamoDB capacity
# AWS Console → DynamoDB → Tables → bk-mind-*
# Click on table → Capacity tab → Edit capacity

# Or via CLI
aws dynamodb update-table \
  --table-name bk-mind-sessions \
  --billing-mode PAY_PER_REQUEST  # Switch to on-demand

# On-demand mode auto-scales, costs more but handles spikes
```

---

## Qdrant Vector Database Offline

### Diagnosis

**Symptom**: All search requests return 503 Service Unavailable

**Code**: `search_routes.py` lines 107-115 detects this:
```python
if is_qdrant_unreachable(e):
    return JSONResponse(status_code=503, content={"error": "Vector database temporarily unavailable"})
```

### Recovery

**Step 1: Check Qdrant service** (1 minute)
```bash
# Test connectivity
curl http://localhost:6333/health

# If failed: "Connection refused"
# → Qdrant Docker container not running
```

**Step 2: Restart Qdrant** (1-2 minutes)
```bash
# If using Docker Compose
docker-compose -f Phase_2_FE_AI_Merge/backend/docker-compose.yml \
  restart qdrant

# If using Kubernetes
kubectl rollout restart deployment/qdrant-deployment

# If using AWS managed (VectorDB): check AWS Console
```

**Step 3: Verify recovery** (1 minute)
```bash
# Test search again
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"test"}' \
  -w "HTTP %{http_code}\n"

# Should return 200 (not 503)
```

**Step 4: If Qdrant won't start**
```bash
# Check Qdrant logs
docker logs <qdrant-container-id>

# Look for:
✗ "Permission denied" → Check volume permissions
✗ "Database corrupted" → Restore from backup
✗ "Port already in use" → Kill existing process

# Kill and restart cleanly
docker rm -f <qdrant-container-id>
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest
```

---

## Bedrock API Errors

### 429: Too Many Requests (Throttling)

**Diagnosis**:
```bash
aws logs tail /ecs/bk-mind-backend --grep "ThrottlingException"
```

**Recovery**:
- Option A: Wait 60 seconds (exponential backoff in code)
- Option B: Increase Bedrock quota (AWS Console)
- Option C: Implement request queuing (see IMPROVEMENT_ACTION_PLAN.md)

**User Communication**: "Service busy, please retry in 60 seconds"

### 504: Model Timeout

**Diagnosis**:
```bash
aws logs tail /ecs/bk-mind-backend --grep "ModelTimeoutException"
```

**Common Cause**: Bedrock model overloaded (peak traffic)

**Recovery**:
- Wait 5 minutes (peak traffic usually short)
- Retry request automatically (already in code)

**User Communication**: "Generation timeout, please retry"

---

## Document Processing Takes Too Long

### Diagnosis

**Symptom**: Processing a document takes >5 minutes

**Common Causes**:
1. **Large PDF** (100+ pages): Expected 5-10 minutes
2. **Many images**: ColQwen processing slow (~320ms per image)
3. **Video content**: Whisper transcription slow (~1:1 realtime)
4. **GPU memory low**: Falls back to CPU (5-10x slower)

**Check logs**:
```bash
aws logs tail /ecs/bk-mind-backend --grep "Processing"

# Output example:
# 2026-05-14 10:30:00 Starting document processing: document.pdf (145 pages)
# 2026-05-14 10:30:15 Normalized document (5.3s)
# 2026-05-14 10:30:45 Extracted media (30.2s)
# 2026-05-14 10:31:45 Docling processing (60.5s)
# 2026-05-14 10:32:15 Consolidating (30.1s) ← Slow stage?
# 2026-05-14 10:32:45 Complete (2m 45s total)
```

### Recovery

**If Docling slow** (>60 seconds):
- Expected: Large PDFs with complex layouts
- No action needed unless consistently >10 minutes

**If ColQwen slow** (image processing):
```bash
# Check if GPU available
nvidia-smi

# If GPU unavailable:
# → CPU fallback active
# Option: Restart to free GPU memory
docker restart bk-mind-backend
```

**If Whisper slow** (video transcription):
- Expected: Real-time (1 hour video = 60 minutes processing)
- Consider preprocessing video separately before upload

---

## Monitoring & Health Checks

### Key Metrics to Watch (CloudWatch Dashboard)

```
Refresh every 1 minute

┌─────────────────────────────────┐
│ ALB Target Health               │
│ ✓ Healthy: 100%                 │
│ ✗ Unhealthy: 0%                 │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ Backend Error Rate (5XX)         │
│ Target: <1%                      │
│ Current: 0.2% ✓                  │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ Search Endpoint Latency (p99)    │
│ Target: <5s                      │
│ Current: 2.3s ✓                  │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ Qdrant Search Latency            │
│ Target: <100ms                   │
│ Current: 45ms ✓                  │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ Bedrock Errors (4XX + 5XX)       │
│ Target: 0                        │
│ Current: 0 ✓                     │
└─────────────────────────────────┘
```

### Health Check Endpoints

```bash
# Backend health
curl http://localhost:5000/health
# Response: {"status": "healthy"}

# Qdrant health
curl http://localhost:6333/health
# Response: {"status": "ok"}

# Redis health
redis-cli ping
# Response: PONG

# Full system status
curl http://localhost:5000/status
# Response: {
#   "backend": "healthy",
#   "qdrant": "connected",
#   "redis": "connected",
#   "docling": "ready",
#   "colqwen": "loaded",
#   "bedrock": "available"
# }
```

---

## Rollback Procedure (If Major Issue)

### Prerequisites
- Previous task definition ARN (can find in ECS console history)
- Confirm issue is code-related (not infrastructure)

### Steps

```bash
# 1. Identify previous working task definition
aws ecs describe-services \
  --cluster bk-mind \
  --services bk-mind-backend \
  --query 'services[0].deployments' \
  --output table

# 2. Find previous task definition (look for oldest CreatedAt)
PREV_TASK_DEF="arn:aws:ecs:us-east-1:123456789:task-definition/bk-mind-backend:42"

# 3. Rollback service
aws ecs update-service \
  --cluster bk-mind \
  --service bk-mind-backend \
  --task-definition $PREV_TASK_DEF

# 4. Wait for stability
aws ecs wait services-stable \
  --cluster bk-mind \
  --services bk-mind-backend

# 5. Verify
curl http://<ALB-DNS>/health
# Should return 200
```

**Rollback time**: ~2-3 minutes (task termination + new task startup)

---

## Logging & Debugging

### Access Logs

**CloudWatch Logs**:
```bash
# All backend logs
aws logs tail /ecs/bk-mind-backend --follow

# Grep for errors
aws logs tail /ecs/bk-mind-backend --follow --filter-pattern "ERROR"

# Grep for specific component
aws logs tail /ecs/bk-mind-backend --follow --filter-pattern "Qdrant"
```

**Docker (Local Dev)**:
```bash
# Follow logs in real-time
docker logs -f <backend-container-id>

# Get last 100 lines
docker logs --tail 100 <backend-container-id>
```

### Enable Debug Logging (Temporary)

```bash
# Update environment variable
aws ecs update-service \
  --cluster bk-mind \
  --service bk-mind-backend \
  --task-definition bk-mind-backend:XX \
  --overrides '{"containerOverrides": [{"name": "backend", "environment": [{"name": "LOG_LEVEL", "value": "DEBUG"}]}]}'

# Logs will now include DEBUG level messages
# Revert after debugging:
aws ecs update-service \
  --cluster bk-mind \
  --service bk-mind-backend \
  --task-definition bk-mind-backend:XX \
  --overrides '{"containerOverrides": [{"name": "backend", "environment": [{"name": "LOG_LEVEL", "value": "INFO"}]}]}'
```

---

## On-Call Escalation

### Contact List

| Role | Slack | PagerDuty |
|------|-------|-----------|
| Backend Lead | @backend-on-call | PagerDuty: backend-escalation |
| Infra Lead | @infra-on-call | PagerDuty: infra-escalation |
| ML Ops | @ml-ops-on-call | PagerDuty: ml-ops-escalation |

### Escalation Path

```
1. Try recovery steps in this runbook (15 min max)
2. If not resolved → Slack #incidents with:
   - Issue description
   - Error message from logs
   - Recovery steps attempted
3. If critical (search down >30 min) → PagerDuty page on-call engineer
4. If infrastructure issue → Escalate to infra lead
5. If ML model issue → Escalate to ML ops lead
```

---

## Checklist for New On-Call Rotation

- [ ] Can access AWS Console (IAM permissions?)
- [ ] Can access CloudWatch logs
- [ ] Can run aws ecs commands (AWS CLI configured?)
- [ ] Tested health checks (curl, redis-cli)
- [ ] Know ALB DNS name
- [ ] Know ECS cluster name (bk-mind)
- [ ] Know service names (bk-mind-backend, bk-mind-frontend)
- [ ] Slack #incidents channel
- [ ] PagerDuty access
- [ ] This runbook bookmarked

---

**Last Updated**: May 14, 2026  
**Next Review**: June 14, 2026  
**Emergency Contact**: #incidents on Slack
