# Video/Audio Parsing and Frame Alignment Evaluation Summary

## 1. Overview
This document summarizes the current evaluation framework for video/audio parsing and frame alignment in the project. It covers:

1. **Audio/video parsing quality**: how well the media pipeline extracts audio, transcribes speech, chunks transcripts, and preserves timestamps.
2. **Transcript temporal coverage**: whether predicted transcript chunks cover the gold transcript time windows.
3. **Weak frame alignment**: whether frames attached to retrieved transcript chunks fall near the expected gold transcript window.
4. **LLM visual judgement**: a separate diagnostic where a vision-capable LLM looks at the selected frame image and judges whether it visually matches the query/excerpt.

Important scope note: the current dataset has gold transcript timestamps, but it does **not** contain true visual semantic labels such as slide IDs, object labels, keyframe labels, or query-to-frame gold annotations. Therefore, frame alignment is primarily a timestamp-backed weak diagnostic. The one-video visual result below is an LLM judgement, not dataset ground truth.

## 2. Evaluation Data and Sources

### MITFLD Subset
Primary local dataset:

```text
backend/data/mitfld_eval_subset/
├── videos/        # 42 lecture videos
├── transcripts/   # gold timed transcript JSON, fields include text/start/duration
├── frags/         # gold fragment boundary timestamps
├── video_id_list.txt
└── README.md
```

Source: MIT Lecture Fragmentation Dataset (MITFLD), sourced from MIT OpenCourseWare. Local attribution and citation notes are in:

```text
backend/data/mitfld_eval_subset/README.md
```

The evaluated local subset currently contains **42 videos**.

### MIT OCW Single Lecture
Secondary local source:

```text
backend/data/ocw_media_eval_sources/
├── ocw_media_sources_manifest.json
└── Lecture_1_Introduction_to_Real_Numbers_Real_Analysis_Mathematics_MIT_OpenCourseWare/
    ├── *.mp4
    └── *.webvtt
```

This is used for a small WebVTT-backed lecture evaluation.

## 3. Pipeline and Code Locations

### Media Processing
Main implementation:

```text
backend/src/processor/media_processor_enhanced.py
```

Relevant responsibilities:

- Extract audio from video.
- Run Whisper ASR.
- Export transcripts in JSON/TXT/MD/SRT/VTT.
- Chunk timed transcript segments.
- Extract video frames as image files with OpenCV.
- Attach extracted frames to transcript chunks by timestamp.

Frame extraction behavior:

```text
FrameExtractor.extract_frames(...)
```

The extractor saves real image files such as:

```text
output/.../stage2_media_processed/extracted_frames/<video_id>/frame_000300.jpg
```

Each frame has metadata including:

```json
{
  "frame_path": ".../frame_000300.jpg",
  "frame_index": 300,
  "frame_name": "<video_id>_frame_000300",
  "video_timestamp": 10.01,
  "content_type": "extracted_frame"
}
```

### Stage 4 Consolidation
Main implementation:

```text
backend/src/processor/consolidator.py
```

Stage 4 copies transcript chunks and extracted frames into RAG-ready media document folders:

```text
output/.../stage4_rag_ready/<video_id>/
├── <video_id>.md
├── transcript_chunks.json
├── media_metadata.json
├── media_manifest.json
└── frames/
    ├── frame_000000.jpg
    └── ...
```

### Media Evaluation
Core evaluation helpers:

```text
backend/src/evaluation/media_intelligence.py
```

CLI runners:

```text
backend/evals/parsing/media/run_media_eval.py
backend/evals/parsing/media/run_media_frame_alignment_eval.py
```

`run_media_eval.py` evaluates ASR and transcript temporal coverage.

`run_media_frame_alignment_eval.py` evaluates weak frame alignment and optionally runs an LLM visual judge over selected frame images.

## 4. Evaluation Metrics

### 4.1 ASR Quality

The ASR metrics compare the gold transcript text against the predicted transcript chunks.

**Word Error Rate (`word_error_rate`, WER):**

$$
\text{WER} = \frac{\text{word-level Levenshtein distance(reference, prediction)}}{\max(1, \text{reference word count})}
$$

**Character Error Rate (`char_error_rate`, CER):**

$$
\text{CER} = \frac{\text{character-level Levenshtein distance(reference, prediction)}}{\max(1, \text{reference character count})}
$$

Lower is better.

### 4.2 Transcript Temporal Coverage

Gold transcript windows come from:

- MITFLD fragment boundaries, normalized by `normalized_gold_windows(...)`.
- Fixed transcript windows for WebVTT-backed OCW data.

For a gold window $G = [g_s, g_e]$ and predicted chunk $C = [c_s, c_e]$:

**Temporal overlap:**

$$
\text{overlap}(G, C) = \max(0, \min(g_e, c_e) - \max(g_s, c_s))
$$

**Temporal hit:**

$$
\text{hit}(G, C) = 1[\text{overlap}(G, C) > 0]
$$

**Temporal IoU:**

$$
\text{IoU}(G, C) =
\frac{\text{overlap}(G, C)}
{\max(g_e, c_e) - \min(g_s, c_s)}
$$

Report-level metrics average the best overlap/IoU across windows and documents.

### 4.3 Weak Frame Alignment

Weak frame alignment starts from a gold transcript window and creates a deterministic quote-style query from that window. The evaluator retrieves transcript chunks from Stage 4 and checks whether the retrieved chunks and their attached frames line up temporally.

Retrieval method in the current script:

```text
in_script_bm25_lexical_baseline
```

The search scope is:

```text
within_gold_media_id
```

For top-k retrieved chunks:

**Chunk Hit @k (`chunk_hit@k`):**

$$
1[\exists C_i \in \text{top-k}: \text{overlap}(G, C_i) > 0]
$$

**Best Chunk IoU @k (`best_chunk_iou@k`):**

$$
\max_{C_i \in \text{top-k}} \text{IoU}(G, C_i)
$$

**Chunk Temporal Recall @k (`chunk_temporal_recall@k`):**

$$
\min\left(1.0, \frac{\sum_{C_i \in \text{top-k}} \text{overlap}(G, C_i)}{g_e - g_s}\right)
$$

**Frame Hit @k (`frame_hit@k`):**

$$
1[\exists f \in \text{frames(top-k)}: g_s \le t_f \le g_e]
$$

**Frame Hit with Tolerance @k (`frame_hit_with_tolerance@k`):**

With tolerance $\tau = 2.0s$ by default:

$$
1[\exists f \in \text{frames(top-k)}: g_s - \tau \le t_f \le g_e + \tau]
$$

**Best Frame Distance:**

For a frame timestamp $t_f$:

$$
d(t_f, G) =
\begin{cases}
0 & \text{if } g_s \le t_f \le g_e \\
\min(|t_f - g_s|, |t_f - g_e|) & \text{otherwise}
\end{cases}
$$

`mean_best_frame_distance_sec@k` averages the nearest frame distance across evaluated items.

**No Frame Candidate Count (`no_frame_candidate_count`):**

Number of evaluated items where retrieved chunks had no associated frame metadata.

### 4.4 LLM Visual Judgement

The optional visual judge is separate from timestamp metrics. It selects a frame candidate, loads the actual image file, sends the image plus query/excerpt to a vision-capable model, and stores a JSON verdict:

```json
{
  "visual_match": "yes | partial | no | unclear",
  "confidence": 0.0,
  "rationale": "...",
  "visible_evidence": ["..."]
}
```

This is useful as a diagnostic for visual relevance, but it is **not** official ground truth unless backed by human labels or dataset visual annotations.

## 5. Experimental Results

### 5.1 MITFLD Full 42-Video ASR and Temporal Evaluation

Artifact:

```text
backend/output/evaluation/media_intelligence_eval_mitfld_100mb/media_eval_report.json
```

Stage 4 source:

```text
backend/output/evaluation/media_pipeline_mitfld_100mb/processing/stage4_rag_ready
```

This run used the existing MITFLD full 42-video output. It is valid for ASR and transcript temporal metrics, but the original run did not include extracted frames.

| Metric | Result |
|---|---:|
| Documents | 42 |
| Mean WER | 16.63% |
| Mean CER | 11.26% |
| Mean Temporal Hit Rate | 97.32% |
| Mean Temporal IoU | 34.02% |

### 5.2 MITFLD Normalized-Window ASR and Temporal Evaluation

Artifact:

```text
backend/output/evaluation/media_intelligence_eval_mitfld_100mb_normalized_windows/media_eval_report.json
```

This report uses normalized MITFLD fragment windows. Tail/edge slivers with text are merged instead of being silently dropped, and empty-text windows are excluded from text/timestamp evaluation.

| Metric | Result |
|---|---:|
| Documents | 42 |
| Mean WER | 16.63% |
| Mean CER | 11.26% |
| Mean Temporal Hit Rate | 100.00% |
| Mean Temporal IoU | 34.84% |

### 5.3 OCW Single-Lecture ASR and Temporal Evaluation

Artifact:

```text
backend/output/evaluation/media_intelligence_eval_ocw_1/media_eval_report.json
```

Gold source:

```text
backend/data/ocw_media_eval_sources/ocw_media_sources_manifest.json
```

| Metric | Result |
|---|---:|
| Documents | 1 |
| Mean WER | 21.81% |
| Mean CER | 17.38% |
| Mean Temporal Hit Rate | 100.00% |
| Mean Temporal IoU | 56.59% |

### 5.4 MITFLD Full 42-Video Tuned Pipeline with Frames

Artifact:

```text
backend/output/evaluation/media_pipeline_mitfld_100mb_tuned_frames/processing/pipeline_stats.json
backend/output/evaluation/media_pipeline_mitfld_100mb_tuned_frames/processing/stage2_media_processed/media_metadata/processing_statistics.json
backend/output/evaluation/media_pipeline_mitfld_100mb_tuned_frames/processing/stage4_rag_ready/consolidation_stats.json
```

Command configuration:

```text
Whisper model: tiny
Device: CPU
Frame extraction: enabled
Frame interval: 100 video frames
Media max chunk tokens: 50
Media max chunk duration: 30 seconds
Frame deduplication: enabled
Noise reduction: enabled
```

Pipeline result:

| Metric | Result |
|---|---:|
| Total input files | 42 |
| Processed files | 42 |
| Failed files | 0 |
| Audio extracted | 42 |
| Transcribed | 42 |
| Transcript chunks created | 3,072 |
| Frames extracted, pipeline stats | 12,020 |
| Stage 4 media documents | 42 |
| Stage 4 docs with chunks | 42 |
| Stage 4 docs with frames | 42 |

Additional filesystem observation:

```text
backend/output/evaluation/media_pipeline_mitfld_100mb_tuned_frames/processing/stage4_rag_ready
```

contains 42 `transcript_chunks.json` files and 42 media folders with `frames/`.

There is a count discrepancy to keep an eye on: `pipeline_stats.json` reports `frames_extracted = 12020`, while a direct filesystem count of Stage 2/Stage 4 `.jpg` frame files showed `12165`. The report should prefer the official pipeline stat for headline numbers, but this discrepancy should be investigated before presenting frame-count totals as final benchmark results.

### 5.5 One-Video Weak Frame Alignment with Visual LLM Judge

Artifact:

```text
backend/output/evaluation/media_frame_alignment_one_video_frames_visual/frame_alignment_eval_report.json
```

Pipeline source:

```text
backend/output/evaluation/media_pipeline_one_video_frames/processing/stage4_rag_ready
```

Evaluated media:

```text
24iPsnbS6_0
```

This was a targeted one-video visual run to verify that:

1. frames are physically extracted as images,
2. `associated_frames` are present in transcript chunks,
3. the evaluator can resolve a Stage 4 frame image path,
4. a vision LLM can inspect the frame image and produce a visual relevance judgement.

Weak frame alignment summary:

| Metric | @1 | @3 | @5 | @10 |
|---|---:|---:|---:|---:|
| Chunk Hit | 100.00% | 100.00% | 100.00% | 100.00% |
| Best Chunk IoU | 21.49% | 27.41% | 29.15% | 30.25% |
| Chunk Temporal Recall | 22.40% | 45.23% | 56.90% | 84.20% |
| Frame Hit | 100.00% | 100.00% | 100.00% | 100.00% |
| Frame Hit with 2s Tolerance | 100.00% | 100.00% | 100.00% | 100.00% |
| Mean Best Frame Distance | 0.00s | 0.00s | 0.00s | 0.00s |

Other counts:

| Metric | Result |
|---|---:|
| Gold samples | 1 |
| Eval items | 4 |
| Evaluated items | 4 |
| Missing prediction docs | 0 |
| No frame candidate count | 0 |
| Skipped empty-text windows | 0 |

Visual LLM judge:

| Field | Result |
|---|---|
| Provider | OpenAI |
| Model | `gpt-4o-mini` |
| Max judged items | 1 |
| Judged items | 1 |
| Failures | 0 |
| Candidate frame | `stage4_rag_ready/24iPsnbS6_0/frames/frame_000300.jpg` |
| Candidate timestamp | 10.01s |
| Visual match | `partial` |
| Confidence | 0.70 |

LLM rationale summary:

> The frame contains visual content about categories of physics, including references to special relativity and course numbers, matching the lecture topic. However, it does not directly prove the entire spoken transcript excerpt.

This is a useful diagnostic, but it should not be treated as a ground-truth visual benchmark.

### 5.6 Full Visual LLM Run Status

Artifact:

```text
backend/output/evaluation/media_frame_alignment_eval_mitfld_100mb_tuned_frames_visual/frame_alignment_eval_report.json
```

A full run was executed on the MITFLD subset with visual LLM judgement.

Weak frame alignment summary:

| Metric | @1 | @3 | @5 | @10 |
|---|---:|---:|---:|---:|
| Chunk Hit | 100.00% | 100.00% | 100.00% | 100.00% |
| Best Chunk IoU | 18.49% | 21.70% | 22.10% | 22.58% |
| Chunk Temporal Recall | 20.52% | 32.94% | 38.27% | 46.55% |
| Frame Hit | 97.65% | 98.32% | 98.32% | 98.32% |
| Frame Hit with 2s Tolerance | 98.99% | 99.66% | 99.66% | 99.66% |
| Mean Best Frame Distance | 0.00s | 0.00s | 0.05s | 0.04s |

Other counts:

| Metric | Result |
|---|---:|
| Gold samples | 42 |
| Eval items | 298 |
| Evaluated items | 298 |
| Missing prediction docs | 0 |
| No frame candidate count | 0 |
| Skipped empty-text windows | 1 |

Visual LLM judge:

| Field | Result |
|---|---|
| Provider | OpenAI |
| Model | `gpt-4o-mini` |
| Attempted items | 298 |
| Judged items | 66 |
| Failures | 232 |
| Match 'partial' | 29 |
| Match 'yes' | 27 |
| Match 'no' | 10 |

Note: There were 232 failures during the visual judgement phase, primarily due to `429 Rate limit reached` errors from the OpenAI API.

Therefore:

- Full MITFLD frame extraction pipeline result exists.
- Full MITFLD non-visual ASR/temporal metrics exist.
- One-video weak frame alignment + visual LLM judgement exists.
- Full MITFLD visual LLM judgement run was attempted but suffered severe rate-limiting issues (232 failed items).

## 6. Commands Reference

Run from:

```bash
cd backend
```

### 6.1 Full MITFLD Pipeline with Frames

```bash
NUMBA_CACHE_DIR=/tmp/numba_cache PYTHONPATH=. python3 -m src.processor.pipeline \
  data/mitfld_eval_subset/videos \
  output/evaluation/media_pipeline_mitfld_100mb_tuned_frames/processing \
  --media-only \
  --asr-model tiny \
  --no-gpu \
  --frame-interval 100 \
  --media-max-chunk-tokens 50 \
  --media-max-chunk-duration-sec 30 \
  --force
```

### 6.2 Full Weak Frame Alignment without Visual LLM

```bash
python3 evals/parsing/media/run_media_frame_alignment_eval.py \
  --dataset mitfld \
  --gold-root data/mitfld_eval_subset \
  --stage4-root output/evaluation/media_pipeline_mitfld_100mb_tuned_frames/processing/stage4_rag_ready \
  --output-dir output/evaluation/media_frame_alignment_eval_mitfld_100mb_tuned_frames \
  --top-k 1 3 5 10 \
  --frame-tolerance-sec 2.0
```

### 6.3 Full Weak Frame Alignment with Visual LLM

This can be expensive because every evaluated item may send an image to the model. Start bounded first:

```bash
set -a && source .env && set +a && python3 evals/parsing/media/run_media_frame_alignment_eval.py \
  --dataset mitfld \
  --gold-root data/mitfld_eval_subset \
  --stage4-root output/evaluation/media_pipeline_mitfld_100mb_tuned_frames/processing/stage4_rag_ready \
  --output-dir output/evaluation/media_frame_alignment_eval_mitfld_100mb_tuned_frames_visual \
  --top-k 1 3 5 10 \
  --frame-tolerance-sec 2.0 \
  --vision-judge \
  --vision-model gpt-4o-mini \
  --vision-max-items 20
```

After validating cost/runtime, remove the cap:

```bash
set -a && source .env && set +a && python3 evals/parsing/media/run_media_frame_alignment_eval.py \
  --dataset mitfld \
  --gold-root data/mitfld_eval_subset \
  --stage4-root output/evaluation/media_pipeline_mitfld_100mb_tuned_frames/processing/stage4_rag_ready \
  --output-dir output/evaluation/media_frame_alignment_eval_mitfld_100mb_tuned_frames_visual \
  --top-k 1 3 5 10 \
  --frame-tolerance-sec 2.0 \
  --vision-judge \
  --vision-model gpt-4o-mini
```

### 6.4 One-Video Visual Diagnostic

```bash
set -a && source .env && set +a && python3 evals/parsing/media/run_media_frame_alignment_eval.py \
  --dataset mitfld \
  --gold-root data/mitfld_eval_subset \
  --stage4-root output/evaluation/media_pipeline_one_video_frames/processing/stage4_rag_ready \
  --output-dir output/evaluation/media_frame_alignment_one_video_frames_visual \
  --media-id 24iPsnbS6_0 \
  --top-k 1 3 5 10 \
  --frame-tolerance-sec 2.0 \
  --vision-judge \
  --vision-max-items 1
```

## 7. Interpretation

### What the Existing Results Support

- The media pipeline can process the full 42-video MITFLD subset locally with Whisper `tiny` on CPU.
- The pipeline can extract real frame images and copy them into Stage 4 RAG-ready folders.
- Transcript temporal coverage is strong in hit-rate terms, especially after normalized gold windows.
- Frame attachment by timestamp works on the one-video diagnostic: every evaluated item had frame candidates and at least one frame inside the gold window.
- The optional LLM visual judge can inspect the selected frame image and produce a structured visual relevance verdict.

### What the Existing Results Do Not Yet Prove

- They do not prove true visual semantic retrieval quality across the full dataset.
- They do not prove that the LLM can reliably pick the best frame among multiple candidate frames.
- They do not provide human-labeled visual correctness.
- They do not provide full MITFLD visual LLM judgement results yet.
- They do not evaluate slide/object/keyframe semantics independently from transcript timestamps.

### Practical Reading of the Current Metrics

The ASR and temporal metrics are suitable headline metrics for video/audio parsing quality.

The weak frame metrics are useful for validating pipeline wiring:

- frame extraction happened,
- frame metadata exists,
- frames are attached to transcript chunks,
- retrieved transcript chunks carry frame candidates near the expected timestamp.

The LLM visual judge is a qualitative layer. It is helpful for inspecting whether selected frames are visually plausible, but it should be presented as diagnostic evidence rather than official ground truth.

## 8. Recommended Next Steps

1. Run full weak frame alignment without visual LLM and archive the resulting `frame_alignment_eval_report.json`.
2. Run visual LLM judgement with `--vision-max-items 20` first to validate cost, latency, and output quality.
3. If bounded visual judgement looks stable, run the full visual pass.
4. Investigate the frame-count discrepancy between pipeline stats and filesystem `.jpg` counts.
5. Add a stronger visual benchmark later:
   - human-labeled keyframes,
   - slide OCR labels,
   - query-to-frame relevance labels,
   - or a manually curated subset for visual semantic correctness.
