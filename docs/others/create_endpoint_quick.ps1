#!/usr/bin/env powershell
# Create SageMaker Endpoint using existing SageMaker-ColQwen-Role

param(
  [string]$Region = "us-west-2",
  [string]$EndpointName = "phase2-multimodal-rt",
  [string]$ModelName = "phase2-multimodal-rt-model-20260420174057",
  [string]$InstanceType = "ml.g4dn.xlarge"
)

Write-Host "Creating SageMaker Endpoint" -ForegroundColor Cyan
Write-Host "Region: $Region | Endpoint: $EndpointName | Model: $ModelName" -ForegroundColor Yellow
Write-Host ""

$Timestamp = Get-Date -Format "yyyyMMddHHmmss"
$EndpointConfigName = "$EndpointName-cfg-$Timestamp"

# Step 1: Create Endpoint Configuration
Write-Host "[1/4] Creating endpoint configuration..." -ForegroundColor Yellow

$VariantsJson = "[{`"VariantName`":`"AllTraffic`",`"ModelName`":`"$ModelName`",`"InitialInstanceCount`":1,`"InstanceType`":`"$InstanceType`",`"InitialVariantWeight`":1.0}]"

aws sagemaker create-endpoint-config --region $Region --endpoint-config-name $EndpointConfigName --production-variants $VariantsJson 2>&1

if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR: Failed to create endpoint config" -ForegroundColor Red
  exit 1
}
Write-Host "✓ Endpoint config created: $EndpointConfigName" -ForegroundColor Green

# Step 2: Create Endpoint
Write-Host ""
Write-Host "[2/4] Creating endpoint..." -ForegroundColor Yellow
aws sagemaker create-endpoint --region $Region --endpoint-name $EndpointName --endpoint-config-name $EndpointConfigName 2>&1

if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR: Failed to create endpoint" -ForegroundColor Red
  exit 1
}
Write-Host "✓ Endpoint creation initiated: $EndpointName" -ForegroundColor Green

# Step 3: Wait for endpoint to be InService
Write-Host ""
Write-Host "[3/4] Waiting for endpoint to reach InService..." -ForegroundColor Yellow
$MaxWait = 900
$Elapsed = 0

while ($Elapsed -lt $MaxWait) {
  $Status = aws sagemaker describe-endpoint --region $Region --endpoint-name $EndpointName --query 'EndpointStatus' --output text 2>/dev/null
  
  if ($Status -eq "InService") {
    Write-Host "✓ Endpoint is InService!" -ForegroundColor Green
    break
  }
  
  if ($null -ne $Status -and $Status -ne "") {
    Write-Host "  Status: $Status (elapsed: $Elapsed sec)"
  }
  
  Start-Sleep -Seconds 30
  $Elapsed += 30
}

if ($Elapsed -ge $MaxWait) {
  Write-Host "⚠ Reached timeout. Check status manually:" -ForegroundColor Yellow
  Write-Host "  aws sagemaker describe-endpoint --endpoint-name $EndpointName --region $Region --query 'EndpointStatus'" -ForegroundColor Cyan
}

# Step 4: Configure Auto-Scaling
Write-Host ""
Write-Host "[4/4] Configuring auto-scaling..." -ForegroundColor Yellow

aws application-autoscaling register-scalable-target --service-namespace sagemaker --resource-id "endpoint/$EndpointName/variant/AllTraffic" --scalable-dimension sagemaker:variant:DesiredInstanceCount --min-capacity 1 --max-capacity 2 --region $Region 2>&1 | Out-Null

$PolicyJson = '{\"TargetValue\": 6.0, \"PredefinedMetricSpecification\": {\"PredefinedMetricType\": \"SageMakerVariantInvocationsPerInstance\"}, \"ScaleOutCooldown\": 300, \"ScaleInCooldown\": 600}'

aws application-autoscaling put-scaling-policy --policy-name "$EndpointName-autoscaling" --policy-type TargetTrackingScaling --service-namespace sagemaker --resource-id "endpoint/$EndpointName/variant/AllTraffic" --scalable-dimension sagemaker:variant:DesiredInstanceCount --target-tracking-scaling-policy-configuration $PolicyJson --region $Region 2>&1 | Out-Null

Write-Host "✓ Auto-scaling configured" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "✓ ENDPOINT CREATION COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Verify status:"
Write-Host "   aws sagemaker describe-endpoint --endpoint-name $EndpointName --region $Region"
Write-Host ""
Write-Host "2. Run JMeter tests:"
Write-Host "   cd docs/jmeter-final-correctness"
Write-Host "   ./run_final_correctness_tests.ps1"
Write-Host ""
