# SageMaker Endpoint Deployment Guide
**Date:** 2026-04-22  
**Model:** phase2-multimodal-rt-model-20260420174057  
**Model ARN:** arn:aws:sagemaker:us-west-2:381492273521:model/phase2-multimodal-rt-model-20260420174057  
**Region:** us-west-2  
**Purpose:** Deploy Docling multimodal processing with auto-scaling

---

## 📋 Prerequisites

```bash
# Verify AWS CLI is installed and configured
aws --version
aws sts get-caller-identity

# Verify the model exists
aws sagemaker describe-model \
  --model-name phase2-multimodal-rt-model-20260420174057 \
  --region us-west-2
```

---

## 🚀 Step 1: Create SageMaker Endpoint Configuration

### Option A: Using AWS CLI

```bash
# Set variables
export MODEL_NAME="phase2-multimodal-rt-model-20260420174057"
export ENDPOINT_CONFIG_NAME="phase2-multimodal-docling-config-$(date +%Y%m%d-%H%M%S)"
export INSTANCE_TYPE="ml.p3.2xlarge"  # GPU instance for inference
export INITIAL_INSTANCE_COUNT=1
export REGION="us-west-2"

# Create endpoint configuration with Docling environment variables
aws sagemaker create-endpoint-config \
  --endpoint-config-name "${ENDPOINT_CONFIG_NAME}" \
  --production-variants \
    VariantName=docling-variant,\
    ModelName="${MODEL_NAME}",\
    InitialInstanceCount=${INITIAL_INSTANCE_COUNT},\
    InstanceType=${INSTANCE_TYPE},\
    InitialVariantWeight=1.0,\
    Container={Environment={DOCLING_ENABLE_VLM=true,DOCLING_EXPORT_IMAGES=true,DOCLING_EXPORT_TABLES=true,DOCLING_OCR_ENGINE=rapidocr}} \
  --region ${REGION}

echo "Endpoint config created: ${ENDPOINT_CONFIG_NAME}"
```

### Option B: Using Python (boto3)

```python
import boto3
from datetime import datetime

sagemaker_client = boto3.client('sagemaker', region_name='us-west-2')

MODEL_NAME = 'phase2-multimodal-rt-model-20260420174057'
ENDPOINT_CONFIG_NAME = f'phase2-multimodal-docling-config-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
INSTANCE_TYPE = 'ml.p3.2xlarge'  # GPU instance

# Create endpoint configuration
response = sagemaker_client.create_endpoint_config(
    EndpointConfigName=ENDPOINT_CONFIG_NAME,
    ProductionVariants=[
        {
            'VariantName': 'docling-variant',
            'ModelName': MODEL_NAME,
            'InitialInstanceCount': 1,
            'InstanceType': INSTANCE_TYPE,
            'InitialVariantWeight': 1.0,
            # Set Docling environment variables for consistency with local config
            'Container': {
                'Environment': {
                    'DOCLING_ENABLE_VLM': 'true',         # Enable vision/image descriptions
                    'DOCLING_EXPORT_IMAGES': 'true',      # Export extracted images
                    'DOCLING_EXPORT_TABLES': 'true',      # Export extracted tables
                    'DOCLING_OCR_ENGINE': 'rapidocr',     # OCR engine (matches local)
                }
            }
        }
    ]
)

print(f"Endpoint config created: {ENDPOINT_CONFIG_NAME}")
print(f"Config ARN: {response['EndpointConfigArn']}")
```

---

## 🔴 Step 2: Create SageMaker Endpoint

### Option A: Using AWS CLI

```bash
# Set variables
export ENDPOINT_NAME="phase2-docling-endpoint-$(date +%Y%m%d-%H%M%S)"
export ENDPOINT_CONFIG_NAME="phase2-multimodal-docling-config-XXXXX"  # From Step 1
export REGION="us-west-2"

# Create endpoint
aws sagemaker create-endpoint \
  --endpoint-name "${ENDPOINT_NAME}" \
  --endpoint-config-name "${ENDPOINT_CONFIG_NAME}" \
  --region ${REGION}

echo "Endpoint creation initiated: ${ENDPOINT_NAME}"
echo "Checking endpoint status..."

# Monitor endpoint creation
aws sagemaker describe-endpoint \
  --endpoint-name "${ENDPOINT_NAME}" \
  --region ${REGION} \
  --query 'EndpointStatus' \
  --output text

# Wait for endpoint to be ready (can take 5-10 minutes)
aws sagemaker wait endpoint-in-service \
  --endpoint-name "${ENDPOINT_NAME}" \
  --region ${REGION}

echo "✅ Endpoint is ready!"
```

### Option B: Using Python (boto3)

```python
import boto3
import time

sagemaker_client = boto3.client('sagemaker', region_name='us-west-2')

ENDPOINT_NAME = f'phase2-docling-endpoint-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
ENDPOINT_CONFIG_NAME = 'phase2-multimodal-docling-config-XXXXX'  # From Step 1

# Create endpoint
response = sagemaker_client.create_endpoint(
    EndpointName=ENDPOINT_NAME,
    EndpointConfigName=ENDPOINT_CONFIG_NAME
)

print(f"Endpoint creation initiated: {ENDPOINT_NAME}")
print(f"Endpoint ARN: {response['EndpointArn']}")

# Wait for endpoint to be in service (poll status)
print("Waiting for endpoint to be ready (this may take 5-10 minutes)...")
waiter = sagemaker_client.get_waiter('endpoint_in_service')
waiter.wait(EndpointName=ENDPOINT_NAME)
print("✅ Endpoint is ready!")
```

---

## ⚙️ Step 3: Enable Auto-Scaling

### Option A: Using AWS CLI

```bash
# Set variables
export ENDPOINT_NAME="phase2-docling-endpoint-XXXXX"  # From Step 2
export REGION="us-west-2"
export SERVICE_NAMESPACE="sagemaker"
export RESOURCE_ID="endpoint/${ENDPOINT_NAME}/variant/docling-variant"

# Register scalable target
aws application-autoscaling register-scalable-target \
  --service-namespace ${SERVICE_NAMESPACE} \
  --resource-id ${RESOURCE_ID} \
  --scalable-dimension sagemaker:variant:DesiredInstanceCount \
  --min-capacity 1 \
  --max-capacity 4 \
  --region ${REGION}

echo "Scalable target registered"

# Create target tracking scaling policy (CPU utilization)
aws application-autoscaling put-scaling-policy \
  --policy-name phase2-docling-cpu-scaling \
  --service-namespace ${SERVICE_NAMESPACE} \
  --resource-id ${RESOURCE_ID} \
  --scalable-dimension sagemaker:variant:DesiredInstanceCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "SageMakerVariantInvocationsPerInstance"
    },
    "ScaleOutCooldown": 300,
    "ScaleInCooldown": 600
  }' \
  --region ${REGION}

echo "✅ Auto-scaling policy configured (Target: 70% CPU, Scale-out: 5 min, Scale-in: 10 min)"
```

### Option B: Using Python (boto3)

```python
import boto3

autoscaling_client = boto3.client('application-autoscaling', region_name='us-west-2')
sagemaker_client = boto3.client('sagemaker', region_name='us-west-2')

ENDPOINT_NAME = 'phase2-docling-endpoint-XXXXX'  # From Step 2
REGION = 'us-west-2'
SERVICE_NAMESPACE = 'sagemaker'
RESOURCE_ID = f'endpoint/{ENDPOINT_NAME}/variant/docling-variant'

# Register scalable target (min=1, max=4 instances)
autoscaling_client.register_scalable_target(
    ServiceNamespace=SERVICE_NAMESPACE,
    ResourceId=RESOURCE_ID,
    ScalableDimension='sagemaker:variant:DesiredInstanceCount',
    MinCapacity=1,
    MaxCapacity=4,
    RoleARN='arn:aws:iam::381492273521:role/SageMaker-AutoScalingRole'  # Ensure this role exists
)

print("✅ Scalable target registered (1-4 instances)")

# Create target tracking scaling policy
autoscaling_client.put_scaling_policy(
    PolicyName='phase2-docling-cpu-scaling',
    ServiceNamespace=SERVICE_NAMESPACE,
    ResourceId=RESOURCE_ID,
    ScalableDimension='sagemaker:variant:DesiredInstanceCount',
    PolicyType='TargetTrackingScaling',
    TargetTrackingScalingPolicyConfiguration={
        'TargetValue': 70.0,  # Target 70% invocation rate
        'PredefinedMetricSpecification': {
            'PredefinedMetricType': 'SageMakerVariantInvocationsPerInstance'
        },
        'ScaleOutCooldown': 300,    # 5 minutes before scaling out again
        'ScaleInCooldown': 600,     # 10 minutes before scaling in again
    }
)

print("✅ Auto-scaling policy configured")
print("   - Target: 70% invocation rate per instance")
print("   - Min instances: 1, Max instances: 4")
print("   - Scale-out cooldown: 5 minutes")
print("   - Scale-in cooldown: 10 minutes")
```

---

## 🔍 Step 4: Verify and Test Endpoint

### Check Endpoint Status

```bash
# Using AWS CLI
aws sagemaker describe-endpoint \
  --endpoint-name phase2-docling-endpoint-XXXXX \
  --region us-west-2 \
  --query '{Status: EndpointStatus, Variants: ProductionVariants[0].{InstanceCount: CurrentInstanceCount, Type: InstanceType}}'

# Using Python
response = sagemaker_client.describe_endpoint(
    EndpointName='phase2-docling-endpoint-XXXXX'
)
print(f"Status: {response['EndpointStatus']}")
print(f"Instance count: {response['ProductionVariants'][0]['CurrentInstanceCount']}")
```

### Test Inference

```python
import boto3
import base64
import json

sagemaker_client = boto3.client('sagemaker-runtime', region_name='us-west-2')

ENDPOINT_NAME = 'phase2-docling-endpoint-XXXXX'

# Test with a PDF file
with open('/path/to/test.pdf', 'rb') as f:
    pdf_content = base64.b64encode(f.read()).decode('ascii')

# Invoke endpoint
response = sagemaker_client.invoke_endpoint(
    EndpointName=ENDPOINT_NAME,
    ContentType='application/json',
    Body=json.dumps({
        'operation': 'process-document',
        'filename': 'test.pdf',
        'content_base64': pdf_content
    })
)

# Parse response
result = json.loads(response['Body'].read().decode())
print("Response received")
print(f"Markdown length: {len(result.get('markdown', ''))}")
print(f"Additional files: {list(result.get('additional_files', {}).keys())}")
```

---

## 📊 Step 5: Configure Application to Use Endpoint

### Set Environment Variables

```bash
# Backend configuration
export USE_AWS_SAGEMAKER_DOCLING=1
export SAGEMAKER_DOCLING_ENDPOINT_NAME=phase2-docling-endpoint-XXXXX
export AWS_REGION=us-west-2
export SAGEMAKER_DOCLING_READ_TIMEOUT_SECONDS=420
export SAGEMAKER_DOCLING_CONNECT_TIMEOUT_SECONDS=10
```

### Update runtime.yaml

```yaml
inference:
  use_aws_sagemaker_docling: true
  sagemaker_docling_endpoint_name: "phase2-docling-endpoint-XXXXX"
  aws_region: "us-west-2"
  sagemaker_docling_read_timeout_seconds: 420
  sagemaker_docling_connect_timeout_seconds: 10
```

### Python Configuration

```python
from processor.document_processor_v2_1 import DocumentProcessorV2_1, ProcessingConfigV2_1

config = ProcessingConfigV2_1(
    use_sagemaker_for_docling=True,
    sagemaker_docling_endpoint_name='phase2-docling-endpoint-XXXXX',
    aws_region='us-west-2',
    sagemaker_read_timeout_seconds=420,
    sagemaker_connect_timeout_seconds=10,
)

processor = DocumentProcessorV2_1(
    input_dir='./input',
    output_dir='./output',
    config=config
)
```

---

## 🚀 Monitoring and Maintenance

### Monitor Auto-Scaling

```bash
# View scaling activities
aws application-autoscaling describe-scaling-activities \
  --service-namespace sagemaker \
  --region us-west-2 \
  --query 'ScalingActivities[0:5]'

# View current scaling policy
aws application-autoscaling describe-scaling-policies \
  --service-namespace sagemaker \
  --resource-id "endpoint/phase2-docling-endpoint-XXXXX/variant/docling-variant" \
  --region us-west-2
```

### Monitor Endpoint Metrics

```python
import boto3

cloudwatch = boto3.client('cloudwatch', region_name='us-west-2')

# Get invocation count
response = cloudwatch.get_metric_statistics(
    Namespace='AWS/SageMaker',
    MetricName='InvocationsPerInstance',
    Dimensions=[
        {'Name': 'EndpointName', 'Value': 'phase2-docling-endpoint-XXXXX'},
        {'Name': 'VariantName', 'Value': 'docling-variant'}
    ],
    StartTime=datetime.now() - timedelta(hours=1),
    EndTime=datetime.now(),
    Period=300,  # 5 minutes
    Statistics=['Average', 'Sum']
)

for point in response['Datapoints']:
    print(f"Time: {point['Timestamp']}, Average: {point['Average']:.2f}, Sum: {point['Sum']:.0f}")
```

---

## 🗑️ Cleanup

### Delete Endpoint (if needed)

```bash
# Warning: This will stop inference!
aws sagemaker delete-endpoint \
  --endpoint-name phase2-docling-endpoint-XXXXX \
  --region us-west-2

# Delete endpoint configuration
aws sagemaker delete-endpoint-config \
  --endpoint-config-name phase2-multimodal-docling-config-XXXXX \
  --region us-west-2

# Deregister scalable target
aws application-autoscaling deregister-scalable-target \
  --service-namespace sagemaker \
  --resource-id endpoint/phase2-docling-endpoint-XXXXX/variant/docling-variant \
  --scalable-dimension sagemaker:variant:DesiredInstanceCount \
  --region us-west-2
```

---

## 💾 Complete Script (All-in-One)

Create file: `deploy_sagemaker_endpoint.py`

```python
#!/usr/bin/env python3
"""
Complete SageMaker Endpoint Deployment Script
Deploys phase2-multimodal-rt-model with auto-scaling
"""

import boto3
import sys
from datetime import datetime

def deploy_sagemaker_endpoint(region='us-west-2'):
    """Deploy SageMaker endpoint with auto-scaling"""
    
    sagemaker = boto3.client('sagemaker', region_name=region)
    autoscaling = boto3.client('application-autoscaling', region_name=region)
    
    MODEL_NAME = 'phase2-multimodal-rt-model-20260420174057'
    INSTANCE_TYPE = 'ml.p3.2xlarge'
    TIMESTAMP = datetime.now().strftime('%Y%m%d-%H%M%S')
    
    try:
        # Step 1: Create endpoint config
        print("[1/4] Creating endpoint configuration...")
        endpoint_config_name = f'phase2-multimodal-docling-config-{TIMESTAMP}'
        config_response = sagemaker.create_endpoint_config(
            EndpointConfigName=endpoint_config_name,
            ProductionVariants=[{
                'VariantName': 'docling-variant',
                'ModelName': MODEL_NAME,
                'InitialInstanceCount': 1,
                'InstanceType': INSTANCE_TYPE,
                'InitialVariantWeight': 1.0,
                'Container': {
                    'Environment': {
                        'DOCLING_ENABLE_VLM': 'true',
                        'DOCLING_EXPORT_IMAGES': 'true',
                        'DOCLING_EXPORT_TABLES': 'true',
                        'DOCLING_OCR_ENGINE': 'rapidocr',
                    }
                }
            }]
        )
        print(f"✅ Config created: {endpoint_config_name}")
        
        # Step 2: Create endpoint
        print("\n[2/4] Creating endpoint (5-10 minutes)...")
        endpoint_name = f'phase2-docling-endpoint-{TIMESTAMP}'
        endpoint_response = sagemaker.create_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=endpoint_config_name
        )
        print(f"✅ Endpoint creation initiated: {endpoint_name}")
        
        # Step 3: Wait for endpoint
        print("\n[3/4] Waiting for endpoint to be ready...")
        waiter = sagemaker.get_waiter('endpoint_in_service')
        waiter.wait(EndpointName=endpoint_name)
        print("✅ Endpoint is ready!")
        
        # Step 4: Configure auto-scaling
        print("\n[4/4] Configuring auto-scaling...")
        resource_id = f'endpoint/{endpoint_name}/variant/docling-variant'
        
        autoscaling.register_scalable_target(
            ServiceNamespace='sagemaker',
            ResourceId=resource_id,
            ScalableDimension='sagemaker:variant:DesiredInstanceCount',
            MinCapacity=1,
            MaxCapacity=4,
            RoleARN='arn:aws:iam::381492273521:role/SageMaker-AutoScalingRole'
        )
        
        autoscaling.put_scaling_policy(
            PolicyName='phase2-docling-cpu-scaling',
            ServiceNamespace='sagemaker',
            ResourceId=resource_id,
            ScalableDimension='sagemaker:variant:DesiredInstanceCount',
            PolicyType='TargetTrackingScaling',
            TargetTrackingScalingPolicyConfiguration={
                'TargetValue': 70.0,
                'PredefinedMetricSpecification': {
                    'PredefinedMetricType': 'SageMakerVariantInvocationsPerInstance'
                },
                'ScaleOutCooldown': 300,
                'ScaleInCooldown': 600,
            }
        )
        print("✅ Auto-scaling configured!")
        
        # Summary
        print("\n" + "="*60)
        print("DEPLOYMENT SUMMARY")
        print("="*60)
        print(f"Endpoint Name:      {endpoint_name}")
        print(f"Config Name:        {endpoint_config_name}")
        print(f"Instance Type:      {INSTANCE_TYPE}")
        print(f"Initial Instances:  1 (scales 1-4)")
        print(f"Region:             {region}")
        print("\nENVIRONMENT VARIABLES:")
        print(f"export USE_AWS_SAGEMAKER_DOCLING=1")
        print(f"export SAGEMAKER_DOCLING_ENDPOINT_NAME={endpoint_name}")
        print(f"export AWS_REGION={region}")
        print("="*60)
        
        return endpoint_name
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    deploy_sagemaker_endpoint()
```

Run with:
```bash
python3 deploy_sagemaker_endpoint.py
```

---

## 📋 Configuration Reference

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Model** | phase2-multimodal-rt-model-20260420174057 | Production multimodal model |
| **Instance Type** | ml.p3.2xlarge | GPU: 1x NVIDIA V100 (16GB VRAM) |
| **Initial Instances** | 1 | Auto-scales to 4 max |
| **Region** | us-west-2 | Oregon region |
| **DOCLING_ENABLE_VLM** | true | ✅ Enables image descriptions |
| **DOCLING_EXPORT_IMAGES** | true | ✅ Extracts images from PDFs |
| **DOCLING_EXPORT_TABLES** | true | ✅ Extracts tables as CSV |
| **OCR Engine** | rapidocr | Fast CPU-based OCR |
| **Target Scaling** | 70% invocation rate | Scales when usage exceeds 70% |
| **Read Timeout** | 420s (7 min) | Large PDF processing |
| **Connect Timeout** | 10s | Initial connection |

---

## ⚠️ Important Notes

1. **IAM Role:** Ensure SageMaker auto-scaling role exists: `arn:aws:iam::381492273521:role/SageMaker-AutoScalingRole`

2. **GPU Cost:** ml.p3.2xlarge costs ~$3.06/hour. Endpoint runs 24/7 unless deleted.

3. **Config Consistency:** The environment variables set on the endpoint match the local V2.1 defaults:
   - VLM enabled (image descriptions)
   - Images extracted
   - Tables extracted
   - This ensures SageMaker output = Local output (solves Option B config mismatch)

4. **Fallback:** V2.1 automatically falls back to local GPU if SageMaker endpoint is unavailable.

5. **Monitoring:** Check CloudWatch metrics and auto-scaling activities to verify proper operation.

---

**Generated:** 2026-04-22  
**Project:** bk_mind Phase 2  
**Branch:** develop
