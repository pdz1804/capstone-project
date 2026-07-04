import argparse

import boto3  # type: ignore[import-not-found]
from botocore.exceptions import ClientError  # type: ignore[import-not-found]


def safe_delete_endpoint(sm, endpoint_name: str) -> None:
    try:
        sm.delete_endpoint(EndpointName=endpoint_name)
        print(f"Delete requested for endpoint: {endpoint_name}")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "ValidationException":
            print(f"Endpoint not found: {endpoint_name}")
            return
        raise


def safe_delete_endpoint_config(sm, endpoint_name: str) -> None:
    paginator = sm.get_paginator("list_endpoint_configs")
    deleted = 0
    for page in paginator.paginate(SortBy="CreationTime", SortOrder="Descending"):
        for summary in page.get("EndpointConfigs", []):
            name = summary.get("EndpointConfigName", "")
            if name.startswith(f"{endpoint_name}-cfg-"):
                try:
                    sm.delete_endpoint_config(EndpointConfigName=name)
                    deleted += 1
                except ClientError:
                    pass
    print(f"Deleted endpoint configs: {deleted}")


def safe_delete_models(sm, endpoint_name: str) -> None:
    paginator = sm.get_paginator("list_models")
    deleted = 0
    for page in paginator.paginate(SortBy="CreationTime", SortOrder="Descending"):
        for summary in page.get("Models", []):
            name = summary.get("ModelName", "")
            if name.startswith(f"{endpoint_name}-model-"):
                try:
                    sm.delete_model(ModelName=name)
                    deleted += 1
                except ClientError:
                    pass
    print(f"Deleted models: {deleted}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete SageMaker endpoint and optional resources")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--endpoint-name", required=True)
    parser.add_argument("--delete-config-and-models", action="store_true")
    args = parser.parse_args()

    sm = boto3.client("sagemaker", region_name=args.region)
    safe_delete_endpoint(sm, args.endpoint_name)

    if args.delete_config_and_models:
        safe_delete_endpoint_config(sm, args.endpoint_name)
        safe_delete_models(sm, args.endpoint_name)


if __name__ == "__main__":
    main()
