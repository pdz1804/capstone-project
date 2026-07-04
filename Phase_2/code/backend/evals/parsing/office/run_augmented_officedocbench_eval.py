"""Run OfficeDocBench scoring on augmented Pandoc/DECO ground truth."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("NUMBA_DISABLE_JIT", "1")
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba")

from evals.parsing.office.run_officedocbench_eval import (  # noqa: E402
    _load_score_file,
    resolve_v2_metadata_path,
    resolve_v2_parsed_path,
    summarize_results,
    write_outputs,
)
from src.evaluation.deco_officedocbench_gt import (  # noqa: E402
    build_deco_officedocbench_gt,
    discover_deco_xlsx_jobs,
)
from src.evaluation.officedocbench_adapter import load_and_adapt_parsed_json  # noqa: E402
from src.evaluation.pandoc_officedocbench_gt import (  # noqa: E402
    build_pandoc_officedocbench_gt,
    discover_pandoc_docx_jobs,
    discover_pandoc_pptx_jobs,
)
from src.processor.document_processor_v2 import DocumentProcessorV2, ProcessingConfigV2  # noqa: E402


DEFAULT_AILANG_ROOT = REPO_ROOT / "third_party" / "ailang-parse"
DEFAULT_SCORING_PATH = DEFAULT_AILANG_ROOT / "benchmarks" / "officedocbench" / "scoring.py"
DEFAULT_PANDOC_ROOT = REPO_ROOT / "third_party" / "pandoc-test-suite"
DEFAULT_DECO_SOURCE_ROOT = BACKEND_ROOT / "evals" / "annotated" / "completed"
DEFAULT_OUTPUT_DIR = BACKEND_ROOT / "output" / "evaluation" / "augmented_officedocbench_document_processor_v2"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets", default="pandoc-docx,pandoc-pptx,deco-xlsx", help="Comma-separated: pandoc-docx,pandoc-pptx,deco-xlsx")
    parser.add_argument("--pandoc-root", default=str(DEFAULT_PANDOC_ROOT))
    parser.add_argument("--pandoc-docx-dir", default=None)
    parser.add_argument("--pandoc-pptx-dir", default=None)
    parser.add_argument("--deco-source-root", default=str(DEFAULT_DECO_SOURCE_ROOT))
    parser.add_argument("--deco-annotation-root", default=None, help="Directory of per-file annotations or a range_annotations.csv export")
    parser.add_argument("--scoring-path", default=str(DEFAULT_SCORING_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--processing-dir", default=None)
    parser.add_argument("--parsed-root", default=None)
    parser.add_argument("--skip-processing", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument("--doc-id", action="append", default=None)
    parser.add_argument("--doc-id-file", default=None, help="Text file containing one doc_id per line")
    parser.add_argument("--source-path-file", default=None, help="Text file containing one source_path per line")
    parser.add_argument("--prefer-custom-readers", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--excel-reader-mode", choices=["xml", "docling"], default="xml")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir).resolve()
    processing_dir = Path(args.processing_dir).resolve() if args.processing_dir else output_dir / "processing"
    parsed_root = Path(args.parsed_root).resolve() if args.parsed_root else processing_dir
    generated_gt_dir = output_dir / "generated_ground_truth"
    generated_gt_dir.mkdir(parents=True, exist_ok=True)

    jobs = discover_augmented_jobs(args)
    wanted_doc_ids = _load_wanted_doc_ids(args.doc_id, args.doc_id_file)
    if wanted_doc_ids:
        wanted = set(wanted_doc_ids)
        jobs = [job for job in jobs if job.get("doc_id") in wanted or Path(str(job.get("file", ""))).stem in wanted]
    wanted_source_paths = _load_wanted_source_paths(args.source_path_file)
    if wanted_source_paths:
        jobs = [job for job in jobs if _source_path_key(job) in wanted_source_paths or str(job.get("source_path") or "") in wanted_source_paths]
    if args.max_files:
        jobs = jobs[: args.max_files]

    score_file = _load_score_file(Path(args.scoring_path).resolve())
    processor: Optional[DocumentProcessorV2] = None
    if not args.skip_processing:
        processor = DocumentProcessorV2(
            input_dir=REPO_ROOT,
            output_dir=processing_dir,
            config=ProcessingConfigV2(
                prefer_custom_readers=args.prefer_custom_readers,
                excel_reader_mode=args.excel_reader_mode,
                pptx_llm_validate_headers=False,
            ),
        )

    results: List[Dict[str, Any]] = []
    manifests: List[Dict[str, Any]] = []
    for idx, job in enumerate(jobs, 1):
        print(f"[{idx}/{len(jobs)}] {job['dataset']} {job['file']}", file=sys.stderr)
        result, manifest = evaluate_augmented_job(
            job,
            processor=processor,
            parsed_root=parsed_root,
            generated_gt_dir=generated_gt_dir,
            score_file=score_file,
            skip_processing=args.skip_processing,
            force=args.force,
        )
        results.append(result)
        manifests.append(manifest)

    summary = summarize_results(results, total_jobs=len(jobs), args=vars(args))
    summary["schema"] = "document_processor_v2_augmented_officedocbench_eval"
    summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    summary["datasets"] = sorted({str(job.get("dataset")) for job in jobs})
    write_outputs(output_dir, results, summary)
    (output_dir / "manifest.json").write_text(json.dumps(manifests, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": str(output_dir / "summary.json"), "results": str(output_dir / "results.json"), "manifest": str(output_dir / "manifest.json")}, indent=2))
    return 0


def discover_augmented_jobs(args: argparse.Namespace) -> List[Dict[str, Any]]:
    datasets = {item.strip().lower() for item in str(args.datasets or "").split(",") if item.strip()}
    pandoc_root = Path(args.pandoc_root)
    jobs: List[Dict[str, Any]] = []
    if "deco-xlsx" in datasets and args.deco_annotation_root:
        annotation_root = Path(args.deco_annotation_root)
        if not annotation_root.exists():
            raise FileNotFoundError(
                f"DECO annotation root not found: {annotation_root}. "
                "Pass the real annotation directory/CSV, or omit --deco-annotation-root to report DECO files as MISSING_ANNOTATION."
            )
    if "pandoc-docx" in datasets:
        docx_dir = Path(args.pandoc_docx_dir) if args.pandoc_docx_dir else pandoc_root / "test" / "docx"
        if docx_dir.exists():
            jobs.extend(discover_pandoc_docx_jobs(docx_dir))
    if "pandoc-pptx" in datasets:
        pptx_dir = Path(args.pandoc_pptx_dir) if args.pandoc_pptx_dir else pandoc_root / "test" / "pptx"
        if pptx_dir.exists():
            jobs.extend(discover_pandoc_pptx_jobs(pptx_dir))
    if "deco-xlsx" in datasets:
        source_root = Path(args.deco_source_root)
        annotation_root = Path(args.deco_annotation_root) if args.deco_annotation_root else None
        if source_root.exists():
            jobs.extend(discover_deco_xlsx_jobs(source_root, annotation_root))
    return jobs


def evaluate_augmented_job(
    job: Dict[str, Any],
    *,
    processor: Optional[DocumentProcessorV2],
    parsed_root: Path,
    generated_gt_dir: Path,
    score_file,
    skip_processing: bool,
    force: bool,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    start = time.time()
    source_path = Path(str(job.get("source_path", "")))
    doc_id = str(job.get("doc_id") or source_path.stem)
    dataset = str(job.get("dataset") or "")
    manifest: Dict[str, Any] = {
        "dataset": dataset,
        "doc_id": doc_id,
        "source_path": str(source_path),
        "generated_fields": [],
        "skipped_fields": [],
    }

    if job.get("status") and job.get("status") != "OK":
        manifest["status"] = job.get("status")
        reason = (
            "DECO strong GT requires an official annotation file."
            if job.get("status") == "MISSING_ANNOTATION"
            else f"Unsupported augmented source for GT conversion: {job.get('status')}"
        )
        manifest["reason"] = reason
        return {
            **job,
            "status": job.get("status"),
            "error": reason,
            "time_ms": round((time.time() - start) * 1000, 1),
        }, manifest

    try:
        gt_path = generated_gt_dir / dataset / f"{_safe_filename(doc_id)}.json"
        gt = _build_gt(job)
        gt_path.parent.mkdir(parents=True, exist_ok=True)
        gt_path.write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["gt_path"] = str(gt_path)
        manifest["generated_fields"] = _non_empty_fields(gt)
        manifest["skipped_fields"] = [key for key, value in gt.items() if key != "metadata" and not value]

        parsed_path = resolve_v2_parsed_path(parsed_root, doc_id)
        metadata_path = resolve_v2_metadata_path(parsed_root, doc_id)
        processing_info: Dict[str, Any] = {}

        if (not skip_processing) and processor is not None and (force or parsed_path is None):
            processing_info = processor.process_single_file(source_path)
            if not processing_info.get("success"):
                return {
                    **job,
                    "status": "ERROR",
                    "gt_path": str(gt_path),
                    "error": str(processing_info.get("error") or "processing failed")[:500],
                    "time_ms": round((time.time() - start) * 1000, 1),
                }, {**manifest, "status": "ERROR"}
            exported = processor.export_processed_document(processing_info)
            parsed_path = Path(exported.get("parsed_json", "")) if exported.get("parsed_json") else None
            exported_metadata = exported.get("metadata_json") or exported.get("metadata") if exported else None
            metadata_path = Path(exported_metadata) if exported_metadata else None

        if parsed_path is None or not parsed_path.exists():
            return {
                **job,
                "status": "MISSING_PARSED",
                "gt_path": str(gt_path),
                "error": f"No parsed JSON found for {doc_id} under {parsed_root}",
                "time_ms": round((time.time() - start) * 1000, 1),
            }, {**manifest, "status": "MISSING_PARSED"}

        adapter_output = load_and_adapt_parsed_json(
            parsed_path,
            metadata_path=metadata_path if metadata_path and metadata_path.exists() else None,
            source_path=source_path,
            file_format=str(job.get("format") or ""),
        )
        scores = score_file(gt, adapter_output)
        adapted_path = generated_gt_dir.parent / "adapter_outputs" / dataset / f"{_safe_filename(doc_id)}.json"
        adapted_path.parent.mkdir(parents=True, exist_ok=True)
        adapted_path.write_text(json.dumps(adapter_output, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            **job,
            "status": "OK",
            "gt_path": str(gt_path),
            "parsed_path": str(parsed_path),
            "metadata_path": str(metadata_path) if metadata_path else None,
            "adapter_output_path": str(adapted_path),
            "processor_used": processing_info.get("processor_used") if processing_info else None,
            "scores": scores,
            "time_ms": round((time.time() - start) * 1000, 1),
        }, {**manifest, "status": "OK", "adapter_output_path": str(adapted_path)}
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        return {
            **job,
            "status": "ERROR",
            "error": str(exc)[:500],
            "time_ms": round((time.time() - start) * 1000, 1),
        }, {**manifest, "status": "ERROR", "error": str(exc)[:500]}


def _build_gt(job: Dict[str, Any]) -> Dict[str, Any]:
    dataset = str(job.get("dataset") or "")
    if dataset.startswith("pandoc-"):
        gt = build_pandoc_officedocbench_gt(
            Path(str(job["native_path"])),
            file_format=str(job.get("format") or ""),
            source_path=Path(str(job["source_path"])),
        )
        return _with_scoring_fields(gt)
    if dataset == "deco-xlsx":
        annotation_path = job.get("annotation_path")
        if not annotation_path:
            raise ValueError("DECO job is missing annotation_path")
        gt = build_deco_officedocbench_gt(Path(str(job["source_path"])), Path(str(annotation_path)))
        return _with_scoring_fields(gt)
    raise ValueError(f"Unsupported augmented dataset: {dataset}")


def _with_scoring_fields(gt: Dict[str, Any]) -> Dict[str, Any]:
    gt = dict(gt)
    features: Dict[str, Any] = {}

    headings = _list_field(gt, "headings")
    if headings:
        by_level: Dict[str, int] = {}
        for heading in headings:
            level = str(heading.get("level") or 0)
            by_level[level] = by_level.get(level, 0) + 1
        features["headings"] = {"present": True, "count": len(headings), "by_level": by_level}

    tables = _list_field(gt, "tables")
    if tables:
        cells: List[List[Any]] = []
        total_rows = 0
        merge_count = 0
        for table_idx, table in enumerate(tables):
            rows = table.get("rows") or []
            total_rows += int(table.get("row_count") or len(rows) or 0)
            merge_count += int(table.get("merge_count") or 0)
            for row_idx, row in enumerate(rows):
                if not isinstance(row, list):
                    continue
                for col_idx, text in enumerate(row):
                    if str(text).strip():
                        cells.append([table_idx, row_idx, col_idx, str(text)])
        features["tables"] = {
            "present": True,
            "count": len(tables),
            "total_rows": total_rows,
            "has_merged_cells": any(bool(t.get("has_merged_cells")) for t in tables),
            "merge_count": merge_count,
            "cells": cells,
        }

    lists = _list_field(gt, "lists")
    if lists:
        ordered_count = sum(1 for item in lists if item.get("ordered"))
        max_depth = max((int(item.get("depth") or 1) for item in lists), default=1)
        features["lists"] = {
            "present": True,
            "count": len(lists),
            "ordered_count": ordered_count,
            "unordered_count": len(lists) - ordered_count,
            "has_nested": max_depth > 1,
            "max_depth": max_depth,
        }

    for field in ("track_changes", "comments", "headers_footers", "text_boxes", "images", "speaker_notes", "bookmarks", "fields", "section_breaks"):
        items = _list_field(gt, field)
        if items:
            feature_key = "footnotes_endnotes" if field == "footnotes" else field
            features[feature_key] = {"present": True, "count": len(items)}

    footnotes = _list_field(gt, "footnotes")
    if footnotes:
        features["footnotes_endnotes"] = {
            "present": True,
            "count": len(footnotes),
            "texts": [str(item.get("text") or "") for item in footnotes if isinstance(item, dict)],
        }

    hyperlinks = _list_field(gt, "hyperlinks")
    if hyperlinks:
        features["hyperlinks"] = {"present": True, "count": len(hyperlinks), "links": hyperlinks}

    metadata = gt.get("metadata") if isinstance(gt.get("metadata"), dict) else {}
    sheet_names = metadata.get("sheet_names") if isinstance(metadata, dict) else None
    if sheet_names:
        features["sheets"] = {"present": True, "count": len(sheet_names), "names": sheet_names}
    meta_fields = {key: metadata.get(key) for key in ("title", "author", "created", "modified") if metadata.get(key)}
    if meta_fields:
        features["metadata"] = meta_fields

    text_elements = _list_field(gt, "text_elements")
    text_parts = _collect_gt_text_parts(gt)
    if text_parts:
        features["text"] = {
            "present": True,
            "paragraph_count": len(text_elements),
            "key_phrases": _key_phrases(text_parts),
        }
        gt["full_text_words"] = sorted(set(_words(" ".join(text_parts))))
    else:
        gt["full_text_words"] = []

    gt["element_order"] = _build_gt_element_order(gt)
    gt["features"] = features
    return gt


def _list_field(gt: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = gt.get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _collect_gt_text_parts(gt: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    for key in ("text_elements", "headings", "comments", "headers_footers", "text_boxes", "footnotes", "speaker_notes", "images"):
        for item in _list_field(gt, key):
            text = item.get("text") or item.get("description") or ""
            if str(text).strip():
                parts.append(str(text))
    for table in _list_field(gt, "tables"):
        text = table.get("cell_text") or ""
        if str(text).strip():
            parts.append(str(text))
    for listing in _list_field(gt, "lists"):
        for item in listing.get("items") or []:
            if str(item).strip():
                parts.append(str(item))
    for link in _list_field(gt, "hyperlinks"):
        text = link.get("text") or ""
        if str(text).strip():
            parts.append(str(text))
    return parts


def _build_gt_element_order(gt: Dict[str, Any]) -> List[Dict[str, str]]:
    elements: List[Dict[str, str]] = []
    for key, element_type in (
        ("text_elements", "text"),
        ("headings", "heading"),
        ("tables", "table"),
        ("lists", "list"),
    ):
        for item in _list_field(gt, key):
            text = item.get("text") or item.get("cell_text") or " ".join(str(v) for v in item.get("items") or [])
            elements.append({"type": element_type, "text": str(text)[:50]})
    return elements


def _key_phrases(text_parts: List[str]) -> List[str]:
    phrases: List[str] = []
    for text in text_parts:
        normalized = " ".join(str(text).split())
        if len(normalized) >= 12:
            phrases.append(normalized[:120])
        if len(phrases) >= 20:
            break
    return phrases


def _words(text: str) -> List[str]:
    return re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())


def _non_empty_fields(gt: Dict[str, Any]) -> List[str]:
    fields: List[str] = []
    for key, value in gt.items():
        if key == "metadata":
            if value:
                fields.append(key)
        elif value:
            fields.append(key)
    return fields


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value).strip("_") or "document"


def _load_wanted_doc_ids(doc_ids: List[str] | None, doc_id_file: str | None) -> List[str]:
    wanted = list(doc_ids or [])
    if doc_id_file:
        path = Path(doc_id_file)
        wanted.extend(
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    return wanted


def _load_wanted_source_paths(source_path_file: str | None) -> set[str]:
    if not source_path_file:
        return set()
    values = set()
    for line in Path(source_path_file).read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.lstrip().startswith("#"):
            continue
        values.add(value)
        values.add(str(Path(value).resolve()))
    return values


def _source_path_key(job: Dict[str, Any]) -> str:
    return str(Path(str(job.get("source_path") or "")).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
