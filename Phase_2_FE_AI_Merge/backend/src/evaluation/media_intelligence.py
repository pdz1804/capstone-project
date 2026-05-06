"""Evaluation helpers for audio/video processing outputs.

The media pipeline writes timestamped transcript chunks and optional video-frame
associations. This module evaluates those outputs against independent timed
ground truth from datasets such as MITFLD or MIT OCW WebVTT captions.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from rapidfuzz.distance import Levenshtein


_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")
_VTT_TIMING_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}\.\d{3}|\d{1,2}:\d{2}\.\d{3})\s+-->\s+"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}\.\d{3}|\d{1,2}:\d{2}\.\d{3})"
)


@dataclass(frozen=True)
class TimedTextSegment:
    text: str
    start_time: float
    end_time: float


@dataclass(frozen=True)
class MediaGoldSample:
    media_id: str
    modality: str
    source_video_path: Optional[str]
    transcript_path: str
    segments: list[TimedTextSegment]
    fragment_boundaries: list[float]

    @property
    def duration_sec(self) -> float:
        if not self.segments:
            return 0.0
        return max(seg.end_time for seg in self.segments)

    @property
    def text(self) -> str:
        return join_segments(self.segments)


@dataclass(frozen=True)
class PredictedMediaChunk:
    chunk_id: str
    text: str
    start_time: Optional[float]
    end_time: Optional[float]
    associated_frame_times: tuple[float, ...]
    metadata: dict[str, Any]
    associated_frames: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class TemporalWindowMetric:
    start_time: float
    end_time: float
    best_overlap_sec: float
    best_iou: float
    hit: bool


@dataclass(frozen=True)
class GoldWindowSet:
    windows: list[tuple[float, float]]
    source: str
    normalization: dict[str, Any]


@dataclass(frozen=True)
class MediaEvalItem:
    sample_id: str
    media_id: str
    modality: str
    query: str
    reference_answer: str
    gold_start_time: float
    gold_end_time: float
    gold_excerpt: str
    expected_evidence: str
    window_source: str


@dataclass(frozen=True)
class MediaFrameAlignmentEvalItem:
    sample_id: str
    media_id: str
    query: str
    gold_start_time: float
    gold_end_time: float
    gold_excerpt: str
    window_source: str


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def normalize_text(text: str) -> str:
    text = _TAG_RE.sub(" ", str(text or ""))
    text = text.replace("\u00a0", " ")
    return _SPACE_RE.sub(" ", text).strip()


def join_segments(segments: Sequence[TimedTextSegment]) -> str:
    return normalize_text(" ".join(seg.text for seg in segments if seg.text.strip()))


def tokenize_words(text: str) -> list[str]:
    return _WORD_RE.findall(normalize_text(text).lower())


def _levenshtein(reference: Sequence[Any], prediction: Sequence[Any]) -> int:
    return int(Levenshtein.distance(reference, prediction))


def word_error_rate(reference_text: str, prediction_text: str) -> float:
    reference = tokenize_words(reference_text)
    prediction = tokenize_words(prediction_text)
    return _levenshtein(reference, prediction) / max(1, len(reference))


def char_error_rate(reference_text: str, prediction_text: str) -> float:
    reference = list(normalize_text(reference_text).lower())
    prediction = list(normalize_text(prediction_text).lower())
    return _levenshtein(reference, prediction) / max(1, len(reference))


def parse_timecode(value: str) -> float:
    parts = str(value).strip().split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    raise ValueError(f"Invalid timestamp: {value}")


def parse_webvtt(text: str) -> list[TimedTextSegment]:
    """Parse a WebVTT caption file into timed text segments."""
    lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    segments: list[TimedTextSegment] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        match = _VTT_TIMING_RE.search(line)
        if not match:
            idx += 1
            continue
        start = parse_timecode(match.group("start"))
        end = parse_timecode(match.group("end"))
        idx += 1
        payload: list[str] = []
        while idx < len(lines) and lines[idx].strip():
            raw = lines[idx].strip()
            if not raw.startswith(("NOTE", "STYLE", "REGION")):
                payload.append(raw)
            idx += 1
        text_value = normalize_text(" ".join(payload))
        if text_value:
            segments.append(TimedTextSegment(text=text_value, start_time=start, end_time=end))
    return segments


def load_mitfld_gold_sample(root: Path | str, video_id: str) -> MediaGoldSample:
    root = Path(root)
    transcript_path = root / "transcripts" / f"{video_id}.json"
    frag_path = root / "frags" / f"{video_id}.json"
    video_path = root / "videos" / f"{video_id}.mp4"
    raw_segments = _load_json(transcript_path)
    raw_frags = _load_json(frag_path) if frag_path.exists() else []
    segments: list[TimedTextSegment] = []
    for item in raw_segments if isinstance(raw_segments, list) else []:
        if not isinstance(item, dict):
            continue
        start = _coerce_float(item.get("start"))
        duration = _coerce_float(item.get("duration"))
        text = normalize_text(str(item.get("text") or ""))
        if start is None or duration is None or not text:
            continue
        segments.append(TimedTextSegment(text=text, start_time=start, end_time=start + max(0.0, duration)))
    frags = sorted(float(x) for x in raw_frags if _coerce_float(x) is not None)
    return MediaGoldSample(
        media_id=video_id,
        modality="video",
        source_video_path=str(video_path) if video_path.exists() else None,
        transcript_path=str(transcript_path),
        segments=segments,
        fragment_boundaries=frags,
    )


def discover_mitfld_gold_samples(root: Path | str, max_videos: Optional[int] = None) -> list[MediaGoldSample]:
    root = Path(root)
    ids = sorted(path.stem for path in (root / "transcripts").glob("*.json"))
    samples = [load_mitfld_gold_sample(root, video_id) for video_id in ids]
    return samples[:max_videos] if max_videos is not None else samples


def load_ocw_webvtt_gold(
    *,
    media_id: str,
    vtt_path: Path | str,
    source_video_path: Optional[str] = None,
) -> MediaGoldSample:
    vtt_path = Path(vtt_path)
    return MediaGoldSample(
        media_id=media_id,
        modality="video",
        source_video_path=source_video_path,
        transcript_path=str(vtt_path),
        segments=parse_webvtt(vtt_path.read_text(encoding="utf-8", errors="ignore")),
        fragment_boundaries=[],
    )


def fragment_windows(boundaries: Sequence[float], duration_sec: float) -> list[tuple[float, float]]:
    """Convert MITFLD-style fragment boundary timestamps into closed-open windows."""
    if duration_sec <= 0:
        return []
    numeric: list[float] = []
    for value in boundaries:
        coerced = _coerce_float(value)
        if coerced is not None and 0.0 <= coerced <= duration_sec:
            numeric.append(max(0.0, coerced))
    cleaned = sorted(set(numeric))
    points = cleaned[:]
    if not points or points[0] > 0.0:
        points.insert(0, 0.0)
    if points[-1] < duration_sec:
        points.append(duration_sec)
    windows: list[tuple[float, float]] = []
    for start, end in zip(points, points[1:]):
        if end > start:
            windows.append((start, end))
    return windows


def fixed_transcript_windows(
    segments: Sequence[TimedTextSegment],
    *,
    window_sec: float = 60.0,
    min_words: int = 20,
) -> list[tuple[float, float]]:
    """Build fallback gold windows from timed transcript segments."""
    windows: list[tuple[float, float]] = []
    start: Optional[float] = None
    end: Optional[float] = None
    words = 0
    for seg in segments:
        if start is None:
            start = seg.start_time
        end = seg.end_time
        words += len(tokenize_words(seg.text))
        if end - start >= window_sec and words >= min_words:
            windows.append((start, end))
            start = None
            end = None
            words = 0
    if start is not None and end is not None and words >= min_words:
        windows.append((start, end))
    return windows


def text_for_window(segments: Sequence[TimedTextSegment], start_time: float, end_time: float) -> str:
    return join_segments(
        [
            segment
            for segment in segments
            if temporal_overlap(start_time, end_time, segment.start_time, segment.end_time) > 0
        ]
    )


def normalized_gold_windows(
    sample: MediaGoldSample,
    *,
    fallback_window_sec: float = 60.0,
    min_boundary_sliver_sec: float = 2.0,
) -> GoldWindowSet:
    """Return eval windows with explicit, lossless normalization metadata.

    MITFLD fragment boundaries can create tiny first/last windows when a boundary
    lands near the media edge. If those windows contain transcript text, merge
    them into the neighboring window instead of dropping the content. If a window
    has no transcript text, exclude it from text/timestamp eval because there is
    no gold transcript evidence to retrieve or score.
    """
    raw_windows = (
        fragment_windows(sample.fragment_boundaries, sample.duration_sec)
        if sample.fragment_boundaries
        else []
    )
    source = "mitfld_fragments" if raw_windows else "fixed_transcript_windows"
    if not raw_windows:
        windows = fixed_transcript_windows(sample.segments, window_sec=fallback_window_sec)
        return GoldWindowSet(
            windows=windows,
            source=source,
            normalization={
                "enabled": False,
                "reason": "fixed_transcript_windows",
                "original_window_count": len(windows),
                "window_count": len(windows),
            },
        )

    kept: list[dict[str, Any]] = []
    empty_text_windows: list[dict[str, Any]] = []
    for idx, (start, end) in enumerate(raw_windows):
        excerpt = text_for_window(sample.segments, start, end)
        if not tokenize_words(excerpt):
            empty_text_windows.append(
                {
                    "original_index": idx,
                    "start_time": start,
                    "end_time": end,
                    "duration_sec": end - start,
                }
            )
            continue
        kept.append(
            {
                "start_time": start,
                "end_time": end,
                "merged_original_indices": [idx],
            }
        )

    boundary_merges: list[dict[str, Any]] = []
    if len(kept) > 1:
        first = kept[0]
        first_duration = first["end_time"] - first["start_time"]
        if first["start_time"] <= 1e-6 and first_duration < min_boundary_sliver_sec:
            second = kept[1]
            second["start_time"] = first["start_time"]
            second["merged_original_indices"] = (
                first["merged_original_indices"] + second["merged_original_indices"]
            )
            boundary_merges.append(
                {
                    "position": "start",
                    "duration_sec": first_duration,
                    "merged_original_indices": first["merged_original_indices"],
                }
            )
            kept.pop(0)

    if len(kept) > 1:
        last = kept[-1]
        last_duration = last["end_time"] - last["start_time"]
        if abs(last["end_time"] - sample.duration_sec) <= 1e-6 and last_duration < min_boundary_sliver_sec:
            previous = kept[-2]
            previous["end_time"] = last["end_time"]
            previous["merged_original_indices"] = (
                previous["merged_original_indices"] + last["merged_original_indices"]
            )
            boundary_merges.append(
                {
                    "position": "end",
                    "duration_sec": last_duration,
                    "merged_original_indices": last["merged_original_indices"],
                }
            )
            kept.pop()

    windows = [(row["start_time"], row["end_time"]) for row in kept]
    return GoldWindowSet(
        windows=windows,
        source=source,
        normalization={
            "enabled": True,
            "original_window_count": len(raw_windows),
            "window_count": len(windows),
            "min_boundary_sliver_sec": min_boundary_sliver_sec,
            "empty_text_excluded_count": len(empty_text_windows),
            "empty_text_excluded_windows": empty_text_windows,
            "boundary_sliver_merged_count": len(boundary_merges),
            "boundary_sliver_merges": boundary_merges,
        },
    )


def make_media_eval_items(
    samples: Sequence[MediaGoldSample],
    *,
    max_windows_per_media: Optional[int] = None,
    fallback_window_sec: float = 60.0,
    excerpt_max_chars: int = 420,
) -> list[MediaEvalItem]:
    """Build deterministic retrieval eval items from timed gold transcripts.

    These are intentionally dataset-backed and do not rely on generated
    transcripts. The default query is quote-oriented, which is useful for a
    first retrieval benchmark; LLM-paraphrased queries can be layered on top
    later while keeping the same gold timestamp windows.
    """
    items: list[MediaEvalItem] = []
    for sample in samples:
        gold_windows = normalized_gold_windows(sample, fallback_window_sec=fallback_window_sec)
        windows = gold_windows.windows
        if max_windows_per_media is not None:
            windows = windows[:max_windows_per_media]
        for idx, (start, end) in enumerate(windows):
            excerpt = text_for_window(sample.segments, start, end)
            if not excerpt:
                continue
            clipped = excerpt[:excerpt_max_chars].rstrip()
            query_quote = clipped[:180].rstrip()
            items.append(
                MediaEvalItem(
                    sample_id=f"{sample.media_id}:window:{idx:04d}",
                    media_id=sample.media_id,
                    modality=sample.modality,
                    query=f'Find the lecture moment that says: "{query_quote}"',
                    reference_answer=clipped,
                    gold_start_time=start,
                    gold_end_time=end,
                    gold_excerpt=clipped,
                    expected_evidence="transcript",
                    window_source=gold_windows.source,
                )
            )
    return items


def temporal_overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def temporal_iou(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    overlap = temporal_overlap(a_start, a_end, b_start, b_end)
    union = max(a_end, b_end) - min(a_start, b_start)
    return overlap / union if union > 0 else 0.0


def load_predicted_chunks(doc_dir: Path | str) -> list[PredictedMediaChunk]:
    doc_dir = Path(doc_dir)
    chunks_path = doc_dir / "transcript_chunks.json"
    if not chunks_path.exists():
        return []
    payload = _load_json(chunks_path)
    items = payload if isinstance(payload, list) else payload.get("chunks") or []
    out: list[PredictedMediaChunk] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        meta = dict(item.get("metadata") or {})
        start = _coerce_float(item.get("start_time", meta.get("start_time")))
        end = _coerce_float(item.get("end_time", meta.get("end_time")))
        frames = item.get("associated_frames", meta.get("associated_frames", [])) or []
        frame_times: list[float] = []
        frame_rows: list[dict[str, Any]] = []
        for frame in frames if isinstance(frames, list) else []:
            if isinstance(frame, dict):
                ts = _coerce_float(frame.get("video_timestamp"))
                if ts is not None:
                    frame_times.append(ts)
                    frame_row = dict(frame)
                    frame_row["video_timestamp"] = ts
                    frame_rows.append(frame_row)
        out.append(
            PredictedMediaChunk(
                chunk_id=str(item.get("id") or item.get("chunk_id") or item.get("chunk_name") or f"chunk_{idx}"),
                text=normalize_text(str(item.get("text") or "")),
                start_time=start,
                end_time=end,
                associated_frame_times=tuple(frame_times),
                metadata=meta,
                associated_frames=tuple(frame_rows),
            )
        )
    return out


def _chunk_text(chunks: Sequence[PredictedMediaChunk]) -> str:
    return normalize_text(" ".join(chunk.text for chunk in chunks if chunk.text.strip()))


def score_temporal_windows(
    windows: Sequence[tuple[float, float]],
    chunks: Sequence[PredictedMediaChunk],
) -> list[TemporalWindowMetric]:
    metrics: list[TemporalWindowMetric] = []
    timed_chunks = [chunk for chunk in chunks if chunk.start_time is not None and chunk.end_time is not None]
    for start, end in windows:
        best_overlap = 0.0
        best_iou = 0.0
        for chunk in timed_chunks:
            assert chunk.start_time is not None and chunk.end_time is not None
            best_overlap = max(best_overlap, temporal_overlap(start, end, chunk.start_time, chunk.end_time))
            best_iou = max(best_iou, temporal_iou(start, end, chunk.start_time, chunk.end_time))
        metrics.append(
            TemporalWindowMetric(
                start_time=start,
                end_time=end,
                best_overlap_sec=best_overlap,
                best_iou=best_iou,
                hit=best_overlap > 0,
            )
        )
    return metrics


def frame_timestamp_diagnostic(
    windows: Sequence[tuple[float, float]],
    chunks: Sequence[PredictedMediaChunk],
) -> dict[str, Any]:
    """Diagnostic only: timestamp coverage of associated video frames.

    This does not judge visual semantics. It only checks whether the media
    processor attached any extracted frame timestamp inside each gold window.
    """
    frame_times = [
        ts
        for chunk in chunks
        for ts in chunk.associated_frame_times
    ]
    window_rows = []
    for start, end in windows:
        hits = [ts for ts in frame_times if start <= ts <= end]
        window_rows.append(
            {
                "start_time": start,
                "end_time": end,
                "frame_timestamp_count": len(hits),
                "has_frame_timestamp": bool(hits),
            }
        )
    return {
        "description": (
            "Diagnostic only: whether associated frame timestamps fall inside "
            "gold transcript windows. This is not a semantic visual QA metric."
        ),
        "window_count": len(window_rows),
        "frame_timestamp_hit_count": sum(1 for row in window_rows if row["has_frame_timestamp"]),
        "frame_timestamp_hit_rate": (
            sum(1 for row in window_rows if row["has_frame_timestamp"]) / len(window_rows)
            if window_rows
            else 0.0
        ),
        "windows": window_rows,
    }


def summarize_window_metrics(metrics: Sequence[TemporalWindowMetric]) -> dict[str, Any]:
    if not metrics:
        return {
            "window_count": 0,
            "hit_rate": 0.0,
            "mean_best_iou": 0.0,
            "mean_best_overlap_sec": 0.0,
        }
    return {
        "window_count": len(metrics),
        "hit_rate": sum(1 for metric in metrics if metric.hit) / len(metrics),
        "mean_best_iou": sum(metric.best_iou for metric in metrics) / len(metrics),
        "mean_best_overlap_sec": sum(metric.best_overlap_sec for metric in metrics) / len(metrics),
    }


def evaluate_media_doc(
    gold: MediaGoldSample,
    doc_dir: Path | str,
    *,
    fallback_window_sec: float = 60.0,
) -> dict[str, Any]:
    doc_dir = Path(doc_dir)
    chunks = load_predicted_chunks(doc_dir)
    predicted_text = _chunk_text(chunks)
    gold_text = gold.text
    gold_windows = normalized_gold_windows(gold, fallback_window_sec=fallback_window_sec)
    windows = gold_windows.windows
    window_metrics = score_temporal_windows(windows, chunks)
    return {
        "media_id": gold.media_id,
        "modality": gold.modality,
        "doc_dir": str(doc_dir),
        "gold": {
            "transcript_path": gold.transcript_path,
            "source_video_path": gold.source_video_path,
            "duration_sec": gold.duration_sec,
            "segment_count": len(gold.segments),
            "fragment_count": len(gold.fragment_boundaries),
        },
        "prediction": {
            "chunk_count": len(chunks),
            "timed_chunk_count": sum(1 for chunk in chunks if chunk.start_time is not None and chunk.end_time is not None),
            "associated_frame_count": sum(len(chunk.associated_frame_times) for chunk in chunks),
        },
        "asr": {
            "word_error_rate": word_error_rate(gold_text, predicted_text),
            "char_error_rate": char_error_rate(gold_text, predicted_text),
            "gold_word_count": len(tokenize_words(gold_text)),
            "predicted_word_count": len(tokenize_words(predicted_text)),
        },
        "temporal": {
            "window_source": gold_windows.source,
            "window_normalization": gold_windows.normalization,
            **summarize_window_metrics(window_metrics),
            "windows": [asdict(metric) for metric in window_metrics],
        },
        "frame_timestamp_diagnostic": frame_timestamp_diagnostic(windows, chunks),
    }


def evaluate_media_corpus(
    gold_samples: Sequence[MediaGoldSample],
    stage4_root: Path | str,
    *,
    fallback_window_sec: float = 60.0,
) -> dict[str, Any]:
    stage4_root = Path(stage4_root)
    documents: list[dict[str, Any]] = []
    missing: list[str] = []
    for gold in gold_samples:
        doc_dir = stage4_root / gold.media_id
        if not doc_dir.exists():
            missing.append(gold.media_id)
            continue
        documents.append(evaluate_media_doc(gold, doc_dir, fallback_window_sec=fallback_window_sec))
    return {
        "summary": summarize_media_reports(documents),
        "missing_predictions": missing,
        "documents": documents,
    }


def summarize_media_reports(documents: Sequence[dict[str, Any]]) -> dict[str, Any]:
    def mean(path: tuple[str, ...]) -> float:
        values: list[float] = []
        for doc in documents:
            current: Any = doc
            for part in path:
                current = current.get(part) if isinstance(current, dict) else None
            if isinstance(current, (int, float)):
                values.append(float(current))
        return sum(values) / len(values) if values else 0.0

    return {
        "document_count": len(documents),
        "mean_word_error_rate": mean(("asr", "word_error_rate")),
        "mean_char_error_rate": mean(("asr", "char_error_rate")),
        "mean_temporal_hit_rate": mean(("temporal", "hit_rate")),
        "mean_temporal_iou": mean(("temporal", "mean_best_iou")),
    }


def temporal_retrieval_metrics(
    *,
    relevant_window: tuple[float, float],
    retrieved_chunks: Sequence[PredictedMediaChunk],
    k_values: Sequence[int] = (1, 3, 5, 10),
) -> dict[str, float]:
    """Score retrieved timed chunks against one gold answer window."""
    start, end = relevant_window
    out: dict[str, float] = {}
    for k in sorted({int(k) for k in k_values if int(k) > 0}):
        top = retrieved_chunks[:k]
        overlaps = [
            temporal_overlap(start, end, chunk.start_time, chunk.end_time)
            for chunk in top
            if chunk.start_time is not None and chunk.end_time is not None
        ]
        ious = [
            temporal_iou(start, end, chunk.start_time, chunk.end_time)
            for chunk in top
            if chunk.start_time is not None and chunk.end_time is not None
        ]
        out[f"temporal_recall@{k}"] = min(1.0, sum(overlaps) / max(1e-9, end - start))
        out[f"best_iou@{k}"] = max(ious) if ious else 0.0
        out[f"hit@{k}"] = 1.0 if any(overlap > 0 for overlap in overlaps) else 0.0
    return out


def make_media_frame_alignment_eval_items(
    samples: Sequence[MediaGoldSample],
    *,
    dataset: str,
    max_windows_per_media: Optional[int] = None,
    fallback_window_sec: float = 60.0,
    excerpt_max_chars: int = 420,
    query_max_chars: int = 180,
) -> tuple[list[MediaFrameAlignmentEvalItem], dict[str, Any]]:
    """Build weak frame-alignment eval items from gold transcript windows.

    The query is intentionally a deterministic transcript quote. This makes the
    evaluation a timestamp/frame-alignment diagnostic, not a visual-semantic GT.
    """
    dataset = str(dataset).lower()
    items: list[MediaFrameAlignmentEvalItem] = []
    skipped_empty_text = 0
    window_stats: list[dict[str, Any]] = []

    for sample in samples:
        if dataset == "mitfld":
            gold_windows = normalized_gold_windows(sample, fallback_window_sec=fallback_window_sec)
            windows = gold_windows.windows
            source = gold_windows.source
            normalization = gold_windows.normalization
            skipped_empty_text += int(normalization.get("empty_text_excluded_count") or 0)
        else:
            windows = fixed_transcript_windows(sample.segments, window_sec=fallback_window_sec)
            source = "ocw_webvtt_fixed_windows"
            normalization = {
                "enabled": False,
                "reason": "fixed_webvtt_windows",
                "window_count": len(windows),
                "window_sec": fallback_window_sec,
            }

        original_window_count = len(windows)
        if max_windows_per_media is not None:
            windows = windows[:max_windows_per_media]

        sample_item_count = 0
        for idx, (start, end) in enumerate(windows):
            excerpt = normalize_text(text_for_window(sample.segments, start, end))
            if not tokenize_words(excerpt):
                skipped_empty_text += 1
                continue
            gold_excerpt = excerpt[:excerpt_max_chars].rstrip()
            query = excerpt[:query_max_chars].rstrip()
            items.append(
                MediaFrameAlignmentEvalItem(
                    sample_id=f"{sample.media_id}:frame-window:{idx:04d}",
                    media_id=sample.media_id,
                    query=query,
                    gold_start_time=start,
                    gold_end_time=end,
                    gold_excerpt=gold_excerpt,
                    window_source=source,
                )
            )
            sample_item_count += 1

        window_stats.append(
            {
                "media_id": sample.media_id,
                "window_source": source,
                "candidate_window_count": original_window_count,
                "limited_window_count": len(windows),
                "item_count": sample_item_count,
                "normalization": normalization,
            }
        )

    return items, {
        "skipped_empty_text_count": skipped_empty_text,
        "sample_window_stats": window_stats,
    }


def rank_media_chunks_lexical(
    query: str,
    chunks: Sequence[PredictedMediaChunk],
) -> list[tuple[PredictedMediaChunk, float]]:
    """Rank transcript chunks with a small in-process BM25 baseline."""
    if not chunks:
        return []
    tokenized_docs = [tokenize_words(chunk.text) for chunk in chunks]
    query_terms = tokenize_words(query)
    if not query_terms:
        return [(chunk, 0.0) for chunk in chunks]

    doc_freq: Counter[str] = Counter()
    for doc_terms in tokenized_docs:
        doc_freq.update(set(doc_terms))

    doc_count = len(chunks)
    avg_doc_len = sum(len(terms) for terms in tokenized_docs) / max(1, doc_count)
    query_counts = Counter(query_terms)
    k1 = 1.5
    b = 0.75
    scored: list[tuple[int, PredictedMediaChunk, float]] = []
    for idx, (chunk, terms) in enumerate(zip(chunks, tokenized_docs)):
        term_counts = Counter(terms)
        doc_len = len(terms)
        score = 0.0
        for term, query_tf in query_counts.items():
            tf = term_counts.get(term, 0)
            if tf <= 0:
                continue
            df = doc_freq.get(term, 0)
            idf = math.log(1.0 + (doc_count - df + 0.5) / (df + 0.5))
            denom = tf + k1 * (1.0 - b + b * doc_len / max(1e-9, avg_doc_len))
            score += query_tf * idf * (tf * (k1 + 1.0)) / max(1e-9, denom)
        scored.append((idx, chunk, score))

    scored.sort(key=lambda row: (-row[2], row[0]))
    return [(chunk, score) for _, chunk, score in scored]


def frame_distance_to_window(timestamp: float, start_time: float, end_time: float) -> float:
    if start_time <= timestamp <= end_time:
        return 0.0
    return min(abs(timestamp - start_time), abs(timestamp - end_time))


def score_frame_alignment_retrieval(
    *,
    item: MediaFrameAlignmentEvalItem,
    retrieved_chunks: Sequence[PredictedMediaChunk],
    k_values: Sequence[int] = (1, 3, 5, 10),
    frame_tolerance_sec: float = 2.0,
) -> dict[str, Any]:
    start = item.gold_start_time
    end = item.gold_end_time
    metrics: dict[str, Any] = {}
    for k in sorted({int(k) for k in k_values if int(k) > 0}):
        top = retrieved_chunks[:k]
        overlaps = [
            temporal_overlap(start, end, chunk.start_time, chunk.end_time)
            for chunk in top
            if chunk.start_time is not None and chunk.end_time is not None
        ]
        ious = [
            temporal_iou(start, end, chunk.start_time, chunk.end_time)
            for chunk in top
            if chunk.start_time is not None and chunk.end_time is not None
        ]
        frame_times = [ts for chunk in top for ts in chunk.associated_frame_times]
        frame_distances = [frame_distance_to_window(ts, start, end) for ts in frame_times]

        metrics[f"chunk_hit@{k}"] = 1.0 if any(overlap > 0 for overlap in overlaps) else 0.0
        metrics[f"best_chunk_iou@{k}"] = max(ious) if ious else 0.0
        metrics[f"chunk_temporal_recall@{k}"] = min(1.0, sum(overlaps) / max(1e-9, end - start))
        metrics[f"frame_hit@{k}"] = 1.0 if any(start <= ts <= end for ts in frame_times) else 0.0
        metrics[f"frame_hit_with_tolerance@{k}"] = (
            1.0
            if any(start - frame_tolerance_sec <= ts <= end + frame_tolerance_sec for ts in frame_times)
            else 0.0
        )
        metrics[f"best_frame_distance_sec@{k}"] = min(frame_distances) if frame_distances else None
        metrics[f"frame_candidate_count@{k}"] = len(frame_times)
    return metrics


def _retrieved_chunk_report_row(
    *,
    rank: int,
    chunk: PredictedMediaChunk,
    score: float,
) -> dict[str, Any]:
    return {
        "rank": rank,
        "score": score,
        "chunk_id": chunk.chunk_id,
        "start_time": chunk.start_time,
        "end_time": chunk.end_time,
        "associated_frames": list(chunk.associated_frames),
        "associated_frame_times": list(chunk.associated_frame_times),
        "text_preview": chunk.text[:240],
    }


def _summarize_frame_alignment_rows(
    rows: Sequence[dict[str, Any]],
    *,
    k_values: Sequence[int],
) -> dict[str, Any]:
    evaluated_count = len(rows)

    def mean_metric(name: str) -> float:
        values = [
            float(row["metrics"][name])
            for row in rows
            if isinstance(row.get("metrics"), dict) and isinstance(row["metrics"].get(name), (int, float))
        ]
        return sum(values) / len(values) if values else 0.0

    summary: dict[str, Any] = {
        "evaluated_item_count": evaluated_count,
        "no_frame_candidate_count": sum(1 for row in rows if row.get("no_frame_candidate")),
    }
    for k in sorted({int(k) for k in k_values if int(k) > 0}):
        summary[f"chunk_hit@{k}"] = mean_metric(f"chunk_hit@{k}")
        summary[f"best_chunk_iou@{k}"] = mean_metric(f"best_chunk_iou@{k}")
        summary[f"chunk_temporal_recall@{k}"] = mean_metric(f"chunk_temporal_recall@{k}")
        summary[f"frame_hit@{k}"] = mean_metric(f"frame_hit@{k}")
        summary[f"frame_hit_with_tolerance@{k}"] = mean_metric(f"frame_hit_with_tolerance@{k}")
        distances = [
            float(row["metrics"][f"best_frame_distance_sec@{k}"])
            for row in rows
            if isinstance(row.get("metrics"), dict)
            and isinstance(row["metrics"].get(f"best_frame_distance_sec@{k}"), (int, float))
        ]
        summary[f"mean_best_frame_distance_sec@{k}"] = (
            sum(distances) / len(distances) if distances else None
        )
        summary[f"best_frame_distance_observation_count@{k}"] = len(distances)
    return summary


def evaluate_media_frame_alignment_corpus(
    gold_samples: Sequence[MediaGoldSample],
    stage4_root: Path | str,
    *,
    dataset: str,
    k_values: Sequence[int] = (1, 3, 5, 10),
    frame_tolerance_sec: float = 2.0,
    fallback_window_sec: float = 60.0,
    max_windows_per_media: Optional[int] = None,
) -> dict[str, Any]:
    stage4_root = Path(stage4_root)
    k_values = sorted({int(k) for k in k_values if int(k) > 0})
    max_k = max(k_values) if k_values else 0
    items, generation_stats = make_media_frame_alignment_eval_items(
        gold_samples,
        dataset=dataset,
        max_windows_per_media=max_windows_per_media,
        fallback_window_sec=fallback_window_sec,
    )

    media_ids = sorted({item.media_id for item in items})
    chunks_by_media: dict[str, list[PredictedMediaChunk]] = {}
    missing_predictions: list[str] = []
    for media_id in media_ids:
        doc_dir = stage4_root / media_id
        if not doc_dir.exists():
            missing_predictions.append(media_id)
            continue
        chunks_by_media[media_id] = load_predicted_chunks(doc_dir)

    rows: list[dict[str, Any]] = []
    skipped_missing_prediction_items = 0
    for item in items:
        chunks = chunks_by_media.get(item.media_id)
        if chunks is None:
            skipped_missing_prediction_items += 1
            continue
        ranked = rank_media_chunks_lexical(item.query, chunks)
        ranked_top = ranked[:max_k] if max_k else ranked
        retrieved_chunks = [chunk for chunk, _ in ranked_top]
        metrics = score_frame_alignment_retrieval(
            item=item,
            retrieved_chunks=retrieved_chunks,
            k_values=k_values,
            frame_tolerance_sec=frame_tolerance_sec,
        )
        no_frame_candidate = not any(chunk.associated_frame_times for chunk in retrieved_chunks)
        rows.append(
            {
                **asdict(item),
                "metrics": metrics,
                "no_frame_candidate": no_frame_candidate,
                "retrieved_chunks": [
                    _retrieved_chunk_report_row(rank=rank, chunk=chunk, score=score)
                    for rank, (chunk, score) in enumerate(ranked_top, start=1)
                ],
            }
        )

    summary = _summarize_frame_alignment_rows(rows, k_values=k_values)
    summary.update(
        {
            "gold_sample_count": len(gold_samples),
            "item_count": len(items),
            "missing_prediction_doc_count": len(missing_predictions),
            "skipped_missing_prediction_item_count": skipped_missing_prediction_items,
            "skipped_empty_text_count": generation_stats["skipped_empty_text_count"],
        }
    )
    return {
        "weak_ground_truth_type": "transcript_timestamp_window",
        "description": (
            "Weak frame alignment diagnostic: quote-style gold transcript queries "
            "retrieve transcript chunks, then chunk timestamps and associated frame "
            "timestamps are scored against gold transcript windows. This is not "
            "visual semantic ground truth."
        ),
        "retrieval": {
            "method": "in_script_bm25_lexical_baseline",
            "scope": "within_gold_media_id",
        },
        "summary": summary,
        "missing_prediction_docs": missing_predictions,
        "item_generation": generation_stats,
        "per_item_rows": rows,
    }


def write_media_report(path: Path | str, report: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def write_media_eval_items_jsonl(path: Path | str, items: Iterable[MediaEvalItem]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")
