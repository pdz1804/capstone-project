#!/usr/bin/env pwsh
<#
.SYNOPSIS
Create SageMaker endpoint from model with correct JSON formatting
#>

$REGION = "us-west-2"
$MODEL_NAME = "phase2-multimodal-rt-model-20260420174057"
$ENDPOINT_NAME = "phase2-multimodal-rt-endpoint"
$INSTANCE_TYPE = "ml.g4dn.xlarge"

Write-Host "Creating SageMaker Endpoint from Model" -ForegroundColor Cyan
Write-Host "=" * 60

# Get timestamp
$ts = Get-Date -Format "yyyyMMddHHmmss"
$CONFIG_NAME = "$ENDPOINT_NAME-cfg-$ts"

Write-Host "`n[1] Configuration:" -ForegroundColor Yellow
Write-Host "  Model: $MODEL_NAME"
Write-Host "  Endpoint Name: $ENDPOINT_NAME"
Write-Host "  Config Name: $CONFIG_NAME"
Write-Host "  Instance Type: $INSTANCE_TYPE"
Write-Host "  Region: $REGION"

# Step 1: Create endpoint config with PROPER JSON FORMATTING
Write-Host "`n[2] Creating Endpoint Configuration..." -ForegroundColor Yellow

$prodVariants = @"
[
  {
    "VariantName": "AllTraffic",
    "ModelName": "$MODEL_NAME",
    "InitialInstanceCount": 1,
    "InstanceType": "$INSTANCE_TYPE"
  }
]
"@

Write-Host "  Production Variants JSON:"
Write-Host $prodVariants

aws sagemaker create-endpoint-config `
  --endpoint-config-name $CONFIG_NAME `
  --production-variants "$prodVariants" `
  --region $REGION

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Endpoint config created successfully" -ForegroundColor Green
} else {
    Write-Host "  ✗ Failed to create endpoint config" -ForegroundColor Red
    exit 1
}

# Step 2: Create endpoint
Write-Host "`n[3] Creating Endpoint..." -ForegroundColor Yellow

aws sagemaker create-endpoint `
  --endpoint-name $ENDPOINT_NAME `
  --endpoint-config-name $CONFIG_NAME `
  --region $REGION

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Endpoint creation started" -ForegroundColor Green
} else {
    Write-Host "  ✗ Failed to create endpoint" -ForegroundColor Red
    exit 1
}

# Step 3: Wait for endpoint to be ready
Write-Host "`n[4] Waiting for Endpoint to reach InService status..." -ForegroundColor Yellow
Write-Host "  This may take 5-10 minutes. Please wait..."

aws sagemaker wait endpoint-in-service `
  --endpoint-name $ENDPOINT_NAME `
  --region $REGION

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Endpoint is now InService" -ForegroundColor Green
} else {
    Write-Host "  ✗ Failed waiting for endpoint" -ForegroundColor Red
    exit 1
}

# Step 4: Verify endpoint status
Write-Host "`n[5] Endpoint Status:" -ForegroundColor Yellow

aws sagemaker describe-endpoint `
  --endpoint-name $ENDPOINT_NAME `
  --region $REGION `
  --query "{EndpointName:EndpointName,Status:EndpointStatus,CreatedTime:CreationTime,LastModified:LastModifiedTime,ProductionVariants:ProductionVariants[0].{VariantName:VariantName,ModelName:ModelName,InstanceType:InstanceType}}" `
  --output table

Write-Host "`n" + "=" * 60
Write-Host "ENDPOINT READY FOR TESTING" -ForegroundColor Green
Write-Host "=" * 60

Write-Host "`nEndpoint Details:"
Write-Host "  Name: $ENDPOINT_NAME"
Write-Host "  Status: InService"
Write-Host "  Model: $MODEL_NAME"
Write-Host "`nNow you can run the capacity tests:"
Write-Host "  cd 'd:\PDZ\BKU\Learning\LVTN\GD1\Code\docs\jmeter-capacity-tests'"
Write-Host "  powershell -ExecutionPolicy Bypass -File '.\run_capacity_finder_fixed.ps1' -APIs '05_process'"
Write-Host "  powershell -ExecutionPolicy Bypass -File '.\run_capacity_finder_fixed.ps1' -APIs '06_index'"
Write-Host "  powershell -ExecutionPolicy Bypass -File '.\run_capacity_finder_fixed.ps1' -APIs '07_search_retrieval'"
Write-Host "`n"
