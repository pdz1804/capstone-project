"""Scrape MIT OCW resource pages for MP4 and WebVTT evaluation sources.

OCW's "Download transcript" button can point to a PDF without timestamps. The
timestamped ground truth is exposed in the video page HTML as a captions
``<track src="...webvtt">`` element.
"""

from __future__ import annotations

import argparse
import hashlib
import html
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

from src.evaluation.media_intelligence import parse_webvtt


_ATTR_RE = re.compile(r'([a-zA-Z_:-]+)\s*=\s*(".*?"|\'.*?\'|[^\s>]+)', re.DOTALL)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL | re.IGNORECASE)


def _read_url(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 media-eval-scraper"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _attrs(tag: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, raw in _ATTR_RE.findall(tag):
        value = raw.strip().strip('"').strip("'")
        out[key.lower()] = html.unescape(value)
    return out


def _absolute(base_url: str, maybe_url: str) -> str:
    return urllib.parse.urljoin(base_url, html.unescape(maybe_url))


def _media_id(url: str, title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "_", title).strip("_")
    if slug:
        return slug[:90]
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    return f"ocw_{digest}"


def scrape_resource_page(url: str) -> dict[str, Any]:
    text = _read_url(url).decode("utf-8", errors="ignore")
    title_match = _TITLE_RE.search(text)
    title = html.unescape(re.sub(r"\s+", " ", title_match.group(1)).strip()) if title_match else ""

    track_url = ""
    for tag in re.findall(r"<track\b[^>]*>", text, flags=re.IGNORECASE | re.DOTALL):
        attrs = _attrs(tag)
        src = attrs.get("src", "")
        if attrs.get("kind", "").lower() == "captions" and src.lower().endswith((".vtt", ".webvtt")):
            track_url = _absolute(url, src)
            break
        if src.lower().endswith((".vtt", ".webvtt")):
            track_url = _absolute(url, src)
            break

    video_url = ""
    video_match = re.search(r"<video\b[^>]*>", text, flags=re.IGNORECASE | re.DOTALL)
    if video_match:
        attrs = _attrs(video_match.group(0))
        download = attrs.get("data-downloadlink") or attrs.get("src") or ""
        if download:
            video_url = _absolute(url, download)

    youtube_id = ""
    youtube_match = re.search(r"https://www\.youtube\.com/embed/([a-zA-Z0-9_-]+)", text)
    if youtube_match:
        youtube_id = youtube_match.group(1)

    return {
        "media_id": _media_id(url, title or Path(urllib.parse.urlparse(url).path).name),
        "title": title,
        "resource_url": url,
        "video_url": video_url,
        "vtt_url": track_url,
        "youtube_id": youtube_id,
    }


def _download_file(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_read_url(url))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="*", help="MIT OCW resource page URLs.")
    parser.add_argument("--urls-file", default=None, help="One resource URL per line.")
    parser.add_argument("--output-dir", default=str(BACKEND_ROOT / "data" / "ocw_media_eval_sources"))
    parser.add_argument("--download", action="store_true", help="Download MP4 and WebVTT files.")
    parser.add_argument("--skip-missing-vtt", action="store_true", default=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    urls = list(args.urls)
    if args.urls_file:
        urls.extend(
            line.strip()
            for line in Path(args.urls_file).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    if not urls:
        raise SystemExit("Provide at least one OCW resource URL.")

    out_dir = Path(args.output_dir)
    items: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for url in urls:
        item = scrape_resource_page(url)
        if not item.get("vtt_url"):
            skipped.append({"resource_url": url, "reason": "missing_webvtt_track"})
            if args.skip_missing_vtt:
                continue
        if args.download:
            media_dir = out_dir / item["media_id"]
            if item.get("vtt_url"):
                vtt_path = media_dir / f"{item['media_id']}.webvtt"
                _download_file(item["vtt_url"], vtt_path)
                item["vtt_path"] = str(vtt_path.resolve())
                item["caption_segment_count"] = len(parse_webvtt(vtt_path.read_text(encoding="utf-8", errors="ignore")))
            if item.get("video_url"):
                suffix = Path(urllib.parse.urlparse(item["video_url"]).path).suffix or ".mp4"
                video_path = media_dir / f"{item['media_id']}{suffix}"
                _download_file(item["video_url"], video_path)
                item["video_path"] = str(video_path.resolve())
        items.append(item)

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": "mit_ocw_resource_pages",
        "items": items,
        "skipped": skipped,
    }
    manifest_path = out_dir / "ocw_media_sources_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path.resolve()), "items": len(items), "skipped": len(skipped)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
