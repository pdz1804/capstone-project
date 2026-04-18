$ErrorActionPreference = "Stop"

$AWS_REGION = if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-west-2" }
$AWS_ACCOUNT_ID = if ($env:AWS_ACCOUNT_ID) { $env:AWS_ACCOUNT_ID } else { (aws sts get-caller-identity --query Account --output text) }
$REPO_NAME = if ($env:REPO_NAME) { $env:REPO_NAME } else { "phase2-multimodal-unified" }
$IMAGE_TAG = if ($env:IMAGE_TAG) { $env:IMAGE_TAG } else { "v1" }
$IMAGE_URI = "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME`:$IMAGE_TAG"

Write-Host "Checking Docker daemon..."
# Use cmd redirection here to avoid PowerShell treating docker stderr warnings as terminating errors.
cmd /c "docker info >nul 2>nul"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker daemon is not running. Start Docker Desktop and wait until engine is ready." -ForegroundColor Red
    exit 1
}

Write-Host "Checking ECR repository..."
$repoExists = $true
try {
    aws ecr describe-repositories --repository-names $REPO_NAME --region $AWS_REGION > $null 2>&1
    if ($LASTEXITCODE -ne 0) {
        $repoExists = $false
    }
} catch {
    $repoExists = $false
}

if (-not $repoExists) {
    Write-Host "Repository does not exist. Creating $REPO_NAME..."
    aws ecr create-repository --repository-name $REPO_NAME --region $AWS_REGION | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create ECR repository '$REPO_NAME'."
    }
}

Write-Host "Logging in to ECR..."
$LoginPassword = aws ecr get-login-password --region $AWS_REGION
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($LoginPassword)) {
    throw "Failed to retrieve ECR login password."
}
$LoginPassword | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
if ($LASTEXITCODE -ne 0) {
    throw "Docker login to ECR failed."
}

Write-Host "Building image from repo root context..."
docker build -f "Phase_2_FE_AI_Merge/sagemaker/unified/Dockerfile" -t "$REPO_NAME`:$IMAGE_TAG" .
if ($LASTEXITCODE -ne 0) {
    throw "Docker build failed."
}
docker tag "$REPO_NAME`:$IMAGE_TAG" $IMAGE_URI
if ($LASTEXITCODE -ne 0) {
    throw "Docker tag failed."
}
docker push $IMAGE_URI
if ($LASTEXITCODE -ne 0) {
    throw "Docker push failed."
}

Write-Host "Pushed image: $IMAGE_URI"
