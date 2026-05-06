"""Generate timestamped media retrieval eval items from gold transcripts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.paths import workspace_paths_for_user
from evals.parsing.media.run_media_eval import _load_ocw_manifest
from src.evaluation.media_intelligence import (
    discover_mitfld_gold_samples,
    make_media_eval_items,
    write_media_eval_items_jsonl,
)


def build_parser() -> argparse.ArgumentParser:
    paths = workspace_paths_for_user()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=["mitfld", "ocw"], default="mitfld")
    parser.add_argument("--gold-root", default=str(BACKEND_ROOT / "data" / "mitfld_eval_subset"))
    parser.add_argument("--ocw-manifest", default=None)
    parser.add_argument("--output-dir", default=str(paths.output_dir / "evaluation" / "media_eval_set"))
    parser.add_argument("--max-videos", type=int, default=None)
    parser.add_argument("--max-windows-per-media", type=int, default=None)
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

    items = make_media_eval_items(
        samples,
        max_windows_per_media=args.max_windows_per_media,
        fallback_window_sec=args.fallback_window_sec,
    )
    out_dir = Path(args.output_dir)
    out_path = out_dir / "media_eval_items.jsonl"
    write_media_eval_items_jsonl(out_path, items)
    manifest = {
        "dataset": args.dataset,
        "gold_root": str(Path(args.gold_root).resolve()) if args.dataset == "mitfld" else None,
        "ocw_manifest": str(Path(args.ocw_manifest).resolve()) if args.ocw_manifest else None,
        "gold_sample_count": len(samples),
        "item_count": len(items),
        "output_jsonl": str(out_path.resolve()),
        "max_windows_per_media": args.max_windows_per_media,
        "fallback_window_sec": args.fallback_window_sec,
    }
    (out_dir / "media_eval_items_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
