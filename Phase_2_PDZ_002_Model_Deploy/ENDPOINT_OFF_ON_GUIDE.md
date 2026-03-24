# Endpoint OFF/ON Guide (SageMaker Real-Time)

This guide explains how to turn the `phase2-colqwen-rt` endpoint off and on later.

## Important billing note

- If the real-time endpoint exists and is `InService`, instance billing continues.
- To stop instance billing, you must delete the endpoint.
- You can keep endpoint config and model resources for easier restart.
- Keeping config/model does not charge endpoint compute, but small storage charges may still apply (for example S3 artifacts, ECR image storage, CloudWatch logs).

## Variables

```powershell
$ENDPOINT_NAME = "phase2-colqwen-rt"
$REGION = "us-west-2"
```

## Turn OFF (stop compute billing, keep config/model)

```powershell
python .\delete_sagemaker_endpoint.py `
  --region $REGION `
  --endpoint-name $ENDPOINT_NAME
```

What this does:

- Deletes only the endpoint.
- Keeps endpoint config and model resources.

## Turn OFF fully (delete endpoint + config + models)

```powershell
python .\delete_sagemaker_endpoint.py `
  --region $REGION `
  --endpoint-name $ENDPOINT_NAME `
  --delete-config-and-models
```

## Turn ON later (recreate endpoint from latest config)

```powershell
$ENDPOINT_CONFIG = aws sagemaker list-endpoint-configs `
  --region $REGION `
  --name-contains "$ENDPOINT_NAME-cfg-" `
  --query "sort_by(EndpointConfigs,&CreationTime)[-1].EndpointConfigName" `
  --output text

aws sagemaker create-endpoint `
  --region $REGION `
  --endpoint-name $ENDPOINT_NAME `
  --endpoint-config-name $ENDPOINT_CONFIG
```

## Check status

```powershell
aws sagemaker describe-endpoint `
  --region $REGION `
  --endpoint-name $ENDPOINT_NAME `
  --query "{Status:EndpointStatus,LastModified:LastModifiedTime,Failure:FailureReason}" `
  --output table
```

## Wait until ready

```powershell
aws sagemaker wait endpoint-in-service `
  --region $REGION `
  --endpoint-name $ENDPOINT_NAME
```

## Quick functional test

```powershell
python .\test_sagemaker_endpoint.py --region $REGION --endpoint-name $ENDPOINT_NAME --concurrent-users 1
```
