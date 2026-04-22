#!/usr/bin/env pwsh
<#
.SYNOPSIS
Create SageMaker endpoint from existing model and test Process/Index/Search APIs
.DESCRIPTION
Creates a real-time endpoint from phase2-multimodal-rt-model-20260420174057 model
Then runs capacity tests for process, index, and search endpoints
.EXAMPLE
./create_endpoint_and_test.ps1
#>

param(
    [string]$Region = "us-west-2",
    [string]$ModelName = "phase2-multimodal-rt-model-20260420174057",
    [string]$EndpointName = "phase2-multimodal-rt-endpoint",
    [string]$InstanceType = "ml.g4dn.xlarge",
    [int]$InitialInstanceCount = 1,
    [int]$MinCapacity = 1,
    [int]$MaxCapacity = 2,
    [float]$TargetInvocations = 6.0
)

$ErrorActionPreference = "Stop"

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "CREATE SAGEMAKER ENDPOINT FROM MODEL" -ForegroundColor Cyan
Write-Host "=" * 80

Write-Host "`n[1] Configuration:" -ForegroundColor Yellow
Write-Host "  Region: $Region"
Write-Host "  Model: $ModelName"
Write-Host "  Endpoint Name: $EndpointName"
Write-Host "  Instance Type: $InstanceType"
Write-Host "  Initial Instances: $InitialInstanceCount"
Write-Host "  Autoscale Min/Max: $MinCapacity / $MaxCapacity"

# Step 1: Check if endpoint already exists
Write-Host "`n[2] Checking if endpoint exists..." -ForegroundColor Yellow
try {
    $endpoint = aws sagemaker describe-endpoint `
        --endpoint-name $EndpointName `
        --region $Region `
        --output json 2>$null | ConvertFrom-Json
    
    if ($endpoint) {
        Write-Host "  ⚠️  Endpoint '$EndpointName' already exists" -ForegroundColor Yellow
        Write-Host "  Status: $($endpoint.EndpointStatus)" -ForegroundColor Gray
        
        if ($endpoint.EndpointStatus -eq "InService") {
            Write-Host "  ✓ Endpoint is ready for testing" -ForegroundColor Green
            $ENDPOINT_READY = $true
        } else {
            Write-Host "  ⏳ Waiting for endpoint to reach InService..." -ForegroundColor Yellow
            aws sagemaker wait endpoint-in-service `
                --endpoint-name $EndpointName `
                --region $Region
            Write-Host "  ✓ Endpoint is now InService" -ForegroundColor Green
            $ENDPOINT_READY = $true
        }
    }
} catch {
    Write-Host "  ℹ️  Endpoint does not exist, will create new one" -ForegroundColor Gray
    $ENDPOINT_READY = $false
}

# Step 2: Create endpoint if it doesn't exist
if (-not $ENDPOINT_READY) {
    Write-Host "`n[3] Creating endpoint configuration and endpoint..." -ForegroundColor Yellow
    
    # Get current timestamp for unique names
    $ts = Get-Date -Format "yyyyMMddHHmmss"
    $EndpointConfigName = "$EndpointName-cfg-$ts"
    
    # Create endpoint config
    Write-Host "  Creating endpoint config: $EndpointConfigName"
    
    $configJson = @{
        EndpointConfigName = $EndpointConfigName
        ProductionVariants = @(
            @{
                VariantName = "AllTraffic"
                ModelName = $ModelName
                InitialInstanceCount = $InitialInstanceCount
                InstanceType = $InstanceType
            }
        )
    } | ConvertTo-Json
    
    $configJson | aws sagemaker create-endpoint-config `
        --cli-input-json file:///dev/stdin `
        --region $Region 2>&1 | Write-Host
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ✗ Failed to create endpoint config" -ForegroundColor Red
        exit 1
    }
    
    # Create endpoint
    Write-Host "  Creating endpoint: $EndpointName"
    aws sagemaker create-endpoint `
        --endpoint-name $EndpointName `
        --endpoint-config-name $EndpointConfigName `
        --region $Region 2>&1 | Write-Host
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ✗ Failed to create endpoint" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "`n[4] Waiting for endpoint to reach InService..." -ForegroundColor Yellow
    aws sagemaker wait endpoint-in-service `
        --endpoint-name $EndpointName `
        --region $Region
    
    Write-Host "  ✓ Endpoint is now InService" -ForegroundColor Green
    $ENDPOINT_READY = $true
}

# Step 3: Verify endpoint status
Write-Host "`n[5] Endpoint Status:" -ForegroundColor Yellow
aws sagemaker describe-endpoint `
    --endpoint-name $EndpointName `
    --region $Region `
    --query "{EndpointName:EndpointName,Status:EndpointStatus,CreatedTime:CreationTime,LastModified:LastModifiedTime,ProductionVariants:ProductionVariants[0].{VariantName:VariantName,ModelName:ModelName,InstanceType:InstanceType}}" `
    --output table

# Step 4: Quick functional test
Write-Host "`n[6] Quick Functional Test:" -ForegroundColor Yellow
Write-Host "  Testing endpoint connectivity..." -ForegroundColor Gray

$testResult = aws sagemaker-runtime invoke-endpoint `
    --endpoint-name $EndpointName `
    --body '{"test":"connection"}' `
    --content-type "application/json" `
    --region $Region `
    --output json 2>&1 | ConvertFrom-Json

if ($testResult.ResponseMetadata.HTTPStatusCode -eq 200) {
    Write-Host "  ✓ Endpoint is responding correctly" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Endpoint returned: $($testResult.ResponseMetadata.HTTPStatusCode)" -ForegroundColor Yellow
}

# Step 5: Run capacity tests
Write-Host "`n[7] Running Capacity Tests (Process, Index, Search):" -ForegroundColor Yellow
Write-Host "  Starting JMeter tests..." -ForegroundColor Gray

$testDir = "d:\PDZ\BKU\Learning\LVTN\GD1\Code\docs\jmeter-capacity-tests"

if (-not (Test-Path $testDir)) {
    Write-Host "  ✗ Test directory not found: $testDir" -ForegroundColor Red
    exit 1
}

cd $testDir

# Test Process
Write-Host "`n  Testing: 05_process" -ForegroundColor Cyan
powershell -ExecutionPolicy Bypass -File '.\run_capacity_finder_fixed.ps1' -APIs '05_process'

# Test Index
Write-Host "`n  Testing: 06_index" -ForegroundColor Cyan
powershell -ExecutionPolicy Bypass -File '.\run_capacity_finder_fixed.ps1' -APIs '06_index'

# Test Search
Write-Host "`n  Testing: 07_search_retrieval" -ForegroundColor Cyan
powershell -ExecutionPolicy Bypass -File '.\run_capacity_finder_fixed.ps1' -APIs '07_search_retrieval'

Write-Host "`n" + "=" * 80
Write-Host "ENDPOINT CREATION AND TESTING COMPLETE" -ForegroundColor Green
Write-Host "=" * 80

Write-Host "`nEndpoint Summary:" -ForegroundColor Yellow
Write-Host "  Name: $EndpointName"
Write-Host "  Region: $Region"
Write-Host "  Model: $ModelName"
Write-Host "  Status: InService"
Write-Host "`nTest Results:" -ForegroundColor Yellow
Write-Host "  ✓ Process API tested"
Write-Host "  ✓ Index API tested"
Write-Host "  ✓ Search API tested"

Write-Host "`nNext Steps:" -ForegroundColor Yellow
Write-Host "  1. Review capacity test results in: results/"
Write-Host "  2. Monitor endpoint in SageMaker Console"
Write-Host "  3. Set up CloudWatch alarms for InvocationsFailed"
Write-Host "`n"
