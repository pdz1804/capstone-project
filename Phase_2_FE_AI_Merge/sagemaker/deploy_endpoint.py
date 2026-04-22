#!/usr/bin/env python3
"""
Deploy SageMaker endpoint with auto-scaling
Model: phase2-multimodal-rt-model-20260420174057
Endpoint: phase2-multimodal-rt
Instance: ml.g4dn.xlarge (1x NVIDIA T4 GPU)
Auto-scale: 1-3 instances
"""

import boto3
import sys

MODEL_NAME = "phase2-multimodal-rt-model-20260420174057"
ENDPOINT_NAME = "phase2-multimodal-rt"
ENDPOINT_CONFIG_NAME = "phase2-multimodal-rt-config"
INSTANCE_TYPE = "ml.g4dn.xlarge"
REGION = "us-west-2"

def main():
    print("\n" + "="*70)
    print("🚀 DEPLOYING SAGEMAKER ENDPOINT")
    print("="*70)
    print(f"Model:     {MODEL_NAME}")
    print(f"Endpoint:  {ENDPOINT_NAME}")
    print(f"Instance:  {INSTANCE_TYPE} (1x NVIDIA T4 GPU)")
    print(f"Region:    {REGION}\n")

    sagemaker = boto3.client('sagemaker', region_name=REGION)
    autoscaling = boto3.client('application-autoscaling', region_name=REGION)

    try:
        # Step 1: Create endpoint config
        print("[1/4] Creating endpoint configuration...")
        sagemaker.create_endpoint_config(
            EndpointConfigName=ENDPOINT_CONFIG_NAME,
            ProductionVariants=[{
                'VariantName': 'multimodal-variant',
                'ModelName': MODEL_NAME,
                'InitialInstanceCount': 1,
                'InstanceType': INSTANCE_TYPE,
            }]
        )
        print(f"      ✅ Config created: {ENDPOINT_CONFIG_NAME}\n")

        # Step 2: Create endpoint
        print("[2/4] Creating endpoint (5-10 minutes)...")
        print("      This may take a while, please wait...")
        sagemaker.create_endpoint(
            EndpointName=ENDPOINT_NAME,
            EndpointConfigName=ENDPOINT_CONFIG_NAME
        )
        print(f"      ✅ Endpoint creation initiated: {ENDPOINT_NAME}\n")

        # Step 3: Wait
        print("[3/4] Waiting for endpoint to be ready...")
        print("      (Do not close this window...)\n")
        waiter = sagemaker.get_waiter('endpoint_in_service')
        waiter.wait(
            EndpointName=ENDPOINT_NAME,
            WaiterConfig={'Delay': 30, 'MaxAttempts': 20}
        )
        print("      ✅ Endpoint is ready!\n")

        # Verify endpoint
        endpoint_info = sagemaker.describe_endpoint(EndpointName=ENDPOINT_NAME)
        print(f"      Status: {endpoint_info['EndpointStatus']}")
        print(f"      Instance count: {endpoint_info['ProductionVariants'][0]['CurrentInstanceCount']}\n")

        # Step 4: Auto-scaling
        print("[4/4] Configuring auto-scaling...")
        resource_id = f'endpoint/{ENDPOINT_NAME}/variant/multimodal-variant'

        # Register scalable target
        autoscaling.register_scalable_target(
            ServiceNamespace='sagemaker',
            ResourceId=resource_id,
            ScalableDimension='sagemaker:variant:DesiredInstanceCount',
            MinCapacity=1,
            MaxCapacity=3,
            RoleARN='arn:aws:iam::381492273521:role/SageMaker-AutoScalingRole'
        )
        print("      ✅ Scalable target registered (1-3 instances)\n")

        # Create scaling policy
        autoscaling.put_scaling_policy(
            PolicyName='phase2-multimodal-scaling',
            ServiceNamespace='sagemaker',
            ResourceId=resource_id,
            ScalableDimension='sagemaker:variant:DesiredInstanceCount',
            PolicyType='TargetTrackingScaling',
            TargetTrackingScalingPolicyConfiguration={
                'TargetValue': 70.0,
                'PredefinedMetricSpecification': {
                    'PredefinedMetricType': 'SageMakerVariantInvocationsPerInstance'
                },
                'ScaleOutCooldown': 300,      # 5 minutes
                'ScaleInCooldown': 600,       # 10 minutes
            }
        )
        print("      ✅ Auto-scaling policy configured\n")

        # Final summary
        print("="*70)
        print("✅ ENDPOINT DEPLOYMENT COMPLETE")
        print("="*70)
        print(f"\nEndpoint Details:")
        print(f"  Name:           {ENDPOINT_NAME}")
        print(f"  Instance Type:  {INSTANCE_TYPE} (1x NVIDIA T4 GPU)")
        print(f"  Auto-scale:     1-3 instances")
        print(f"  Target:         70% invocation rate")
        print(f"  Region:         {REGION}")
        print(f"\nCost Estimate:")
        print(f"  Rate:           ~$0.35/hour (1x T4)")
        print(f"  Monthly (24/7): ~$252/month\n")

        print("="*70)
        print("📋 UPDATE .env FILE")
        print("="*70)
        print(f"\nSet these environment variables:\n")
        print(f"USE_AWS_SAGEMAKER_DOCLING=1")
        print(f"SAGEMAKER_DOCLING_ENDPOINT_NAME={ENDPOINT_NAME}")
        print(f"AWS_REGION={REGION}")
        print(f"SAGEMAKER_DOCLING_READ_TIMEOUT_SECONDS=420")
        print(f"SAGEMAKER_DOCLING_CONNECT_TIMEOUT_SECONDS=10")

        print("\n" + "="*70)
        print("✅ Ready to use!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        sys.exit(1)

if __name__ == '__main__':
    main()
