import argparse
import time
from datetime import datetime, timezone

import boto3  # type: ignore[import-not-found]
from botocore.exceptions import ClientError  # type: ignore[import-not-found]


def endpoint_exists(sm_client, endpoint_name: str) -> bool:
    try:
        sm_client.describe_endpoint(EndpointName=endpoint_name)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ValidationException":
            return False
        raise


def wait_until_endpoint_in_service(sm_client, endpoint_name: str) -> None:
    print("Waiting for endpoint to reach InService before configuring autoscaling...")
    waiter = sm_client.get_waiter("endpoint_in_service")
    waiter.wait(EndpointName=endpoint_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy ColQwen endpoint on SageMaker")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--role-arn", required=True)
    parser.add_argument("--image-uri", required=True)
    parser.add_argument("--endpoint-name", default="phase2-colqwen-rt")
    parser.add_argument("--instance-type", default="ml.g4dn.xlarge")
    parser.add_argument("--initial-instance-count", type=int, default=1)
    parser.add_argument("--min-capacity", type=int, default=1)
    parser.add_argument("--max-capacity", type=int, default=2)
    parser.add_argument("--target-invocations-per-instance", type=float, default=6.0)
    parser.add_argument("--model-name", default="vidore/colqwen2-v1.0")
    parser.add_argument("--quantization", choices=["none", "4bit", "8bit"], default="8bit")
    parser.add_argument("--max-concurrent-inferences", type=int, default=2)
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()

    sm = boto3.client("sagemaker", region_name=args.region)
    aas = boto3.client("application-autoscaling", region_name=args.region)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    model_resource_name = f"{args.endpoint_name}-model-{ts}"
    endpoint_config_name = f"{args.endpoint_name}-cfg-{ts}"

    env = {
        "COLQWEN_MODEL": args.model_name,
        "COLQWEN_QUANTIZATION": args.quantization,
        "COLQWEN_MAX_CONCURRENT_INFERENCES": str(args.max_concurrent_inferences),
        "SAGEMAKER_SERVICE_MODE": "true",
    }

    print(f"Creating model: {model_resource_name}")
    sm.create_model(
        ModelName=model_resource_name,
        ExecutionRoleArn=args.role_arn,
        PrimaryContainer={
            "Image": args.image_uri,
            "Environment": env,
        },
    )

    print(f"Creating endpoint config: {endpoint_config_name}")
    sm.create_endpoint_config(
        EndpointConfigName=endpoint_config_name,
        ProductionVariants=[
            {
                "VariantName": "AllTraffic",
                "ModelName": model_resource_name,
                "InitialInstanceCount": args.initial_instance_count,
                "InstanceType": args.instance_type,
                "InitialVariantWeight": 1.0,
            }
        ],
    )

    if endpoint_exists(sm, args.endpoint_name):
        print(f"Updating endpoint: {args.endpoint_name}")
        sm.update_endpoint(
            EndpointName=args.endpoint_name,
            EndpointConfigName=endpoint_config_name,
        )
    else:
        print(f"Creating endpoint: {args.endpoint_name}")
        sm.create_endpoint(
            EndpointName=args.endpoint_name,
            EndpointConfigName=endpoint_config_name,
        )

    wait_until_endpoint_in_service(sm, args.endpoint_name)

    resource_id = f"endpoint/{args.endpoint_name}/variant/AllTraffic"

    print("Configuring auto scaling...")
    aas.register_scalable_target(
        ServiceNamespace="sagemaker",
        ResourceId=resource_id,
        ScalableDimension="sagemaker:variant:DesiredInstanceCount",
        MinCapacity=args.min_capacity,
        MaxCapacity=args.max_capacity,
    )

    aas.put_scaling_policy(
        PolicyName=f"{args.endpoint_name}-target-tracking",
        ServiceNamespace="sagemaker",
        ResourceId=resource_id,
        ScalableDimension="sagemaker:variant:DesiredInstanceCount",
        PolicyType="TargetTrackingScaling",
        TargetTrackingScalingPolicyConfiguration={
            "TargetValue": args.target_invocations_per_instance,
            "PredefinedMetricSpecification": {
                "PredefinedMetricType": "SageMakerVariantInvocationsPerInstance"
            },
            "ScaleOutCooldown": 60,
            "ScaleInCooldown": 300,
        },
    )

    if args.wait:
        print("Waiting for endpoint to become InService...")
        waiter = sm.get_waiter("endpoint_in_service")
        waiter.wait(EndpointName=args.endpoint_name)

    print("Deployment request submitted successfully")
    print(f"Endpoint: {args.endpoint_name}")
    print(f"Instance type: {args.instance_type}")
    print(f"Autoscaling min/max: {args.min_capacity}/{args.max_capacity}")
    print(f"Target invocations per instance: {args.target_invocations_per_instance}")


if __name__ == "__main__":
    main()
