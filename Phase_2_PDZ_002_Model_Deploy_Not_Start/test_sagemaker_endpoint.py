import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3  # type: ignore[import-not-found]


def invoke(runtime, endpoint_name: str, payload: dict) -> dict:
    started = time.perf_counter()
    response = runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="application/json",
        Body=json.dumps(payload).encode("utf-8"),
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    body = response["Body"].read().decode("utf-8")
    return {
        "status": response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0),
        "elapsed_ms": elapsed_ms,
        "body": json.loads(body),
    }


def test_single(runtime, endpoint_name: str) -> None:
    payload = {
        "operation": "embed-query",
        "query": "What is multimodal retrieval?",
    }
    result = invoke(runtime, endpoint_name, payload)
    if result["status"] != 200:
        raise RuntimeError(f"Single invoke failed: {result}")
    print(f"Single invoke latency: {result['elapsed_ms']:.1f} ms")


def test_concurrent(runtime, endpoint_name: str, users: int) -> None:
    print(f"Running concurrent invoke test with {users} users")
    payloads = [
        {
            "operation": "embed-query",
            "query": f"Concurrent request {idx + 1}",
        }
        for idx in range(users)
    ]

    latencies = []
    with ThreadPoolExecutor(max_workers=users) as executor:
        futures = [executor.submit(invoke, runtime, endpoint_name, payload) for payload in payloads]
        for future in as_completed(futures):
            result = future.result()
            if result["status"] != 200:
                raise RuntimeError(f"Concurrent invoke failed: {result}")
            latencies.append(result["elapsed_ms"])

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)]
    print(f"Concurrent latency p50: {p50:.1f} ms")
    print(f"Concurrent latency p95: {p95:.1f} ms")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test SageMaker ColQwen endpoint")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--endpoint-name", default="phase2-colqwen-rt")
    parser.add_argument("--concurrent-users", type=int, default=5)
    args = parser.parse_args()

    runtime = boto3.client("sagemaker-runtime", region_name=args.region)

    print(f"Testing endpoint: {args.endpoint_name}")
    test_single(runtime, args.endpoint_name)

    if args.concurrent_users > 1:
        test_concurrent(runtime, args.endpoint_name, args.concurrent_users)

    print("SageMaker endpoint tests passed")


if __name__ == "__main__":
    main()
