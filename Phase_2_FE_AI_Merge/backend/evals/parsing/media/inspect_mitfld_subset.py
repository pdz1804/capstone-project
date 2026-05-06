"""Inspect MITFLD video sizes without downloading video blobs.

This helper reads Hugging Face Hub metadata for robotwang/MITFLD, then
optionally fetches transcript/fragment JSON for videos under a size threshold.
It is intended for choosing a small evaluation subset from the 100GB+ dataset.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


REPO_ID = "robotwang/MITFLD"
API_ROOT = f"https://huggingface.co/api/datasets/{REPO_ID}/tree/main"
RAW_ROOT = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main"


@dataclass(frozen=True)
class VideoRow:
    video_id: str
    path: str
    size_bytes: int
    has_transcript: bool
    has_frag: bool
    duration_sec: float | None = None
    segment_count: int | None = None
    word_count: int | None = None
    frag_count: int | None = None

    @property
    def size_mb(self) -> float:
        return self.size_bytes / 1024 / 1024


def _load_json_url(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _tree_files(path: str) -> list[dict[str, Any]]:
    url = f"{API_ROOT}/{urllib.parse.quote(path)}?recursive=1&expand=true&limit=100"
    out: list[dict[str, Any]] = []
    while url:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            out.extend(item for item in data if item.get("type") == "file")
            link = resp.headers.get("link") or ""
        match = re.search(r'<([^>]+)>; rel="next"', link)
        url = match.group(1) if match else ""
    return out


def _video_id(path: str) -> str:
    return path.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def _file_size(item: dict[str, Any]) -> int:
    lfs = item.get("lfs") if isinstance(item.get("lfs"), dict) else {}
    return int(lfs.get("size") or item.get("size") or 0)


def _raw_json(kind: str, video_id: str) -> Any:
    safe_id = urllib.parse.quote(video_id)
    return _load_json_url(f"{RAW_ROOT}/{kind}/{safe_id}.json")


def _duration_stats(video_id: str) -> dict[str, Any]:
    transcript = _raw_json("transcripts", video_id)
    frags = _raw_json("frags", video_id)
    starts: list[float] = []
    ends: list[float] = []
    words = 0
    if isinstance(transcript, list):
        for seg in transcript:
            if not isinstance(seg, dict):
                continue
            start = float(seg.get("start") or 0)
            duration = float(seg.get("duration") or 0)
            starts.append(start)
            ends.append(start + duration)
            words += len(str(seg.get("text") or "").split())
    return {
        "duration_sec": (max(ends) - min(starts)) if starts and ends else 0.0,
        "segment_count": len(transcript) if isinstance(transcript, list) else 0,
        "word_count": words,
        "frag_count": len(frags) if isinstance(frags, list) else 0,
    }


def inspect(fetch_stats_under_mb: float) -> list[VideoRow]:
    videos = _tree_files("videos")
    transcript_ids = {_video_id(item["path"]) for item in _tree_files("transcripts")}
    frag_ids = {_video_id(item["path"]) for item in _tree_files("frags")}

    rows: list[VideoRow] = []
    for item in videos:
        video_id = _video_id(item["path"])
        base = {
            "video_id": video_id,
            "path": item["path"],
            "size_bytes": _file_size(item),
            "has_transcript": video_id in transcript_ids,
            "has_frag": video_id in frag_ids,
        }
        if base["size_bytes"] / 1024 / 1024 <= fetch_stats_under_mb:
            rows.append(VideoRow(**base, **_duration_stats(video_id)))
        else:
            rows.append(VideoRow(**base))
    return sorted(rows, key=lambda row: row.size_bytes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-video-mb", type=float, default=100.0)
    parser.add_argument("--fetch-stats-under-mb", type=float, default=100.0)
    parser.add_argument("--top", type=int, default=50)
    args = parser.parse_args()

    rows = inspect(args.fetch_stats_under_mb)
    total_gb = sum(row.size_bytes for row in rows) / 1024 / 1024 / 1024
    selected = [row for row in rows if row.size_mb <= args.max_video_mb]
    complete_selected = [row for row in selected if row.has_transcript and row.has_frag]
    durations = [row.duration_sec / 60 for row in selected if row.duration_sec is not None]

    print(
        json.dumps(
            {
                "repo_id": REPO_ID,
                "video_count": len(rows),
                "total_video_gb": round(total_gb, 2),
                "max_video_mb": args.max_video_mb,
                "selected_count": len(selected),
                "selected_with_transcript_and_frag": len(complete_selected),
                "selected_total_gb": round(sum(row.size_bytes for row in selected) / 1024 / 1024 / 1024, 2),
                "selected_duration_min": {
                    "min": round(min(durations), 2) if durations else None,
                    "median": round(statistics.median(durations), 2) if durations else None,
                    "max": round(max(durations), 2) if durations else None,
                },
            },
            indent=2,
        )
    )
    print("\nvideo_id\tsize_mb\tduration_min\tsegments\twords\tfrags\tcomplete_gt")
    for row in selected[: args.top]:
        duration = "" if row.duration_sec is None else f"{row.duration_sec / 60:.1f}"
        complete = row.has_transcript and row.has_frag
        print(
            f"{row.video_id}\t{row.size_mb:.1f}\t{duration}\t"
            f"{row.segment_count or ''}\t{row.word_count or ''}\t{row.frag_count or ''}\t{complete}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
