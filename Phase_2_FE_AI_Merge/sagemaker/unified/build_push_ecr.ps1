$ErrorActionPreference = "Stop"

$AWS_REGION = if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-west-2" }
$AWS_ACCOUNT_ID = if ($env:AWS_ACCOUNT_ID) { $env:AWS_ACCOUNT_ID } else { (aws sts get-caller-identity --query Account --output text) }
$REPO_NAME = if ($env:REPO_NAME) { $env:REPO_NAME } else { "phase2-multimodal-unified" }
$IMAGE_TAG = if ($env:IMAGE_TAG) { $env:IMAGE_TAG } else { "v1" }
$IMAGE_URI = "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME`:$IMAGE_TAG"

Write-Host "Checking Docker daemon..."
docker info > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker daemon is not running. Start Docker Desktop and wait until engine is ready." -ForegroundColor Red
    exit 1
}

Write-Host "Checking ECR repository..."
aws ecr describe-repositories --repository-names $REPO_NAME --region $AWS_REGION > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Repository does not exist. Creating $REPO_NAME..."
    aws ecr create-repository --repository-name $REPO_NAME --region $AWS_REGION | Out-Null
}

Write-Host "Logging in to ECR..."
$LoginPassword = aws ecr get-login-password --region $AWS_REGION
$LoginPassword | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

Write-Host "Building image from repo root context..."
docker build -f "Phase_2_FE_AI_Merge/sagemaker/unified/Dockerfile" -t "$REPO_NAME`:$IMAGE_TAG" .
docker tag "$REPO_NAME`:$IMAGE_TAG" $IMAGE_URI
docker push $IMAGE_URI

Write-Host "Pushed image: $IMAGE_URI"
