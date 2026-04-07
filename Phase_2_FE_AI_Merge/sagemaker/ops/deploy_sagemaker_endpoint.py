import argparse
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


def parse_env_pairs(items: list[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --env value '{item}'. Expected KEY=VALUE.")
        k, v = item.split("=", 1)
        k = k.strip()
        if not k:
            raise ValueError(f"Invalid --env key in '{item}'.")
        env[k] = v
    return env


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy/update a SageMaker real-time endpoint")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--role-arn", required=True)
    parser.add_argument("--image-uri", required=True)
    parser.add_argument("--endpoint-name", required=True)
    parser.add_argument("--instance-type", default="ml.g4dn.xlarge")
    parser.add_argument("--initial-instance-count", type=int, default=1)
    parser.add_argument("--min-capacity", type=int, default=1)
    parser.add_argument("--max-capacity", type=int, default=2)
    parser.add_argument("--target-invocations-per-instance", type=float, default=2.0)
    parser.add_argument("--variant-name", default="AllTraffic")
    parser.add_argument("--env", action="append", default=[], help="Container env KEY=VALUE (repeatable)")
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()

    env = parse_env_pairs(args.env)

    sm = boto3.client("sagemaker", region_name=args.region)
    aas = boto3.client("application-autoscaling", region_name=args.region)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    model_name = f"{args.endpoint_name}-model-{ts}"
    cfg_name = f"{args.endpoint_name}-cfg-{ts}"

    print(f"Creating model: {model_name}")
    sm.create_model(
        ModelName=model_name,
        ExecutionRoleArn=args.role_arn,
        PrimaryContainer={"Image": args.image_uri, "Environment": env},
    )

    print(f"Creating endpoint config: {cfg_name}")
    sm.create_endpoint_config(
        EndpointConfigName=cfg_name,
        ProductionVariants=[
            {
                "VariantName": args.variant_name,
                "ModelName": model_name,
                "InitialInstanceCount": args.initial_instance_count,
                "InstanceType": args.instance_type,
                "InitialVariantWeight": 1.0,
            }
        ],
    )

    if endpoint_exists(sm, args.endpoint_name):
        print(f"Updating endpoint: {args.endpoint_name}")
        sm.update_endpoint(EndpointName=args.endpoint_name, EndpointConfigName=cfg_name)
    else:
        print(f"Creating endpoint: {args.endpoint_name}")
        sm.create_endpoint(EndpointName=args.endpoint_name, EndpointConfigName=cfg_name)

    if args.wait:
        print("Waiting for endpoint to become InService...")
        waiter = sm.get_waiter("endpoint_in_service")
        waiter.wait(EndpointName=args.endpoint_name)

    resource_id = f"endpoint/{args.endpoint_name}/variant/{args.variant_name}"
    print("Configuring autoscaling...")
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

    print("Deployment submitted.")
    print(f"Endpoint: {args.endpoint_name}")
    print(f"Region: {args.region}")


if __name__ == "__main__":
    main()
