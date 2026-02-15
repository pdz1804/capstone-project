# GitHub Actions CI/CD Pipelines

Complete documentation for GitHub Actions CI/CD pipelines for RAG Pipeline deployment to AWS.

## 📑 Table of Contents

1. [Pipeline Overview](#pipeline-overview)
2. [Workflows](#workflows)
3. [Configuration](#configuration)
4. [Monitoring](#monitoring)
5. [Troubleshooting](#troubleshooting)

---

## Pipeline Overview

Three automated CI/CD pipelines handle:

1. **Backend Build & Deploy** - Python FastAPI application
2. **Frontend Build & Deploy** - React Vite application
3. **Infrastructure as Code** - Terraform AWS resources

### Trigger Rules

```yaml
Backend CI/CD:
  - Triggers on: push/PR to main/develop
  - Watches: Phase_2/backend/**
  - Deploys to: rag-pipeline-cluster-backend-service
  - Auto-triggers on: manifest/code changes

Frontend CI/CD:
  - Triggers on: push/PR to main/develop
  - Watches: Phase_2/frontend/**
  - Deploys to: rag-pipeline-cluster-frontend-service
  - Auto-triggers on: manifest/code changes

Infrastructure CI/CD:
  - Triggers on: push to main
  - Watches: Phase_2/terraform/**
  - Deploys to: AWS via Terraform
  - Manual approval: Before apply to production
```

---

## Workflows

### 1. Backend CI/CD Workflow (backend-cicd.yml)

**Trigger:** Push/PR to main or develop with changes in `Phase_2/backend/`

**Steps:**

```
┌─────────────────────────────────────────────────────────┐
│ JOB 1: BUILD & PUSH                                     │
├─────────────────────────────────────────────────────────┤
│ ✓ Checkout code                                         │
│ ✓ Configure AWS credentials (OIDC)                      │
│ ✓ Login to ECR                                          │
│ ✓ Setup Docker Buildx                                  │
│ ✓ Build & push Docker image (with cache)              │
│ ✓ Create ECS task definition                          │
│ ✓ [LOG] Print all details for debugging               │
└─────────────────────────────────────────────────────────┘
                           │
                    [If main branch]
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│ JOB 2: DEPLOY TO ECS                                   │
├─────────────────────────────────────────────────────────┤
│ ✓ Checkout code                                        │
│ ✓ Configure AWS credentials                            │
│ ✓ Login to ECR                                         │
│ ✓ Render task definition with new image               │
│ ✓ Deploy to ECS service                               │
│ ✓ Wait for service stability (2/2 tasks)              │
│ ✓ Health check via target group                       │
│ ✓ [LOG] Print service status & metrics                │
└─────────────────────────────────────────────────────────┘
```

**Key Features:**

- **Multi-stage Docker builds** - Smaller image size
- **Docker layer caching** - Faster builds for unchanged dependencies
- **Detailed logging** - Every step prints progress for debugging
- **Health checks** - Waits for tasks to become healthy
- **Auto-rollback** - Old version remains if new deployment fails

**Logs:**

```bash
# View logs in GitHub Actions
GitHub > Actions > backend-cicd.yml > <Run> > <Job>

# Key log sections:
✓ STEP 1: CODE CHECKOUT COMPLETE
  - Repository, branch, commit SHA
  
✓ STEP 2: AWS CREDENTIALS CONFIGURED
  - AWS account ID, IAM role
  
✓ STEP 3: ECR LOGIN SUCCESSFUL
  - ECR registry URL
  
✓ STEP 5: DOCKER IMAGE BUILD COMPLETE
  - Image digest, size
  
✓ STEP 6: DEPLOYMENT TO ECS COMPLETE
  - Service status (desired/running tasks)
```

---

### 2. Frontend CI/CD Workflow (frontend-cicd.yml)

**Trigger:** Push/PR to main or develop with changes in `Phase_2/frontend/`

**Steps:**

```
┌─────────────────────────────────────────────────────────┐
│ JOB 1: BUILD & PUSH                                     │
├─────────────────────────────────────────────────────────┤
│ ✓ Checkout code                                         │
│ ✓ Configure AWS credentials                             │
│ ✓ Login to ECR                                          │
│ ✓ Setup Node.js & npm cache                           │
│ ✓ Install dependencies (npm ci)                        │
│ ✓ Run ESLint (optional, continue on error)             │
│ ✓ Build React app (npm run build)                      │
│ ✓ Setup Docker Buildx                                 │
│ ✓ Build & push Docker image                           │
│ ✓ Create ECS task definition                          │
│ ✓ [LOG] Print npm versions & build artifacts          │
└─────────────────────────────────────────────────────────┘
                           │
                    [If main branch]
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│ JOB 2: DEPLOY TO ECS                                    │
├─────────────────────────────────────────────────────────┤
│ ✓ Checkout code                                        │
│ ✓ Configure AWS credentials                            │
│ ✓ Login to ECR                                         │
│ ✓ Render task definition                              │
│ ✓ Deploy to ECS service                               │
│ ✓ Monitor deployment progress                         │
│ ✓ Verify service health                               │
│ ✓ [LOG] Print container logs & health status          │
└─────────────────────────────────────────────────────────┘
```

**Key Features:**

- **npm cache** - Faster dependency installation
- **Linting** - ESLint validation (non-blocking)
- **Build optimization** - Vite production build
- **Docker layer caching** - Reuses npm build cache
- **Detailed progress tracking** - Monitors deployment in real-time

**Logs:**

```bash
# Key log sections:
✓ STEP 4: NODE.JS SETUP
  - Node version, npm version
  
✓ STEP 5: INSTALLING DEPENDENCIES
  - npm ci output, package count
  
✓ STEP 7: BUILDING APPLICATION
  - npm run build output, bundle size
  
✓ STEP 9: DOCKER IMAGE PUSHED
  - Image digest, ECR repository listing
```

---

### 3. Infrastructure CI/CD Workflow (infrastructure-cicd.yml)

**Trigger:** Push to main with changes in `Phase_2/terraform/`

**Steps:**

```
[PR Flow]
┌──────────────────────────────────┐
│ 1. Terraform Plan                │
│    - terraform init              │
│    - terraform validate          │
│    - terraform plan              │
│    - Save plan artifact          │
│    - Comment on PR with plan     │
└──────────────────────────────────┘

[Main Branch - Push]
┌──────────────────────────────────┐
│ 1. Terraform Plan (same as above)│
│    - terraform plan              │
│    - Save tfplan artifact        │
└──────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ 2. Terraform Apply               │
│    - Download tfplan artifact    │
│    - terraform apply tfplan      │
│    - Verify infrastructure       │
│    - Save outputs to artifact    │
└──────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ 3. Post-Apply Verification       │
│    - Check ECS cluster           │
│    - Verify ECR repositories     │
│    - Check ALB status            │
│    - Print infrastructure URLs   │
└──────────────────────────────────┘
```

**Key Features:**

- **Terraform state management** - Tracks infrastructure
- **Plan artifacts** - Saved for audit and rollback
- **PR comments** - Shows plan details for review
- **Sequential execution** - Plan, then apply
- **Detailed verification** - Confirms all resources created

**Logs:**

```bash
# Key log sections:
✓ STEP 2: TERRAFORM SETUP
  - terraform version
  
✓ STEP 4: TERRAFORM INIT
  - Backend configuration
  
✓ STEP 6: TERRAFORM PLAN
  - Resource changes (+34 new, ~0 changes, ~0 destroyed)
  
✓ STEP 6: TERRAFORM APPLY
  - Resource creation confirmation
  
✓ STEP 7: INFRASTRUCTURE VERIFICATION
  - ECS cluster status
  - ECR repositories listing
  - ALB DNS name
```

---

## Configuration

### GitHub Secrets Required

```bash
# Required for CI/CD to work:

AWS_ROLE_TO_ASSUME
  Value: arn:aws:iam::ACCOUNT_ID:role/GitHubActionsRole
  Purpose: OIDC role for AWS authentication

# Optional:

AWS_REGION
  Value: us-west-2
  Purpose: Explicit region specification

ECR_REGISTRY_ALIAS
  Value: rag-pipeline
  Purpose: Custom registry alias (if used)
```

### GitHub Actions Secrets Setup

```bash
# In GitHub repository:
1. Go to Settings > Secrets and variables > Actions
2. Click "New repository secret"
3. Fill in:
   - Name: AWS_ROLE_TO_ASSUME
   - Value: arn:aws:iam::ACCOUNT_ID:role/GitHubActionsRole
4. Click "Add secret"

# Verify:
- Secrets appear in list (masked)
- Available in workflows (if actor has access)
```

### IAM Role for GitHub Actions

```bash
# Create OIDC provider (one-time setup)
aws iam create-openid-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# Create role with trust relationship
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:OWNER/REPO:ref:*"
        }
      }
    }
  ]
}
EOF

aws iam create-role \
  --role-name GitHubActionsRole \
  --assume-role-policy-document file://trust-policy.json

# Attach policy (need ECS, ECR, IAM, Terraform permissions)
aws iam attach-role-policy \
  --role-name GitHubActionsRole \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

### Workflow Customization

#### Change deployment trigger

```yaml
# In backend-cicd.yml
on:
  push:
    branches:
      - main          # ← Change to 'main' only, 'main|develop', etc
      - develop
    paths:
      - 'Phase_2/backend/**'
```

#### Change AWS region

```yaml
env:
  AWS_REGION: us-west-2  # ← Change region here
```

#### Add deployment approval

```yaml
# In backend-cicd.yml
deploy:
  needs: build-and-push
  environment:
    name: production
    # Requires approval from GitHub environment protection rule
```

---

## Monitoring

### GitHub Actions Dashboard

```bash
# View workflow runs
1. GitHub > Actions
2. Click workflow (backend-cicd.yml, frontend-cicd.yml, etc)
3. See list of runs with status

# View job details
1. Click on run
2. Click on job (Build & Push, Deploy, etc)
3. Expand steps to see logs
4. Search logs with browser Find (Ctrl+F)
```

### Real-time Monitoring

```bash
# Watch runs update in real-time
GitHub > Actions > <Workflow> > <Run>
  - Refreshes every 5 seconds
  - Shows live logs as workflow executes

# Check status badge
1. Click "..." on workflow
2. Create status badge
3. Add to README.md for quick status view
```

### Workflow Notifications

```yaml
# Enable notifications in GitHub settings:
1. Account > Notifications > Actions
2. Enable "Notify me when actions fail in my repositories"
3. Configure as Email or Web notification
```

---

## Troubleshooting

### Common Issues

#### Issue 1: AWS Credentials Failure

**Error:** `Unable to assume role arn:aws:iam::...`

**Solution:**
```bash
# 1. Verify secret exists
GitHub > Settings > Secrets > AWS_ROLE_TO_ASSUME

# 2. Check OIDC provider
aws iam list-open-id-connect-providers

# 3. Verify trust policy
aws iam get-role-policy \
  --role-name GitHubActionsRole \
  --policy-name TrustPolicy

# 4. Check GitHub repo name matches trust policy
# Trust policy should have: repo:OWNER/REPO:ref:*
```

#### Issue 2: Docker Build Failure

**Error:** `Docker build failed` or `Error response from daemon`

**Solution:**
```bash
# 1. Check Dockerfile syntax
docker build Phase_2/backend/ -t test

# 2. Check Dockerfile exit code
# Ensure all RUN commands exit 0

# 3. Check dependencies available
# Review requirements.txt or package.json

# 4. Check Docker layer caching
# Remove cache if issues: --no-cache
```

#### Issue 3: ECR Push Failure

**Error:** `ImagePushFailed` or `no basic auth credentials`

**Solution:**
```bash
# 1. Verify ECR repository exists
aws ecr describe-repositories --repository-names rag-pipeline-backend

# 2. Check IAM permissions
# Role needs: ecr:GetDownloadUrlForLayer, ecr:BatchGetImage, etc

# 3. Verify ECR login
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin <ID>.dkr.ecr.us-west-2.amazonaws.com
```

#### Issue 4: ECS Deployment Failure

**Error:** `Service failed to stabilize` or `Task stopped`

**Solution:**
```bash
# 1. Check cloudwatch logs
aws logs tail /ecs/rag-pipeline-cluster/backend --follow

# 2. Check task status
aws ecs describe-tasks --cluster rag-pipeline-cluster --tasks <TASK_ARN> \
  | jq '.tasks[0] | {lastStatus, stoppedReason}'

# 3. Check health check endpoint
curl -f http://localhost:8000/health

# 4. Check port availability
# Ensure port is not already in use

# 5. Check task definition
# Verify image URI, port, CPU/memory
```

#### Issue 5: Terraform Plan Fails

**Error:** `Terraform validation failed` or `Invalid resource configuration`

**Solution:**
```bash
# 1. Validate syntax locally
terraform -chdir=Phase_2/terraform validate

# 2. Format check
terraform fmt -check -recursive Phase_2/terraform/

# 3. Review error message in workflow logs
# Error message usually points to specific issue

# 4. Check AWS credentials
aws sts get-caller-identity

# 5. Verify IAM permissions for Terraform
# iam:CreateRole, iam:AttachRolePolicy, etc
```

### Debug Mode

```yaml
# Enable debug logging in workflow
- name: Enable debug logging
  env:
    RUNNER_DEBUG: 1
  run: echo "Debug mode enabled"

# Or add to workflow:
env:
  TERRAFORM_LOG: DEBUG  # For Terraform debugging
```

### Log Analysis

```bash
# Search for key patterns
# 1. "Error" - Find actual errors
# 2. "WARNING" - Non-critical issues
# 3. "SUCCESS" - Completed steps
# 4. "FAILED" - Failed steps

# Use GitHub search
GitHub > Actions > <Run> > Logs > Search (Ctrl+F)

# Or download logs
GitHub > Actions > <Run> > "Download logs" button
```

---

## Best Practices

### 1. Branch Strategy

```
main (production)
  └─ Only merged after PR review
  └─ Triggers deployment to production
  
develop (staging)
  └─ Where features are integrated
  └─ Triggers deployment to staging
  
feature/* (development)
  └─ Individual feature branches
  └─ Do not trigger deployment
```

### 2. Pull Request Workflow

```
1. Create feature branch: git checkout -b feature/name
2. Make changes and commit
3. Push to GitHub: git push origin feature/name
4. Create PR: "Compare & pull request"
5. Wait for CI/CD plan: Terraform plan shows changes
6. Review & approve
7. Merge to main
8. CD: Automatic deployment to production
```

### 3. Logging Standards

```
Every critical operation should log:
- What: Description of operation
- When: Timestamp
- Where: Component/service
- Status: Success/failure
- Details: Relevant metrics/output

Example:
echo "========================================"
echo "STEP 1: CHECKOUT CODE"
echo "========================================"
echo "Branch: ${{ github.ref }}"
echo "Commit: ${{ github.sha }}"
```

### 4. Error Handling

```yaml
# Use continue-on-error for non-critical steps
- name: ESLint
  continue-on-error: true
  run: npm run lint

# Use if conditions to handle failures
- name: Deploy
  if: success()  # Only run if previous steps succeeded
  run: AWS deploy
```

---

## Monitoring Checklist

- [ ] Workflow triggered correctly
- [ ] All steps completed successfully
- [ ] Docker image pushed to ECR
- [ ] ECS service updated
- [ ] New tasks are healthy
- [ ] No errors in CloudWatch logs
- [ ] Application responding to health checks
- [ ] ALB routing traffic correctly

---

**Last Updated:** February 8, 2026  
**Version:** 1.0  
**Status:** Production Ready
