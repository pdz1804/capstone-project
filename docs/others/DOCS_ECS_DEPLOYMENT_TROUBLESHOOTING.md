# ECS Deployment Troubleshooting Guide

## Problem Summary
Backend container exits with code 1 during ECS deployment, failing health checks.

**Error Status:** Essential container exited with exit code 1  
**Health Check Grace Period:** 0 seconds (too aggressive)  
**Failed Tasks:** 18+ attempts  

---

## Root Cause Analysis

Exit code 1 typically indicates an **application-level error during startup**, not infrastructure. The issue is likely in the FastAPI lifespan startup (app/main.py lines 112-134).

### Potential Startup Failures

1. **User Repository Initialization** (line 120-124)
   - `get_user_repository_from_env()` may fail if credentials are missing/invalid
   - Firebase/DynamoDB auth issues
   - Connection timeouts to external services

2. **Environment Variable Loading** (line 116)
   - `.env` file inside container may not be loading correctly
   - Docker secrets/environment not properly passed
   - Missing required variables: `DYNAMODB_APP_USAGE_TABLE`, `RUN_API_PORT`, etc.

3. **Data Directory Creation** (line 117)
   - `ensure_data_dirs()` may fail if `/data` mount doesn't exist
   - Permission issues in container

4. **App Usage Service** (line 126-130)
   - DynamoDB connection timeout if not on same VPC
   - Invalid AWS credentials in container

---

## Immediate Fixes

### 1. Increase Health Check Grace Period (CRITICAL)
```powershell
aws ecs update-service \
  --cluster rag-pipeline-cluster \
  --service rag-pipeline-cluster-backend-service \
  --health-check-grace-period-seconds 120 \
  --region us-west-2
```

This gives the app 120 seconds to start before health checks begin.

### 2. Add Startup Logging (FIX BACKEND CODE)

Edit `Phase_2_FE_AI_Merge/backend/app/main.py` to add more detailed logging:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global USAGE_SERVICE
    
    logger.info("🚀 AI service startup initiated")
    
    try:
        # Load env
        load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
        logger.info("✓ Environment variables loaded")
        
        # Ensure directories
        ensure_data_dirs("default")
        logger.info("✓ Data directories ensured")
        
        # Bootstrap admin
        user_repo = get_user_repository_from_env()
        logger.info("✓ User repository initialized")
        
        UserService(user_repo).ensure_default_admin_account()
        logger.info("✓ Default admin bootstrap complete")
        
    except Exception as bootstrap_err:
        logger.exception("❌ Bootstrap failed (will continue): %s", bootstrap_err)

    try:
        USAGE_SERVICE = AppUsageService.from_env_optional()
        if USAGE_SERVICE is None:
            logger.warning("⚠️  App usage tracking disabled (DYNAMODB_APP_USAGE_TABLE is not configured)")
        else:
            logger.info("✓ App usage tracking enabled")
    except Exception as usage_err:
        logger.exception("❌ App usage service initialization failed: %s", usage_err)

    logger.info("✅ AI service startup complete - listening on port %s", os.getenv("RUN_API_PORT", "5000"))
    yield
    logger.info("🛑 AI service shutdown")
```

### 3. Check CloudWatch Logs

```powershell
# View live logs
aws logs tail /ecs/rag-pipeline-cluster-backend --follow --region us-west-2

# Search for errors
aws logs filter-log-events \
  --log-group-name /ecs/rag-pipeline-cluster-backend \
  --filter-pattern "ERROR or Exception" \
  --region us-west-2
```

---

## Container Validation

### 1. Test Image Locally

```bash
docker run -p 5000:5000 \
  -e RUN_API_HOST=0.0.0.0 \
  -e RUN_API_PORT=5000 \
  381492273521.dkr.ecr.us-west-2.amazonaws.com/rag-pipeline-backend:latest

# In another terminal
curl http://localhost:5000/health
curl http://localhost:5000/api
```

### 2. Inspect Container Image

```bash
# Check if app is installed
docker run --entrypoint pip list \
  381492273521.dkr.ecr.us-west-2.amazonaws.com/rag-pipeline-backend:latest | grep -i fastapi

# Check if main.py exists
docker run --entrypoint ls -la \
  381492273521.dkr.ecr.us-west-2.amazonaws.com/rag-pipeline-backend:latest /app/main.py

# Check working directory
docker run --entrypoint pwd \
  381492273521.dkr.ecr.us-west-2.amazonaws.com/rag-pipeline-backend:latest
```

---

## Environment Configuration Checklist

### Required Environment Variables

```bash
# Core API
RUN_API_HOST=0.0.0.0
RUN_API_PORT=5000
RUN_API_WORKERS=2
RUN_API_RELOAD=false

# Firebase/Auth
FIREBASE_CREDENTIALS_JSON=<base64-encoded or path to JSON>
FIREBASE_PROJECT_ID=<your-project-id>

# AWS/DynamoDB
AWS_REGION=us-west-2
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>
DYNAMODB_APP_USAGE_TABLE=rag-pipeline-app-usage

# Qdrant
QDRANT_URL=http://<qdrant-host>:6333
QDRANT_API_KEY=<key>

# S3
AWS_S3_BUCKET=<bucket-name>

# SageMaker
SAGEMAKER_ENDPOINT_NAME=<endpoint-name>

# Bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
```

### Task Definition Environment Variables

When updating the ECS task definition, ensure:

1. **All secrets are in AWS Secrets Manager**, not in plain text
2. **Use `secrets` array for sensitive values:**
   ```json
   {
     "name": "containerDefinitions",
     "environment": [
       {"name": "RUN_API_PORT", "value": "5000"},
       {"name": "RUN_API_HOST", "value": "0.0.0.0"}
     ],
     "secrets": [
       {"name": "FIREBASE_CREDENTIALS_JSON", "valueFrom": "arn:aws:secretsmanager:us-west-2:account:secret:firebase-creds"},
       {"name": "AWS_SECRET_ACCESS_KEY", "valueFrom": "arn:aws:secretsmanager:us-west-2:account:secret:aws-secret"}
     ]
   }
   ```

3. **Volume mounts for persistent data:**
   ```json
   {
     "name": "data",
     "sourceVolume": "data-volume",
     "containerPath": "/data"
   }
   ```

---

## ECS Configuration Improvements

### 1. Slow Start for Target Group

```powershell
aws elbv2 modify-target-group-attributes \
  --target-group-arn arn:aws:elasticloadbalancing:us-west-2:381492273521:targetgroup/rag-pipeline-alb-backend-tg/d4821025b98f5ddc \
  --attributes Key=slow_start.duration_seconds,Value=300 \
  --region us-west-2
```

This prevents the load balancer from sending traffic until the app is fully warmed up.

### 2. Update Health Check

```powershell
aws elbv2 modify-target-group \
  --target-group-arn arn:aws:elasticloadbalancing:us-west-2:381492273521:targetgroup/rag-pipeline-alb-backend-tg/d4821025b98f5ddc \
  --health-check-protocol HTTP \
  --health-check-path /health \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 10 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3 \
  --matcher HttpCode=200 \
  --region us-west-2
```

### 3. Service Configuration

```powershell
aws ecs update-service \
  --cluster rag-pipeline-cluster \
  --service rag-pipeline-cluster-backend-service \
  --deployment-configuration \
  "maximumPercent=200,minimumHealthyPercent=50" \
  --health-check-grace-period-seconds 120 \
  --region us-west-2
```

---

## Dockerfile Best Practices

### Ensure Proper Working Directory

```dockerfile
WORKDIR /app

# Copy requirements first (for layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make sure run_api.py exists
RUN ls -la run_api.py

# Expose port
EXPOSE 5000

# Use exec form to ensure signals are properly handled
CMD ["python", "run_api.py", "--workers", "2", "--no-reload"]
```

---

## Debugging Steps

### Step 1: Check Task Status
```powershell
aws ecs describe-tasks \
  --cluster rag-pipeline-cluster \
  --tasks <task-arn> \
  --region us-west-2
```

Look for:
- `lastStatus`: Should be RUNNING
- `containers[0].exitCode`: Should be 0 or null
- `containers[0].reason`: Check for error messages

### Step 2: Get Recent Logs
```powershell
aws logs get-log-events \
  --log-group-name /ecs/rag-pipeline-cluster-backend \
  --log-stream-name <stream-name> \
  --limit 100 \
  --region us-west-2 | Select-Object -ExpandProperty events | ForEach-Object {$_.message}
```

### Step 3: Manual Container Test
```powershell
# SSH into ECS instance or use CloudShell
docker exec <container-id> python run_api.py --help
docker exec <container-id> curl localhost:5000/health
docker exec <container-id> tail -50 /var/log/app.log
```

---

## Common Issues & Fixes

### Issue: "ModuleNotFoundError: No module named 'app'"
**Cause:** Working directory is wrong or app directory not copied into image  
**Fix:** Ensure `WORKDIR /app` in Dockerfile and files are copied correctly

### Issue: "Connection refused" to Qdrant/DynamoDB
**Cause:** Services not accessible from ECS task network  
**Fix:** 
- Check security groups allow traffic
- Ensure task is on same VPC as services
- Verify service URLs are correct (internal DNS, not public)

### Issue: "FIREBASE_CREDENTIALS_JSON not found"
**Cause:** Environment variable not passed or secrets not resolved  
**Fix:**
- Check task definition has `secrets` array, not `environment`
- Verify Secrets Manager ARN is correct
- Check IAM role has `secretsmanager:GetSecretValue` permission

### Issue: Timeout waiting for app to start
**Cause:** App taking >60 seconds to initialize  
**Fix:**
- Increase health check grace period to 180+ seconds
- Profile startup with more logging
- Consider moving heavy initialization to async tasks

---

## Deployment Checklist

Before pushing a new version:

- [ ] **Add startup logging** (see code changes above)
- [ ] **Test locally**: `docker run -p 5000:5000 <image>`
- [ ] **Verify health check**: `curl http://localhost:5000/health`
- [ ] **Check all required env vars** are in task definition or Secrets Manager
- [ ] **Update health check grace period** to 120+ seconds
- [ ] **Enable slow start** on target group (300+ seconds)
- [ ] **Update task definition** (increment revision)
- [ ] **Force new deployment** to ECS service
- [ ] **Monitor CloudWatch logs** for 5 minutes after deployment
- [ ] **Check target group health** in EC2 console

---

## Verification Commands

After deployment:

```powershell
# Check service is running
aws ecs describe-services \
  --cluster rag-pipeline-cluster \
  --services rag-pipeline-cluster-backend-service \
  --region us-west-2

# Check task status
aws ecs list-tasks \
  --cluster rag-pipeline-cluster \
  --region us-west-2 | Select-Object -ExpandProperty taskArns | ForEach-Object {
    aws ecs describe-tasks --cluster rag-pipeline-cluster --tasks $_ --region us-west-2
  }

# Check target group health
aws elbv2 describe-target-health \
  --target-group-arn arn:aws:elasticloadbalancing:us-west-2:381492273521:targetgroup/rag-pipeline-alb-backend-tg/d4821025b98f5ddc \
  --region us-west-2

# Test health endpoint
curl https://k2p-bkmind-learning-platform.com/health
```

---

## Next Steps

1. **Apply immediate fixes** (health check grace period + slow start)
2. **Add startup logging** to app/main.py
3. **Update Dockerfile** with proper CMD
4. **Test locally** before deploying
5. **Monitor CloudWatch** logs during deployment
6. **Verify health** via target group status

Once the app starts successfully, focus on optimization (memory, CPU, scaling policies).
