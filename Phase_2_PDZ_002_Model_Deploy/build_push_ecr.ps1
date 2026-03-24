$ErrorActionPreference = "Continue"

$AWS_REGION = if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-west-2" }
$AWS_ACCOUNT_ID = if ($env:AWS_ACCOUNT_ID) { $env:AWS_ACCOUNT_ID } else { (aws sts get-caller-identity --query Account --output text) }
$REPO_NAME = if ($env:REPO_NAME) { $env:REPO_NAME } else { "phase2-colqwen-sagemaker" }
$IMAGE_TAG = if ($env:IMAGE_TAG) { $env:IMAGE_TAG } else { "latest" }
$IMAGE_URI = "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME`:$IMAGE_TAG"

# Create ECR repository if it doesn't exist
Write-Host "Checking if ECR repository exists..."
aws ecr describe-repositories --repository-names $REPO_NAME --region $AWS_REGION > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Repository does not exist. Creating it..."
    aws ecr create-repository --repository-name $REPO_NAME --region $AWS_REGION
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create ECR repository" -ForegroundColor Red
        exit 1
    }
    Write-Host "Repository created successfully. Waiting for availability..."
    Start-Sleep -Seconds 2
}
else {
    Write-Host "Repository already exists"
}

$ErrorActionPreference = "Stop"

$LoginPassword = aws ecr get-login-password --region $AWS_REGION
$LoginPassword | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

docker build --no-cache -t "$REPO_NAME`:$IMAGE_TAG" .
docker tag "$REPO_NAME`:$IMAGE_TAG" $IMAGE_URI
docker push $IMAGE_URI

Write-Host "Pushed image: $IMAGE_URI"
