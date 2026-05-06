"""Run weak frame-alignment evaluation against Stage 4 media outputs."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.paths import workspace_paths_for_user
from evals.parsing.media.run_media_eval import _load_ocw_manifest
from src.evaluation.media_intelligence import (
    discover_mitfld_gold_samples,
    evaluate_media_frame_alignment_corpus,
    frame_distance_to_window,
    write_media_report,
)


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".webp"}:
        return "image/webp"
    return "image/jpeg"


def _image_data_url(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{_mime_type(path)};base64,{data}"


def _resolve_frame_path(raw_path: str, *, stage4_root: Path, media_id: str) -> Path | None:
    if not raw_path:
        return None
    raw = Path(raw_path)
    candidates = []
    candidates.append(stage4_root / media_id / "frames" / raw.name)
    candidates.append(stage4_root / media_id / raw.name)
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(Path.cwd() / raw)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _select_visual_candidate(row: dict[str, Any], *, stage4_root: Path) -> dict[str, Any] | None:
    start = float(row["gold_start_time"])
    end = float(row["gold_end_time"])
    media_id = str(row["media_id"])
    candidates: list[dict[str, Any]] = []
    for retrieved in row.get("retrieved_chunks") or []:
        rank = int(retrieved.get("rank") or 0)
        for frame in retrieved.get("associated_frames") or []:
            ts = frame.get("video_timestamp")
            if not isinstance(ts, (int, float)):
                continue
            resolved = _resolve_frame_path(
                str(frame.get("frame_path") or ""),
                stage4_root=stage4_root,
                media_id=media_id,
            )
            if resolved is None:
                continue
            candidates.append(
                {
                    "retrieved_chunk_rank": rank,
                    "frame_path": str(resolved),
                    "frame_index": frame.get("frame_index"),
                    "frame_name": frame.get("frame_name"),
                    "video_timestamp": float(ts),
                    "distance_to_gold_window_sec": frame_distance_to_window(float(ts), start, end),
                }
            )
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item["distance_to_gold_window_sec"], item["retrieved_chunk_rank"]))
    return candidates[0]


def _extract_json_object(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {"raw_response": text}
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                payload = json.loads(text[start : end + 1])
                return payload if isinstance(payload, dict) else {"raw_response": text}
            except Exception:
                pass
    return {"raw_response": text}


def _judge_frame_with_openai(
    *,
    client: Any,
    model: str,
    frame_path: Path,
    query: str,
    gold_excerpt: str,
    timestamp: float,
    window: tuple[float, float],
) -> dict[str, Any]:
    prompt = f"""
You are evaluating a video frame retrieved for a lecture query.

Return valid JSON only with:
- visual_match: one of "yes", "partial", "no", "unclear"
- confidence: number from 0 to 1
- rationale: short explanation grounded only in visible frame content
- visible_evidence: short list of visible objects/text/slide cues

Question/query:
{query}

Gold transcript excerpt for the target moment:
{gold_excerpt}

Candidate frame timestamp: {timestamp:.2f}s
Gold timestamp window: {window[0]:.2f}s to {window[1]:.2f}s

Judge whether the image visually matches the query/excerpt. Do not assume correctness from timestamps alone.
"""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Return valid JSON only. Evaluate visible image evidence, not timestamp metadata.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": _image_data_url(frame_path), "detail": "high"},
                    },
                ],
            },
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    return _extract_json_object(content)


def add_openai_vision_judgements(
    report: dict[str, Any],
    *,
    stage4_root: Path,
    model: str,
    api_key: str | None,
    max_items: int | None,
) -> dict[str, Any]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is required for --vision-judge.") from exc
    resolved_key = api_key or os.getenv("OPENAI_API_KEY")
    if not resolved_key:
        raise RuntimeError("OPENAI_API_KEY is required for --vision-judge.")

    client = OpenAI(api_key=resolved_key)
    judged = 0
    skipped_no_frame = 0
    failures: list[dict[str, Any]] = []
    for row in report.get("per_item_rows") or []:
        if max_items is not None and judged >= max_items:
            row["vision_judgement"] = {"status": "not_run", "reason": "max_items_reached"}
            continue
        candidate = _select_visual_candidate(row, stage4_root=stage4_root)
        if candidate is None:
            skipped_no_frame += 1
            row["vision_judgement"] = {"status": "skipped", "reason": "no_resolvable_frame_candidate"}
            continue
        try:
            verdict = _judge_frame_with_openai(
                client=client,
                model=model,
                frame_path=Path(candidate["frame_path"]),
                query=str(row["query"]),
                gold_excerpt=str(row["gold_excerpt"]),
                timestamp=float(candidate["video_timestamp"]),
                window=(float(row["gold_start_time"]), float(row["gold_end_time"])),
            )
            row["vision_judgement"] = {
                "status": "judged",
                "model": model,
                "candidate": candidate,
                "verdict": verdict,
            }
            judged += 1
        except Exception as exc:
            failure = {"sample_id": row.get("sample_id"), "error": str(exc)}
            failures.append(failure)
            row["vision_judgement"] = {
                "status": "failed",
                "candidate": candidate,
                "error": str(exc),
            }

    report["vision_judge"] = {
        "enabled": True,
        "provider": "openai",
        "model": model,
        "max_items": max_items,
        "judged_item_count": judged,
        "skipped_no_resolvable_frame_count": skipped_no_frame,
        "failure_count": len(failures),
        "failures": failures,
        "note": "Visual judgement uses the candidate frame image. It is separate from timestamp-only weak GT metrics.",
    }
    return report


def build_parser() -> argparse.ArgumentParser:
    paths = workspace_paths_for_user()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        choices=["mitfld", "ocw"],
        default="mitfld",
        help="Ground-truth source format.",
    )
    parser.add_argument(
        "--gold-root",
        default=str(BACKEND_ROOT / "data" / "mitfld_eval_subset"),
        help="MITFLD subset root when --dataset mitfld.",
    )
    parser.add_argument(
        "--ocw-manifest",
        default=None,
        help="Manifest produced by scrape_ocw_media_eval_sources.py when --dataset ocw.",
    )
    parser.add_argument(
        "--stage4-root",
        default=str(paths.rag_ready_dir),
        help="Stage 4 media document root containing one directory per media_id.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(paths.output_dir / "evaluation" / "media_frame_alignment_eval"),
    )
    parser.add_argument("--max-videos", type=int, default=None)
    parser.add_argument("--media-id", action="append", default=None, help="Limit evaluation to one or more media IDs.")
    parser.add_argument("--max-windows-per-media", type=int, default=None)
    parser.add_argument("--fallback-window-sec", type=float, default=60.0)
    parser.add_argument("--top-k", type=int, nargs="+", default=[1, 3, 5, 10])
    parser.add_argument("--frame-tolerance-sec", type=float, default=2.0)
    parser.add_argument("--vision-judge", action="store_true", help="Ask an OpenAI vision model to judge selected frame images.")
    parser.add_argument("--vision-model", default=os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini"))
    parser.add_argument("--vision-max-items", type=int, default=None)
    parser.add_argument("--openai-api-key", default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.dataset == "mitfld":
        samples = discover_mitfld_gold_samples(args.gold_root, max_videos=args.max_videos)
    else:
        if not args.ocw_manifest:
            raise SystemExit("--ocw-manifest is required when --dataset ocw")
        samples = _load_ocw_manifest(Path(args.ocw_manifest))
        if args.max_videos is not None:
            samples = samples[: args.max_videos]
    if args.media_id:
        allowed = set(args.media_id)
        samples = [sample for sample in samples if sample.media_id in allowed]

    report = evaluate_media_frame_alignment_corpus(
        samples,
        args.stage4_root,
        dataset=args.dataset,
        k_values=args.top_k,
        frame_tolerance_sec=args.frame_tolerance_sec,
        fallback_window_sec=args.fallback_window_sec,
        max_windows_per_media=args.max_windows_per_media,
    )
    report["config"] = {
        "dataset": args.dataset,
        "gold_root": str(Path(args.gold_root).resolve()) if args.dataset == "mitfld" else None,
        "ocw_manifest": str(Path(args.ocw_manifest).resolve()) if args.ocw_manifest else None,
        "stage4_root": str(Path(args.stage4_root).resolve()),
        "output_dir": str(Path(args.output_dir).resolve()),
        "top_k": args.top_k,
        "frame_tolerance_sec": args.frame_tolerance_sec,
        "fallback_window_sec": args.fallback_window_sec,
        "max_videos": args.max_videos,
        "media_id": args.media_id,
        "max_windows_per_media": args.max_windows_per_media,
        "gold_sample_count": len(samples),
        "vision_judge": args.vision_judge,
        "vision_model": args.vision_model if args.vision_judge else None,
        "vision_max_items": args.vision_max_items if args.vision_judge else None,
    }

    if args.vision_judge:
        report = add_openai_vision_judgements(
            report,
            stage4_root=Path(args.stage4_root),
            model=args.vision_model,
            api_key=args.openai_api_key,
            max_items=args.vision_max_items,
        )

    out_dir = Path(args.output_dir)
    out_path = out_dir / "frame_alignment_eval_report.json"
    write_media_report(out_path, report)
    print(
        json.dumps(
            {
                "output": str(out_path.resolve()),
                "gold_sample_count": len(samples),
                "item_count": report["summary"]["item_count"],
                "evaluated_item_count": report["summary"]["evaluated_item_count"],
                "missing_predictions": len(report["missing_prediction_docs"]),
                "summary": report["summary"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
