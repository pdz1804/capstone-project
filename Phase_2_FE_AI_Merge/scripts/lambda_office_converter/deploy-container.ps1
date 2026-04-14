# Deploy LibreOffice Lambda Container Function (PowerShell)

$ErrorActionPreference = "Stop"

# Configuration
$FUNCTION_NAME = "office-to-pdf-converter"
$REGION = if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-west-2" }
$MEMORY = 3008
$TIMEOUT = 180

# Get AWS Account ID
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
$ECR_REPO = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$FUNCTION_NAME"

Write-Host "========================================"
Write-Host "Deploying LibreOffice Lambda Container"
Write-Host "========================================"
Write-Host "Function: $FUNCTION_NAME"
Write-Host "Region: $REGION"
Write-Host "Account: $ACCOUNT_ID"
Write-Host ""

# Step 1: Create ECR repository if it doesn't exist
Write-Host "Step 1: Creating ECR repository..."
try {
    $null = aws ecr describe-repositories --repository-names $FUNCTION_NAME --region $REGION 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Done: Repository already exists"
    }
} catch {
    Write-Host "Creating repository..."
    aws ecr create-repository --repository-name $FUNCTION_NAME --region $REGION
    Write-Host "Done: Repository created"
}

# Step 2: Login to ECR
Write-Host ""
Write-Host "Step 2: Logging into ECR..."
$password = aws ecr get-login-password --region $REGION
$password | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
Write-Host "Done: Logged in"

# Step 3: Build Docker image
Write-Host ""
Write-Host "Step 3: Building Docker image..."
docker build -t "${FUNCTION_NAME}:latest" .
Write-Host "Done: Image built"

# Step 4: Tag and push image
Write-Host ""
Write-Host "Step 4: Pushing image to ECR..."
docker tag "${FUNCTION_NAME}:latest" "${ECR_REPO}:latest"
docker push "${ECR_REPO}:latest"
Write-Host "Done: Image pushed"

# Step 5: Create or update Lambda function
Write-Host ""
Write-Host "Step 5: Creating/updating Lambda function..."

$functionExists = $false
try {
    $null = aws lambda get-function --function-name $FUNCTION_NAME --region $REGION 2>&1
    if ($LASTEXITCODE -eq 0) {
        $functionExists = $true
    }
} catch {
    $functionExists = $false
}

if ($functionExists) {
    Write-Host "Function exists. Updating..."
    aws lambda update-function-code `
        --function-name $FUNCTION_NAME `
        --image-uri "${ECR_REPO}:latest" `
        --region $REGION

    Write-Host "Waiting for update to complete..."
    aws lambda wait function-updated `
        --function-name $FUNCTION_NAME `
        --region $REGION

    Write-Host "Updating configuration..."
    aws lambda update-function-configuration `
        --function-name $FUNCTION_NAME `
        --timeout $TIMEOUT `
        --memory-size $MEMORY `
        --environment "Variables={HOME=/tmp}" `
        --region $REGION

    Write-Host "Done: Function updated"
} else {
    Write-Host "Function does not exist. Creating..."

    # Get or create IAM role
    $ROLE_NAME = "$FUNCTION_NAME-role"
    $ROLE_ARN = ""

    try {
        $ROLE_ARN = aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text 2>&1
        if ($LASTEXITCODE -ne 0) {
            $ROLE_ARN = ""
        }
    } catch {
        $ROLE_ARN = ""
    }

    if (-not $ROLE_ARN -or $ROLE_ARN -eq "") {
        Write-Host "Creating IAM role..."

        # Create trust policy
        $trustPolicy = @'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
'@
        $trustPolicy | Out-File -FilePath trust-policy.json -Encoding ascii

        aws iam create-role `
            --role-name $ROLE_NAME `
            --assume-role-policy-document file://trust-policy.json `
            --region $REGION

        aws iam attach-role-policy `
            --role-name $ROLE_NAME `
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole `
            --region $REGION

        Remove-Item trust-policy.json

        $ROLE_ARN = aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text

        Write-Host "Done: IAM role created: $ROLE_ARN"
        Write-Host "Waiting 10 seconds for IAM role to propagate..."
        Start-Sleep -Seconds 10
    }

    # Create Lambda function
    aws lambda create-function `
        --function-name $FUNCTION_NAME `
        --package-type Image `
        --code "ImageUri=${ECR_REPO}:latest" `
        --role $ROLE_ARN `
        --timeout $TIMEOUT `
        --memory-size $MEMORY `
        --environment "Variables={HOME=/tmp}" `
        --region $REGION

    Write-Host "Done: Function created"
}

# Step 6: Test the function
Write-Host ""
Write-Host "Step 6: Testing function..."

# Create test HTML file
$TEST_HTML = '<html><body><h1>Hello LibreOffice!</h1><p>This is a test document.</p></body></html>'
$TEST_BYTES = [System.Text.Encoding]::UTF8.GetBytes($TEST_HTML)
$TEST_BASE64 = [Convert]::ToBase64String($TEST_BYTES)

# Create test payload
$testPayload = @"
{
    "operation": "convert-to-pdf",
    "filename": "test.html",
    "extension": ".html",
    "content_base64": "$TEST_BASE64"
}
"@
$testPayload | Out-File -FilePath test-payload.json -Encoding ascii

Write-Host "Invoking function..."
aws lambda invoke `
    --function-name $FUNCTION_NAME `
    --payload file://test-payload.json `
    --region $REGION `
    response.json

Write-Host ""
Write-Host "Response:"
Get-Content response.json | python -m json.tool

# Check if conversion was successful
$response = Get-Content response.json | ConvertFrom-Json
if ($response.ok -eq $true) {
    Write-Host ""
    Write-Host "Done: Test conversion successful!"

    # Decode and save PDF
    $pdf_bytes = [Convert]::FromBase64String($response.pdf_base64)
    [System.IO.File]::WriteAllBytes("test-output.pdf", $pdf_bytes)
    Write-Host "Done: Test PDF saved as test-output.pdf"
} else {
    Write-Host ""
    Write-Host "Failed: Test conversion failed!"
}

Remove-Item test-payload.json
Remove-Item response.json

Write-Host ""
Write-Host "========================================"
Write-Host "Deployment Complete!"
Write-Host "========================================"
Write-Host ""
Write-Host "Function ARN:"
aws lambda get-function --function-name $FUNCTION_NAME --region $REGION --query 'Configuration.FunctionArn' --output text
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Set environment variables in your backend:"
Write-Host "   OFFICE_PDF_LAMBDA_FUNCTION_NAME=$FUNCTION_NAME"
Write-Host "   OFFICE_PDF_LAMBDA_REGION=$REGION"
Write-Host ""
Write-Host "2. Ensure your ECS task role has permission to invoke this Lambda:"
Write-Host "   aws iam put-role-policy --role-name <your-ecs-task-role> --policy-name InvokeLambda --policy-document file://ecs-lambda-invoke-policy.json"
Write-Host ""
