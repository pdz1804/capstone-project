# Technical Documentation

This folder contains maintained technical documentation for BK-MInD. It is intended for developers, reviewers, technical leads, and future maintainers.

## Documents

| Document | Purpose |
|---|---|
| [`APPLICATION_OVERVIEW.md`](APPLICATION_OVERVIEW.md) | Product scope, feature overview, system capabilities, architecture summary, and operational qualities |
| [`API_REFERENCE.md`](API_REFERENCE.md) | API reference grouped by authentication, files, processing, search, chat, insights, feedback, and history |
| [`DOCS_deployment-alb-acm-custom-domain.md`](DOCS_deployment-alb-acm-custom-domain.md) | ALB, ACM, HTTPS, DNS, and custom-domain deployment notes |
| [`DOCS_search-cache-redis-setup.md`](DOCS_search-cache-redis-setup.md) | Redis/ElastiCache search-cache setup and runtime behavior |
| [`DOCS_REDIS_ASYNC_JOB_SYSTEM_GUIDE.md`](DOCS_REDIS_ASYNC_JOB_SYSTEM_GUIDE.md) | Redis-backed async job system guidance |
| [`DOCS_create-endpoint-script.md`](DOCS_create-endpoint-script.md) | Endpoint creation/deployment helper script notes |
| [`13-04-firewall-guidelines.md`](13-04-firewall-guidelines.md) | Firewall and access-control guidelines |
| [`14-04-2026-backend-analysis.md`](14-04-2026-backend-analysis.md) | Backend analysis notes and technical review material |

## Related References

| Location | Description |
|---|---|
| [`../../Phase_2_FE_AI_Merge/README.md`](../../Phase_2_FE_AI_Merge/README.md) | Application folder map and local run guidance |
| [`../../Phase_2_FE_AI_Merge/backend/README.md`](../../Phase_2_FE_AI_Merge/backend/README.md) | Backend implementation notes and API details |
| [`../../Phase_2_FE_AI_Merge/terraform/README.md`](../../Phase_2_FE_AI_Merge/terraform/README.md) | AWS infrastructure, ALB, ECS, ECR, Terraform, and deployment notes |
| [`../testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md`](../testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md) | Final performance test evidence and scaling analysis |

## Maintenance Guidelines

- Keep this folder focused on stable, review-ready documentation.
- Avoid storing raw experiment outputs here.
- When implementation changes alter user-visible behavior or API contracts, update the relevant document in the same change set.
