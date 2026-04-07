import argparse
import base64
import json
from pathlib import Path
import time

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


def payload_for(service: str, audio_file: str | None) -> dict:
    if service == "colqwen":
        return {"operation": "embed-query", "query": "What is multimodal retrieval?"}

    if service == "docling":
        sample = "# Sample\n\nThis is a SageMaker Docling smoke test.\n"
        return {
            "operation": "process-document",
            "filename": "smoke.md",
            "content_base64": base64.b64encode(sample.encode("utf-8")).decode("ascii"),
        }

    if service == "whisper":
        if not audio_file:
            return {"operation": "health"}
        data = Path(audio_file).read_bytes()
        return {
            "operation": "transcribe-audio",
            "filename": Path(audio_file).name,
            "audio_base64": base64.b64encode(data).decode("ascii"),
        }

    raise ValueError(f"Unsupported service: {service}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test a SageMaker endpoint")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--endpoint-name", required=True)
    parser.add_argument("--service", choices=["colqwen", "docling", "whisper"], required=True)
    parser.add_argument("--audio-file", default=None, help="Required to test whisper transcription operation")
    args = parser.parse_args()

    runtime = boto3.client("sagemaker-runtime", region_name=args.region)
    payload = payload_for(args.service, args.audio_file)
    result = invoke(runtime, args.endpoint_name, payload)

    print(f"HTTP status: {result['status']}")
    print(f"Latency ms: {result['elapsed_ms']:.1f}")
    print(json.dumps(result["body"], indent=2)[:3000])

    if result["status"] != 200:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
