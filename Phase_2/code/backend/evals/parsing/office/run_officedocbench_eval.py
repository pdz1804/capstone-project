"""Run OfficeDocBench evaluation for DocumentProcessorV2 Office outputs."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("NUMBA_DISABLE_JIT", "1")
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba")

from src.evaluation.officedocbench_adapter import load_and_adapt_parsed_json
from src.processor.document_processor_v2 import DocumentProcessorV2, ProcessingConfigV2


DEFAULT_AILANG_ROOT = REPO_ROOT / "third_party" / "ailang-parse"
DEFAULT_OFFICEDOCBENCH_ROOT = DEFAULT_AILANG_ROOT / "benchmarks" / "officedocbench"
DEFAULT_TEST_ROOT = DEFAULT_AILANG_ROOT / "data" / "test_files"
DEFAULT_OUTPUT_DIR = BACKEND_ROOT / "output" / "evaluation" / "officedocbench_document_processor_v2"
SUPPORTED_FORMATS = {"docx", "xlsx", "pptx"}
METRIC_KEYS = [
    "feature_detection",
    "structural_recall",
    "structural_quality",
    "content_fidelity",
    "text_jaccard",
    "element_count",
    "metadata",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--officedocbench-root", default=str(DEFAULT_OFFICEDOCBENCH_ROOT))
    parser.add_argument("--test-root", default=str(DEFAULT_TEST_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--processing-dir", default=None, help="Where DocumentProcessorV2 writes parsed outputs. Defaults to <output-dir>/processing.")
    parser.add_argument("--parsed-root", default=None, help="Use existing DocumentProcessorV2 export root instead of processing files.")
    parser.add_argument("--skip-processing", action="store_true", help="Only adapt and score existing parsed outputs.")
    parser.add_argument("--formats", default="docx,xlsx,pptx", help="Comma-separated Office formats to evaluate.")
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument("--doc-id", action="append", default=None, help="Evaluate one or more source filenames or stems.")
    parser.add_argument("--include-core", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-challenge", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--force", action="store_true", help="Reprocess even when a parsed JSON already exists.")
    parser.add_argument("--prefer-custom-readers", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--excel-reader-mode", choices=["xml", "docling"], default="xml")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir).resolve()
    processing_dir = Path(args.processing_dir).resolve() if args.processing_dir else output_dir / "processing"
    parsed_root = Path(args.parsed_root).resolve() if args.parsed_root else processing_dir

    officedocbench_root = Path(args.officedocbench_root).resolve()
    test_root = Path(args.test_root).resolve()
    gt_dir = officedocbench_root / "ground_truth"
    scoring_path = officedocbench_root / "scoring.py"

    if not gt_dir.exists():
        raise FileNotFoundError(f"OfficeDocBench ground_truth directory not found: {gt_dir}")
    if not test_root.exists():
        raise FileNotFoundError(f"OfficeDocBench test root not found: {test_root}")

    score_file = _load_score_file(scoring_path)
    jobs = discover_jobs(
        gt_dir=gt_dir,
        test_root=test_root,
        formats=_parse_formats(args.formats),
        doc_ids=set(args.doc_id or []),
        include_core=args.include_core,
        include_challenge=args.include_challenge,
        max_files=args.max_files,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    adapted_dir = output_dir / "adapter_outputs"
    adapted_dir.mkdir(parents=True, exist_ok=True)

    processor: Optional[DocumentProcessorV2] = None
    if not args.skip_processing:
        processor = DocumentProcessorV2(
            input_dir=test_root,
            output_dir=processing_dir,
            config=ProcessingConfigV2(
                prefer_custom_readers=args.prefer_custom_readers,
                excel_reader_mode=args.excel_reader_mode,
                pptx_llm_validate_headers=False,
            ),
        )

    results: List[Dict[str, Any]] = []
    for idx, job in enumerate(jobs, 1):
        print(f"[{idx}/{len(jobs)}] {job['file']} ({job['format']})", file=sys.stderr)
        result = evaluate_job(
            job,
            processor=processor,
            parsed_root=parsed_root,
            adapted_dir=adapted_dir,
            score_file=score_file,
            skip_processing=args.skip_processing,
            force=args.force,
        )
        results.append(result)

    summary = summarize_results(results, total_jobs=len(jobs), args=vars(args))
    write_outputs(output_dir, results, summary)
    print(json.dumps({"summary": str(output_dir / "summary.json"), "results": str(output_dir / "results.json")}, indent=2))
    return 0


def discover_jobs(
    *,
    gt_dir: Path,
    test_root: Path,
    formats: set[str],
    doc_ids: set[str],
    include_core: bool,
    include_challenge: bool,
    max_files: Optional[int],
) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    for gt_path in sorted(gt_dir.glob("*.json")):
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        fmt = str(gt.get("format", "")).lower()
        source_file = str(gt.get("file", ""))
        if fmt not in formats or fmt not in SUPPORTED_FORMATS:
            continue
        stem = Path(source_file).stem
        if doc_ids and source_file not in doc_ids and stem not in doc_ids:
            continue
        source_path = _find_test_file(test_root, source_file)
        if source_path is None:
            jobs.append({"file": source_file, "format": fmt, "gt_path": str(gt_path), "status": "MISSING_SOURCE"})
            continue
        is_challenge = source_path.parent.name == "challenge" or source_file.startswith("challenge_")
        if is_challenge and not include_challenge:
            continue
        if not is_challenge and not include_core:
            continue
        jobs.append(
            {
                "file": source_file,
                "doc_id": stem,
                "format": fmt,
                "source_path": str(source_path),
                "gt_path": str(gt_path),
                "is_challenge": is_challenge,
            }
        )
        if max_files and len(jobs) >= max_files:
            break
    return jobs


def evaluate_job(
    job: Dict[str, Any],
    *,
    processor: Optional[DocumentProcessorV2],
    parsed_root: Path,
    adapted_dir: Path,
    score_file,
    skip_processing: bool,
    force: bool,
) -> Dict[str, Any]:
    if job.get("status") == "MISSING_SOURCE":
        return {**job, "status": "MISSING_SOURCE"}

    source_path = Path(job["source_path"])
    gt_path = Path(job["gt_path"])
    doc_id = job["doc_id"]
    start = time.time()

    try:
        parsed_path = resolve_v2_parsed_path(parsed_root, doc_id)
        metadata_path = resolve_v2_metadata_path(parsed_root, doc_id)
        processing_info: Dict[str, Any] = {}

        if (not skip_processing) and processor is not None and (force or parsed_path is None):
            processing_info = processor.process_single_file(source_path)
            if not processing_info.get("success"):
                return {
                    **job,
                    "status": "ERROR",
                    "error": str(processing_info.get("error") or "processing failed")[:500],
                    "time_ms": round((time.time() - start) * 1000, 1),
                }
            exported = processor.export_processed_document(processing_info)
            parsed_path = Path(exported.get("parsed_json", "")) if exported.get("parsed_json") else None
            metadata_path = Path(exported.get("metadata_json") or exported.get("metadata") or "") if exported else None

        if parsed_path is None or not parsed_path.exists():
            return {
                **job,
                "status": "MISSING_PARSED",
                "error": f"No parsed JSON found for {doc_id} under {parsed_root}",
                "time_ms": round((time.time() - start) * 1000, 1),
            }

        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        adapter_output = load_and_adapt_parsed_json(
            parsed_path,
            metadata_path=metadata_path if metadata_path and metadata_path.exists() else None,
            source_path=source_path,
            file_format=job["format"],
        )
        scores = score_file(gt, adapter_output)

        adapted_path = adapted_dir / f"{source_path.name}.json"
        adapted_path.write_text(json.dumps(adapter_output, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            **job,
            "status": "OK",
            "time_ms": round((time.time() - start) * 1000, 1),
            "processor_used": processing_info.get("processor_used") if processing_info else None,
            "parsed_path": str(parsed_path),
            "metadata_path": str(metadata_path) if metadata_path else None,
            "adapter_output_path": str(adapted_path),
            "scores": scores,
        }
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        return {
            **job,
            "status": "ERROR",
            "error": str(exc)[:500],
            "time_ms": round((time.time() - start) * 1000, 1),
        }


def resolve_v2_parsed_path(root: Path, doc_id: str) -> Optional[Path]:
    candidates = [
        root / doc_id / f"{doc_id}_parsed.json",
        root / f"{doc_id}_parsed.json",
        root / f"{doc_id}.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    matches = sorted(root.glob(f"**/{doc_id}_parsed.json")) if root.exists() else []
    return matches[0] if matches else None


def resolve_v2_metadata_path(root: Path, doc_id: str) -> Optional[Path]:
    candidates = [
        root / doc_id / f"{doc_id}_metadata.json",
        root / f"{doc_id}_metadata.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    matches = sorted(root.glob(f"**/{doc_id}_metadata.json")) if root.exists() else []
    return matches[0] if matches else None


def summarize_results(results: List[Dict[str, Any]], *, total_jobs: int, args: Dict[str, Any]) -> Dict[str, Any]:
    ok = [r for r in results if r.get("status") == "OK"]
    coverage = len(ok) / total_jobs if total_jobs else 0.0
    composite = _mean([r["scores"]["composite"] for r in ok])
    by_format: Dict[str, Dict[str, Any]] = {}
    for fmt in sorted({r.get("format") for r in results if r.get("format")}):
        fmt_results = [r for r in results if r.get("format") == fmt]
        fmt_ok = [r for r in fmt_results if r.get("status") == "OK"]
        by_format[fmt] = {
            "files_ok": len(fmt_ok),
            "files_total": len(fmt_results),
            "coverage": round(len(fmt_ok) / len(fmt_results), 4) if fmt_results else 0.0,
            "composite": round(_mean([r["scores"]["composite"] for r in fmt_ok]), 4),
        }

    times = [r.get("time_ms") for r in ok if isinstance(r.get("time_ms"), (int, float))]
    timing = {}
    if times:
        timing = {
            "median_ms": round(statistics.median(times), 1),
            "mean_ms": round(statistics.mean(times), 1),
            "total_ms": round(sum(times), 1),
        }

    return {
        "schema": "document_processor_v2_officedocbench_eval",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "adapter": "DocumentProcessorV2",
        "files_ok": len(ok),
        "files_total": total_jobs,
        "coverage": round(coverage, 4),
        "composite": round(composite, 4),
        "coverage_adjusted": round(composite * coverage, 4),
        **{key: round(_mean([r["scores"].get(key, {}).get("score", 0.0) for r in ok]), 4) for key in METRIC_KEYS},
        "by_format": by_format,
        "timing": timing,
        "status_counts": _status_counts(results),
        "args": args,
    }


def write_outputs(output_dir: Path, results: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_lines = ["file,format,status,composite,feature_detection,structural_recall,structural_quality,content_fidelity,text_jaccard,element_count,metadata,time_ms"]
    for r in results:
        scores = r.get("scores") or {}
        csv_lines.append(
            ",".join(
                [
                    _csv(r.get("file", "")),
                    _csv(r.get("format", "")),
                    _csv(r.get("status", "")),
                    _csv(scores.get("composite", "")),
                    *[_csv(scores.get(key, {}).get("score", "")) for key in METRIC_KEYS],
                    _csv(r.get("time_ms", "")),
                ]
            )
        )
    (output_dir / "results.csv").write_text("\n".join(csv_lines) + "\n", encoding="utf-8")


def _load_score_file(scoring_path: Path):
    if not scoring_path.exists():
        raise FileNotFoundError(f"OfficeDocBench scoring.py not found: {scoring_path}")
    spec = importlib.util.spec_from_file_location("officedocbench_scoring", scoring_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load OfficeDocBench scorer: {scoring_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.score_file


def _find_test_file(test_root: Path, source_file: str) -> Optional[Path]:
    direct = test_root / source_file
    if direct.exists():
        return direct
    matches = sorted(test_root.glob(f"**/{source_file}"))
    return matches[0] if matches else None


def _parse_formats(value: str) -> set[str]:
    return {item.strip().lower().lstrip(".") for item in (value or "").split(",") if item.strip()}


def _mean(values: Iterable[float]) -> float:
    values = [float(v) for v in values]
    return sum(values) / len(values) if values else 0.0


def _status_counts(results: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for result in results:
        status = str(result.get("status") or "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _csv(value: Any) -> str:
    text = str(value)
    if "," in text or '"' in text or "\n" in text:
        return '"' + text.replace('"', '""') + '"'
    return text


if __name__ == "__main__":
    raise SystemExit(main())
