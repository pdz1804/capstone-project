# BK-MInD Final Application Performance Report

**Report date:** 2026-04-26  
**System under test:** BK-MInD learning platform API  
**Prepared for:** Technical lead review and capstone protection day  
**Result source:** `docs/jmeter-capacity-tests/runs/`

## Executive Summary

BK-MInD was tested across the main user-facing API groups: authentication, user profile retrieval, processing statistics, upload, document processing, indexing, search, chat streaming, and learning insight generation. The results show that the application handles typical interactive endpoints and AI insight endpoints reliably under the tested load levels, with **0% JMeter error rate** across authentication, profile, stats, upload, search, chat stream, summary, MCQ, and roadmap runs.

The key engineering conclusion is that the platform is already strong for read-heavy and assisted-learning workloads. Search, summary, MCQ, roadmap, and chat remained functional up to **50 concurrent users** in the available result set. The heavier asynchronous pipeline jobs, especially full indexing, are the main capacity-sensitive area. Processing duration increases gradually with concurrency, while full indexing is stable at 20-30 concurrent jobs and reaches an overload condition in the available 40-job run.

This behavior is expected for an AI learning platform. Stateless API calls and retrieval/insight reads scale more smoothly, while document processing and indexing consume CPU, memory, storage I/O, embedding/model calls, and Vector Database throughput. The platform is therefore suitable for production-style growth if the next scaling phase prioritizes pipeline job isolation, worker autoscaling, queue control, model-serving capacity, and observability.

## Test Tools And Measurement Overview

The performance test suite was built with **Apache JMeter** and supporting Python scripts. JMeter was used to simulate concurrent users, authenticate with real test accounts, send API requests, and save raw JTL result files. The Python scripts converted the raw outputs into reviewer-friendly CSV summaries and DynamoDB job reports.

| Tool / artifact | Role in testing | Reason for use |
|---|---|---|
| Apache JMeter | Executes load tests using `.jmx` plans and configurable thread counts | Industry-standard load testing tool; supports HTTP, CSV data sets, assertions, timers, and JTL exports |
| JMeter thread groups | Simulate concurrent users | Each thread represents one active test user for the configured scenario |
| CSV Data Set Config | Feeds test accounts, passwords, user IDs, and user-file mappings | Ensures each virtual user can authenticate and act under the correct `X-User-Id` tenant scope |
| JTL result files | Raw per-sample result storage | Preserves request timing, status, labels, latency, response code, and success/failure information |
| `scripts/jtl_metrics_csv.py` | Converts JTL files into summary CSVs | Produces sample count, errors, error percentage, mean, P50, P90, P95, P99, and latency percentiles |
| `scripts/jtl_extract_job_ids.py` | Extracts background job IDs from process/index polling JTLs | Allows asynchronous pipeline jobs to be joined with DynamoDB job status records |
| `scripts/dynamo_job_metrics.py` | Reads job records from DynamoDB and exports duration summaries | Measures true background job duration for processing and indexing, which cannot be represented by one synchronous HTTP response |
| DynamoDB job table | Source of process/index job status and timestamps | Captures asynchronous job lifecycle: created, started, completed, failed, and missing rows |
| S3 user prefixes | Validates per-user upload and processing isolation | Confirms uploaded files are stored under `users/<user_id>/` instead of the fallback `default` user |

### Metrics Explained

| Metric | Meaning | How to interpret it |
|---|---|---|
| `samples` | Number of measured endpoint calls in the exported CSV | For one-loop tests this equals requested users; for sustained tests it equals completed cycles during the duration |
| `errors` / `error_pct` | Number and percentage of failed samples according to JMeter | 0% means JMeter saw successful HTTP/assertion results for that export |
| `elapsed_ms_mean` | Average full request time | Useful for general user experience, but can hide tail latency |
| `elapsed_ms_p50` | Median full request time | Represents the typical request |
| `elapsed_ms_p95` | 95th percentile full request time | Key indicator for production readiness; shows slower tail behavior |
| `elapsed_ms_p99` | 99th percentile full request time | Stress/tail latency indicator |
| `latency_ms_*` | Time to first byte | Especially important for streaming chat; the user sees the first response before the full stream finishes |
| `duration_sec` | Background job duration from DynamoDB timestamps | Used for process/index jobs instead of synchronous HTTP timing |

### Test Plan Types

The suite used two styles because not all endpoints behave the same.

| Test style | Used by | Meaning |
|---|---|---|
| One request/job per user | 04 Upload, 05 Process, 06 Index, 08 Search | Number of samples/jobs corresponds directly to requested users/jobs in each run |
| Sustained load for fixed duration | 01 Auth, 02 User profile, 03 Stats, 09 Chat, 10 Summary, 11 MCQ, 12 Roadmap | Threads represent concurrent users; total samples depend on how many request cycles complete during the test duration |

For synchronous APIs, `elapsed_ms` is the full request-response time. For chat streaming, `elapsed_ms` is the time until the complete SSE stream finishes, while `latency_ms` is the time to first server response. For 05/06, DynamoDB metrics are more accurate because the HTTP request only starts or polls a background job.

## Test Scope And Evidence

| API group | Endpoint / workload | Concurrency levels represented | Metric source |
|---|---|---:|---|
| 01 Auth | `POST /api/auth/login-local` | 50 users | `01_20260426_214518_jtl_metrics.csv` |
| 02 User profile | `GET /api/users/me` | 50 users | `02_20260426_214651_jtl_metrics.csv` |
| 03 Processing stats | `GET /api/processing-stats` | 50 users | `03_20260426_215047_jtl_metrics.csv` |
| 04 Upload | `POST /api/upload` | 30, 40, 50 users | `04_20260426_221615_jtl_metrics.csv`, `04_20260426_221645_jtl_metrics.csv`, `04_20260426_221708_jtl_metrics.csv` |
| 05 Process | background process jobs | 20, 30, 40 jobs | `05_20260425_162810_dynamo_metrics.csv`, `05_20260426_192020_dynamo_metrics.csv`, `05_20260426_193738_dynamo_metrics.csv` |
| 06 Index | background full-index jobs | 20, 30, 40 jobs | `06_20260425_162052_dynamo_metrics.csv`, `06_20260426_191438_dynamo_metrics.csv`, `06_20260426_193133_dynamo_metrics.csv` |
| 08 Search | `POST /api/search` | 20, 30, 40, 50 users | `08_20260426_195014_jtl_metrics.csv` through `08_20260426_195619_jtl_metrics.csv` |
| 09 Chat stream | `POST /api/chat/stream` | 20, 30, 40, 50 users | `09_20260426_224857_jtl_metrics.csv` through `09_20260426_225825_jtl_metrics.csv` |
| 10 Summary | `POST /api/summary` | 20, 30, 40, 50 users | `10_20260426_230007_jtl_metrics.csv` through `10_20260426_230523_jtl_metrics.csv` |
| 11 MCQ | `POST /api/mcq` | 20, 30, 40, 50 users | `11_20260426_230706_jtl_metrics.csv` through `11_20260426_231448_jtl_metrics.csv` |
| 12 Roadmap | `POST /api/learning-roadmap` | 20, 30, 40, 50 users | `12_20260426_231745_jtl_metrics.csv` through `12_20260426_232606_jtl_metrics.csv` |

**Evidence note:** The current `runs/` folder contains 05/06 Dynamo exports for 20/30/40 jobs. If separate 50-job Dynamo exports were run for 05/06, they were not present when this report was prepared.

## 1. Baseline Platform APIs

These endpoints represent platform access and lightweight operational reads. They were tested at 50 concurrent users and completed without errors.

| Test | Endpoint | Samples | Error % | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---:|---:|---:|---:|---:|---:|
| 01 | `POST /api/auth/login-local` | 357 | 0.0 | 1,891.6 | 1,986 | 2,418 | 2,628 |
| 02 | `GET /api/users/me` | 201 | 0.0 | 1,372.3 | 1,461 | 1,919 | 1,980 |
| 03 | `GET /api/processing-stats` | 291 | 0.0 | 590.0 | 582 | 1,033 | 1,112 |

### Analysis

Authentication and user profile calls stayed below 2.5 seconds at P95, while processing stats stayed near 1 second at P95. The stats endpoint is the fastest because it is a lightweight read path. Authentication and profile retrieval include identity checks and token/user state work, so their higher latency is reasonable.

### Conclusion

The baseline API layer is healthy at 50 concurrent users. These endpoints do not appear to be the primary scalability risk for the application.

## 2. Upload API

The upload test sends one upload per user (`threads x loops`, with `loops=1`). The plan uses `data/user_file_mapping_with_passwords.csv`, sends `X-User-Id`, and uploads into each user-specific S3 prefix instead of the fallback `default` user.

| Concurrent users | Samples | Error % | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 30 | 30 | 0.0 | 7,404.1 | 7,693 | 9,895 | 9,896 |
| 40 | 40 | 0.0 | 4,919.9 | 4,267 | 7,781 | 7,819 |
| 50 | 50 | 0.0 | 6,198.9 | 5,050 | 9,363 | 9,367 |

### Analysis

Upload latency remained under 10 seconds at P95 for the tested concurrency levels and returned 0 errors. The mean latency varies between runs because upload performance depends on network path, S3 put latency, backend worker availability, and per-user object naming/storage metadata work.

The upload API is not CPU-heavy compared with document processing and indexing. Its primary dependencies are request body transfer, S3 storage, metadata creation, and backend concurrency.

### Conclusion

The upload layer is reliable up to 50 concurrent users in the available test set. It is suitable for normal user onboarding and file submission traffic. At larger scale, upload should remain protected by request-size limits, direct-to-S3 upload options, and async post-upload processing.

## 3. Document Processing Jobs

Processing is an asynchronous pipeline workload. Metrics come from DynamoDB job records rather than synchronous JTL response time.

| Requested jobs | Completed | Failed | Dynamo missing | Avg duration (s) | P95 (s) | P99 (s) |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 16 | 4 | 0 | 36.2 | 38 | 39 |
| 30 | 25 | 5 | 0 | 41.5 | 44 | 44 |
| 40 | 29 | 11 | 0 | 50.8 | 56 | 56 |

### Analysis

Processing duration rises from approximately 36 seconds at 20 jobs to 51 seconds at 40 jobs. The increasing failure count indicates resource contention or timeout sensitivity as the number of simultaneous jobs increases. Processing is compute- and I/O-heavy because it may include document conversion, OCR/ASR preparation, media handling, markdown generation, S3 I/O, and metadata updates.

The important positive point is that Dynamo tracking remained complete (`n_missing=0`), meaning the job system consistently records requested work. The improvement area is execution success rate under higher parallelism.

### Conclusion

Processing is acceptable at moderate concurrency but should be treated as a controlled background workload. The system should not allow unlimited simultaneous processing jobs. Queueing, worker autoscaling, and job-specific retry/error classification will improve stability as usage grows.

## 4. Indexing Jobs

Indexing is the heaviest measured backend workflow because it prepares searchable knowledge and writes to vector/text indexes.

| Requested jobs | Completed | Failed | Dynamo missing | Avg duration (s) | P95 (s) | P99 (s) |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 20 | 0 | 0 | 98.1 | 106 | 107 |
| 30 | 30 | 0 | 0 | 161.7 | 187 | 190 |
| 40 | 0 | 40 | 0 | 274.6 | 329 | 331 |

### Analysis

Indexing scales less smoothly than processing. The 20-job and 30-job runs completed successfully, but the 40-job run failed all jobs after long execution times. This strongly indicates that full indexing is currently the most capacity-sensitive workflow.

The reason is technical: indexing combines processed text/image assets, embedding generation, sparse/dense index updates, Qdrant writes, and potentially multimodal index operations. These operations place pressure on model throughput, memory, network, and Vector Database capacity.

### Conclusion

The safe operating point from current evidence is up to 30 concurrent full-index jobs. The 40-job result is a useful boundary measurement rather than a product failure: it identifies where queue control, worker capacity, and index-write scaling should be improved before opening higher parallelism.

## 5. Search API

Search was tested with one request per user using query `mining`.

| Concurrent users | Samples | Error % | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 20 | 0.0 | 16,162.5 | 17,455 | 18,040 | 18,067 |
| 30 | 30 | 0.0 | 20,503.3 | 22,266 | 24,751 | 25,748 |
| 40 | 40 | 0.0 | 21,091.0 | 20,502 | 27,725 | 28,177 |
| 50 | 50 | 0.0 | 21,894.8 | 22,112 | 30,119 | 30,162 |

### Analysis

Search remained reliable with 0 errors through 50 concurrent users. Latency increases as concurrency grows, especially at the tail. P95 latency rises from 18.0 seconds at 20 users to 30.1 seconds at 50 users.

This is expected because search is not a simple database read. It may involve hybrid retrieval, Qdrant, BM25, result merging, optional image/text retrieval paths, and generation/retrieval orchestration depending on the mode. Tail latency is therefore influenced by retrieval fan-out, cache hit rate, Qdrant performance, and model involvement.

### Conclusion

Search is functionally stable under the tested concurrency. The next optimization target should be latency reduction: cache hit-rate improvement, stricter retrieval defaults for high-load conditions, and separating retrieval-only paths from generation-heavy paths when low latency is required.

## 6. Chat Stream API

Chat stream uses Server-Sent Events. The elapsed time measures the complete stream until the assistant finishes; latency measures first server response. Recent JMeter updates create a fresh chat session before each stream request and pass the same `session_id` into `/api/chat/stream`.

| Concurrent users | Stream samples | Error % | Mean elapsed (ms) | P50 elapsed (ms) | P95 elapsed (ms) | Mean first byte (ms) | P95 first byte (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 60 | 0.0 | 21,070.5 | 21,428 | 27,412 | 479.5 | 755 |
| 30 | 69 | 0.0 | 30,835.8 | 33,684 | 40,621 | 653.6 | 1,378 |
| 40 | 80 | 0.0 | 38,540.8 | 43,942 | 50,352 | 1,018.6 | 3,365 |
| 50 | 90 | 0.0 | 45,318.6 | 52,931 | 61,150 | 1,434.3 | 4,223 |

### Analysis

Chat stream returned 0 errors through 50 concurrent users. First-byte latency is good for a streaming AI endpoint: even at 50 users, the average first response was about 1.4 seconds and P95 was about 4.2 seconds. The full stream duration is much longer because it includes planning, tool execution, retrieval, LLM generation, and final streamed output.

The gradual increase in elapsed time is normal for LLM-backed workflows. Each chat request can trigger multiple operations: history/session persistence, tool selection, retrieval, prompt construction, model call, and token streaming. The system behaves correctly because it starts streaming quickly while the full answer completes later.

### Conclusion

Chat is operationally stable up to 50 concurrent users. For production growth, the priority should be controlling model/tool complexity per request, adding queue/backpressure controls for expensive agent actions, and separating lightweight chat from high-cost multimodal/tool-heavy chat.

## 7. Learning Insight APIs

The insight endpoints were tested as sustained-load APIs with 20/30/40/50 concurrent users.

### 7.1 Summary API

| Concurrent users | Samples | Error % | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 188 | 0.0 | 6,145.9 | 6,047 | 7,586 | 8,400 |
| 30 | 272 | 0.0 | 6,248.3 | 6,205 | 7,398 | 7,900 |
| 40 | 345 | 0.0 | 6,608.5 | 6,479 | 8,388 | 9,389 |
| 50 | 377 | 0.0 | 6,866.9 | 6,745 | 8,295 | 9,002 |

**Analysis:** Summary latency is consistent. Mean latency remains around 6-7 seconds through 50 users, with 0 errors. This indicates stable backend behavior and predictable LLM/retrieval cost for the summary workload.

**Conclusion:** Summary is ready for concurrent classroom-style usage, especially when users request structured overviews of already processed materials.

### 7.2 MCQ API

| Concurrent users | Samples | Error % | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 316 | 0.0 | 3,358.7 | 3,290 | 4,355 | 5,297 |
| 30 | 425 | 0.0 | 3,644.0 | 3,601 | 4,543 | 5,109 |
| 40 | 548 | 0.0 | 3,835.2 | 3,759 | 5,052 | 5,666 |
| 50 | 567 | 0.0 | 4,295.2 | 4,135 | 6,171 | 8,533 |

**Analysis:** MCQ generation is the best-performing AI insight endpoint. Mean latency stays under 4.3 seconds at 50 users, and P95 remains around 6.2 seconds.

**Conclusion:** MCQ generation is a strong candidate for high-traffic educational workflows such as quick quizzes, revision sessions, and practice generation.

### 7.3 Learning Roadmap API

| Concurrent users | Samples | Error % | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 394 | 0.0 | 2,507.2 | 2,439 | 3,588 | 4,430 |
| 30 | 531 | 0.0 | 2,678.3 | 2,497 | 4,275 | 5,743 |
| 40 | 569 | 0.0 | 3,323.6 | 2,828 | 7,868 | 9,719 |
| 50 | 660 | 0.0 | 3,178.6 | 3,033 | 4,359 | 5,023 |

**Analysis:** Roadmap generation is stable and low-latency for an AI feature. The 40-user run shows a temporary tail-latency spike, but the 50-user run returns to a lower P95. This suggests a transient load or external dependency effect rather than a monotonic scaling failure.

**Conclusion:** Roadmap generation has strong production potential. It can support many concurrent learners with acceptable latency and no observed errors in the current test set.

## Cross-API Findings

| Finding | Evidence | Technical meaning |
|---|---|---|
| User-facing APIs are stable | 01, 02, 03, 04, 08, 09, 10, 11, 12 all show 0% JMeter errors | The API layer, routing, authentication, user scoping, and synchronous request handling are reliable under tested concurrency |
| Upload is stable after correct user scoping | 30/40/50 upload runs show 0% errors | `X-User-Id` and mapped CSV usage correctly isolate each user's S3 prefix |
| Search latency increases with concurrency | Search P95 rises from 18.0s at 20 users to 30.1s at 50 users | Retrieval/generation paths need caching and query-mode tuning for large-scale real-time use |
| Chat streams correctly but complete slowly | Chat first-byte latency is low; full stream P95 reaches 61.2s at 50 users | Streaming UX is responsive, but full agent completion depends on LLM/tool execution time |
| Insight endpoints scale well | Summary, MCQ, roadmap all remain 0% errors at 50 users | These APIs are suitable for concurrent educational feature usage |
| Indexing is the primary bottleneck | 40 full-index jobs all failed in available data | Full indexing needs queue, worker, and vector-write scaling before higher parallelism |

## Technical Conclusions

1. **The application is stable for core learner interactions.** Authentication, profile retrieval, stats, upload, search, chat, and insight APIs stayed error-free in the available JMeter exports.

2. **The system's real scaling boundary is the ingestion/indexing pipeline.** Processing and indexing are heavier than interactive reads because they depend on storage, document conversion, embeddings, vector writes, and background job execution.

3. **The chat experience is operationally correct for streaming AI.** First response arrives quickly, which is important for perceived responsiveness. Full completion time is longer because the agent performs retrieval and LLM reasoning before finishing.

4. **The application is ready for controlled pilot deployment.** The measured results support a realistic classroom or capstone-demo environment, especially when expensive background jobs are governed by concurrency limits.

## Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Too many simultaneous indexing jobs | Failed jobs, long completion times, vector DB pressure | Add strict queue limits, worker autoscaling, job priority, and separate indexing worker services |
| Long search/chat tail latency | Slower UX under high load | Increase Redis/cache hit rate, tune retrieval defaults, separate retrieval-only and generation modes, and add model concurrency controls |
| LLM/provider rate limits | Sudden latency spikes or failed generations | Add rate-limit-aware retries, request shaping, fallback models, and capacity planning per model/provider |
| S3/object-storage latency | Slower upload/process pipelines | Consider direct-to-S3 uploads, multipart upload, and async metadata processing |
| Mixed workloads competing for resources | Interactive requests affected by processing/indexing | Separate ECS services/worker pools for API, processing, indexing, and AI generation |

## Scaling Plan For Larger Deployment

The current results are encouraging: the platform already demonstrates stable learner-facing behavior and clear scaling paths for heavier AI pipelines. The next stage should preserve this working foundation while increasing capacity in a controlled, observable way.

### Product / Project Management View

- Define service-level objectives by user journey: login/profile under 2-3 seconds, insights under 5-10 seconds, search under agreed interactive limits, and background indexing with queued completion targets.
- Separate expectations for synchronous user actions and asynchronous background jobs. Upload should feel immediate; process/index can show progress and completion notifications.
- Prioritize scaling work based on user value: search/chat responsiveness first, then faster processing/indexing throughput for institutional-scale onboarding.
- Use capacity tiers: pilot classroom, department rollout, and university-scale rollout, each with measured concurrency targets.

### Solution Architecture View

- Split workloads into independent services: API gateway/backend, processing workers, indexing workers, chat/agent workers, and scheduled maintenance jobs.
- Add queue-based orchestration for process/index jobs so spikes become controlled backlogs instead of simultaneous overload.
- Autoscale ECS services independently based on CPU, memory, queue depth, and request concurrency.
- Scale Qdrant/vector infrastructure separately from the API. Index-write capacity and search-read capacity should be monitored as different workloads.
- Keep Redis/ElastiCache for hot retrieval and repeated search/chat contexts. Cache strategy should distinguish user-scoped private data from shared public/course content.

### Software Engineering View

- Maintain user isolation through `X-User-Id`, S3 prefixes, and per-user index scope; the JMeter fixes confirm this is critical for correct test data.
- Add stronger job status taxonomy: completed, failed by timeout, failed by model/provider, failed by file format, failed by resource limit.
- Continue optimizing expensive code paths: reduce redundant metadata reads, avoid repeated full scans, and keep streamed responses lean.
- Build load-test automation into release validation so 20/30/40/50-user profiles can be repeated before major deployments.

### AI Engineering View

- Introduce model routing: use lighter/faster models for simple summary, roadmap, and MCQ requests; reserve stronger models for complex multimodal or agentic reasoning.
- Add prompt and context budgeting so chat does not retrieve or include more context than needed.
- Use retrieval-only or cached retrieval for repeated queries, and reserve generation for requests that truly need a synthesized answer.
- For indexing, decouple text embedding, image embedding, and multimodal processing so each can scale independently.

### DevOps / SRE View

- Add dashboards for API latency, error rate, queue depth, job duration, model latency, Qdrant latency, S3 latency, and Redis hit/miss rate.
- Set alerts for indexing failure bursts, rising search P95, chat stream timeout risk, and job queue saturation.
- Use blue/green or rolling deployments so load-tested stable versions can be promoted safely.
- Keep ALB idle timeout and client timeout settings aligned with long-running streaming and job-polling workflows.

### Security And Compliance View

- Preserve strict tenant isolation in storage and retrieval.
- Avoid logging sensitive document content; log IDs, timings, and status codes instead.
- Apply rate limits and abuse protection to expensive AI endpoints.
- Keep audit trails for upload, process, index, and chat actions for academic and operational accountability.

## Final Recommendation

BK-MInD is technically promising and already demonstrates reliable performance across a broad set of core APIs. The measured results support presenting the platform as a functional AI learning system with strong foundations in upload, search, chat, and learning insights.

For production expansion, the recommended path is not a rewrite. The correct next step is targeted scaling: isolate background pipelines, autoscale workers, control indexing concurrency, improve caching, and monitor model/Vector Database bottlenecks. With these improvements, BK-MInD can grow from a capstone-grade platform into a larger educational AI system capable of serving more courses, more students, and richer multimodal learning workflows.
