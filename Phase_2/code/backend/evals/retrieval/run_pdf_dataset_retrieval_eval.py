"""Run PDF-only English retrieval evaluation for the local eval-input dataset.

The runner is intentionally separate from the API/workspace retrieval eval:

1. Discover PDFs under backend/input/eval-input.
2. Exclude obvious non-English PDFs by filename.
3. Stage selected PDFs into a run-local workspace.
4. Run the existing processing pipeline to create parsed JSON and RAG chunks.
5. Filter parsed PDFs for mostly-English content.
6. Generate section-level synthetic questions.
7. Retrieve from the run-local index and judge top-k relevance with the LLM.

Outputs are written under:
backend/evals/retrieval/results/pdf_dataset_eval/
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import copy
import hashlib
import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DEFAULT_K_VALUES = (1, 3, 5, 7, 10)
QUESTION_TYPES = ("simple", "multi_intent", "reasoning")
FIXED_RUN_ID = "pdf_dataset_eval"
FILENAME_EXCLUDE_RE = re.compile(r"(zh-cn|-zh|_zh|chinese|中文)", re.IGNORECASE)
JSON_BLOCK_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)
JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL | re.IGNORECASE)
SKIP_HEADING_RE = re.compile(
    r"\b("
    r"declaration|authorship|author.?ship|preface|foreword|acknowledg(e)?ments?|"
    r"table\s+of\s+contents|contents|mục\s+lục|lời\s+mở\s+đầu"
    r")\b",
    re.IGNORECASE,
)
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
LATIN_RE = re.compile(r"[A-Za-z]")


@dataclass(frozen=True)
class PdfCandidate:
    source_path: str
    relative_path: str
    top_folder: str
    doc_id: str
    staged_filename: str
    size_bytes: int


@dataclass(frozen=True)
class SectionRecord:
    doc_id: str
    section_id: str
    section_index: int
    top_folder: str
    relative_path: str
    heading_text: str
    heading_level: int
    heading_breadcrumb: List[str]
    source_text: str
    char_count: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _json_or_empty(raw: str) -> Dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    fence = JSON_FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"items": parsed}
    except json.JSONDecodeError:
        pass
    match = JSON_BLOCK_RE.search(text)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(1))
        return parsed if isinstance(parsed, dict) else {"items": parsed}
    except json.JSONDecodeError:
        return {}


def _slug_doc_id(relative_path: Path) -> str:
    raw = relative_path.with_suffix("").as_posix()
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._-")
    if not slug:
        slug = "document"
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]
    suffix = f"_{digest}"
    max_slug_len = 50 - len(suffix)
    if len(slug) > max_slug_len:
        slug = slug[:max_slug_len].rstrip("._-")
    return f"{slug}{suffix}"


def _normalizer_safe_stem(stem: str, max_length: int = 50) -> str:
    """Mirror DocumentNormalizer._get_safe_filename for old long-stem runs."""
    value = str(stem or "").strip()
    while value and value[-1] in ". \t":
        value = value[:-1]
    value = value or "untitled"
    if len(value) <= max_length:
        return value
    digest = hashlib.md5(value.encode()).hexdigest()[:8]
    truncated = value[: max_length - 9].rstrip("._-")
    return f"{truncated}_{digest}"


def _progress(label: str, done: int, total: int, extra: str = "") -> None:
    pct = (done / total * 100.0) if total else 100.0
    suffix = f" | {extra}" if extra else ""
    print(f"[{label}] {done}/{total} ({pct:.1f}%){suffix}", flush=True)


class _Tee:
    def __init__(self, *streams: Any) -> None:
        self.streams = streams

    def write(self, data: str) -> int:
        for stream in self.streams:
            stream.write(data)
        return len(data)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()


def _discover_pdf_candidates(dataset_root: Path, max_pdfs: int | None = None) -> tuple[List[PdfCandidate], List[Dict[str, Any]]]:
    candidates: List[PdfCandidate] = []
    skipped: List[Dict[str, Any]] = []
    pdfs = sorted(
        p
        for p in dataset_root.rglob("*")
        if p.is_file()
        and p.suffix.lower() == ".pdf"
        and not any(part.startswith(".") for part in p.relative_to(dataset_root).parts)
        and not p.name.startswith("~$")
    )
    for path in pdfs:
        rel = path.relative_to(dataset_root)
        top = rel.parts[0] if rel.parts else ""
        if FILENAME_EXCLUDE_RE.search(path.name):
            skipped.append(
                {
                    "relative_path": rel.as_posix(),
                    "top_folder": top,
                    "reason": "filename_language_marker",
                    "severity": "warning",
                }
            )
            continue
        doc_id = _slug_doc_id(rel)
        candidates.append(
            PdfCandidate(
                source_path=str(path.resolve()),
                relative_path=rel.as_posix(),
                top_folder=top,
                doc_id=doc_id,
                staged_filename=f"{doc_id}.pdf",
                size_bytes=path.stat().st_size,
            )
        )
        if max_pdfs is not None and len(candidates) >= max_pdfs:
            break
    return candidates, skipped


def _load_candidates_from_manifest(path: Path) -> tuple[List[PdfCandidate], List[Dict[str, Any]]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing pdf_manifest.json at {path}. Run --stage parse first.")
    manifest = _read_json(path)
    candidates = [PdfCandidate(**row) for row in manifest.get("pdf_candidates", [])]
    skipped = list(manifest.get("prefilter_skipped") or [])
    return candidates, skipped


def _load_selected_sections(path: Path) -> List[SectionRecord]:
    if not path.exists():
        raise FileNotFoundError(f"Missing selected_sections.json at {path}. Run --stage generate first.")
    return [SectionRecord(**row) for row in _read_json(path)]


def _load_candidates_list(path: Path, label: str) -> List[PdfCandidate]:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label} at {path}. Run --stage parse first.")
    return [PdfCandidate(**row) for row in _read_json(path)]


def _selected_candidates_for_index(run_dir: Path, english_passed_path: Path) -> List[PdfCandidate]:
    selected_sections_path = run_dir / "selected_sections.json"
    if not selected_sections_path.exists():
        raise FileNotFoundError(
            f"Missing selected_sections.json at {selected_sections_path}. "
            "Run --stage generate before --stage index/retrieve."
        )
    selected = _load_selected_sections(selected_sections_path)
    selected_doc_ids = {section.doc_id for section in selected}
    english_candidates = _load_candidates_list(english_passed_path, "english_passed_pdfs.json")
    by_doc_id = {candidate.doc_id: candidate for candidate in english_candidates}
    selected_candidates = [by_doc_id[doc_id] for doc_id in sorted(selected_doc_ids) if doc_id in by_doc_id]
    missing = sorted(doc_id for doc_id in selected_doc_ids if doc_id not in by_doc_id)
    if missing:
        raise RuntimeError(f"{len(missing)} selected-section docs are missing from english_passed_pdfs.json: {missing[:5]}")
    if not selected_candidates:
        raise RuntimeError("No selected-section PDFs found for indexing.")
    print(
        f"Index scope: {len(selected_candidates)} PDFs that contain the {len(selected)} selected sections.",
        flush=True,
    )
    return selected_candidates


def _pdf_page_count(path: Path) -> int | None:
    try:
        import fitz

        doc = fitz.open(path)
        try:
            return int(doc.page_count)
        finally:
            doc.close()
    except Exception:
        return None


def _filter_visual_candidates_by_page_limit(
    candidates: Sequence[PdfCandidate],
    *,
    max_pages: int,
    report_path: Path,
) -> tuple[List[PdfCandidate], List[Dict[str, Any]]]:
    if max_pages <= 0:
        _safe_write_json(
            report_path,
            {
                "created_at": _utc_now(),
                "enabled": False,
                "max_pages": max_pages,
                "kept": len(candidates),
                "skipped": 0,
                "files": [],
            },
        )
        return list(candidates), []

    kept: List[PdfCandidate] = []
    skipped: List[Dict[str, Any]] = []
    files: List[Dict[str, Any]] = []
    for idx, candidate in enumerate(candidates, start=1):
        page_count = _pdf_page_count(Path(candidate.source_path))
        status = "kept"
        reason = ""
        if page_count is None:
            status = "skipped"
            reason = "page_count_unavailable"
        elif page_count > max_pages:
            status = "skipped"
            reason = "page_limit_exceeded"

        row = {
            "stage": "index",
            "doc_id": candidate.doc_id,
            "relative_path": candidate.relative_path,
            "top_folder": candidate.top_folder,
            "status": status,
            "output_exists": status == "kept",
            "page_count": page_count,
            "max_pages": max_pages,
            "reason": reason,
            "severity": "warning" if status == "skipped" else "",
            "source_path": candidate.source_path,
        }
        files.append(row)
        if status == "kept":
            kept.append(candidate)
        else:
            skipped.append(row)
        if idx == 1 or idx == len(candidates) or idx % 25 == 0:
            _progress("visual-page-filter", idx, len(candidates), f"{candidate.relative_path} pages={page_count}")

    _safe_write_json(
        report_path,
        {
            "created_at": _utc_now(),
            "enabled": True,
            "max_pages": max_pages,
            "total": len(candidates),
            "kept": len(kept),
            "skipped": len(skipped),
            "skipped_doc_ids": [row["doc_id"] for row in skipped],
            "files": files,
        },
    )
    if skipped:
        print(
            f"Visual page filter: kept {len(kept)}/{len(candidates)} PDFs; "
            f"skipped {len(skipped)} PDFs over {max_pages} pages or with unknown page count.",
            flush=True,
        )
    if not kept:
        raise RuntimeError(f"No PDFs remain for visual indexing after applying --max-visual-pdf-pages {max_pages}.")
    return kept, skipped


def _filter_questions_by_skipped_visual_docs(
    questions: Sequence[Dict[str, Any]],
    skipped_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    skipped_doc_ids = {str(row.get("doc_id") or "") for row in skipped_rows if row.get("doc_id")}
    if not skipped_doc_ids:
        return list(questions)
    filtered = [q for q in questions if str(q.get("doc_id") or "") not in skipped_doc_ids]
    print(
        f"Visual retrieve question filter: kept {len(filtered)}/{len(questions)} questions; "
        f"skipped {len(questions) - len(filtered)} questions from {len(skipped_doc_ids)} over-limit PDFs.",
        flush=True,
    )
    return filtered


def _stage_outputs_done(paths: Sequence[Path], force: bool) -> bool:
    return (not force) and all(path.exists() for path in paths)


def _same_candidate_set(left: Sequence[PdfCandidate], right: Sequence[PdfCandidate]) -> bool:
    return {candidate.doc_id for candidate in left} == {candidate.doc_id for candidate in right}


def _parser_config_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "pdf_content_source": args.pdf_content_source,
        "pdf_ocr": not args.no_pdf_ocr,
        "pdf_vlm": bool(args.enable_pdf_vlm),
        "pdf_formula_enrichment": bool(args.enable_pdf_formula_enrichment),
        "pdf_vlm_model": args.pdf_vlm_model,
        "pdf_vlm_batch_size": int(args.pdf_vlm_batch_size),
        "pdf_vlm_page_filter": args.pdf_vlm_page_filter,
    }


def _stage_pdfs(candidates: Sequence[PdfCandidate], input_dir: Path) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    for idx, candidate in enumerate(candidates, start=1):
        dest = input_dir / candidate.staged_filename
        source = Path(candidate.source_path)
        if dest.exists() or dest.is_symlink():
            current_target = dest.resolve() if dest.is_symlink() else None
            if current_target == source.resolve():
                pass
            else:
                dest.unlink()
                dest.symlink_to(source)
        else:
            dest.symlink_to(source)
        if idx == 1 or idx == len(candidates) or idx % 25 == 0:
            _progress("stage", idx, len(candidates), candidate.relative_path)


def _clear_input_dir(input_dir: Path) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    for path in input_dir.iterdir():
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_symlink() or child.is_file():
                    child.unlink()
            path.rmdir()


def _clear_dir_contents(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)


def _load_runtime_config() -> Dict[str, Any]:
    try:
        from app.core.paths import merged_runtime_settings

        return merged_runtime_settings()
    except Exception as exc:
        print(f"WARNING: could not load backend runtime config, using defaults: {exc}", flush=True)
        return {}


def _local_docling_runtime_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    local_cfg = copy.deepcopy(cfg or {})
    inference_cfg = local_cfg.setdefault("inference", {})
    inference_cfg["use_aws_sagemaker_docling"] = False
    document_cfg = local_cfg.setdefault("processing", {}).setdefault("document", {})
    document_cfg["docling_backend"] = "local"
    return local_cfg


def _build_processing_config(
    cfg: Dict[str, Any],
    pdf_content_source: str,
    enable_pdf_ocr: bool,
    enable_pdf_vlm: bool,
    enable_pdf_formula_enrichment: bool,
    pdf_vlm_model: str,
    pdf_vlm_batch_size: int,
    pdf_vlm_page_filter: str,
    prune_outputs_not_in_input: bool = True,
) -> Any:
    from src.processor.normalizer import NormalizerConfig
    from src.processor.pipeline import PipelineConfig

    local_cfg = _local_docling_runtime_config(cfg)
    processing = local_cfg.get("processing", {}) or {}
    normalizer_cfg = processing.get("normalizer", {}) or {}
    document_cfg = processing.get("document", {}) or {}
    v2_cfg = document_cfg.get("v2", {}) or {}
    content_source = str(pdf_content_source or "docling").strip().lower()
    if content_source not in {"pymupdf", "docling", "hybrid", "hybrid_batched"}:
        content_source = "docling"
    normalizer = NormalizerConfig(
        generate_pdf=True,
        generate_markdown=False,
        image_to_pdf=False,
        pdf_content_source=content_source,
        pdf_reader_enable_ocr=enable_pdf_ocr,
        pdf_reader_extract_images=False,
        pdf_docling_batch_size=int(v2_cfg.get("pdf_docling_batch_size") or normalizer_cfg.get("pdf_docling_batch_size") or 8),
        pdf_max_docling_concurrency=v2_cfg.get("pdf_max_docling_concurrency")
        or normalizer_cfg.get("pdf_max_docling_concurrency"),
        pdf_docling_batched_min_pages=int(
            v2_cfg.get("pdf_docling_batched_min_pages") or normalizer_cfg.get("pdf_docling_batched_min_pages") or 12
        ),
        pdf_reader_enable_vlm=enable_pdf_vlm,
        pdf_do_formula_enrichment=enable_pdf_formula_enrichment,
        pdf_vlm_model=pdf_vlm_model,
        pdf_vlm_batch_size=pdf_vlm_batch_size,
        pdf_vlm_page_filter=pdf_vlm_page_filter,
        runtime_yaml=local_cfg,
    )
    return PipelineConfig(
        enable_normalization=True,
        enable_media_processing=False,
        enable_document_processing=True,
        normalizer_config=normalizer,
        runtime_yaml=local_cfg,
        skip_processed=True,
        prune_outputs_not_in_input=prune_outputs_not_in_input,
        use_gpu=bool(processing.get("use_gpu", True)),
    )


def _run_processing(
    input_dir: Path,
    processing_dir: Path,
    cfg: Dict[str, Any],
    pdf_content_source: str,
    enable_pdf_ocr: bool,
    enable_pdf_vlm: bool,
    enable_pdf_formula_enrichment: bool,
    pdf_vlm_model: str,
    pdf_vlm_batch_size: int,
    pdf_vlm_page_filter: str,
    prune_outputs_not_in_input: bool = True,
    log_path: Path | None = None,
) -> Dict[str, Any]:
    from src.processor.pipeline import DocumentProcessingPipeline

    os.environ["USE_AWS_SAGEMAKER_DOCLING"] = "false"
    log_file = None
    file_handler = None
    try:
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = log_path.open("a", encoding="utf-8")
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logging.getLogger().addHandler(file_handler)
        stdout = _Tee(sys.stdout, log_file) if log_file else sys.stdout
        stderr = _Tee(sys.stderr, log_file) if log_file else sys.stderr
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            print("\n=== Processing PDFs into artifacts ===", flush=True)
            print(
                f"PDF parser: CustomPdfReader content_source={pdf_content_source} "
                f"docling_backend=local ocr={enable_pdf_ocr} "
                f"vlm={enable_pdf_vlm} formula={enable_pdf_formula_enrichment}",
                flush=True,
            )
            pipeline = DocumentProcessingPipeline(
                input_dir=input_dir,
                output_dir=processing_dir,
                config=_build_processing_config(
                    cfg,
                    pdf_content_source,
                    enable_pdf_ocr,
                    enable_pdf_vlm,
                    enable_pdf_formula_enrichment,
                    pdf_vlm_model,
                    pdf_vlm_batch_size,
                    pdf_vlm_page_filter,
                    prune_outputs_not_in_input=prune_outputs_not_in_input,
                ),
            )
            return pipeline.run()
    finally:
        if file_handler:
            logging.getLogger().removeHandler(file_handler)
            file_handler.close()
        if log_file:
            log_file.close()


def _run_processing_batches(
    *,
    candidates: Sequence[PdfCandidate],
    work_dir: Path,
    processing_dir: Path,
    run_dir: Path,
    args: argparse.Namespace,
    batch_size: int,
    parse_log_path: Path,
) -> List[Dict[str, Any]]:
    pending = [candidate for candidate in candidates if args.force or not _parsed_artifact_path(processing_dir, candidate)]
    existing = len(candidates) - len(pending)
    print(f"\nParse artifacts already present: {existing}/{len(candidates)}", flush=True)
    print(f"Pending PDFs to parse: {len(pending)}", flush=True)
    if not pending:
        return []

    pending_total = len(pending)
    completed_files = 0
    heartbeat_seconds = max(5, int(args.parse_heartbeat_seconds))
    batch_stats: List[Dict[str, Any]] = []
    total_batches = math.ceil(len(pending) / max(1, batch_size))
    batches_root = work_dir / "batches"
    batches_root.mkdir(parents=True, exist_ok=True)
    for batch_index, start in enumerate(range(0, len(pending), max(1, batch_size)), start=1):
        batch = pending[start : start + max(1, batch_size)]
        batch_file = run_dir / f"parse_batch_{batch_index:04d}.json"
        batch_stats_file = run_dir / f"parse_batch_{batch_index:04d}_stats.json"
        batch_input_dir = batches_root / f"batch_{batch_index:04d}" / "input"
        _clear_input_dir(batch_input_dir)
        _safe_write_json(batch_file, [asdict(candidate) for candidate in batch])
        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--internal-parse-batch-file",
            str(batch_file),
            "--internal-batch-input-dir",
            str(batch_input_dir),
            "--internal-processing-dir",
            str(processing_dir),
            "--internal-batch-stats-file",
            str(batch_stats_file),
            "--output-root",
            str(args.output_root),
            "--work-root",
            str(args.work_root),
            "--pdf-content-source",
            args.pdf_content_source,
        ]
        if args.no_pdf_ocr:
            cmd.append("--no-pdf-ocr")
        if args.enable_pdf_vlm:
            cmd.append("--enable-pdf-vlm")
        if args.enable_pdf_formula_enrichment:
            cmd.append("--enable-pdf-formula-enrichment")
        cmd.extend(
            [
                "--pdf-vlm-model",
                args.pdf_vlm_model,
                "--pdf-vlm-batch-size",
                str(args.pdf_vlm_batch_size),
                "--pdf-vlm-page-filter",
                args.pdf_vlm_page_filter,
            ]
        )
        print(
            f"\n=== Parse batch {batch_index}/{total_batches}: {len(batch)} PDF(s) ===",
            flush=True,
        )
        for offset, candidate in enumerate(batch, start=1):
            absolute_pos = start + offset
            print(
                f"[parse-file] {absolute_pos}/{pending_total} "
                f"({absolute_pos / pending_total * 100:.1f}%) | start | {candidate.relative_path}",
                flush=True,
            )
        started_docs: set[str] = set()
        completed_docs: set[str] = set()
        active_file = batch[0].relative_path if batch else ""
        active_started_at = time.monotonic()
        last_heartbeat_at = time.monotonic()
        returncode = 0
        timed_out = False
        with parse_log_path.open("a", encoding="utf-8") as log_file:
            proc = subprocess.Popen(
                cmd,
                cwd=str(BACKEND_ROOT.parent),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            assert proc.stdout is not None
            deadline = time.monotonic() + max(1, int(args.parse_batch_timeout_seconds))
            while True:
                now = time.monotonic()
                if now > deadline:
                    timed_out = True
                    proc.kill()
                    log_file.write(f"\nPARSE BATCH TIMEOUT after {args.parse_batch_timeout_seconds}s\n")
                    break
                if now - last_heartbeat_at >= heartbeat_seconds:
                    elapsed = int(now - active_started_at)
                    print(
                        f"[parse-file] still running | elapsed={elapsed}s | active={active_file} | "
                        f"batch={batch_index}/{total_batches}",
                        flush=True,
                    )
                    last_heartbeat_at = now
                line = proc.stdout.readline()
                if line:
                    log_file.write(line)
                    log_file.flush()
                    stripped = line.strip()
                    for candidate in batch:
                        if candidate.staged_filename in stripped and "Normalizing pdf:" in stripped:
                            active_file = candidate.relative_path
                            active_started_at = time.monotonic()
                            print(f"[parse-file] normalizing | {candidate.relative_path}", flush=True)
                        if candidate.staged_filename in stripped and "Processing document" in stripped and candidate.doc_id not in started_docs:
                            started_docs.add(candidate.doc_id)
                            active_file = candidate.relative_path
                            active_started_at = time.monotonic()
                            print(f"[parse-file] processing | {candidate.relative_path}", flush=True)
                        if candidate.staged_filename in stripped and "Finished converting document" in stripped:
                            print(f"[parse-file] converted | {candidate.relative_path}", flush=True)
                        if candidate.staged_filename in stripped and "CustomPdfReader:" in stripped:
                            print(f"[parse-file] {stripped}", flush=True)
                        if candidate.staged_filename in stripped and "Born-digital PDF parsed" in stripped and candidate.doc_id not in completed_docs:
                            completed_docs.add(candidate.doc_id)
                            completed_files += 1
                            _progress("parse-file", completed_files, pending_total, candidate.relative_path)
                    continue
                returncode = proc.poll()
                if returncode is not None:
                    break
                time.sleep(0.2)
        if timed_out:
            returncode = 124
        for candidate in batch:
            if candidate.doc_id not in completed_docs and _parsed_artifact_path(processing_dir, candidate):
                completed_files += 1
                _progress("parse-file", completed_files, pending_total, candidate.relative_path)
        row = {
            "batch": batch_index,
            "pdfs": [candidate.relative_path for candidate in batch],
            "returncode": returncode,
            "timed_out": timed_out,
            "stats_file": str(batch_stats_file),
        }
        if batch_stats_file.exists():
            row["stats"] = _read_json(batch_stats_file)
        batch_stats.append(row)
        _progress("parse-batch", batch_index, total_batches, f"returncode={returncode}")
        if returncode != 0:
            raise RuntimeError(f"Parse batch {batch_index} failed; see {parse_log_path}")
    return batch_stats


def _language_stats(text: str) -> Dict[str, Any]:
    latin = len(LATIN_RE.findall(text or ""))
    cjk = len(CJK_RE.findall(text or ""))
    denom = max(latin + cjk, 1)
    return {
        "latin_alpha_chars": latin,
        "cjk_chars": cjk,
        "cjk_ratio": cjk / denom,
    }


def _looks_like_toc(text: str) -> bool:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if len(lines) < 5:
        return False
    dotted = sum(1 for line in lines[:80] if re.search(r"\.{3,}\s*\d+\s*$", line))
    short_numbered = sum(1 for line in lines[:80] if re.match(r"^(\d+(\.\d+)*|[IVX]+)\s+.{3,80}\s+\d+$", line))
    return (dotted + short_numbered) >= max(4, int(len(lines[:80]) * 0.25))


def _valid_section(section: Any, min_section_chars: int) -> tuple[bool, str]:
    if isinstance(section, dict):
        text = str(section.get("source_text") or "").strip()
        heading = str(section.get("heading_text") or "").strip()
    else:
        text = str(getattr(section, "source_text", "") or "").strip()
        heading = str(getattr(section, "heading_text", "") or "").strip()
    if not text:
        return False, "empty_section"
    if len(text) < min_section_chars:
        return False, "short_section"
    if SKIP_HEADING_RE.search(heading):
        return False, "boilerplate_heading"
    if _looks_like_toc(text):
        return False, "table_of_contents_like"
    return True, ""


def _node_heading(node: Dict[str, Any]) -> str:
    for key in ("heading_text", "sheet_name", "section", "title", "name"):
        value = str(node.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _flatten_sections(tree: Any, doc_id: str) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []

    def _walk(nodes: Sequence[Dict[str, Any]], breadcrumb: Sequence[str]) -> None:
        for node in nodes:
            if not isinstance(node, dict):
                continue
            heading = _node_heading(node)
            level = _coerce_int(node.get("heading_level"), 0)
            content = str(node.get("content", "") or "")
            children = list(node.get("children") or [])
            current = list(breadcrumb) + ([heading] if heading else [])
            if content.strip():
                idx = len(sections)
                sections.append(
                    {
                        "doc_id": doc_id,
                        "section_id": f"{doc_id}:section:{idx:04d}",
                        "section_index": idx,
                        "heading_text": heading,
                        "heading_level": level,
                        "heading_breadcrumb": current,
                        "source_text": content,
                    }
                )
            if children:
                _walk(children, current)

    if isinstance(tree, list):
        _walk(tree, [])
    return sections


def _parsed_artifact_path(processing_dir: Path, candidate: PdfCandidate) -> Path | None:
    parsed_root = processing_dir / "stage1_normalized" / "pdf_parsed"
    parsed_path = parsed_root / f"{candidate.doc_id}.json"
    if parsed_path.exists():
        return parsed_path
    safe_doc_id = _normalizer_safe_stem(candidate.doc_id)
    safe_path = parsed_root / f"{safe_doc_id}.json"
    if safe_path.exists():
        return safe_path
    return None


def _validate_english_artifacts(
    *,
    candidates: Sequence[PdfCandidate],
    processing_dir: Path,
    min_alpha_chars: int,
    max_cjk_ratio: float,
    skipped_rows: Sequence[Dict[str, Any]],
) -> tuple[List[PdfCandidate], List[Dict[str, Any]]]:
    skipped = list(skipped_rows)
    passed: List[PdfCandidate] = []
    for idx, candidate in enumerate(candidates, start=1):
        parsed_path = _parsed_artifact_path(processing_dir, candidate)
        if not parsed_path:
            skipped.append(
                {
                    "relative_path": candidate.relative_path,
                    "top_folder": candidate.top_folder,
                    "doc_id": candidate.doc_id,
                    "reason": "parse_failed",
                    "severity": "error",
                }
            )
            continue
        try:
            tree = _read_json(parsed_path)
            flat = _flatten_sections(tree, candidate.doc_id)
        except Exception as exc:
            skipped.append(
                {
                    "relative_path": candidate.relative_path,
                    "top_folder": candidate.top_folder,
                    "doc_id": candidate.doc_id,
                    "reason": "parse_failed",
                    "severity": "error",
                    "error": str(exc),
                }
            )
            continue

        combined = "\n\n".join(str(section.get("source_text") or "") for section in flat)
        lang = _language_stats(combined)
        if lang["latin_alpha_chars"] < min_alpha_chars:
            skipped.append(
                {
                    "relative_path": candidate.relative_path,
                    "top_folder": candidate.top_folder,
                    "doc_id": candidate.doc_id,
                    "reason": "too_little_text",
                    "severity": "warning",
                    **lang,
                }
            )
            continue
        if lang["cjk_ratio"] > max_cjk_ratio:
            skipped.append(
                {
                    "relative_path": candidate.relative_path,
                    "top_folder": candidate.top_folder,
                    "doc_id": candidate.doc_id,
                    "reason": "not_mostly_english",
                    "severity": "warning",
                    **lang,
                }
            )
            continue
        passed.append(candidate)
        if idx == 1 or idx == len(candidates) or idx % 25 == 0:
            _progress("english-filter", idx, len(candidates), candidate.relative_path)
    return passed, skipped


def _extract_log_warnings(log_path: Path, candidates: Sequence[PdfCandidate]) -> List[Dict[str, Any]]:
    if not log_path.exists():
        return []
    doc_lookup = {
        key: candidate
        for candidate in candidates
        for key in (candidate.staged_filename, f"{candidate.doc_id}.pdf", candidate.doc_id)
    }
    rows: List[Dict[str, Any]] = []
    for line_no, line in enumerate(log_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        lowered = line.lower()
        if not any(marker in lowered for marker in ("warning", "userwarning", "rapidocr returned empty result", "text detection result is empty")):
            continue
        candidate = next((item for key, item in doc_lookup.items() if key and key in line), None)
        rows.append(
            {
                "relative_path": candidate.relative_path if candidate else "",
                "top_folder": candidate.top_folder if candidate else "",
                "doc_id": candidate.doc_id if candidate else "",
                "reason": "parse_log_warning",
                "severity": "warning",
                "line": line_no,
                "message": line[:1000],
            }
        )
    return rows


def _write_parse_outputs(
    path: Path,
    *,
    candidates: Sequence[PdfCandidate],
    prefilter_skipped: Sequence[Dict[str, Any]],
    english_candidates: Sequence[PdfCandidate],
    skipped: Sequence[Dict[str, Any]],
    log_warnings: Sequence[Dict[str, Any]],
    processing_dir: Path,
) -> List[Dict[str, Any]]:
    passed_doc_ids = {candidate.doc_id for candidate in english_candidates}
    skipped_by_doc: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in [*skipped, *log_warnings]:
        skipped_by_doc[str(row.get("doc_id") or "")].append(row)

    rows: List[Dict[str, Any]] = []
    for row in prefilter_skipped:
        rows.append(
            {
                "stage": "parse",
                "relative_path": row.get("relative_path"),
                "top_folder": row.get("top_folder"),
                "status": "skipped",
                "output_exists": False,
                "reason": row.get("reason"),
                "severity": row.get("severity", "warning"),
            }
        )
    for candidate in candidates:
        parsed_path = _parsed_artifact_path(processing_dir, candidate)
        rag_dir = processing_dir / "stage4_rag_ready" / _normalizer_safe_stem(candidate.doc_id)
        issues = skipped_by_doc.get(candidate.doc_id, [])
        status = "processed" if candidate.doc_id in passed_doc_ids else "failed_or_rejected"
        rows.append(
            {
                "stage": "parse",
                "doc_id": candidate.doc_id,
                "relative_path": candidate.relative_path,
                "top_folder": candidate.top_folder,
                "status": status,
                "english_passed": candidate.doc_id in passed_doc_ids,
                "parsed_json": str(parsed_path) if parsed_path else "",
                "rag_dir": str(rag_dir) if rag_dir.exists() else "",
                "output_exists": bool(parsed_path),
                "issues": issues,
            }
        )
    _safe_write_json(path, rows)
    return rows


def _collect_sections(
    *,
    candidates: Sequence[PdfCandidate],
    processing_dir: Path,
    min_section_chars: int,
    skipped_rows: Sequence[Dict[str, Any]],
) -> tuple[List[SectionRecord], List[Dict[str, Any]]]:
    by_doc = {candidate.doc_id: candidate for candidate in candidates}
    skipped = list(skipped_rows)
    sections: List[SectionRecord] = []
    parsed_root = processing_dir / "stage1_normalized" / "pdf_parsed"

    for idx, candidate in enumerate(candidates, start=1):
        parsed_path = _parsed_artifact_path(processing_dir, candidate)
        if not parsed_path:
            skipped.append(
                {
                    "relative_path": candidate.relative_path,
                    "top_folder": candidate.top_folder,
                    "doc_id": candidate.doc_id,
                    "reason": "parse_failed",
                    "severity": "error",
                }
            )
            continue
        try:
            tree = _read_json(parsed_path)
            flat = _flatten_sections(tree, candidate.doc_id)
        except Exception as exc:
            skipped.append(
                {
                    "relative_path": candidate.relative_path,
                    "top_folder": candidate.top_folder,
                    "doc_id": candidate.doc_id,
                    "reason": "parse_failed",
                    "severity": "error",
                    "error": str(exc),
                }
            )
            continue

        combined = "\n\n".join(str(section.get("source_text") or "") for section in flat)
        lang = _language_stats(combined)

        valid_for_doc = 0
        skip_reasons = Counter()
        for section in flat:
            ok, reason = _valid_section(section, min_section_chars)
            if not ok:
                skip_reasons[reason] += 1
                continue
            valid_for_doc += 1
            sections.append(
                SectionRecord(
                    doc_id=str(section.get("doc_id") or ""),
                    section_id=str(section.get("section_id") or ""),
                    section_index=int(section.get("section_index") or 0),
                    top_folder=candidate.top_folder,
                    relative_path=candidate.relative_path,
                    heading_text=str(section.get("heading_text") or ""),
                    heading_level=int(section.get("heading_level") or 0),
                    heading_breadcrumb=list(section.get("heading_breadcrumb") or []),
                    source_text=str(section.get("source_text") or ""),
                    char_count=len(str(section.get("source_text") or "")),
                )
            )
        if valid_for_doc == 0:
            skipped.append(
                {
                    "relative_path": candidate.relative_path,
                    "top_folder": candidate.top_folder,
                    "doc_id": candidate.doc_id,
                    "reason": "no_valid_sections",
                    "severity": "warning",
                    "section_skip_reasons": dict(skip_reasons),
                    **lang,
                }
            )
        if idx == 1 or idx == len(candidates) or idx % 25 == 0:
            _progress("artifact-filter", idx, len(candidates), candidate.relative_path)

    # Keep deterministic order by source candidate order.
    order = {candidate.doc_id: i for i, candidate in enumerate(candidates)}
    sections.sort(key=lambda s: (order.get(s.doc_id, 10**9), s.section_index))
    return sections, skipped


def _balanced_select_sections(sections: Sequence[SectionRecord], section_cap: int) -> List[SectionRecord]:
    if section_cap <= 0 or len(sections) <= section_cap:
        return list(sections)
    grouped: Dict[str, List[SectionRecord]] = defaultdict(list)
    for section in sections:
        grouped[section.top_folder].append(section)
    selected: List[SectionRecord] = []
    folder_names = sorted(grouped)
    cursor = {folder: 0 for folder in folder_names}
    while len(selected) < section_cap:
        progressed = False
        for folder in folder_names:
            items = grouped[folder]
            pos = cursor[folder]
            if pos >= len(items):
                continue
            selected.append(items[pos])
            cursor[folder] += 1
            progressed = True
            if len(selected) >= section_cap:
                break
        if not progressed:
            break
    return selected


def _build_generator(cfg: Dict[str, Any], provider: str | None, model: str, max_tokens: int) -> Any:
    from src.generation.generator import GenerationConfig, RAGGenerator

    gyaml = cfg.get("generation", {}) or {}
    selected_provider = str(provider or os.getenv("RETRIEVAL_EVAL_GENERATION_PROVIDER") or gyaml.get("provider") or "bedrock").strip()
    selected_model = str(model or os.getenv("RETRIEVAL_EVAL_GENERATION_MODEL") or gyaml.get("model") or "gpt-5.4-nano").strip()
    gc = GenerationConfig(
        provider=selected_provider,
        model_name=selected_model,
        api_key=gyaml.get("api_key"),
        base_url=gyaml.get("base_url"),
        bedrock_region=gyaml.get("bedrock_region") or None,
        temperature=0.0,
        max_tokens=max_tokens,
        enable_citations=False,
        base_dir=str(BACKEND_ROOT),
        enable_guardrails=False,
    )
    return RAGGenerator(gc)


def _generate_questions_for_section(gen: Any, section: SectionRecord) -> List[Dict[str, Any]]:
    prompt = f"""
Generate retrieval-evaluation questions from one PDF section.

Return JSON only:
{{
  "items": [
    {{
      "question_type": "simple",
      "question": "...",
      "reference_answer": "...",
      "expected_evidence_hint": "..."
    }}
  ]
}}

Requirements:
- Generate exactly 5 questions.
- The first 3 items must have question_type exactly "simple".
- The fourth item must have question_type exactly "multi_intent".
- The fifth item must have question_type exactly "reasoning".
- Use only information from the source section.
- Questions must be precise and useful for retrieval evaluation.
- Reference answers must be concise and grounded in the source section.

PDF: {section.relative_path}
Section heading: {section.heading_text}
Section breadcrumb: {" > ".join(section.heading_breadcrumb)}

Source section:
{section.source_text}
""".strip()
    raw = gen._call_llm(prompt)
    payload = _json_or_empty(raw)
    items = list(payload.get("items") or [])
    expected_types = ["simple", "simple", "simple", "multi_intent", "reasoning"]
    out: List[Dict[str, Any]] = []
    for idx, expected_type in enumerate(expected_types, start=1):
        item = items[idx - 1] if idx - 1 < len(items) and isinstance(items[idx - 1], dict) else {}
        question = str(item.get("question") or "").strip()
        if not question:
            continue
        qtype = str(item.get("question_type") or item.get("category") or expected_type).strip()
        if qtype not in QUESTION_TYPES:
            qtype = expected_type
        if qtype != expected_type:
            qtype = expected_type
        out.append(
            {
                "query_id": f"{section.doc_id}:section:{section.section_index:04d}:{qtype}:{idx}",
                "doc_id": section.doc_id,
                "section_id": section.section_id,
                "section_index": section.section_index,
                "top_folder": section.top_folder,
                "relative_path": section.relative_path,
                "heading_text": section.heading_text,
                "heading_breadcrumb": section.heading_breadcrumb,
                "question_type": qtype,
                "question": question,
                "reference_answer": str(item.get("reference_answer") or "").strip(),
                "expected_evidence_hint": str(item.get("expected_evidence_hint") or "").strip(),
                "generation_raw": raw if idx == 1 else "",
                "created_at": _utc_now(),
            }
        )
    return out


def _generate_questions(
    *,
    gen: Any,
    sections: Sequence[SectionRecord],
    output_path: Path,
    concurrency: int,
    resume: bool,
) -> List[Dict[str, Any]]:
    existing = _read_jsonl(output_path) if resume else []
    done_sections = {str(row.get("section_id") or "") for row in existing}
    questions = list(existing)
    total = len(sections)
    processed = 0
    grouped: Dict[str, Dict[str, List[SectionRecord]]] = defaultdict(lambda: defaultdict(list))
    for section in sections:
        grouped[section.top_folder][section.relative_path].append(section)

    for folder in sorted(grouped):
        print(f"\n=== Generating questions: folder={folder} ===", flush=True)
        for rel_path in sorted(grouped[folder]):
            file_sections = [s for s in grouped[folder][rel_path] if s.section_id not in done_sections]
            print(f"File: {rel_path} | sections={len(file_sections)}", flush=True)
            batch_rows: List[Dict[str, Any]] = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
                future_map = {executor.submit(_generate_questions_for_section, gen, section): section for section in file_sections}
                for future in concurrent.futures.as_completed(future_map):
                    section = future_map[future]
                    try:
                        rows = future.result()
                    except Exception as exc:
                        rows = [
                            {
                                "query_id": f"{section.doc_id}:section:{section.section_index:04d}:error",
                                "doc_id": section.doc_id,
                                "section_id": section.section_id,
                                "top_folder": section.top_folder,
                                "relative_path": section.relative_path,
                                "question_type": "error",
                                "question": "",
                                "reason": "question_generation_failed",
                                "severity": "error",
                                "error": str(exc),
                                "created_at": _utc_now(),
                            }
                        ]
                    batch_rows.extend(rows)
                    processed += 1
                    _progress("question-gen", processed, total, section.relative_path)
            _append_jsonl(output_path, batch_rows)
            questions.extend(batch_rows)
    return questions


def _evidence_id(row: Dict[str, Any]) -> str:
    return f"text:{str(row.get('id') or '').strip()}"


def _visual_evidence_id(row: Dict[str, Any]) -> str:
    return f"image:{str(row.get('source') or '').strip()}:page:{int(row.get('page') or 0)}"


def _normalize_evidence(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, raw in enumerate(rows, start=1):
        row = dict(raw or {})
        meta = dict(row.get("metadata") or {})
        text = str(row.get("full_text") or row.get("text") or "")
        out.append(
            {
                "evidence_id": _evidence_id(row),
                "modality": "text",
                "rank": int(row.get("rank") or idx),
                "score": float(row.get("score") or 0.0),
                "source": str(row.get("source") or meta.get("source") or ""),
                "doc_id": str(row.get("doc_id") or meta.get("doc_id") or ""),
                "text": text[:6000],
                "text_preview": text.replace("\n", " ")[:700],
                "metadata": meta,
            }
        )
    return out


def _normalize_visual_evidence(
    rows: Sequence[Dict[str, Any]],
    *,
    candidates: Sequence[PdfCandidate],
) -> List[Dict[str, Any]]:
    by_filename = {candidate.staged_filename: candidate for candidate in candidates}
    out: List[Dict[str, Any]] = []
    for idx, raw in enumerate(rows, start=1):
        row = dict(raw or {})
        source_name = str(row.get("source") or "")
        candidate = by_filename.get(source_name)
        source_path = candidate.source_path if candidate else str(row.get("source_path") or "")
        out.append(
            {
                "evidence_id": _visual_evidence_id(row),
                "modality": "image",
                "rank": int(row.get("rank") or idx),
                "score": float(row.get("score") or 0.0),
                "source": source_name,
                "source_path": source_path,
                "doc_id": candidate.doc_id if candidate else "",
                "relative_path": candidate.relative_path if candidate else "",
                "top_folder": candidate.top_folder if candidate else "",
                "page": int(row.get("page") or 0),
                "total_pages": int(row.get("total_pages") or 0),
                "text": str(row.get("text") or ""),
                "text_preview": str(row.get("text") or "")[:700],
                "retrieval_type": str(row.get("retrieval_type") or "colqwen"),
            }
        )
    return out


def _compact_evidence(evidence: Sequence[Dict[str, Any]], max_items: int = 10) -> str:
    lines = []
    for item in evidence[:max_items]:
        content = item.get("text") or item.get("text_preview") or ""
        if not content and item.get("modality") == "image":
            content = (
                f"PDF page image from {item.get('relative_path') or item.get('source')}, "
                f"page {item.get('page')} of {item.get('total_pages')}."
            )
        lines.append(
            f"- evidence_id: {item['evidence_id']}\n"
            f"  modality: {item.get('modality') or 'text'}\n"
            f"  rank: {item['rank']}\n"
            f"  attached_image: {item.get('attached_image') or ''}\n"
            f"  content: {content}"
        )
    return "\n".join(lines)


def _judge_relevance(
    gen: Any,
    question: Dict[str, Any],
    evidence: Sequence[Dict[str, Any]],
    image_paths: Sequence[str] | None = None,
) -> Dict[str, Any]:
    if not evidence:
        return {"labels": [], "raw": "", "error": ""}
    image_instruction = ""
    if image_paths:
        image_instruction = (
            "\nImage evidence pages are attached to this request. "
            "For each evidence item with an attached_image value, inspect that corresponding attached image "
            "before assigning relevance."
        )
    prompt = f"""
Judge retrieval relevance for one query.

Return JSON only:
{{"items": [{{"evidence_id": "...", "relevance": 0, "rationale": "short"}}]}}

Relevance scale:
- 0 = irrelevant
- 1 = slightly relevant, same topic but cannot answer the question
- 2 = partially relevant, answers part of the question
- 3 = highly relevant and sufficient for answering the question

Question: {question.get('question')}
Reference answer: {question.get('reference_answer')}
Expected evidence hint: {question.get('expected_evidence_hint')}
{image_instruction}

Evidence:
{_compact_evidence(evidence)}
""".strip()
    try:
        raw = gen._call_llm(prompt, list(image_paths or []) or None)
    except Exception as exc:
        return {"labels": [], "raw": "", "error": str(exc)}
    payload = _json_or_empty(raw)
    labels = []
    for item in payload.get("items") or []:
        eid = str(item.get("evidence_id") or "").strip()
        if not eid:
            continue
        try:
            relevance = int(item.get("relevance") or 0)
        except Exception:
            relevance = 0
        labels.append(
            {
                "evidence_id": eid,
                "relevance": max(0, min(3, relevance)),
                "rationale": str(item.get("rationale") or "").strip(),
            }
        )
    return {"labels": labels, "raw": raw, "error": ""}


def _metrics_for_one(evidence: Sequence[Dict[str, Any]], labels: Sequence[Dict[str, Any]], k_values: Sequence[int]) -> Dict[str, float]:
    relevance = {str(item.get("evidence_id") or ""): int(item.get("relevance") or 0) for item in labels}
    relevant_total = sum(1 for value in relevance.values() if value > 0)
    ranked_ids = [str(item.get("evidence_id") or "") for item in evidence]
    out: Dict[str, float] = {}
    for k in k_values:
        top_ids = ranked_ids[:k]
        hits = sum(1 for eid in top_ids if relevance.get(eid, 0) > 0)
        out[f"recall@{k}"] = float(hits / relevant_total) if relevant_total else 0.0
    return out


def _render_visual_evidence_for_judge(
    visual_evidence: Sequence[Dict[str, Any]],
    *,
    max_images: int = 10,
) -> tuple[List[Dict[str, Any]], List[str]]:
    def _render_with_pymupdf(pdf_path: str, page: int) -> str | None:
        import tempfile

        try:
            import fitz

            doc = fitz.open(pdf_path)
            try:
                page_index = max(0, int(page) - 1)
                if page_index >= int(doc.page_count):
                    return None
                pix = doc.load_page(page_index).get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                tmp.close()
                pix.save(tmp.name)
                return tmp.name
            finally:
                doc.close()
        except Exception:
            return None

    rendered: List[Dict[str, Any]] = []
    image_paths: List[str] = []
    for item in visual_evidence[:max_images]:
        row = dict(item)
        source_path = str(row.get("source_path") or "").strip()
        if not source_path:
            rendered.append(row)
            continue
        page = int(row.get("page") or 1)
        image_path = _render_with_pymupdf(source_path, page)
        if image_path:
            image_paths.append(image_path)
            row["attached_image"] = f"Image {len(image_paths)}"
        rendered.append(row)
    if len(visual_evidence) > max_images:
        rendered.extend(dict(item) for item in visual_evidence[max_images:])
    return rendered, image_paths


def _mean(values: Sequence[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _aggregate(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    values: Dict[str, List[float]] = defaultdict(list)
    for row in rows:
        for key, value in (row.get("metrics") or {}).items():
            values[key].append(float(value))
    return {
        key: {
            "mean": _mean(vals),
            "count": len(vals),
            "min": min(vals) if vals else 0.0,
            "max": max(vals) if vals else 0.0,
        }
        for key, vals in sorted(values.items())
    }


def _group_summary(rows: Sequence[Dict[str, Any]], key: str) -> Dict[str, Any]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "")].append(row)
    return {name: _aggregate(items) for name, items in sorted(grouped.items())}


def _write_stage_stats(
    path: Path,
    *,
    run_id: str,
    stage: str,
    counts: Dict[str, Any],
    rows: Sequence[Dict[str, Any]] | None = None,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    records = list(rows or [])
    errors = [row for row in records if str(row.get("severity") or "").lower() == "error"]
    warnings = [row for row in records if str(row.get("severity") or "").lower() != "error"]
    payload = {
        "run_id": run_id,
        "stage": stage,
        "created_at": _utc_now(),
        "counts": {
            **counts,
            "errors": len(errors),
            "warnings": len(warnings),
            "by_reason": dict(Counter(str(row.get("reason") or "unknown") for row in records)),
        },
        "errors": errors,
        "warnings": warnings,
    }
    if extra:
        payload["extra"] = extra
    _safe_write_json(path, payload)
    return payload


def _write_generate_outputs(path: Path, sections: Sequence[SectionRecord], questions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    questions_by_section: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for question in questions:
        questions_by_section[str(question.get("section_id") or "")].append(question)
    rows: List[Dict[str, Any]] = []
    for section in sections:
        section_questions = questions_by_section.get(section.section_id, [])
        good = [q for q in section_questions if q.get("question") and q.get("question_type") in QUESTION_TYPES]
        errors = [q for q in section_questions if q.get("reason") or q.get("error")]
        rows.append(
            {
                "stage": "generate",
                "section_id": section.section_id,
                "doc_id": section.doc_id,
                "relative_path": section.relative_path,
                "top_folder": section.top_folder,
                "status": "processed" if len(good) >= 5 else "partial_or_failed",
                "output_exists": bool(good),
                "question_count": len(good),
                "query_ids": [q.get("query_id") for q in good],
                "issues": errors,
            }
        )
    _safe_write_json(path, rows)
    return rows


def _write_retrieve_outputs(path: Path, questions: Sequence[Dict[str, Any]], judgments: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    judgments_by_query = {str(row.get("query_id") or ""): row for row in judgments}
    rows: List[Dict[str, Any]] = []
    for question in questions:
        query_id = str(question.get("query_id") or "")
        judgment = judgments_by_query.get(query_id)
        error = (judgment.get("llm_judgment") or {}).get("error") if judgment else ""
        rows.append(
            {
                "stage": "retrieve",
                "query_id": query_id,
                "doc_id": question.get("doc_id"),
                "section_id": question.get("section_id"),
                "relative_path": question.get("relative_path"),
                "top_folder": question.get("top_folder"),
                "question_type": question.get("question_type"),
                "status": "processed" if judgment and not error else ("failed" if error else "missing"),
                "output_exists": bool(judgment),
                "retrieved_count": len(judgment.get("retrieved") or []) if judgment else 0,
                "visual_retrieved_count": len(judgment.get("visual_retrieved") or []) if judgment else 0,
                "metrics": judgment.get("metrics") if judgment else {},
                "error": error,
            }
        )
    _safe_write_json(path, rows)
    return rows


def _stage_text_rag_source(
    *,
    candidates: Sequence[PdfCandidate],
    processing_dir: Path,
    text_source_dir: Path,
) -> List[Dict[str, Any]]:
    """Create a symlink-only RAG source containing English-passed document folders."""
    _clear_dir_contents(text_source_dir)
    stage4_dir = processing_dir / "stage4_rag_ready"
    rows: List[Dict[str, Any]] = []
    for idx, candidate in enumerate(candidates, start=1):
        source_dir = stage4_dir / candidate.doc_id
        if not source_dir.exists():
            source_dir = stage4_dir / _normalizer_safe_stem(candidate.doc_id)
        if not source_dir.exists():
            rows.append(
                {
                    "stage": "index",
                    "doc_id": candidate.doc_id,
                    "relative_path": candidate.relative_path,
                    "top_folder": candidate.top_folder,
                    "status": "missing",
                    "output_exists": False,
                    "reason": "missing_rag_source",
                    "severity": "error",
                }
            )
            continue
        dest = text_source_dir / source_dir.name
        dest.symlink_to(source_dir.resolve(), target_is_directory=True)
        rows.append(
            {
                "stage": "index",
                "doc_id": candidate.doc_id,
                "relative_path": candidate.relative_path,
                "top_folder": candidate.top_folder,
                "status": "staged",
                "output_exists": True,
                "text_rag_source": str(dest),
            }
        )
        if idx == 1 or idx == len(candidates) or idx % 25 == 0:
            _progress("text-index-source", idx, len(candidates), candidate.relative_path)
    return rows


def _stage_visual_pdf_source(
    *,
    candidates: Sequence[PdfCandidate],
    visual_source_dir: Path,
    manifest_path: Path,
) -> List[Dict[str, Any]]:
    """Create a symlink-only PDF source for ColQwen page-image indexing."""
    _clear_dir_contents(visual_source_dir)
    rows: List[Dict[str, Any]] = []
    for idx, candidate in enumerate(candidates, start=1):
        source = Path(candidate.source_path)
        dest = visual_source_dir / candidate.staged_filename
        if not source.exists():
            rows.append(
                {
                    "stage": "index",
                    "doc_id": candidate.doc_id,
                    "relative_path": candidate.relative_path,
                    "top_folder": candidate.top_folder,
                    "status": "missing",
                    "output_exists": False,
                    "reason": "missing_pdf_source",
                    "severity": "error",
                    "source_path": candidate.source_path,
                }
            )
            continue
        dest.symlink_to(source.resolve())
        rows.append(
            {
                "stage": "index",
                "doc_id": candidate.doc_id,
                "relative_path": candidate.relative_path,
                "top_folder": candidate.top_folder,
                "status": "staged",
                "output_exists": True,
                "staged_filename": candidate.staged_filename,
                "source_path": candidate.source_path,
                "visual_pdf_source": str(dest),
            }
        )
        if idx == 1 or idx == len(candidates) or idx % 25 == 0:
            _progress("visual-index-source", idx, len(candidates), candidate.relative_path)
    _safe_write_json(manifest_path, rows)
    return rows


def _build_retriever(doc_dir: Path, output_dir: Path, retriever_type: str, cfg: Dict[str, Any], force: bool):
    from src.retrieval.rag_retrievers import create_rag_retriever, load_rag_retriever

    tr = cfg.get("text_retrieval", {}) or {}
    chunking = tr.get("chunking", {}) or {}
    index_dir = output_dir / "retrieval_index"
    if not force and (index_dir / "index_meta.json").exists():
        loaded = load_rag_retriever(index_dir, reranker_model=None)
        if loaded and retriever_type in loaded.get_available_retrievers():
            print(f"Loaded existing text retrieval index: {index_dir}", flush=True)
            return loaded
    return create_rag_retriever(
        doc_dir=doc_dir,
        retriever_types=[retriever_type],
        index_dir=index_dir,
        save_index=True,
        chunk_size=int(chunking.get("chunk_size", 1000)),
        chunk_overlap=int(chunking.get("chunk_overlap", 200)),
        enable_chunking=bool(chunking.get("enabled", True)),
        reranker_model=None,
    )


def _colqwen_config_from_runtime(cfg: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    import torch

    image_cfg = cfg.get("image_retrieval", {}) or {}
    colqwen_cfg = image_cfg.get("colqwen", {}) or {}
    quantization = args.colqwen_quantization
    if quantization is None:
        quantization = colqwen_cfg.get("quantization")
    cuda_available = torch.cuda.is_available()
    if quantization in {"4bit", "8bit"} and not cuda_available:
        print(
            f"WARNING: ColQwen {quantization} quantization requires CUDA/bitsandbytes; "
            "CUDA is not available, so quantization is disabled for local indexing.",
            flush=True,
        )
        quantization = None
    return {
        "model": args.colqwen_model or colqwen_cfg.get("model") or "vidore/colqwen2-v1.0",
        "dtype": args.colqwen_dtype or colqwen_cfg.get("torch_dtype") or colqwen_cfg.get("dtype") or "bfloat16",
        "load_in_4bit": cuda_available and (quantization == "4bit" or bool(colqwen_cfg.get("load_in_4bit", False))),
        "load_in_8bit": cuda_available and (quantization == "8bit" or bool(colqwen_cfg.get("load_in_8bit", False))),
        "device_map": colqwen_cfg.get("device_map") or "auto",
        "pdf_dpi": int(args.colqwen_pdf_dpi or colqwen_cfg.get("pdf_dpi") or 150),
    }


def _build_image_retriever(
    *,
    visual_source_dir: Path,
    output_dir: Path,
    cfg: Dict[str, Any],
    args: argparse.Namespace,
):
    from src.retrieval.image_retrievers import create_image_retriever, load_image_retriever

    index_dir = output_dir / "visual_retrieval_index"
    colqwen_config = _colqwen_config_from_runtime(cfg, args)
    if not args.force and (index_dir / "image_index_meta.json").exists():
        loaded = load_image_retriever(index_dir, colqwen_config=colqwen_config)
        if loaded:
            print(f"Loaded existing visual ColQwen index: {index_dir}", flush=True)
            return loaded
    return create_image_retriever(
        pdf_dir=visual_source_dir,
        retriever_types=["colqwen"],
        index_dir=index_dir,
        save_index=True,
        colqwen_config=colqwen_config,
    )


def _visual_batch_complete(batch_index_dir: Path, expected_files: Sequence[str]) -> bool:
    meta_path = batch_index_dir / "image_index_meta.json"
    colqwen_meta_path = batch_index_dir / "colqwen" / "colqwen_meta.json"
    batch_manifest_path = batch_index_dir / "batch_manifest.json"
    if not (meta_path.exists() and colqwen_meta_path.exists() and batch_manifest_path.exists()):
        return False
    try:
        meta = _read_json(colqwen_meta_path)
        manifest = _read_json(batch_manifest_path)
    except Exception:
        return False
    return int(meta.get("num_pages") or 0) > 0 and sorted(manifest.get("files") or []) == sorted(expected_files)


def _merge_visual_batch_indexes(batch_index_dirs: Sequence[Path], output_dir: Path) -> None:
    import pickle

    merged_index: List[Any] = []
    batch_meta: List[Dict[str, Any]] = []
    missing_batches: List[str] = []
    for batch_index_dir in batch_index_dirs:
        index_path = batch_index_dir / "colqwen" / "colqwen_index.pkl"
        meta_path = batch_index_dir / "colqwen" / "colqwen_meta.json"
        if not index_path.exists():
            missing_batches.append(batch_index_dir.name)
            continue
        with index_path.open("rb") as f:
            rows = pickle.load(f)
        if not rows:
            missing_batches.append(batch_index_dir.name)
            continue
        merged_index.extend(rows)
        meta = _read_json(meta_path) if meta_path.exists() else {}
        batch_meta.append(
            {
                "batch": batch_index_dir.name,
                "batch_index_dir": str(batch_index_dir),
                "num_pages": len(rows),
                "model_name": meta.get("model_name"),
            }
        )

    if missing_batches:
        raise RuntimeError(
            "Visual batch index is incomplete; missing or empty batches: "
            + ", ".join(sorted(missing_batches))
        )
    if not merged_index:
        raise RuntimeError("No visual batch embeddings were available to merge.")

    colqwen_dir = output_dir / "visual_retrieval_index" / "colqwen"
    colqwen_dir.mkdir(parents=True, exist_ok=True)
    with (colqwen_dir / "colqwen_index.pkl").open("wb") as f:
        pickle.dump(merged_index, f)
    _safe_write_json(
        colqwen_dir / "colqwen_meta.json",
        {
            "model_name": next((row.get("model_name") for row in batch_meta if row.get("model_name")), None),
            "num_pages": len(merged_index),
            "pdf_dir": "batched_visual_pdf_source",
            "batches": batch_meta,
        },
    )
    _safe_write_json(
        output_dir / "visual_retrieval_index" / "image_index_meta.json",
        {
            "retrievers": ["colqwen"],
            "pdf_dir": "batched_visual_pdf_source",
            "num_pages": len(merged_index),
            "batch_count": len(batch_meta),
        },
    )


def _build_image_retriever_batches(
    *,
    candidates: Sequence[PdfCandidate],
    work_dir: Path,
    output_dir: Path,
    cfg: Dict[str, Any],
    args: argparse.Namespace,
) -> Any:
    from src.retrieval.image_retrievers import load_image_retriever

    batch_size = max(1, int(args.visual_index_batch_size))
    batch_root = work_dir / "visual_index_batches"
    batch_index_root = output_dir / "visual_retrieval_batches"
    batch_root.mkdir(parents=True, exist_ok=True)
    batch_index_root.mkdir(parents=True, exist_ok=True)
    batch_index_dirs: List[Path] = []
    total_batches = math.ceil(len(candidates) / batch_size)
    planned_batches: List[tuple[int, List[PdfCandidate], Path, List[str]]] = []

    for batch_idx, start in enumerate(range(0, len(candidates), batch_size), start=1):
        batch = list(candidates[start : start + batch_size])
        batch_index_dir = batch_index_root / f"batch_{batch_idx:04d}"
        expected_files = [candidate.staged_filename for candidate in batch]
        planned_batches.append((batch_idx, batch, batch_index_dir, expected_files))

    if any(not _visual_batch_complete(batch_index_dir, expected_files) for _, _, batch_index_dir, expected_files in planned_batches):
        stale_merged_index = output_dir / "visual_retrieval_index"
        if stale_merged_index.exists():
            shutil.rmtree(stale_merged_index)
            print(f"Removed stale merged visual index: {stale_merged_index}", flush=True)

    for batch_idx, batch, batch_index_dir, expected_files in planned_batches:
        batch_input_dir = batch_root / f"batch_{batch_idx:04d}" / "input"
        batch_file = output_dir / f"visual_index_batch_{batch_idx:04d}.json"
        batch_stats_file = output_dir / f"visual_index_batch_{batch_idx:04d}_stats.json"
        batch_index_dirs.append(batch_index_dir)

        if not args.force and _visual_batch_complete(batch_index_dir, expected_files):
            print(f"Visual batch {batch_idx}/{total_batches} already indexed; skipping.", flush=True)
            continue

        if batch_index_dir.exists():
            shutil.rmtree(batch_index_dir)
        _safe_write_json(batch_file, [asdict(candidate) for candidate in batch])
        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--internal-visual-index-batch-file",
            str(batch_file),
            "--internal-visual-batch-input-dir",
            str(batch_input_dir),
            "--internal-visual-batch-index-dir",
            str(batch_index_dir),
            "--internal-visual-batch-stats-file",
            str(batch_stats_file),
            "--colqwen-pdf-dpi",
            str(args.colqwen_pdf_dpi),
        ]
        if args.colqwen_model:
            cmd.extend(["--colqwen-model", args.colqwen_model])
        if args.colqwen_dtype:
            cmd.extend(["--colqwen-dtype", args.colqwen_dtype])
        if args.colqwen_quantization:
            cmd.extend(["--colqwen-quantization", args.colqwen_quantization])

        print(f"\n=== Visual index batch {batch_idx}/{total_batches}: {len(batch)} PDF(s) ===", flush=True)
        for candidate in batch:
            print(f"[visual-index-file] {candidate.relative_path}", flush=True)
        result = subprocess.run(cmd, cwd=str(BACKEND_ROOT.parent), text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Visual index batch {batch_idx} failed with exit code {result.returncode}.")
        if not _visual_batch_complete(batch_index_dir, expected_files):
            raise RuntimeError(
                f"Visual index batch {batch_idx} did not produce a complete ColQwen index: {batch_index_dir}"
            )

    _merge_visual_batch_indexes(batch_index_dirs, output_dir)
    loaded = load_image_retriever(
        output_dir / "visual_retrieval_index",
        colqwen_config=_colqwen_config_from_runtime(cfg, args),
    )
    if not loaded:
        raise RuntimeError("Merged visual ColQwen index could not be loaded.")
    return loaded


def _index_stats(text_retriever: Any | None, image_retriever: Any | None) -> Dict[str, Any]:
    text_docs = len(getattr(text_retriever, "documents", []) or []) if text_retriever else 0
    image_pages = 0
    if image_retriever:
        for retriever in getattr(image_retriever, "retrievers", {}).values():
            image_pages += len(getattr(retriever, "index", []) or [])
    return {
        "text_chunks": text_docs,
        "text_retrievers": text_retriever.get_available_retrievers() if text_retriever else [],
        "visual_pages": image_pages,
        "visual_retrievers": image_retriever.get_available_retrievers() if image_retriever else [],
    }


def _load_existing_visual_retriever_for_judge(
    *,
    cfg: Dict[str, Any],
    args: argparse.Namespace,
    run_dir: Path,
):
    from src.retrieval.image_retrievers import load_image_retriever

    visual_index_dir = run_dir / "visual_retrieval_index"
    image_retriever = load_image_retriever(
        visual_index_dir,
        colqwen_config=_colqwen_config_from_runtime(cfg, args),
    )
    if not image_retriever or "colqwen" not in image_retriever.get_available_retrievers():
        raise RuntimeError(f"Missing existing visual ColQwen index at {visual_index_dir}.")
    return image_retriever


def _indexed_visual_candidates(
    image_retriever: Any,
    candidates: Sequence[PdfCandidate],
) -> tuple[List[PdfCandidate], set[str]]:
    by_filename = {candidate.staged_filename: candidate for candidate in candidates}
    indexed_doc_ids: set[str] = set()
    for retriever in getattr(image_retriever, "retrievers", {}).values():
        for row in getattr(retriever, "index", []) or []:
            source = str((row or {}).get("source") or "")
            candidate = by_filename.get(source)
            if candidate:
                indexed_doc_ids.add(candidate.doc_id)
    indexed_candidates = [candidate for candidate in candidates if candidate.doc_id in indexed_doc_ids]
    return indexed_candidates, indexed_doc_ids


def _filter_questions_to_indexed_visual_docs(
    questions: Sequence[Dict[str, Any]],
    *,
    indexed_doc_ids: set[str],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    kept: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    for question in questions:
        doc_id = str(question.get("doc_id") or "")
        if doc_id in indexed_doc_ids:
            kept.append(question)
            continue
        skipped.append(
            {
                "stage": "retrieve",
                "query_id": question.get("query_id"),
                "doc_id": doc_id,
                "section_id": question.get("section_id"),
                "relative_path": question.get("relative_path"),
                "reason": "visual_doc_not_in_current_index",
                "severity": "warning",
            }
        )
    return kept, skipped


def _setup_retrieval_indexes(
    *,
    cfg: Dict[str, Any],
    args: argparse.Namespace,
    english_candidates: Sequence[PdfCandidate],
    processing_dir: Path,
    work_dir: Path,
    run_dir: Path,
) -> tuple[Any | None, Any | None, List[Dict[str, Any]], Dict[str, Any]]:
    text_retriever = None
    image_retriever = None
    rows: List[Dict[str, Any]] = []

    if args.retrieval_modalities in {"text", "both"}:
        print("\n=== Building run-local text index (BM25 + dense via hybrid) ===", flush=True)
        text_source_dir = work_dir / "text_rag_source"
        rows.extend(
            _stage_text_rag_source(
                candidates=english_candidates,
                processing_dir=processing_dir,
                text_source_dir=text_source_dir,
            )
        )
        text_retriever = _build_retriever(text_source_dir, run_dir, args.retriever_type, cfg, args.force)

    if args.retrieval_modalities in {"image", "both"}:
        print("\n=== Building run-local visual index (ColQwen page embeddings) ===", flush=True)
        visual_candidates, visual_skipped_rows = _filter_visual_candidates_by_page_limit(
            english_candidates,
            max_pages=int(args.max_visual_pdf_pages),
            report_path=run_dir / "visual_page_filter_report.json",
        )
        rows.extend(visual_skipped_rows)
        visual_source_dir = work_dir / "visual_pdf_source"
        rows.extend(
            _stage_visual_pdf_source(
                candidates=visual_candidates,
                visual_source_dir=visual_source_dir,
                manifest_path=run_dir / "visual_pdf_manifest.json",
            )
        )
        image_retriever = _build_image_retriever_batches(
            candidates=visual_candidates,
            work_dir=work_dir,
            output_dir=run_dir,
            cfg=cfg,
            args=args,
        )
        if not image_retriever or "colqwen" not in image_retriever.get_available_retrievers():
            raise RuntimeError(
                "Visual ColQwen index was not built. "
                "Check ColQwen dependencies/device settings and rerun --stage index."
            )

    stats = _index_stats(text_retriever, image_retriever)
    stats.update(
        {
            "retrieval_modalities": args.retrieval_modalities,
            "text_index_dir": str(run_dir / "retrieval_index"),
            "visual_index_dir": str(run_dir / "visual_retrieval_index"),
            "max_visual_pdf_pages": int(args.max_visual_pdf_pages),
        }
    )
    return text_retriever, image_retriever, rows, stats


def _judge_one_question(
    *,
    gen: Any,
    retriever: Any,
    image_retriever: Any | None,
    image_candidates: Sequence[PdfCandidate],
    question: Dict[str, Any],
    retriever_type: str,
    top_k: int,
    image_top_k: int,
    k_values: Sequence[int],
    llm_gate: Any,
) -> Dict[str, Any]:
    raw_results = []
    if retriever:
        raw_results = retriever.search(
            str(question.get("question") or ""),
            retriever_type=retriever_type,
            top_k=top_k,
            use_reranker=False,
        )
    evidence = _normalize_evidence(raw_results)
    visual_evidence: List[Dict[str, Any]] = []
    if image_retriever:
        raw_visual = image_retriever.search(
            str(question.get("question") or ""),
            retriever_type="colqwen",
            top_k=image_top_k,
        )
        visual_evidence = _normalize_visual_evidence(raw_visual, candidates=image_candidates)
    judged_visual_evidence, judge_image_paths = _render_visual_evidence_for_judge(
        visual_evidence,
        max_images=image_top_k,
    )
    judged_evidence = [*evidence, *judged_visual_evidence]
    try:
        with llm_gate:
            judgment = _judge_relevance(gen, question, judged_evidence, image_paths=judge_image_paths)
    finally:
        for image_path in judge_image_paths:
            with contextlib.suppress(Exception):
                Path(image_path).unlink()
    metrics = _metrics_for_one(judged_evidence, judgment.get("labels") or [], k_values)
    return {
        "query_id": question.get("query_id"),
        "doc_id": question.get("doc_id"),
        "section_id": question.get("section_id"),
        "top_folder": question.get("top_folder"),
        "relative_path": question.get("relative_path"),
        "question_type": question.get("question_type"),
        "question": question.get("question"),
        "retrieved": evidence,
        "visual_retrieved": visual_evidence,
        "llm_judgment": judgment,
        "metrics": metrics,
        "created_at": _utc_now(),
    }


def _run_judgments(
    *,
    gen: Any,
    retriever: Any,
    image_retriever: Any | None,
    image_candidates: Sequence[PdfCandidate],
    questions: Sequence[Dict[str, Any]],
    output_path: Path,
    retriever_type: str,
    top_k: int,
    image_top_k: int,
    k_values: Sequence[int],
    concurrency: int,
    llm_concurrency: int,
    resume: bool,
) -> List[Dict[str, Any]]:
    existing = _read_jsonl(output_path) if resume else []
    done = {str(row.get("query_id") or "") for row in existing}
    pending = [q for q in questions if q.get("question") and str(q.get("query_id") or "") not in done]
    results = list(existing)
    print(f"\n=== Judging retrieval relevance: pending={len(pending)} existing={len(existing)} ===", flush=True)
    llm_gate = threading.Semaphore(max(1, int(llm_concurrency)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        futures = [
            executor.submit(
                _judge_one_question,
                gen=gen,
                retriever=retriever,
                image_retriever=image_retriever,
                image_candidates=image_candidates,
                question=question,
                retriever_type=retriever_type,
                top_k=top_k,
                image_top_k=image_top_k,
                k_values=k_values,
                llm_gate=llm_gate,
            )
            for question in pending
        ]
        batch: List[Dict[str, Any]] = []
        for idx, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            row = future.result()
            batch.append(row)
            results.append(row)
            if len(batch) >= 20:
                _append_jsonl(output_path, batch)
                batch = []
            _progress("judge", idx, len(pending), str(row.get("relative_path") or ""))
        _append_jsonl(output_path, batch)
    return results


def _build_report(
    *,
    run_id: str,
    args: argparse.Namespace,
    candidates: Sequence[PdfCandidate],
    skipped: Sequence[Dict[str, Any]],
    selected_sections: Sequence[SectionRecord],
    questions: Sequence[Dict[str, Any]],
    judgments: Sequence[Dict[str, Any]],
    processing_stats: Dict[str, Any],
    started_at: float,
) -> Dict[str, Any]:
    metric_rows = [
        {
            "query_id": row.get("query_id"),
            "doc_id": row.get("doc_id"),
            "top_folder": row.get("top_folder"),
            "relative_path": row.get("relative_path"),
            "question_type": row.get("question_type"),
            "metrics": row.get("metrics") or {},
        }
        for row in judgments
    ]
    skipped_by_reason = Counter(str(row.get("reason") or "unknown") for row in skipped)
    return {
        "run_id": run_id,
        "status": "completed",
        "created_at": _utc_now(),
        "config": {
            "stage": args.stage,
            "dataset_root": str(Path(args.dataset_root).resolve()),
            "section_cap": args.section_cap,
            "top_k": args.top_k,
            "k_values": list(args.k_values),
            "retriever_type": args.retriever_type,
            "retrieval_modalities": args.retrieval_modalities,
            "image_top_k": args.image_top_k,
            "model": args.model,
            "provider": args.provider,
            "colqwen_model": args.colqwen_model,
            "colqwen_dtype": args.colqwen_dtype,
            "colqwen_quantization": args.colqwen_quantization,
            "colqwen_pdf_dpi": args.colqwen_pdf_dpi,
            "visual_index_batch_size": args.visual_index_batch_size,
            "pdf_content_source": args.pdf_content_source,
            "pdf_ocr": not args.no_pdf_ocr,
            "generation_concurrency": args.generation_concurrency,
            "judge_concurrency": args.judge_concurrency,
            "min_alpha_chars": args.min_alpha_chars,
            "max_cjk_ratio": args.max_cjk_ratio,
            "min_section_chars": args.min_section_chars,
        },
        "counts": {
            "pdf_candidates": len(candidates),
            "skipped_pdfs": len(skipped),
            "selected_sections": len(selected_sections),
            "questions": len([q for q in questions if q.get("question")]),
            "judgments": len(judgments),
            "skipped_by_reason": dict(skipped_by_reason),
        },
        "processing_stats": processing_stats,
        "metrics": {
            "overall": _aggregate(metric_rows),
            "by_question_type": _group_summary(metric_rows, "question_type"),
            "by_folder": _group_summary(metric_rows, "top_folder"),
            "by_file": _group_summary(metric_rows, "relative_path"),
        },
        "duration_seconds": round(time.perf_counter() - started_at, 2),
    }


def _write_summary(path: Path, report: Dict[str, Any]) -> None:
    lines = [
        f"# PDF Retrieval Evaluation Summary",
        "",
        f"- Evaluation: `{report['run_id']}`",
        f"- Status: `{report['status']}`",
        f"- PDFs considered: {report['counts']['pdf_candidates']}",
        f"- PDFs skipped: {report['counts']['skipped_pdfs']}",
        f"- Selected sections: {report['counts']['selected_sections']}",
        f"- Questions: {report['counts']['questions']}",
        f"- Judgments: {report['counts']['judgments']}",
        f"- Duration seconds: {report['duration_seconds']}",
        "",
        "## Overall Recall",
        "",
    ]
    for metric, data in (report.get("metrics", {}).get("overall") or {}).items():
        lines.append(f"- {metric}: {data.get('mean', 0.0):.4f} (n={data.get('count', 0)})")
    lines.extend(["", "## Skipped PDFs", ""])
    for reason, count in sorted((report.get("counts", {}).get("skipped_by_reason") or {}).items()):
        lines.append(f"- {reason}: {count}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_k_values(raw: str) -> List[int]:
    values = []
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        values.append(int(part))
    return sorted({k for k in values if k > 0}) or list(DEFAULT_K_VALUES)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PDF-only English retrieval evaluation over eval-input.")
    parser.add_argument(
        "--stage",
        choices=["all", "parse", "generate", "index", "retrieve", "report"],
        default="all",
        help="Run one stage. Later stages reuse the selected --run-id output folder.",
    )
    parser.add_argument(
        "--run-id",
        default=FIXED_RUN_ID,
        help="Folder name under --output-root and --work-root for this evaluation run.",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Run retrieval judging only. Loads existing indexes and never builds or deletes embeddings.",
    )
    parser.add_argument("--dataset-root", default=str(BACKEND_ROOT / "input" / "eval-input"))
    parser.add_argument("--output-root", default=str(BACKEND_ROOT / "evals" / "retrieval" / "results"))
    parser.add_argument("--work-root", default=str(BACKEND_ROOT / "evals" / "retrieval" / ".work"))
    parser.add_argument("--max-pdfs", type=int, default=None, help="Optional cap for smoke tests.")
    parser.add_argument("--section-cap", type=int, default=120)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--image-top-k", type=int, default=10)
    parser.add_argument("--k-values", type=_parse_k_values, default=list(DEFAULT_K_VALUES))
    parser.add_argument("--retriever-type", choices=["bm25", "dense", "hybrid"], default="hybrid")
    parser.add_argument("--retrieval-modalities", choices=["text", "image", "both"], default="both")
    parser.add_argument("--model", default="gpt-5.4-nano")
    parser.add_argument("--provider", default="openai", help="LLM provider for generation and judging.")
    parser.add_argument("--colqwen-model", default=None)
    parser.add_argument("--colqwen-dtype", default=None)
    parser.add_argument("--colqwen-quantization", choices=["4bit", "8bit"], default=None)
    parser.add_argument("--colqwen-pdf-dpi", type=int, default=150)
    parser.add_argument(
        "--max-visual-pdf-pages",
        type=int,
        default=100,
        help="Maximum PDF page count for visual indexing.",
    )
    parser.add_argument("--visual-index-batch-size", type=int, default=5)
    parser.add_argument(
        "--pdf-content-source",
        choices=["pymupdf", "docling", "hybrid", "hybrid_batched"],
        default="docling",
        help="PDF text extraction mode for parsing. Default uses local Docling, not SageMaker.",
    )
    parser.add_argument("--no-pdf-ocr", action="store_true", help="Disable OCR for CustomPdfReader parsing.")
    parser.add_argument(
        "--enable-pdf-vlm",
        action="store_true",
        help="Enable Docling picture-description VLM during PDF parsing.",
    )
    parser.add_argument(
        "--enable-pdf-formula-enrichment",
        action="store_true",
        help="Enable Docling formula enrichment during PDF parsing.",
    )
    parser.add_argument(
        "--pdf-vlm-model",
        default="HuggingFaceTB/SmolVLM-256M-Instruct",
        help="Docling picture-description VLM model used when --enable-pdf-vlm is set.",
    )
    parser.add_argument("--pdf-vlm-batch-size", type=int, default=4)
    parser.add_argument(
        "--pdf-vlm-page-filter",
        choices=["visual_or_formula_pages", "all", "all_pages"],
        default="visual_or_formula_pages",
        help="Pages selected for the extra VLM/formula enrichment pass in hybrid_batched mode.",
    )
    parser.add_argument("--generation-concurrency", type=int, default=10)
    parser.add_argument("--judge-concurrency", type=int, default=20)
    parser.add_argument(
        "--llm-concurrency",
        type=int,
        default=2,
        help="Maximum concurrent LLM judge calls. Retrieval/rendering still uses --judge-concurrency.",
    )
    parser.add_argument("--min-alpha-chars", type=int, default=500)
    parser.add_argument("--max-cjk-ratio", type=float, default=0.05)
    parser.add_argument("--min-section-chars", type=int, default=500)
    parser.add_argument("--parse-batch-size", type=int, default=1, help="PDFs per parse subprocess. Default 1 releases memory after every PDF.")
    parser.add_argument("--parse-batch-timeout-seconds", type=int, default=3600, help="Timeout per parse subprocess batch.")
    parser.add_argument("--parse-heartbeat-seconds", type=int, default=30, help="Print still-running parse status every N seconds.")
    parser.add_argument("--skip-processing", action="store_true", help="Use existing run-local artifacts.")
    parser.add_argument("--resume", action="store_true", help="Reuse existing questions/judgments.")
    parser.add_argument("--force", action="store_true", help="Re-run a stage even when its output files already exist.")
    parser.add_argument("--internal-parse-batch-file", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    parser.add_argument("--internal-batch-input-dir", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    parser.add_argument("--internal-processing-dir", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    parser.add_argument("--internal-batch-stats-file", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    parser.add_argument("--internal-visual-index-batch-file", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    parser.add_argument("--internal-visual-batch-input-dir", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    parser.add_argument("--internal-visual-batch-index-dir", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    parser.add_argument("--internal-visual-batch-stats-file", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.judge:
        args.stage = "retrieve"
    started = time.perf_counter()
    cfg = _load_runtime_config()

    if hasattr(args, "internal_parse_batch_file"):
        batch_candidates = _load_candidates_list(Path(args.internal_parse_batch_file), "internal parse batch")
        batch_input_dir = Path(args.internal_batch_input_dir).resolve()
        batch_processing_dir = Path(args.internal_processing_dir).resolve()
        _stage_pdfs(batch_candidates, batch_input_dir)
        stats = _run_processing(
            batch_input_dir,
            batch_processing_dir,
            cfg,
            args.pdf_content_source,
            enable_pdf_ocr=not args.no_pdf_ocr,
            enable_pdf_vlm=args.enable_pdf_vlm,
            enable_pdf_formula_enrichment=args.enable_pdf_formula_enrichment,
            pdf_vlm_model=args.pdf_vlm_model,
            pdf_vlm_batch_size=args.pdf_vlm_batch_size,
            pdf_vlm_page_filter=args.pdf_vlm_page_filter,
            prune_outputs_not_in_input=False,
        )
        _safe_write_json(
            Path(args.internal_batch_stats_file),
            {
                "created_at": _utc_now(),
                "pdf_count": len(batch_candidates),
                "pdfs": [candidate.relative_path for candidate in batch_candidates],
                "processing_stats": stats,
            },
        )
        return

    if hasattr(args, "internal_visual_index_batch_file"):
        from src.retrieval.image_retrievers import create_image_retriever

        batch_candidates = _load_candidates_list(Path(args.internal_visual_index_batch_file), "internal visual index batch")
        batch_input_dir = Path(args.internal_visual_batch_input_dir).resolve()
        batch_index_dir = Path(args.internal_visual_batch_index_dir).resolve()
        batch_stats_file = Path(args.internal_visual_batch_stats_file).resolve()
        _stage_visual_pdf_source(
            candidates=batch_candidates,
            visual_source_dir=batch_input_dir,
            manifest_path=batch_index_dir / "batch_sources.json",
        )
        manager = create_image_retriever(
            pdf_dir=batch_input_dir,
            retriever_types=["colqwen"],
            index_dir=batch_index_dir,
            save_index=True,
            colqwen_config=_colqwen_config_from_runtime(cfg, args),
        )
        if "colqwen" not in manager.get_available_retrievers():
            raise RuntimeError("ColQwen visual batch failed: no colqwen retriever was created.")
        page_count = 0
        for retriever in manager.retrievers.values():
            page_count += len(getattr(retriever, "index", []) or [])
        if page_count <= 0:
            raise RuntimeError("ColQwen visual batch failed: produced 0 page embeddings.")
        _safe_write_json(
            batch_index_dir / "batch_manifest.json",
            {
                "created_at": _utc_now(),
                "files": [candidate.staged_filename for candidate in batch_candidates],
                "relative_paths": [candidate.relative_path for candidate in batch_candidates],
                "page_count": page_count,
            },
        )
        _safe_write_json(
            batch_stats_file,
            {
                "created_at": _utc_now(),
                "pdf_count": len(batch_candidates),
                "page_count": page_count,
                "pdfs": [candidate.relative_path for candidate in batch_candidates],
            },
        )
        return

    run_id = str(args.run_id or FIXED_RUN_ID).strip() or FIXED_RUN_ID
    run_dir = Path(args.output_root).resolve() / run_id
    work_dir = Path(args.work_root).resolve() / run_id
    input_dir = work_dir / "input"
    processing_dir = work_dir / "processing"
    run_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    dataset_root = Path(args.dataset_root).resolve()
    print("=" * 80)
    print("PDF-ONLY ENGLISH RETRIEVAL EVALUATION")
    print("=" * 80)
    print(f"Dataset root: {dataset_root}")
    print(f"Run dir: {run_dir}")
    print(f"Work dir: {work_dir}")
    print(f"Stage: {args.stage}")
    print(f"Parser config: {_parser_config_from_args(args)}")

    selected_sections: List[SectionRecord] = []
    questions: List[Dict[str, Any]] = []
    judgments: List[Dict[str, Any]] = []
    text_retriever: Any | None = None
    image_retriever: Any | None = None
    english_candidates_for_index: List[PdfCandidate] = []
    processing_stats: Dict[str, Any] = {}
    english_passed_path = run_dir / "english_passed_pdfs.json"
    questions_path = run_dir / "questions.jsonl"
    retrieve_suffix = "" if args.retrieval_modalities == "both" else f"_{args.retrieval_modalities}"
    judgments_path = run_dir / f"judgments{retrieve_suffix}.jsonl"
    parse_log_path = run_dir / "parse_console.log"
    parse_outputs_path = run_dir / "stage_parse_outputs.json"
    index_outputs_path = run_dir / "stage_index_outputs.json"
    generate_outputs_path = run_dir / "stage_generate_outputs.json"
    retrieve_stats_path = run_dir / f"stage_retrieve_stats{retrieve_suffix}.json"
    retrieve_outputs_path = run_dir / f"stage_retrieve_outputs{retrieve_suffix}.json"
    report_outputs_path = run_dir / "stage_report_outputs.json"

    if args.stage in {"all", "parse"}:
        candidates, skipped = _discover_pdf_candidates(dataset_root, args.max_pdfs)
        prefilter_skipped = list(skipped)
        previous_candidates: List[PdfCandidate] = []
        previous_parser_config: Dict[str, Any] = {}
        if (run_dir / "pdf_manifest.json").exists():
            previous_manifest = _read_json(run_dir / "pdf_manifest.json")
            previous_candidates = [PdfCandidate(**row) for row in previous_manifest.get("pdf_candidates", [])]
            previous_parser_config = dict(previous_manifest.get("parser_config") or {})
        candidate_set_unchanged = _same_candidate_set(candidates, previous_candidates)
        parser_config = _parser_config_from_args(args)
        parser_config_unchanged = previous_parser_config == parser_config
        parse_done = _stage_outputs_done(
            [
                run_dir / "pdf_manifest.json",
                english_passed_path,
                run_dir / "english_filter_report.json",
                run_dir / "stage_parse_stats.json",
                parse_outputs_path,
            ],
            args.force,
        ) and candidate_set_unchanged and parser_config_unchanged
        if parse_done:
            english_candidates = _load_candidates_list(english_passed_path, "english_passed_pdfs.json")
            skipped = _read_json(run_dir / "english_filter_report.json")
            if (run_dir / "processing_stats.json").exists():
                processing_stats = _read_json(run_dir / "processing_stats.json")
            print(
                f"\nParse stage already has outputs; skipping. "
                f"PDFs={len(candidates)} english_passed={len(english_candidates)}"
            )
            print(f"Parse outputs: {parse_outputs_path}")
            if args.stage == "parse":
                return
        else:
            by_folder = Counter(c.top_folder for c in candidates)
            manifest = {
                "run_id": run_id,
                "dataset_root": str(dataset_root),
                "created_at": _utc_now(),
                "parser_config": parser_config,
                "pdf_candidates": [asdict(c) for c in candidates],
                "candidate_counts_by_folder": dict(sorted(by_folder.items())),
                "prefilter_skipped": skipped,
            }
            _safe_write_json(run_dir / "pdf_manifest.json", manifest)
            print(f"PDF candidates after filename filter: {len(candidates)}")
            print(f"Filename-filter skipped: {len(skipped)}")
            print(f"Top-level folders: {len(by_folder)}")
            for folder, count in sorted(by_folder.items()):
                print(f"  - {folder}: {count}")

            if not candidates:
                raise RuntimeError("No PDF candidates found after filename filtering.")

            all_parse_artifacts_exist = all(_parsed_artifact_path(processing_dir, candidate) for candidate in candidates)
            if args.skip_processing or (all_parse_artifacts_exist and not args.force):
                reason = "--skip-processing" if args.skip_processing else "all parsed JSON artifacts already exist"
                print(f"\nSkipping processing because {reason}.")
                if (run_dir / "processing_stats.json").exists():
                    processing_stats = _read_json(run_dir / "processing_stats.json")
            else:
                batch_stats = _run_processing_batches(
                    candidates=candidates,
                    work_dir=work_dir,
                    processing_dir=processing_dir,
                    run_dir=run_dir,
                    args=args,
                    batch_size=args.parse_batch_size,
                    parse_log_path=parse_log_path,
                )
                processing_stats = {"parse_batches": batch_stats}
                _safe_write_json(run_dir / "processing_stats.json", processing_stats)

            parse_log_warnings = _extract_log_warnings(parse_log_path, candidates)
            english_candidates, skipped = _validate_english_artifacts(
                candidates=candidates,
                processing_dir=processing_dir,
                min_alpha_chars=args.min_alpha_chars,
                max_cjk_ratio=args.max_cjk_ratio,
                skipped_rows=skipped,
            )
            _safe_write_json(run_dir / "english_filter_report.json", skipped)
            _safe_write_json(english_passed_path, [asdict(candidate) for candidate in english_candidates])
            _write_parse_outputs(
                parse_outputs_path,
                candidates=candidates,
                prefilter_skipped=prefilter_skipped,
                english_candidates=english_candidates,
                skipped=skipped,
                log_warnings=parse_log_warnings,
                processing_dir=processing_dir,
            )
            _write_stage_stats(
                run_dir / "stage_parse_stats.json",
                run_id=run_id,
                stage="parse",
                counts={
                    "pdf_candidates_after_filename_filter": len(candidates),
                    "filename_skipped": len([row for row in skipped if row.get("reason") == "filename_language_marker"]),
                    "english_passed": len(english_candidates),
                    "skipped_or_rejected": len(skipped),
                },
                rows=[*skipped, *parse_log_warnings],
                extra={"processing_stats": processing_stats, "parse_log": str(parse_log_path)},
            )
            print(f"\nParsed JSON artifact dir: {processing_dir / 'stage1_normalized' / 'pdf_parsed'}")
            print(f"RAG artifact dir: {processing_dir / 'stage4_rag_ready'}")
            print(f"English-passed PDFs: {len(english_candidates)}")
            print(f"Parse outputs: {parse_outputs_path}")
            print(f"Parse stats: {run_dir / 'stage_parse_stats.json'}")
            if not english_candidates:
                raise RuntimeError(
                    "No PDFs passed artifact-level English filtering. "
                    "Check processing artifacts or relax --min-alpha-chars."
                )
            if args.stage == "parse":
                print("\nParse stage complete. Continue with --stage generate")
                return
    else:
        candidates, skipped = _load_candidates_from_manifest(run_dir / "pdf_manifest.json")
        if (run_dir / "english_filter_report.json").exists():
            skipped = _read_json(run_dir / "english_filter_report.json")
        if (run_dir / "processing_stats.json").exists():
            processing_stats = _read_json(run_dir / "processing_stats.json")
        print(f"Loaded parsed run: PDFs={len(candidates)} skipped={len(skipped)}")

    if args.stage in {"all", "generate"}:
        generate_done = _stage_outputs_done(
            [
                run_dir / "selected_sections.json",
                questions_path,
                run_dir / "stage_generate_stats.json",
                generate_outputs_path,
            ],
            args.force,
        )
        if generate_done:
            selected_sections = _load_selected_sections(run_dir / "selected_sections.json")
            questions = _read_jsonl(questions_path)
            good_questions = [q for q in questions if q.get("question") and q.get("question_type") in QUESTION_TYPES]
            expected_questions = len(selected_sections) * 5
            if len(good_questions) >= expected_questions:
                print(f"\nGenerate stage already has outputs; skipping. Questions={len(good_questions)}")
                print(f"Generate outputs: {generate_outputs_path}")
                if args.stage == "generate":
                    return
            else:
                print(
                    f"\nGenerate outputs exist but are incomplete "
                    f"({len(good_questions)}/{expected_questions} valid questions); regenerating.",
                    flush=True,
                )
                generate_done = False
        if not generate_done and args.resume and (run_dir / "selected_sections.json").exists():
            selected_sections = _load_selected_sections(run_dir / "selected_sections.json")
            section_filter_report_path = run_dir / "section_filter_report.json"
            section_filter_rows = _read_json(section_filter_report_path) if section_filter_report_path.exists() else []
            gen = _build_generator(cfg, args.provider, args.model, max_tokens=3000)
            questions = _generate_questions(
                gen=gen,
                sections=selected_sections,
                output_path=questions_path,
                concurrency=args.generation_concurrency,
                resume=args.resume,
            )
            good_questions = [q for q in questions if q.get("question") and q.get("question_type") in QUESTION_TYPES]
            question_errors = [q for q in questions if q.get("reason") or q.get("error")]
            _write_generate_outputs(generate_outputs_path, selected_sections, questions)
            _write_stage_stats(
                run_dir / "stage_generate_stats.json",
                run_id=run_id,
                stage="generate",
                counts={
                    "selected_sections": len(selected_sections),
                    "expected_questions": len(selected_sections) * 5,
                    "questions": len(good_questions),
                },
                rows=[*section_filter_rows, *question_errors],
            )
            print(f"\nGenerated questions: {len(good_questions)}")
            print(f"Generate outputs: {generate_outputs_path}")
            print(f"Generate stats: {run_dir / 'stage_generate_stats.json'}")
            expected_questions = len(selected_sections) * 5
            if len(good_questions) < expected_questions:
                raise RuntimeError(
                    f"Question generation incomplete: {len(good_questions)}/{expected_questions}. "
                    f"Check {run_dir / 'stage_generate_stats.json'}."
                )
            if args.stage == "generate":
                print("\nGenerate stage complete. Continue with --stage retrieve")
                return
        elif not generate_done:
            english_candidates = _load_candidates_list(english_passed_path, "english_passed_pdfs.json")
            all_sections, section_filter_rows = _collect_sections(
                candidates=english_candidates,
                processing_dir=processing_dir,
                min_section_chars=args.min_section_chars,
                skipped_rows=[],
            )
            selected_sections = _balanced_select_sections(all_sections, args.section_cap)
            _safe_write_json(run_dir / "section_filter_report.json", section_filter_rows)
            _safe_write_json(run_dir / "selected_sections.json", [asdict(section) for section in selected_sections])
            print(f"\nValid sections after section filtering: {len(all_sections)}")
            print(f"Selected sections: {len(selected_sections)}")
            print(f"Expected questions: {len(selected_sections) * 5}")
            if not selected_sections:
                _write_stage_stats(
                    run_dir / "stage_generate_stats.json",
                    run_id=run_id,
                    stage="generate",
                    counts={
                        "english_pdfs": len(english_candidates),
                        "valid_sections": len(all_sections),
                        "selected_sections": 0,
                        "questions": 0,
                    },
                    rows=section_filter_rows,
                )
                raise RuntimeError(
                    "No valid sections found after section filtering. "
                    "Check section_filter_report.json or relax --min-section-chars."
                )
            gen = _build_generator(cfg, args.provider, args.model, max_tokens=3000)
            if questions_path.exists():
                questions_path.unlink()
            questions = _generate_questions(
                gen=gen,
                sections=selected_sections,
                output_path=questions_path,
                concurrency=args.generation_concurrency,
                resume=False,
            )
            good_questions = [q for q in questions if q.get("question") and q.get("question_type") in QUESTION_TYPES]
            question_errors = [q for q in questions if q.get("reason") or q.get("error")]
            _write_generate_outputs(generate_outputs_path, selected_sections, questions)
            _write_stage_stats(
                run_dir / "stage_generate_stats.json",
                run_id=run_id,
                stage="generate",
                counts={
                    "selected_sections": len(selected_sections),
                    "expected_questions": len(selected_sections) * 5,
                    "questions": len(good_questions),
                },
                rows=[*section_filter_rows, *question_errors],
            )
            print(f"\nGenerated questions: {len(good_questions)}")
            print(f"Generate outputs: {generate_outputs_path}")
            print(f"Generate stats: {run_dir / 'stage_generate_stats.json'}")
            expected_questions = len(selected_sections) * 5
            if len(good_questions) < expected_questions:
                raise RuntimeError(
                    f"Question generation incomplete: {len(good_questions)}/{expected_questions}. "
                    f"Check {run_dir / 'stage_generate_stats.json'}."
                )
            if args.stage == "generate":
                print("\nGenerate stage complete. Continue with --stage retrieve")
                return
    else:
        questions = _read_jsonl(questions_path)
        good_questions = [q for q in questions if q.get("question") and q.get("question_type") in QUESTION_TYPES]
        print(f"Loaded questions: {len(good_questions)}")

    if args.stage in {"all", "index"}:
        english_candidates_for_index = _selected_candidates_for_index(run_dir, english_passed_path)
        text_retriever, image_retriever, index_rows, index_stats = _setup_retrieval_indexes(
            cfg=cfg,
            args=args,
            english_candidates=english_candidates_for_index,
            processing_dir=processing_dir,
            work_dir=work_dir,
            run_dir=run_dir,
        )
        _safe_write_json(index_outputs_path, index_rows)
        _write_stage_stats(
            run_dir / "stage_index_stats.json",
            run_id=run_id,
            stage="index",
            counts={
                "indexed_pdfs": len(english_candidates_for_index),
                **index_stats,
            },
            rows=[row for row in index_rows if row.get("reason")],
        )
        print(f"Index outputs: {index_outputs_path}")
        print(f"Index stats: {run_dir / 'stage_index_stats.json'}")
        if args.stage == "index":
            print("\nIndex stage complete. Continue with --stage retrieve")
            return

    if args.stage in {"all", "retrieve"}:
        if not good_questions:
            raise RuntimeError(f"No valid questions found at {questions_path}. Run --stage generate first.")
        top_k = max(int(args.top_k), max(args.k_values))
        retrieve_questions = list(good_questions)
        visual_question_skip_rows: List[Dict[str, Any]] = []
        retrieve_done = _stage_outputs_done(
            [
                judgments_path,
                retrieve_stats_path,
                retrieve_outputs_path,
            ],
            args.force,
        )
        if retrieve_done:
            judgments = _read_jsonl(judgments_path)
            print(f"\nRetrieve stage already has outputs; skipping. Judgments={len(judgments)}")
            print(f"Retrieve outputs: {retrieve_outputs_path}")
            if args.stage == "retrieve":
                return
        else:
            gen = _build_generator(cfg, args.provider, args.model, max_tokens=3000)
            if text_retriever is None and image_retriever is None:
                english_candidates_for_index = _selected_candidates_for_index(run_dir, english_passed_path)
                if args.judge:
                    if args.retrieval_modalities != "image":
                        raise RuntimeError("--judge currently supports --retrieval-modalities image only.")
                    image_retriever = _load_existing_visual_retriever_for_judge(
                        cfg=cfg,
                        args=args,
                        run_dir=run_dir,
                    )
                    english_candidates_for_index, indexed_visual_doc_ids = _indexed_visual_candidates(
                        image_retriever,
                        english_candidates_for_index,
                    )
                    retrieve_questions, visual_question_skip_rows = _filter_questions_to_indexed_visual_docs(
                        retrieve_questions,
                        indexed_doc_ids=indexed_visual_doc_ids,
                    )
                    print(
                        f"Judge visual database: {len(english_candidates_for_index)} PDFs present in current visual index; "
                        f"kept {len(retrieve_questions)}/{len(good_questions)} questions and skipped "
                        f"{len(visual_question_skip_rows)} questions outside that database.",
                        flush=True,
                    )
                else:
                    index_args = copy.copy(args)
                    index_args.force = False
                    text_retriever, image_retriever, index_rows, index_stats = _setup_retrieval_indexes(
                        cfg=cfg,
                        args=index_args,
                        english_candidates=english_candidates_for_index,
                        processing_dir=processing_dir,
                        work_dir=work_dir,
                        run_dir=run_dir,
                    )
                    _safe_write_json(index_outputs_path, index_rows)
                    _write_stage_stats(
                        run_dir / "stage_index_stats.json",
                        run_id=run_id,
                        stage="index",
                        counts={
                            "indexed_pdfs": len(english_candidates_for_index),
                            **index_stats,
                        },
                        rows=[row for row in index_rows if row.get("reason")],
                    )
            if args.retrieval_modalities in {"image", "both"} and not args.judge:
                visual_filter_path = run_dir / "visual_page_filter_report.json"
                if not visual_filter_path.exists():
                    raise FileNotFoundError(
                        f"Missing {visual_filter_path}. Run --stage index --retrieval-modalities image first."
                    )
                visual_filter = _read_json(visual_filter_path)
                skipped_visual_docs = {
                    str(row.get("doc_id") or ""): row
                    for row in visual_filter.get("files", [])
                    if row.get("status") == "skipped" and row.get("doc_id")
                }
                if skipped_visual_docs:
                    filtered_questions = []
                    for question in retrieve_questions:
                        doc_id = str(question.get("doc_id") or "")
                        skipped_doc = skipped_visual_docs.get(doc_id)
                        if skipped_doc:
                            visual_question_skip_rows.append(
                                {
                                    "stage": "retrieve",
                                    "query_id": question.get("query_id"),
                                    "doc_id": doc_id,
                                    "section_id": question.get("section_id"),
                                    "relative_path": question.get("relative_path"),
                                    "reason": "visual_doc_not_indexed",
                                    "severity": "warning",
                                    "page_count": skipped_doc.get("page_count"),
                                    "max_pages": skipped_doc.get("max_pages"),
                                    "visual_skip_reason": skipped_doc.get("reason"),
                                }
                            )
                            continue
                        filtered_questions.append(question)
                    retrieve_questions = filtered_questions
                    print(
                        f"Visual retrieve question filter: kept {len(retrieve_questions)}/{len(good_questions)} "
                        f"questions; skipped {len(visual_question_skip_rows)} questions from "
                        f"{len(skipped_visual_docs)} non-embedded PDFs.",
                        flush=True,
                    )
            if not args.resume and judgments_path.exists():
                judgments_path.unlink()
            judgments = _run_judgments(
                gen=gen,
                retriever=text_retriever,
                image_retriever=image_retriever,
                image_candidates=english_candidates_for_index,
                questions=retrieve_questions,
                output_path=judgments_path,
                retriever_type=args.retriever_type,
                top_k=top_k,
                image_top_k=int(args.image_top_k),
                k_values=args.k_values,
                concurrency=args.judge_concurrency,
                llm_concurrency=args.llm_concurrency,
                resume=args.resume,
            )
        judgment_errors = [
            {
                "query_id": row.get("query_id"),
                "relative_path": row.get("relative_path"),
                "reason": "judgment_failed",
                "severity": "error",
                "error": (row.get("llm_judgment") or {}).get("error"),
            }
            for row in judgments
            if (row.get("llm_judgment") or {}).get("error")
        ]
        _write_retrieve_outputs(retrieve_outputs_path, retrieve_questions, judgments)
        _write_stage_stats(
            retrieve_stats_path,
            run_id=run_id,
            stage="retrieve",
            counts={
                "source_questions": len(good_questions),
                "questions": len(retrieve_questions),
                "visual_skipped_questions": len(visual_question_skip_rows),
                "judgments": len(judgments),
                "top_k": top_k,
            },
            rows=[*visual_question_skip_rows, *judgment_errors],
        )
        print(f"Retrieve outputs: {retrieve_outputs_path}")
        print(f"Retrieve stats: {retrieve_stats_path}")
        if args.stage == "retrieve":
            print("\nRetrieve stage complete. Continue with --stage report")
            return
    else:
        judgments = _read_jsonl(judgments_path)
        print(f"Loaded judgments: {len(judgments)}")

    if not selected_sections:
        selected_sections = _load_selected_sections(run_dir / "selected_sections.json")

    report_done = _stage_outputs_done(
        [
            run_dir / "report.json",
            run_dir / "summary.md",
            run_dir / "stage_report_stats.json",
            report_outputs_path,
        ],
        args.force,
    )
    if report_done:
        print(f"\nReport stage already has outputs; skipping. Report: {run_dir / 'report.json'}")
        return

    report = _build_report(
        run_id=run_id,
        args=args,
        candidates=candidates,
        skipped=skipped,
        selected_sections=selected_sections,
        questions=good_questions,
        judgments=judgments,
        processing_stats=processing_stats,
        started_at=started,
    )
    _safe_write_json(run_dir / "report.json", report)
    _write_summary(run_dir / "summary.md", report)
    _safe_write_json(
        report_outputs_path,
        [
            {
                "stage": "report",
                "status": "processed",
                "output_exists": True,
                "report_json": str(run_dir / "report.json"),
                "summary_md": str(run_dir / "summary.md"),
            }
        ],
    )
    _write_stage_stats(
        run_dir / "stage_report_stats.json",
        run_id=run_id,
        stage="report",
        counts={
            "questions": len(good_questions),
            "judgments": len(judgments),
            "report_written": 1,
        },
        rows=[],
    )
    print("\n" + "=" * 80)
    print("Evaluation complete")
    print("=" * 80)
    print(f"Questions: {len(good_questions)}")
    print(f"Judgments: {len(judgments)}")
    print(f"Report: {run_dir / 'report.json'}")
    for metric, data in (report.get("metrics", {}).get("overall") or {}).items():
        print(f"{metric}: {data.get('mean', 0.0):.4f} (n={data.get('count', 0)})")


if __name__ == "__main__":
    main()
