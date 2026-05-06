"""Run media-intelligence evaluation against Stage 4 media outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.paths import workspace_paths_for_user
from src.evaluation.media_intelligence import (
    discover_mitfld_gold_samples,
    evaluate_media_corpus,
    load_ocw_webvtt_gold,
    write_media_report,
)


def _load_ocw_manifest(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else payload
    samples = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        media_id = str(item.get("media_id") or item.get("id") or "").strip()
        vtt_path = str(item.get("vtt_path") or "").strip()
        if not media_id or not vtt_path:
            continue
        samples.append(
            load_ocw_webvtt_gold(
                media_id=media_id,
                vtt_path=Path(vtt_path),
                source_video_path=str(item.get("video_path") or item.get("video_url") or "") or None,
            )
        )
    return samples


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
    parser.add_argument("--stage4-root", default=str(paths.rag_ready_dir))
    parser.add_argument(
        "--output-dir",
        default=str(paths.output_dir / "evaluation" / "media_intelligence_eval"),
    )
    parser.add_argument("--max-videos", type=int, default=None)
    parser.add_argument("--fallback-window-sec", type=float, default=60.0)
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

    report = evaluate_media_corpus(
        samples,
        args.stage4_root,
        fallback_window_sec=args.fallback_window_sec,
    )
    report["config"] = {
        "dataset": args.dataset,
        "gold_root": str(Path(args.gold_root).resolve()) if args.dataset == "mitfld" else None,
        "ocw_manifest": str(Path(args.ocw_manifest).resolve()) if args.ocw_manifest else None,
        "stage4_root": str(Path(args.stage4_root).resolve()),
        "fallback_window_sec": args.fallback_window_sec,
        "gold_sample_count": len(samples),
    }
    out_dir = Path(args.output_dir)
    write_media_report(out_dir / "media_eval_report.json", report)
    print(
        json.dumps(
            {
                "output": str((out_dir / "media_eval_report.json").resolve()),
                "gold_sample_count": len(samples),
                "evaluated_documents": report["summary"]["document_count"],
                "missing_predictions": len(report["missing_predictions"]),
                "summary": report["summary"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
