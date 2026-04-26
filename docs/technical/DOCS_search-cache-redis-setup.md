# Search Cache Setup (Redis / ElastiCache)

This project now caches retrieval contents (`text_results` and `image_results`) used by the shared search orchestrator. It does not cache full `/api/search` response payloads.

## Environment Variables

Set these in `Phase_2_FE_AI_Merge/backend/.env` (or deployment env vars):

```dotenv
SEARCH_CACHE_ENABLED=true
SEARCH_CACHE_BACKEND=redis
SEARCH_CACHE_TTL_SECONDS=600
SEARCH_CACHE_REDIS_URL=redis://localhost:6379/0
SEARCH_CACHE_REDIS_CONNECT_TIMEOUT_SECONDS=2
SEARCH_CACHE_REDIS_READ_TIMEOUT_SECONDS=2
SEARCH_CACHE_KEY_PREFIX=phase2:search:v1
```

Notes:
- `SEARCH_CACHE_TTL_SECONDS=600` gives 10-minute cache.
- Retrieval cache key includes `namespace=retrieval`, `user_id`, and retrieval-driving request fields.
- If Redis is unavailable, search still works (cache fails open).

## Local Docker Test (Redis)

Run Redis locally:

```powershell
docker run --name phase2-redis -p 6379:6379 -d redis:7-alpine
```

Backend values for local test:

```dotenv
SEARCH_CACHE_ENABLED=true
SEARCH_CACHE_BACKEND=redis
SEARCH_CACHE_TTL_SECONDS=600
SEARCH_CACHE_REDIS_URL=redis://localhost:6379/0
```

Quick verification flow:
1. Restart backend after env changes.
2. Call same `/api/search` request twice.
3. Backend logs should show retrieval cache behavior:
   - `Search cache miss: namespace=retrieval ...` on first call
   - `Search cache hit: namespace=retrieval ...` on subsequent identical call

Inspect Redis keys:

```powershell
docker exec -it phase2-redis redis-cli KEYS "phase2:search:v1:*"
```

## Docker Compose Style (optional)

If backend and Redis are in the same compose network:

- Use this Redis URL in backend container:

```dotenv
SEARCH_CACHE_REDIS_URL=redis://redis:6379/0
```

(Where `redis` is the service name.)

## AWS ElastiCache (Redis) for Deployment

If you deploy via `Phase_2_FE_AI_Merge/terraform`, the recommended path is to let Terraform create and wire ElastiCache Serverless automatically (`enable_search_cache_serverless=true`).

Terraform wiring now manages:
- ElastiCache Serverless cache + cache security group
- Ingress rule from ECS task SG to cache SG on TCP 6379
- Backend ECS env vars (`SEARCH_CACHE_*`), including computed `SEARCH_CACHE_REDIS_URL`

Use Redis endpoint from ElastiCache in `SEARCH_CACHE_REDIS_URL`:

```dotenv
SEARCH_CACHE_ENABLED=true
SEARCH_CACHE_BACKEND=redis
SEARCH_CACHE_TTL_SECONDS=600
SEARCH_CACHE_REDIS_URL=redis://<elasticache-primary-endpoint>:6379/0
SEARCH_CACHE_REDIS_CONNECT_TIMEOUT_SECONDS=2
SEARCH_CACHE_REDIS_READ_TIMEOUT_SECONDS=2
```

For ElastiCache Serverless with TLS enabled, prefer:

```dotenv
SEARCH_CACHE_REDIS_URL=rediss://<elasticache-serverless-endpoint>:6379/0
```

Recommended deployment notes:
- Put backend service and ElastiCache in same VPC/subnets/security groups.
- Allow backend SG egress to Redis port 6379 and ElastiCache SG ingress from backend SG.
- If using TLS-enabled Redis, use `rediss://...` endpoint URL.

## Disable Cache

```dotenv
SEARCH_CACHE_ENABLED=false
```

No code change needed; cache is bypassed.
