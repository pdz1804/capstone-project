"""Download a size-bounded MITFLD subset without pulling the full dataset."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


REPO_ID = "robotwang/MITFLD"
API_ROOT = f"https://huggingface.co/api/datasets/{REPO_ID}/tree/main"


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(BACKEND_ROOT / "data" / "mitfld_eval_subset"))
    parser.add_argument("--max-video-mb", type=float, default=100.0)
    parser.add_argument("--max-videos", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError("huggingface_hub is required; install huggingface_hub first.") from exc

    output_dir = Path(args.output_dir)
    videos = sorted(_tree_files("videos"), key=_file_size)
    transcripts = {_video_id(item["path"]) for item in _tree_files("transcripts")}
    frags = {_video_id(item["path"]) for item in _tree_files("frags")}

    selected: list[dict[str, Any]] = []
    for item in videos:
        size_mb = _file_size(item) / 1024 / 1024
        video_id = _video_id(item["path"])
        if size_mb > args.max_video_mb:
            continue
        if video_id not in transcripts or video_id not in frags:
            continue
        selected.append(
            {
                "video_id": video_id,
                "video_path": item["path"],
                "size_mb": round(size_mb, 3),
                "transcript_path": f"transcripts/{video_id}.json",
                "frag_path": f"frags/{video_id}.json",
            }
        )
        if args.max_videos is not None and len(selected) >= args.max_videos:
            break

    files: list[str] = ["README.md", "video_id_list.txt"]
    for row in selected:
        files.extend([row["video_path"], row["transcript_path"], row["frag_path"]])

    manifest = {
        "repo_id": REPO_ID,
        "max_video_mb": args.max_video_mb,
        "video_count": len(selected),
        "total_video_gb": round(sum(row["size_mb"] for row in selected) / 1024, 3),
        "videos": selected,
        "files": files,
    }

    print(json.dumps({k: manifest[k] for k in ("repo_id", "max_video_mb", "video_count", "total_video_gb")}, indent=2))
    if args.dry_run:
        print("\n".join(files))
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    for idx, rel in enumerate(files, start=1):
        target = output_dir / rel
        if target.exists() and target.stat().st_size > 0:
            print(f"[{idx}/{len(files)}] exists {rel}", flush=True)
            continue
        print(f"[{idx}/{len(files)}] downloading {rel}", flush=True)
        hf_hub_download(repo_id=REPO_ID, repo_type="dataset", filename=rel, local_dir=str(output_dir))
    (output_dir / "subset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(str(output_dir.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
