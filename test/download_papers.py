#!/usr/bin/env python3
"""
Batch PDF downloader with smart naming for arXiv, ACL Anthology, CVF (CVPR/NeurIPS/ICCV/ECCV openaccess),
ACM DL, and AAAI OJS links. Produces a CSV log and a concise end-of-run report.

Usage:
    python download_papers.py --out downloads

Design notes (simple, clean pattern):
- PaperDownloader orchestrates the flow.
- NameResolver encapsulates per-domain naming heuristics with small strategy functions.
- Robustness: retries, content checks, fallbacks to generic names, detailed error logging.

Author: (you)
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from slugify import slugify
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tqdm import tqdm


# ====== User-provided URLs (raw; duplicates/whitespace handled in code) ======
RAW_URLS = [
    "https://arxiv.org/pdf/1704.00051",
    "https://arxiv.org/pdf/1906.00300",
    "https://arxiv.org/pdf/1911.00172",
    "https://arxiv.org/pdf/2002.08909",
    "https://arxiv.org/pdf/2005.11401",
    " https://arxiv.org/pdf/2004.04906 ",
    "https://aclanthology.org/2021.naacl-main.466.pdf",
    "https://arxiv.org/pdf/2110.07367",
    "https://aclanthology.org/2021.emnlp-main.75.pdf",
    "https://arxiv.org/pdf/2112.09118",
    "https://arxiv.org/pdf/2112.07899 ",
    "https://arxiv.org/pdf/2112.01488",
    "https://arxiv.org/pdf/2107.05720",
    "https://arxiv.org/pdf/2109.10086",
    "https://arxiv.org/pdf/2106.05346",
    "https://arxiv.org/pdf/2009.12756",
    "https://arxiv.org/pdf/2007.01282",
    "https://arxiv.org/pdf/2110.04330",
    "https://arxiv.org/pdf/2209.14290",
    "https://arxiv.org/pdf/2112.04426",
    "https://arxiv.org/pdf/2212.02027",
    "https://aclanthology.org/2022.naacl-main.194.pdf",
    "https://aclanthology.org/2021.acl-long.316.pdf",
    "https://arxiv.org/pdf/2210.03350",
    "https://arxiv.org/pdf/2210.03629",
    "https://arxiv.org/pdf/2112.09332",
    "https://arxiv.org/pdf/2212.10496",
    "https://arxiv.org/pdf/2305.06983",
    " https://arxiv.org/pdf/2403.14403",
    "https://arxiv.org/pdf/2406.19215",
    "https://aclanthology.org/2024.acl-long.702.pdf",
    "https://arxiv.org/pdf/2310.11511",
    "https://arxiv.org/pdf/2401.15884",
    "https://aclanthology.org/2024.findings-emnlp.607.pdf",
    "https://arxiv.org/pdf/2404.10198v1",
    "https://proceedings.neurips.cc/paper_files/paper/2024/file/db93ccb6cf392f352570dd5af0a223d3-Paper-Conference.pdf",
    "https://aclanthology.org/2023.emnlp-main.825.pdf",
    "https://arxiv.org/pdf/2409.13385",
    "https://dl.acm.org/doi/pdf/10.1145/3673791.3698416",
    "https://arxiv.org/pdf/2411.00689v1",
    "https://arxiv.org/pdf/2404.16130",
    "https://arxiv.org/pdf/2405.16506",
    "https://arxiv.org/pdf/2406.15319",
    "https://arxiv.org/pdf/2407.16833",
    "https://arxiv.org/pdf/2501.09136v2",
    "https://arxiv.org/pdf/2506.10408v1",
    "https://arxiv.org/pdf/2502.12442",
    "https://arxiv.org/pdf/2503.10677",
    "https://arxiv.org/pdf/2506.00054v1",
    "https://arxiv.org/pdf/2506.08938",
    "https://arxiv.org/pdf/2407.01796",
    "https://arxiv.org/pdf/2504.15629",
    "https://arxiv.org/pdf/2507.04480",
    "https://arxiv.org/pdf/2506.01829v1",
    "https://aclanthology.org/2024.naacl-long.20.pdf",
    "https://arxiv.org/pdf/2504.14891",
    "https://arxiv.org/pdf/2506.14412v2",
    "https://arxiv.org/pdf/2502.14802",
    "https://arxiv.org/pdf/2409.05591v3",
    "https://arxiv.org/pdf/2504.19413",
    "https://arxiv.org/pdf/2507.07957",
    "https://arxiv.org/pdf/2507.03724",
    "https://arxiv.org/pdf/1809.01124",
    "https://arxiv.org/pdf/1906.00067",
    "https://arxiv.org/pdf/2109.04014",
    "https://openaccess.thecvf.com/content/CVPR2022/papers/Gao_Transform-Retrieve-Generate_Natural_Language-Centric_Outside-Knowledge_Visual_Question_Answering_CVPR_2022_paper.pdf",
    "https://arxiv.org/pdf/2210.03809",
    "https://arxiv.org/pdf/2103.00020",
    "https://arxiv.org/pdf/2102.05918",
    "https://arxiv.org/pdf/2103.00020",
    "https://arxiv.org/pdf/2102.05918",
    "https://arxiv.org/pdf/2212.05221",
    "https://aclanthology.org/2023.eacl-main.266.pdf",
    "https://openaccess.thecvf.com/content/CVPR2024/papers/Li_EVCap_Retrieval-Augmented_Image_Captioning_with_External_Visual-Name_Memory_for_Open-World_CVPR_2024_paper.pdf",
    "https://aclanthology.org/2022.emnlp-main.772.pdf",
    "https://arxiv.org/pdf/2309.17133",
    "https://arxiv.org/pdf/2410.10594",
    "https://arxiv.org/pdf/2406.19150v1",
    "https://arxiv.org/pdf/2412.01115v1",
    "https://openaccess.thecvf.com/content/CVPR2024/papers/Li_EVCap_Retrieval-Augmented_Image_Captioning_with_External_Visual-Name_Memory_for_Open-World_CVPR_2024_paper.pdf",
    "https://openaccess.thecvf.com/content/CVPR2023/papers/Girdhar_ImageBind_One_Embedding_Space_To_Bind_Them_All_CVPR_2023_paper.pdf",
    "https://arxiv.org/pdf/2410.13085",
    "https://arxiv.org/pdf/2505.17471",
    "https://arxiv.org/pdf/2504.04988",
    "https://arxiv.org/pdf/2502.01549",
    "https://arxiv.org/pdf/2505.23990",
    "https://arxiv.org/pdf/2504.09795",
    "https://ojs.aaai.org/index.php/AAAI/article/view/34653/36808",
    "https://arxiv.org/pdf/2502.16636v2",
    "https://arxiv.org/pdf/2502.17297",
    "https://arxiv.org/pdf/2504.08748",
]


# ====== Utilities ======

PDF_EXT = ".pdf"

ARXIV_ID_RE = re.compile(r"(?:arxiv\.org)/(?:pdf|abs)/([0-9]{4}\.[0-9]{4,5})(v\d+)?", re.I)
ACL_ID_RE = re.compile(r"aclanthology\.org/([0-9]{4}\.[a-z-]+?\.\d+)", re.I)
CVF_PAPER_RE = re.compile(r"/papers/([^/]+?)_paper\.pdf$", re.I)
CVF_PATH_TITLE_RE = re.compile(r"/content/[^/]+/papers/([^/]+?)_paper\.pdf$", re.I)
ACM_DOI_RE = re.compile(r"/doi/(?:pdf/)?(10\.\d{4,9}/[^\s/?#]+)", re.I)
AAAI_VIEW_RE = re.compile(r"/article/view/(\d+)", re.I)


def is_probably_pdf_bytes(data: bytes) -> bool:
    """Quick PDF sniff: most PDFs start with '%PDF' signature."""
    return data[:4] == b"%PDF"


def ensure_unique_path(path: str) -> str:
    """Append numeric suffix if file exists."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    k = 2
    while True:
        candidate = f"{base} ({k}){ext}"
        if not os.path.exists(candidate):
            return candidate
        k += 1


@dataclass
class DownloadResult:
    url: str
    ok: bool
    filepath: Optional[str]
    reason: Optional[str]
    http_status: Optional[int]


class NameResolver:
    """Domain-aware naming strategies with graceful fallbacks."""

    def __init__(self, session: requests.Session):
        self.session = session

    def for_url(self, url: str, pdf_bytes: Optional[bytes], headers: Dict[str, str]) -> str:
        """Return a safe filename stem (without extension)."""
        netloc = urllib.parse.urlparse(url).netloc.lower()
        # Dispatch by domain
        if "arxiv.org" in netloc:
            name = self._name_from_arxiv(url)
            if name:
                return name
        if "aclanthology.org" in netloc:
            name = self._name_from_acl(url)
            if name:
                return name
        if "openaccess.thecvf.com" in netloc or "proceedings.neurips.cc" in netloc:
            name = self._name_from_cvf_style(url)
            if name:
                return name
        if "dl.acm.org" in netloc:
            name = self._name_from_acm(url, headers)
            if name:
                return name
        if "ojs.aaai.org" in netloc or "aaai.org" in netloc:
            name = self._name_from_aaai(url)
            if name:
                return name

        # Fallbacks:
        # 1) PDF metadata title (if present)
        if pdf_bytes:
            try:
                title = self._title_from_pdf_bytes(pdf_bytes)
                if title:
                    return slugify(title)[:180]
            except Exception:
                pass
        # 2) Content-Disposition filename header
        cd = headers.get("content-disposition", "")
        m = re.search(r'filename="?([^";]+)"?', cd, flags=re.I)
        if m:
            return slugify(os.path.splitext(m.group(1))[0])[:180]
        # 3) URL path fallback
        path = urllib.parse.urlparse(url).path
        tail = os.path.basename(path).replace("_paper", "").replace("_", " ").strip()
        tail = re.sub(r"\.pdf$", "", tail, flags=re.I) or "document"
        return slugify(tail)[:180]

    # ---- Specific strategies ----

    def _name_from_arxiv(self, url: str) -> Optional[str]:
        m = ARXIV_ID_RE.search(url)
        if not m:
            return None
        arx_id, ver = m.group(1), (m.group(2) or "")
        abs_url = f"https://arxiv.org/abs/{arx_id}"
        try:
            html = self._get_text(abs_url)
            soup = BeautifulSoup(html, "lxml")
            title = soup.find("meta", attrs={"name": "citation_title"})
            date = soup.find("meta", attrs={"name": "citation_date"})
            year = ""
            if date and date.get("content"):
                year = re.search(r"\d{4}", date["content"]).group(0) if re.search(r"\d{4}", date["content"]) else ""
            title_txt = title["content"].strip() if title and title.get("content") else f"arXiv {arx_id}{ver}"
            # Example: "2024 - Title - arXiv-2407.12345v1"
            stem = f"{(year + ' - ') if year else ''}{title_txt} - arXiv-{arx_id}{ver}"
            return slugify(stem)[:180]
        except Exception:
            return None

    def _name_from_acl(self, url: str) -> Optional[str]:
        # ACL: https://aclanthology.org/ID.pdf -> scrape landing page /ID
        m = ACL_ID_RE.search(url)
        paper_id = m.group(1) if m else None
        page_url = f"https://aclanthology.org/{paper_id}" if paper_id else url.replace(".pdf", "")
        try:
            html = self._get_text(page_url)
            soup = BeautifulSoup(html, "lxml")
            title = soup.find("meta", attrs={"name": "citation_title"})
            year = soup.find("meta", attrs={"name": "citation_year"})
            t = title["content"].strip() if title and title.get("content") else None
            y = year["content"].strip() if year and year.get("content") else ""
            if t:
                stem = f"{(y + ' - ') if y else ''}{t} - ACLAnthology-{paper_id or ''}".strip()
                return slugify(stem)[:180]
        except Exception:
            return None
        return None

    def _name_from_cvf_style(self, url: str) -> Optional[str]:
        # CVF OpenAccess usually embeds title in filename before "_paper.pdf"
        path = urllib.parse.urlparse(url).path
        m = CVF_PAPER_RE.search(path) or CVF_PATH_TITLE_RE.search(path)
        if not m:
            # NeurIPS proceedings url includes a hash; keep hash suffix in name
            tail = os.path.basename(path)
            tail = re.sub(r"\.pdf$", "", tail, flags=re.I)
            if tail:
                return slugify(tail)[:180]
            return None
        raw = m.group(1)
        # Often formatted like: "Author_Title_Venue_Year"
        parts = raw.split("_")
        # Heuristic: title is everything between first and last 2 tokens if last looks like VENUE_YEAR
        if len(parts) >= 3 and re.match(r"[A-Z]{3,5}\d{4}", parts[-1]) or re.match(r"\d{4}", parts[-1]):
            title = " ".join(parts[1:-1]) or raw
        else:
            title = " ".join(parts[1:]) or raw
        return slugify(title)[:180]

    def _name_from_acm(self, url: str, headers: Dict[str, str]) -> Optional[str]:
        # Try Content-Disposition first
        cd = headers.get("content-disposition", "")
        m = re.search(r'filename="?([^";]+)"?', cd, flags=re.I)
        if m:
            return slugify(os.path.splitext(m.group(1))[0])[:180]
        # Else scrape DOI landing page meta
        m = ACM_DOI_RE.search(url)
        doi = m.group(1) if m else None
        if not doi:
            return None
        try:
            landing = f"https://dl.acm.org/doi/{urllib.parse.quote(doi)}"
            html = self._get_text(landing)
            soup = BeautifulSoup(html, "lxml")
            title = soup.find("meta", attrs={"name": "citation_title"})
            year = soup.find("meta", attrs={"name": "citation_date"})
            t = title["content"].strip() if title and title.get("content") else None
            y = ""
            if year and year.get("content"):
                ym = re.search(r"\d{4}", year["content"])
                y = ym.group(0) if ym else ""
            if t:
                stem = f"{(y + ' - ') if y else ''}{t} - ACM-DL"
                return slugify(stem)[:180]
        except Exception:
            return None
        return None

    def _name_from_aaai(self, url: str) -> Optional[str]:
        # OJS PDFs often are /article/view/<id>/<fileid>; landing page is /article/view/<id>
        m = AAAI_VIEW_RE.search(url)
        art_id = m.group(1) if m else None
        if not art_id:
            return None
        try:
            landing = f"https://ojs.aaai.org/index.php/AAAI/article/view/{art_id}"
            html = self._get_text(landing)
            soup = BeautifulSoup(html, "lxml")
            title = soup.find("meta", attrs={"name": "citation_title"})
            year = soup.find("meta", attrs={"name": "citation_date"})
            t = title["content"].strip() if title and title.get("content") else None
            y = ""
            if year and year.get("content"):
                ym = re.search(r"\d{4}", year["content"])
                y = ym.group(0) if ym else ""
            if t:
                stem = f"{(y + ' - ') if y else ''}{t} - AAAI"
                return slugify(stem)[:180]
        except Exception:
            return None
        return None

    def _get_text(self, url: str) -> str:
        # Simple GET with headers (no heavy retry; caller is best-effort)
        resp = self.session.get(url, timeout=20)
        resp.raise_for_status()
        return resp.text

    @staticmethod
    def _title_from_pdf_bytes(pdf_bytes: bytes) -> Optional[str]:
        """Try reading PDF metadata (Title) or first page text for a sensible name."""
        reader = PdfReader(io.BytesIO(pdf_bytes))
        # 1) Document metadata title
        meta = reader.metadata or {}
        title = None
        if meta:
            # Different keys possible across PDFs
            title = meta.get("/Title") or meta.get("Title")
            if title:
                title = title.strip()
        # 2) First page text as last resort (shortened)
        if not title:
            first = reader.pages[0]
            text = (first.extract_text() or "").strip().splitlines()
            if text:
                # Heuristic: first non-empty line as title candidate
                for line in text:
                    l = line.strip()
                    if len(l) > 8:
                        title = l
                        break
        return title


class PaperDownloader:
    """Coordinates downloading and naming; writes log and prints a summary."""

    def __init__(self, out_dir: str, max_retries: int = 3):
        self.out_dir = out_dir
        os.makedirs(self.out_dir, exist_ok=True)

        # Configure a single Session with default headers.
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) PDFFetcher/1.0 (+https://example.org)",
            "Accept": "application/pdf,application/octet-stream;q=0.9,text/html;q=0.8,*/*;q=0.5",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.resolver = NameResolver(self.session)
        self.max_retries = max_retries
        self.results: List[DownloadResult] = []

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((requests.RequestException, requests.Timeout)),
    )
    def _get(self, url: str) -> requests.Response:
        # Stream = False (we need content for verification + naming fallbacks).
        return self.session.get(url, timeout=40, allow_redirects=True)

    def download_one(self, url: str) -> DownloadResult:
        url = url.strip()
        if not url:
            return DownloadResult(url=url, ok=False, filepath=None, reason="empty-url", http_status=None)
        try:
            resp = self._get(url)
            status = resp.status_code
            if status != 200:
                return DownloadResult(url=url, ok=False, filepath=None, reason=f"http-{status}", http_status=status)

            data = resp.content
            ctype = (resp.headers.get("Content-Type") or "").lower()

            # Some sources deliver HTML errors; verify PDF signature or content-type
            if ("pdf" not in ctype) and not is_probably_pdf_bytes(data):
                # Try a secondary URL tweak for arXiv missing .pdf extension
                if "arxiv.org" in url and not url.endswith(".pdf"):
                    alt = url + ".pdf"
                    resp2 = self._get(alt)
                    data = resp2.content
                    status = resp2.status_code
                    ctype = (resp2.headers.get("Content-Type") or "").lower()
                    if status != 200 or (("pdf" not in ctype) and not is_probably_pdf_bytes(data)):
                        return DownloadResult(url=url, ok=False, filepath=None,
                                              reason="not-pdf-content", http_status=status)
                else:
                    return DownloadResult(url=url, ok=False, filepath=None,
                                          reason="not-pdf-content", http_status=status)

            # Suggest a human-friendly filename (no extension)
            stem = self.resolver.for_url(url, data, {k.lower(): v for k, v in resp.headers.items()})
            if not stem:
                stem = slugify(os.path.basename(urllib.parse.urlparse(url).path).replace(".pdf", "")) or "document"
            filename = stem[:200] + PDF_EXT
            filepath = ensure_unique_path(os.path.join(self.out_dir, filename))

            # Write file to disk
            with open(filepath, "wb") as f:
                f.write(data)

            return DownloadResult(url=url, ok=True, filepath=filepath, reason=None, http_status=status)

        except requests.RequestException as e:
            return DownloadResult(url=url, ok=False, filepath=None, reason=f"network-error: {e.__class__.__name__}", http_status=None)
        except Exception as e:
            return DownloadResult(url=url, ok=False, filepath=None, reason=f"other-error: {e.__class__.__name__}", http_status=None)

    def run(self, urls: List[str]) -> None:
        # Deduplicate and normalize URLs
        seen = set()
        clean_urls = []
        for u in urls:
            u = (u or "").strip()
            if not u:
                continue
            # Normalize redundant spaces and strip tracking params
            parsed = urllib.parse.urlparse(u)
            # Keep query for ACM pdf (?download=) but drop fragments
            norm = urllib.parse.urlunparse(parsed._replace(fragment=""))
            if norm not in seen:
                seen.add(norm)
                clean_urls.append(norm)

        print(f"[Info] Downloading {len(clean_urls)} unique URLs...")
        time.sleep(0.2)

        for url in tqdm(clean_urls, desc="Fetching PDFs", unit="file"):
            res = self.download_one(url)
            self.results.append(res)
            # Gentle politeness delay to avoid hammering hosts
            time.sleep(0.25)

        self._write_log()
        self._print_summary()

    def _write_log(self) -> None:
        log_path = os.path.join(self.out_dir, "download_log.csv")
        with open(log_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["url", "ok", "filepath", "reason", "http_status"])
            for r in self.results:
                w.writerow([r.url, r.ok, r.filepath or "", r.reason or "", r.http_status or ""])
        print(f"[Info] Wrote log: {log_path}")

    def _print_summary(self) -> None:
        total = len(self.results)
        ok = sum(1 for r in self.results if r.ok)
        fail = total - ok
        print("\n====== Download Summary ======")
        print(f"Total: {total} | Success: {ok} | Failed: {fail}")
        if fail:
            # Aggregate reasons
            reasons: Dict[str, int] = {}
            for r in self.results:
                if not r.ok:
                    reasons[r.reason or "unknown"] = reasons.get(r.reason or "unknown", 0) + 1
            print("Failure reasons:")
            for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
                print(f"  - {reason}: {count}")
            print("\nExamples of failures:")
            shown = 0
            for r in self.results:
                if not r.ok and shown < 10:
                    print(f"  * {r.url} -> {r.reason}")
                    shown += 1
        print("=============================\n")


def main():
    parser = argparse.ArgumentParser(description="Download PDFs from a list of URLs with smart naming.")
    parser.add_argument("--out", type=str, default="downloads", help="Output folder (default: downloads)")
    args = parser.parse_args()

    dl = PaperDownloader(out_dir=args.out)
    dl.run(RAW_URLS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Interrupted] Exiting.")
        sys.exit(130)
