# Redis + Async Job System and Optimization Guide (Merged)

## Purpose

Single merged reference for:
- Redis/Docker setup
- Async job architecture and operations
- Optimization implementation summary and results

---

## Quick Start

```bash
cd Phase_2_FE_AI_Merge/backend
docker-compose up -d
docker-compose ps
docker exec bk_mind_redis redis-cli ping
# Expected: PONG
```

Start backend:

```bash
python run_api.py
```

---

## Async Job Model

### Flow

1. Client calls `POST /api/index`
2. Backend creates Redis job and returns `202` + `job_id`
3. Background task executes indexing
4. Client polls `GET /api/index/status/{job_id}`
5. Job ends in `completed` or `failed`

### Redis keys

- `phase2:index:job:{job_id}` (hash)
- `phase2:index:active:{user_id}` (set)
- `phase2:index:global_active` (set)

### Job states

- `accepted`
- `running`
- `completed`
- `failed`

---

## API Endpoints

- `POST /api/index`
- `POST /api/index/text`
- `POST /api/index/image`
- `POST /api/process`
- `GET /api/index/status/{job_id}`

### API contract (async default)

Create job response:

```json
{
  "status": "accepted",
  "job_id": "uuid",
  "message": "Indexing started. Poll /api/index/status/{job_id}"
}
```

Status response contains:
- current `status`
- `progress` while running
- `result` on completion
- `error` on failure

---

## Optimization Summary

Status: complete.

### Implemented changes

1. Redis-backed async job lifecycle and concurrency control
2. Pipeline routes return immediate `202` with polling-based status
3. S3 downloads parallelized
4. ColQwen image embedding batched
5. Higher image flush threshold before inference
6. Larger Qdrant write batch sizes

### Modified files

- `app/services/indexing_job_service.py`
- `app/api/routes/pipeline_routes.py`
- `app/services/indexing_service.py`
- `app/services/colqwen_inference.py`
- `app/repositories/text_index_repository.py`
- `app/repositories/image_index_repository.py`
- `tests/services/test_indexing_job_service.py`

### Performance highlights

- End-to-end: ~90s -> ~25s (~3.6x faster)
- S3 stage: ~3.3x faster
- ColQwen stage: ~7.5x faster
- Qdrant upsert stage: ~1.7x faster
- Throughput improved through non-blocking async flow

---

## Current Issues and Recommended Fixes

### Issues

1. Redis dependency can be unclear if container is not running
2. Async limits may remain hardcoded if config is not fully wired
3. Redis outage can appear as misleading `429`
4. Missing fallback path can hard-fail job creation

### Fixes

1. Add `async_indexing` config in `backend/config/default.yaml`
2. Make `IndexingJobService` read config for limits/TTL/enable flag
3. Return `503` for Redis unavailability (unless fallback enabled)
4. Optionally support fallback-to-blocking mode

Suggested config:

```yaml
async_indexing:
  enabled: true
  max_concurrent_per_user: 3
  max_concurrent_global: 20
  job_ttl_seconds: 3600
  redis_url: redis://localhost:6379/0
  fallback_to_blocking: false
```

---

## Operations and Troubleshooting

### Useful commands

```bash
docker-compose ps
docker-compose logs -f redis
docker-compose stop
docker-compose start
docker-compose down
docker-compose down -v
```

Inspect Redis:

```bash
docker exec -it bk_mind_redis redis-cli
PING
KEYS phase2:*
SMEMBERS phase2:index:global_active
HGETALL phase2:index:job:{job_id}
INFO memory
```

### Common issues

- Port conflict on `6379`: free the port or remap host port
- Connection refused: check `docker-compose ps` and Redis logs
- Too many jobs: verify user active set count
- Job not found: wrong `job_id` or TTL expiry

---

## Minimal Validation

```bash
curl -X POST http://localhost:5000/api/index -H "X-User-Id: test_user" -H "Content-Type: application/json"
curl http://localhost:5000/api/index/status/{job_id} -H "X-User-Id: test_user"
```

Expected: accepted response first, then progress, then terminal status.
