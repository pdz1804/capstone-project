#!/bin/bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-west-2}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
REPO_NAME="${REPO_NAME:-phase2-multimodal-unified}"
IMAGE_TAG="${IMAGE_TAG:-v1}"
IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}"

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker daemon is not running. Start Docker Desktop / dockerd first." >&2
  exit 1
fi

aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name "${REPO_NAME}" --region "${AWS_REGION}" >/dev/null

aws ecr get-login-password --region "${AWS_REGION}" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker build -f "Phase_2_FE_AI_Merge/sagemaker/unified/Dockerfile" -t "${REPO_NAME}:${IMAGE_TAG}" .
docker tag "${REPO_NAME}:${IMAGE_TAG}" "${IMAGE_URI}"
docker push "${IMAGE_URI}"

echo "Pushed image: ${IMAGE_URI}"
