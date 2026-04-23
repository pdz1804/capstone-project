# Variables from your model info

```powershell
$region = "us-west-2"
$accountId = "381492273521"
$modelName = "phase2-multimodal-rt-model-20260420174057"
$endpointName = "phase2-multimodal-rt"
$instanceType = "ml.g4dn.xlarge"
$initialCount = 1

# 1) Create endpoint config from your existing model
$cfg = "$endpointName-cfg-$(Get-Date -Format yyyyMMddHHmmss)"
$productionVariant = "VariantName=AllTraffic,ModelName=$modelName,InitialInstanceCount=$initialCount,InstanceType=$instanceType,InitialVariantWeight=1.0"

aws sagemaker create-endpoint-config --region $region --endpoint-config-name $cfg --production-variants $productionVariant

# 2) Create endpoint if missing, otherwise update endpoint to new config
aws sagemaker describe-endpoint --region $region --endpoint-name $endpointName 1>$null 2>$null
if ($LASTEXITCODE -eq 0) {
  Write-Host "Endpoint exists, updating to new config: $cfg"
  aws sagemaker update-endpoint --region $region --endpoint-name $endpointName --endpoint-config-name $cfg
} else {
  Write-Host "Endpoint does not exist, creating: $endpointName"
  aws sagemaker create-endpoint --region $region --endpoint-name $endpointName --endpoint-config-name $cfg
}

# 3) Wait until ready
aws sagemaker wait endpoint-in-service --region $region --endpoint-name $endpointName

# 4) Configure autoscaling
$resourceId = "endpoint/$endpointName/variant/AllTraffic"

aws application-autoscaling register-scalable-target --region $region --service-namespace sagemaker --resource-id $resourceId --scalable-dimension sagemaker:variant:DesiredInstanceCount --min-capacity 1 --max-capacity 2

aws application-autoscaling put-scaling-policy --region $region --policy-name "$endpointName-target-tracking" --service-namespace sagemaker --resource-id $resourceId --scalable-dimension sagemaker:variant:DesiredInstanceCount --policy-type TargetTrackingScaling --target-tracking-scaling-policy-configuration '{"TargetValue":6.0,"PredefinedMetricSpecification":{"PredefinedMetricType":"SageMakerVariantInvocationsPerInstance"},"ScaleOutCooldown":60,"ScaleInCooldown":300}'
```
