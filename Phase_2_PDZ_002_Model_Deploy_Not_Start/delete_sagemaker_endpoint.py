import argparse

import boto3  # type: ignore[import-not-found]
from botocore.exceptions import ClientError  # type: ignore[import-not-found]


def safe_delete(callable_obj, **kwargs):
    try:
        callable_obj(**kwargs)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"ValidationException", "ResourceNotFound"}:
            return
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete SageMaker endpoint resources")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--endpoint-name", default="phase2-colqwen-rt")
    parser.add_argument("--delete-config-and-models", action="store_true")
    args = parser.parse_args()

    sm = boto3.client("sagemaker", region_name=args.region)

    endpoint_config_name = None
    try:
        desc = sm.describe_endpoint(EndpointName=args.endpoint_name)
        endpoint_config_name = desc.get("EndpointConfigName")
    except ClientError:
        pass

    print(f"Deleting endpoint: {args.endpoint_name}")
    safe_delete(sm.delete_endpoint, EndpointName=args.endpoint_name)

    if not args.delete_config_and_models:
        print("Endpoint deletion requested. Config and model resources were kept.")
        return

    if endpoint_config_name:
        print(f"Deleting endpoint config: {endpoint_config_name}")
        safe_delete(sm.delete_endpoint_config, EndpointConfigName=endpoint_config_name)

    paginator = sm.get_paginator("list_models")
    for page in paginator.paginate(NameContains=f"{args.endpoint_name}-model-"):
        for model in page.get("Models", []):
            name = model["ModelName"]
            print(f"Deleting model: {name}")
            safe_delete(sm.delete_model, ModelName=name)

    print("Cleanup request submitted")


if __name__ == "__main__":
    main()
