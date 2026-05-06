#!/usr/bin/env python3
"""Resume-friendly downloader for OmniDocBench page images.

The Hugging Face snapshot downloader can hit Xet token rate limits when it
fetches every image in parallel. This script reads OmniDocBench.json, verifies
which referenced page images are present, optionally syncs files downloaded to
another local directory, and downloads missing files one by one with backoff.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Iterable


DEFAULT_REPO_ID = "opendatalab/OmniDocBench"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gt",
        type=Path,
        default=Path("data/omnidocbench/OmniDocBench.json"),
        help="Path to OmniDocBench.json.",
    )
    parser.add_argument(
        "--local-dir",
        type=Path,
        default=Path("data/omnidocbench"),
        help="Local OmniDocBench directory containing images/.",
    )
    parser.add_argument(
        "--sync-from",
        type=Path,
        action="append",
        default=[],
        help="Additional OmniDocBench local dirs to copy existing images from.",
    )
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download missing images. Without this flag the script only verifies.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Maximum missing images to download in this run.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.75,
        help="Seconds to sleep after each successful file download.",
    )
    parser.add_argument(
        "--backoff",
        type=float,
        default=310.0,
        help="Seconds to sleep after a rate-limit response.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Retries per file before leaving it missing.",
    )
    parser.add_argument(
        "--use-xet",
        action="store_true",
        help="Use Hugging Face Xet transport. Default disables it to reduce token calls.",
    )
    return parser.parse_args()


def load_expected_images(gt_path: Path) -> list[str]:
    data = json.loads(gt_path.read_text(encoding="utf-8"))
    images: list[str] = []
    for page in data:
        page_info = page.get("page_info") or {}
        image_path = page_info.get("image_path")
        if image_path:
            images.append(Path(image_path).name)
    return sorted(set(images))


def existing_images(images_dir: Path) -> set[str]:
    if not images_dir.exists():
        return set()
    return {p.name for p in images_dir.iterdir() if p.is_file() and not p.name.endswith(".incomplete")}


def sync_existing_images(expected: Iterable[str], target_dir: Path, source_dirs: Iterable[Path]) -> int:
    target_images = target_dir / "images"
    target_images.mkdir(parents=True, exist_ok=True)
    copied = 0
    for source_dir in source_dirs:
        source_images = source_dir / "images"
        if not source_images.exists():
            continue
        for name in expected:
            dst = target_images / name
            src = source_images / name
            if not dst.exists() and src.exists() and src.is_file():
                shutil.copy2(src, dst)
                copied += 1
    return copied


def is_rate_limited(exc: BaseException) -> bool:
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    return status_code == 429 or "429" in str(exc) or "Too Many Requests" in str(exc)


def download_missing(args: argparse.Namespace, missing: list[str]) -> tuple[int, int]:
    if not args.use_xet:
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

    from huggingface_hub import hf_hub_download

    limit = len(missing) if args.max_files is None else min(args.max_files, len(missing))
    attempted = missing[:limit]
    ok = 0
    failed = 0
    for idx, name in enumerate(attempted, start=1):
        filename = f"images/{name}"
        for attempt in range(1, args.retries + 1):
            try:
                hf_hub_download(
                    repo_id=args.repo_id,
                    repo_type="dataset",
                    filename=filename,
                    local_dir=str(args.local_dir),
                )
                ok += 1
                print(f"[{idx}/{limit}] downloaded {filename}")
                time.sleep(args.sleep)
                break
            except Exception as exc:  # noqa: BLE001 - CLI should keep going and report failures.
                if is_rate_limited(exc):
                    wait = args.backoff * attempt
                    print(f"[{idx}/{limit}] rate limited on {filename}; sleeping {wait:.0f}s", file=sys.stderr)
                    time.sleep(wait)
                    continue
                print(f"[{idx}/{limit}] failed {filename}: {exc}", file=sys.stderr)
                failed += 1
                break
        else:
            failed += 1
            print(f"[{idx}/{limit}] left missing after retries: {filename}", file=sys.stderr)
    return ok, failed


def main() -> int:
    args = parse_args()
    expected = load_expected_images(args.gt)
    copied = sync_existing_images(expected, args.local_dir, args.sync_from)
    images_dir = args.local_dir / "images"
    present = existing_images(images_dir)
    missing = sorted(set(expected) - present)

    print(f"expected={len(expected)} present={len(present)} missing={len(missing)} copied={copied}")
    if missing:
        print("missing_sample=" + ", ".join(missing[:10]))

    if args.download and missing:
        ok, failed = download_missing(args, missing)
        present_after = existing_images(images_dir)
        missing_after = sorted(set(expected) - present_after)
        print(
            f"downloaded={ok} failed={failed} "
            f"present_after={len(present_after)} missing_after={len(missing_after)}"
        )
        if missing_after:
            print("missing_after_sample=" + ", ".join(missing_after[:10]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
