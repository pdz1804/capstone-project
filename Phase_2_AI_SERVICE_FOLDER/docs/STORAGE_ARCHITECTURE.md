# AI Service — Cloud-Native Storage Architecture

**Document type:** Architecture specification (planning baseline)  
**Scope:** Phase 2 AI Service as a component of the larger platform  
**Status:** Design reference — implementation may evolve  
**Owner:** System architecture  

---

## 1. Purpose and scope

This document defines how the AI Service stores **user-uploaded originals** and **pipeline-derived artifacts** using **managed cloud object storage**, replacing reliance on container-local or single-host filesystem paths (`backend/input/`, `backend/output/processing/`).

The reference implementation is **Amazon S3** (aligned with existing AWS usage such as SageMaker inference). The **logical model** (two storage planes, key layout, tenancy) applies equally to other object stores (e.g. Azure Blob Storage, Google Cloud Storage) if the platform standardizes elsewhere.

**In scope:** Object storage layout, tenancy, naming, security patterns, operational defaults, testing expectations, alignment with vectors (Qdrant).  
**Out of scope:** Concrete Terraform/CDK modules, exact IAM policy JSON, application code changes (tracked in implementation tasks).

---

## 2. Context and current baseline

Today the service:

- Accepts uploads via `POST /api/upload` and persists files under a configurable **input directory** (default: `backend/input/`).
- Runs the document pipeline with output rooted at **processing output** (default: `backend/output/processing/`), including staged artifacts and RAG-ready exports.
- Lists and deletes files using **local filesystem** paths exposed through the API.

**Constraint for cloud migration:** APIs and internal services should converge on **stable identifiers** (bucket + object key, or URI), not host-specific paths. A **storage abstraction** (local vs cloud) is recommended so development and CI can remain fast without binding tests to AWS.

---

## 3. Architectural principles

| Principle | Implication |
|-----------|-------------|
| **Separation of concerns** | Originals (immutable user intent) and processed outputs (derived, regenerable) live in **distinct logical planes** — typically two buckets or two isolated namespaces. |
| **Multi-tenancy by design** | Every object key is rooted by **tenant identity** (`user_id` or platform `subject`); no shared flat namespace for user content. |
| **Idempotent processing** | Re-runs and force-rebuilds are modeled with a **job** or **run** identifier so outputs do not silently overwrite without traceability. |
| **Least privilege** | Runtime credentials grant access only to the AI service buckets; **authorization** (which prefix a caller may use) is enforced in the application or API gateway. |
| **Portability** | Prefer **provider-agnostic** concepts: bucket/container, key/blob name, server-side encryption, lifecycle rules — map to S3, Blob, or GCS per environment. |

---

## 4. Logical storage topology

### 4.1 Storage planes

| Plane | Purpose | Typical retention | Versioning |
|-------|---------|-------------------|------------|
| **Originals** | User uploads as received (PDF, Office, media). Source of truth for compliance and reprocessing. | Longer; governed by product policy | Recommended **on** |
| **Processed** | Normalized markdown, stage outputs, RAG-ready trees, sidecar JSON, intermediate exports used by indexing. | Shorter or tiered; regenerable from originals | Optional; often **off** + lifecycle |

### 4.2 Resource inventory (AWS reference)

| # | Resource | Notes |
|---|----------|--------|
| 1 | **Originals bucket** | Private; no public ACLs; Block Public Access enabled. |
| 2 | **Processed bucket** | Same baseline security as originals. |
| — | **KMS CMK** (optional) | Use when organizational policy requires customer-managed keys; otherwise default SSE (e.g. SSE-S3) is acceptable for many workloads. |
| — | **S3 Event Notifications** (optional) | Drive asynchronous pipelines (e.g. Step Functions, Lambda) on `PutObject` to originals. |

**Rule of thumb:** Two buckets suffice. Introduce a **third** bucket only for a clearly different trust boundary or lifecycle (e.g. public derivatives, quarantine/staging scan, or short-lived scratch with aggressive expiration).

---

## 5. Naming convention

Buckets are globally unique in AWS. Recommended pattern:

```text
{organization}-{service}-originals-{environment}
{organization}-{service}-processed-{environment}
```

**Example:**

- `bkulvtn-ai-service-originals-dev`
- `bkulvtn-ai-service-processed-prod`

Use the same **service slug** across the wider platform so operations and cost allocation can tag resources consistently (`Service=ai-service`, `Environment=dev|staging|prod`).

---

## 6. Object key layout and identifiers

### 6.1 Identifiers

| ID | Role |
|----|------|
| `user_id` | Platform identity for the end user (or organization sub-tenant if the main app uses org hierarchy — align with the primary product’s IAM model). |
| `document_id` | Stable logical document (UUID). One document may map to one or more original objects if you support multi-file bundles later. |
| `job_id` | Single processing run (UUID). Enables safe retries, force rebuilds, and audit without clobbering prior outputs. |
| `version` (optional) | Original object version when using S3 versioning or explicit version segments in the key. |

### 6.2 Originals bucket — key pattern

```text
users/{user_id}/documents/{document_id}/v{version}/{sanitized_filename}
```

Collisions on filename are resolved by `document_id` / version, not by ad hoc suffixes on a flat folder.

### 6.3 Processed bucket — key pattern

Mirror the document and bind outputs to a job:

```text
users/{user_id}/documents/{document_id}/jobs/{job_id}/processing/{stage_path...}
```

Where `{stage_path...}` preserves the existing conceptual stages (e.g. `stage3_document_processed/`, `stage4_rag_ready/`) for minimal behavioral change when porting the pipeline.

### 6.4 Development without full auth

Use a configuration-driven default until the gateway forwards real identities:

```text
DEFAULT_USER_ID=dev-local-user
```

(or a fixed UUID). This must **not** be enabled in production; it is a development convenience only.

---

## 7. Security and compliance

- **Encryption at rest:** Enable default bucket encryption (SSE-S3 or SSE-KMS per policy).
- **Encryption in transit:** TLS for all API and SDK usage.
- **Public access:** Block all public access at bucket level.
- **IAM:** Grant the AI service task/workload role `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket` scoped to the two bucket ARNs; restrict `ListBucket` with prefix conditions if policy complexity is acceptable.
- **Application-level authorization:** Validate that the authenticated `user_id` matches the key prefix for every read/write/delete; do not expose raw bucket listing across tenants.
- **Presigned URLs (optional):** For large uploads/downloads, issue short-lived presigned URLs so bytes do not traverse the API container; metadata registration remains in the AI Service API.

---

## 8. Integration with the wider system

| Component | Integration note |
|-----------|------------------|
| **Main application / BFF** | Supplies `user_id` (and optionally `document_id`) via trusted header or token claims; AI Service does not trust client-supplied IDs without verification. |
| **Qdrant** | Store `user_id` and `document_id` in **point payload** (or enforce collection-per-tenant if required). Enables consistent **right to delete** and query scoping. |
| **Observability** | Log `document_id`, `job_id`, and key prefix — not full bucket URLs with secrets in query strings. |
| **Cost and lifecycle** | Apply lifecycle rules on the **processed** bucket (transition to IA / expire old `jobs/*`) per product retention. |

---

## 9. API and data contract evolution

Current responses expose **local filesystem paths**. Target contract:

- References are **opaque storage references** (e.g. `s3://bucket/key` or structured `{ "bucket", "key" }`) or **presigned URLs** for time-bound access.
- **List** endpoints paginate (`ListObjectsV2` continuation tokens) instead of scanning directories.

Document these changes in `docs/API_SCHEMA.md` when implemented.

---

## 10. Testing strategy (implementation phase)

| Layer | Approach |
|-------|----------|
| **Unit** | Pure functions for key construction, path normalization, and tenancy validation — no network. |
| **Integration** | `moto` (AWS) or equivalent emulator for S3-compatible tests; inject bucket names from environment. |
| **Contract** | Tests for each route that changes from `path` to storage reference or presigned response shape. |

---

## 11. Migration and rollout (high level)

1. Introduce configuration for **storage backend** (`local` | `s3`) and bucket names.
2. Implement storage adapter behind upload, list, delete, and pipeline I/O.
3. Run dual-write or batch migration for any existing local data if required.
4. Cut over API contracts and remove dependency on local paths in production deployments.

---

## 12. Summary

- **Two logical planes** (originals + processed), **two buckets** in the AWS reference design.  
- **Keys** are always rooted at `users/{user_id}/...` with **`document_id`** and **`job_id`** for processed outputs.  
- **Security** combines bucket defaults, scoped IAM, and **application-level** tenant checks.  
- **S3** is the reference implementation; the same design maps to other cloud object stores by renaming bucket/container and SDK calls.

---

## 13. References (in-repo)

- Path constants and env merge: `backend/app/core/paths.py`
- Upload and file listing: `backend/app/api/routes/files_routes.py`
- Pipeline entry: `backend/app/services/processing_service.py`
- API overview: `docs/API_SCHEMA.md`
- Environment variables: `docs/ENVIRONMENT.md`
