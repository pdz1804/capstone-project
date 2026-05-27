# Terraform: ECS + ALB + SageMaker (Phase 2 FE / AI merge)

Parent overview of this repo folder: [`../README.md`](../README.md).

This directory defines AWS infrastructure aligned with **`Phase_2_FE_AI_Merge`**: ECR repos, IAM for ECS tasks, an Application Load Balancer (optional **HTTPS** via ACM), Fargate services with auto scaling, DynamoDB chat history tables, and an optional **SageMaker real-time endpoint** for the unified multimodal image (`sagemaker/unified`). Build and push the container separately; see `../sagemaker/README.md`.

---

## What gets created (high level)

| Area | Resources |
|------|-----------|
| ECR | Backend, frontend, and (if enabled) unified SageMaker image repository |
| IAM | ECS task execution + task roles; backend task role can invoke the SageMaker endpoint when enabled |
| ALB | HTTP `:80`; HTTPS `:443` when `acm_certificate_arn` is set (HTTP then **301** redirects to HTTPS) |
| ECS | Fargate cluster, backend + frontend services, CloudWatch log groups |
| ElastiCache | Optional serverless cache (Redis/Valkey) + dedicated SG, wired to backend via env vars |
| Auto Scaling | ECS service scaling (CPU, memory, ALB request count) |
| SageMaker | Optional: execution role, model, endpoint config + endpoint, Application Auto Scaling on the variant |
| DynamoDB | Optional `chatbot-session` and `chatbot-messages` tables for persistent chat history |
| AgentCore prep | Optional ECR repository for packaging Bedrock AgentCore runtime container |

---

## Prerequisites

- [Terraform](https://www.terraform.io/downloads) `>= 1.0`
- [AWS CLI](https://aws.amazon.com/cli/) (only if you later run `plan`/`apply` against a real/sandbox account)

---

## Configuration

Copy the example variables file and edit values (do not commit secrets or real `terraform.tfvars` if your repo is public).

```powershell
cd "D:\PDZ\BKU\Learning\LVTN\GD1\Code\Phase_2_FE_AI_Merge\terraform"
Copy-Item terraform.tfvars.example terraform.tfvars
```

Important variables:

- **`acm_certificate_arn`**   ACM certificate in the **same region as the ALB**. Empty string = HTTP only on `:80`.
- **`enable_sagemaker_endpoint`**   `false` if you only want ECS/ALB and will manage SageMaker elsewhere.
- **`sagemaker_image_tag`**   Tag you pushed to the unified ECR repo (endpoint creation expects the image to exist).
- **`enable_chatbot_history_tables`**   `true` creates DynamoDB chat tables using defaults:
	- sessions table: `chatbot-session` (PK=`user_id`, SK=`session_id`)
	- messages table: `chatbot-messages` (PK=`session_id`, SK=`message_id`)
- **`enable_agentcore_runtime_prep`**   `true` creates an ECR repository for the future AgentCore runtime image.
- **`enable_search_cache_serverless`**   `true` creates ElastiCache Serverless and injects `SEARCH_CACHE_*` env vars into backend ECS task definition.
- **`search_cache_use_tls`**   when `true`, backend gets `SEARCH_CACHE_REDIS_URL=rediss://...`.
- **`search_cache_subnet_ids`**   optional explicit subnets for serverless cache endpoint placement.

---

## Safe local testing (no changes to AWS)

These commands **do not** create, update, or destroy cloud resources. They only format/check configuration and validate syntax.

From this `terraform` directory:

```powershell
# 1) Install providers modules (writes .terraform/ locally; no AWS API required for provider download)
terraform init -backend=false

# 2) Consistent formatting (optional but recommended)
terraform fmt -recursive

# 3) Fail CI-style if format would change anything
terraform fmt -recursive -check

# 4) Validate configuration (syntax + provider schema); uses init output only
terraform validate
```

**Notes:**

- Use **`-backend=false`** while you are not using a remote S3 backend so state stays local and you do not need bucket credentials for init.
- **`terraform validate`** does **not** call the AWS APIs.

---

## `plan` and `apply` (read this before you run them)

- **`terraform plan`** still **calls AWS** (for example default VPC, subnets, caller identity data sources). It does not apply changes, but it needs valid credentials and will read your account. **Do not run it against production until you intend to.**
- **`terraform apply`** creates and bills real resources. **Do not run `apply` for now** unless you are deliberately using a dedicated sandbox account and accept cost and side effects.

If you later use a sandbox:

```powershell
terraform init
terraform plan -out=tfplan
# Review the plan file, then only if intentional:
# terraform apply tfplan
```

---

## ECS to ElastiCache wiring (managed)

When `enable_search_cache_serverless=true`, Terraform now manages:

- Dedicated cache SG (`{project_name}-cache-sg`)
- ElastiCache Serverless cache (`{project_name}-cache` by default)
- Ingress rule allowing ECS task SG to connect on TCP `6379`
- Backend task env vars:
	- `SEARCH_CACHE_ENABLED=true`
	- `SEARCH_CACHE_BACKEND=redis`
	- `SEARCH_CACHE_REDIS_URL` (built from cache endpoint, `redis://` or `rediss://`)
	- timeout / TTL / retry envs from `search_cache_*` Terraform variables

Useful outputs:

- `search_cache_serverless_name`
- `search_cache_endpoint`
- `search_cache_port`
- `search_cache_security_group_id`
- `backend_search_cache_redis_url`

If you already created the cache manually (for example `rag-pipeline-cache`), import it into Terraform state before apply to avoid duplicate-name errors:

```powershell
terraform import 'aws_elasticache_serverless_cache.search_cache[0]' <existing-cache-name>
```

---

## After a real deploy (reference only)

Align the backend with SageMaker using the outputs / names from your `terraform.tfvars` (see `../sagemaker/README.md` for full env list). Example:

```dotenv
USE_AWS_SAGEMAKER_INFERENCE=true
SAGEMAKER_ENDPOINT_NAME=<output sagemaker_endpoint_name>
AWS_REGION=<same as var.aws_region>
```

---

## Related docs

- `../sagemaker/README.md`   build, push ECR, and endpoint smoke tests
- Repository root `docs/technical/DOCS_deployment-alb-acm-custom-domain.md`   ACM + ALB HTTPS checklist
- Repository root `docs/technical/APPLICATION_OVERVIEW.md`   maintained application overview
- Repository root `docs/testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md`   final performance and scaling report
