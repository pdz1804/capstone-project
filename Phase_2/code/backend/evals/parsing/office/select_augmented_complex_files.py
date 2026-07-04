"""Select complex augmented OfficeDocBench files for focused parsing evals."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

BACKEND_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.evaluation.pandoc_officedocbench_gt import (  # noqa: E402
    build_pandoc_officedocbench_gt,
    discover_pandoc_docx_jobs,
    discover_pandoc_pptx_jobs,
)


DEFAULT_PANDOC_ROOT = REPO_ROOT / "third_party" / "pandoc-test-suite"
DEFAULT_DECO_SOURCE_ROOT = BACKEND_ROOT / "evals" / "annotated" / "completed"
DEFAULT_DECO_RANGE_CSV = BACKEND_ROOT / "output" / "evaluation" / "deco_annotation_exports" / "range_annotations.csv"
DEFAULT_OUTPUT_DIR = BACKEND_ROOT / "output" / "evaluation" / "augmented_complex_file_selection"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pandoc-root", default=str(DEFAULT_PANDOC_ROOT))
    parser.add_argument("--deco-source-root", default=str(DEFAULT_DECO_SOURCE_ROOT))
    parser.add_argument("--deco-range-annotations", default=str(DEFAULT_DECO_RANGE_CSV))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--limit", type=int, default=50)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    rows.extend(_pandoc_rows(Path(args.pandoc_root)))
    rows.extend(_deco_rows(Path(args.deco_source_root), Path(args.deco_range_annotations)))

    for row in rows:
        row["complexity_score"] = _complexity_score(row)
        row["complexity_reasons"] = _complexity_reasons(row)

    rows = sorted(rows, key=lambda row: (-float(row["complexity_score"]), str(row["dataset"]), str(row["file"])))
    selected = _balanced_selection(rows, limit=args.limit)

    _write_csv(output_dir / "augmented_file_statistics.csv", rows)
    _write_csv(output_dir / "selected_complex_50.csv", selected)
    (output_dir / "selected_complex_50.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "selected_doc_ids.txt").write_text("\n".join(str(row["doc_id"]) for row in selected) + "\n", encoding="utf-8")
    (output_dir / "selected_source_paths.txt").write_text(
        "\n".join(str(row["source_path"]) for row in selected) + "\n",
        encoding="utf-8",
    )

    summary = {
        "files_total": len(rows),
        "selected_total": len(selected),
        "by_dataset": _count_by(rows, "dataset"),
        "selected_by_dataset": _count_by(selected, "dataset"),
        "outputs": {
            "statistics_csv": str(output_dir / "augmented_file_statistics.csv"),
            "selected_csv": str(output_dir / "selected_complex_50.csv"),
            "selected_json": str(output_dir / "selected_complex_50.json"),
            "selected_doc_ids": str(output_dir / "selected_doc_ids.txt"),
            "selected_source_paths": str(output_dir / "selected_source_paths.txt"),
        },
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _pandoc_rows(pandoc_root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for job in discover_pandoc_docx_jobs(pandoc_root / "test" / "docx"):
        rows.append(_pandoc_row(job))
    for job in discover_pandoc_pptx_jobs(pandoc_root / "test" / "pptx"):
        rows.append(_pandoc_row(job))
    return rows


def _pandoc_row(job: Dict[str, Any]) -> Dict[str, Any]:
    source_path = Path(str(job["source_path"]))
    gt: Dict[str, Any] = {}
    if job.get("status") == "OK":
        try:
            gt = build_pandoc_officedocbench_gt(
                Path(str(job["native_path"])),
                file_format=str(job.get("format") or ""),
                source_path=source_path,
            )
        except Exception:
            gt = {}
    ooxml = _ooxml_stats(source_path)
    return {
        "dataset": job.get("dataset", ""),
        "format": job.get("format", ""),
        "file": job.get("file", ""),
        "doc_id": job.get("doc_id", source_path.stem),
        "source_path": str(source_path),
        "native_path": str(job.get("native_path") or ""),
        "annotation_path": "",
        "status": job.get("status", "OK"),
        "tables": len(gt.get("tables") or []),
        "table_rows": sum(int(table.get("row_count") or 0) for table in gt.get("tables") or [] if isinstance(table, dict)),
        "merged_cells": sum(int(table.get("merge_count") or 0) for table in gt.get("tables") or [] if isinstance(table, dict)),
        "headings": len(gt.get("headings") or []),
        "lists": len(gt.get("lists") or []),
        "images_gt": len(gt.get("images") or []),
        "hyperlinks": len(gt.get("hyperlinks") or []),
        "speaker_notes": len(gt.get("speaker_notes") or []),
        **ooxml,
    }


def _deco_rows(source_root: Path, range_csv: Path) -> List[Dict[str, Any]]:
    annotations = _read_deco_table_annotations(range_csv)
    rows: List[Dict[str, Any]] = []
    for source_path in sorted(source_root.glob("*")):
        if source_path.suffix.lower() not in {".xlsx", ".xlsm", ".xls"}:
            continue
        table_rows = annotations.get(source_path.name, [])
        table_count = len(table_rows)
        status = "OK" if table_count else "MISSING_ANNOTATION"
        if source_path.suffix.lower() == ".xls":
            status = "UNSUPPORTED_WORKBOOK"
        row_count = sum(max(0, int(row["last_row"]) - int(row["first_row"]) + 1) for row in table_rows)
        ooxml = _ooxml_stats(source_path) if source_path.suffix.lower() in {".xlsx", ".xlsm"} else {}
        rows.append(
            {
                "dataset": "deco-xlsx",
                "format": "xlsx",
                "file": source_path.name,
                "doc_id": source_path.stem,
                "source_path": str(source_path),
                "native_path": "",
                "annotation_path": str(range_csv) if table_count else "",
                "status": status,
                "tables": table_count,
                "table_rows": row_count,
                "merged_cells": ooxml.get("merged_cells", 0),
                "headings": 0,
                "lists": 0,
                "images_gt": 0,
                "hyperlinks": 0,
                "speaker_notes": 0,
                **ooxml,
            }
        )
    return rows


def _read_deco_table_annotations(range_csv: Path) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    if not range_csv.exists():
        return grouped
    with range_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if (row.get("AnnotationLabel") or "").strip().lower() != "table":
                continue
            file_name = (row.get("FileName") or "").strip()
            if not file_name:
                continue
            grouped[file_name].append(
                {
                    "sheet": row.get("SheetName") or "",
                    "first_row": _int(row.get("FirstRow")),
                    "last_row": _int(row.get("LastRow")),
                    "first_col": _int(row.get("FirstColumn")),
                    "last_col": _int(row.get("LastColumn")),
                }
            )
    return grouped


def _ooxml_stats(path: Path) -> Dict[str, Any]:
    stats = {
        "sheets_or_slides": 0,
        "images_ooxml": 0,
        "charts_ooxml": 0,
        "diagrams_ooxml": 0,
        "drawings_ooxml": 0,
        "comments_ooxml": 0,
        "notes_ooxml": 0,
        "merged_cells": 0,
        "formulas": 0,
    }
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            stats["images_ooxml"] = sum(1 for name in names if re.search(r"/media/[^/]+$", name))
            stats["charts_ooxml"] = sum(1 for name in names if re.search(r"/charts/chart\d+\.xml$", name))
            stats["diagrams_ooxml"] = sum(1 for name in names if "/diagrams/" in name)
            stats["drawings_ooxml"] = sum(1 for name in names if re.search(r"/drawings/drawing\d+\.xml$", name))
            stats["comments_ooxml"] = sum(1 for name in names if "comments" in name.lower() and name.endswith(".xml"))
            stats["notes_ooxml"] = sum(1 for name in names if re.search(r"ppt/notesSlides/notesSlide\d+\.xml$", name))
            stats["sheets_or_slides"] = _count_sheets_or_slides(names)
            if path.suffix.lower() in {".xlsx", ".xlsm"}:
                for name in names:
                    if re.search(r"xl/worksheets/sheet\d+\.xml$", name):
                        data = zf.read(name)
                        stats["merged_cells"] += data.count(b"<mergeCell ")
                        stats["formulas"] += data.count(b"<f")
    except Exception:
        pass
    return stats


def _count_sheets_or_slides(names: Iterable[str]) -> int:
    values = list(names)
    ppt_slides = sum(1 for name in values if re.search(r"ppt/slides/slide\d+\.xml$", name))
    if ppt_slides:
        return ppt_slides
    xlsx_sheets = sum(1 for name in values if re.search(r"xl/worksheets/sheet\d+\.xml$", name))
    if xlsx_sheets:
        return xlsx_sheets
    return 1 if any(name == "word/document.xml" for name in values) else 0


def _complexity_score(row: Dict[str, Any]) -> float:
    if row.get("status") != "OK":
        return -1.0
    score = 0.0
    score += min(_num(row, "tables"), 8) * 5
    score += min(_num(row, "table_rows") / 25, 12)
    score += min(_num(row, "merged_cells"), 20) * 4
    score += min(_num(row, "images_ooxml") + _num(row, "images_gt"), 10) * 6
    score += min(_num(row, "charts_ooxml"), 8) * 8
    score += min(_num(row, "diagrams_ooxml"), 8) * 8
    score += min(_num(row, "drawings_ooxml"), 8) * 3
    score += min(_num(row, "comments_ooxml"), 5) * 3
    score += min(_num(row, "notes_ooxml") + _num(row, "speaker_notes"), 6) * 5
    score += min(_num(row, "lists"), 6) * 2
    score += min(_num(row, "headings"), 8)
    score += min(_num(row, "formulas") / 50, 10)
    return round(score, 3)


def _complexity_reasons(row: Dict[str, Any]) -> str:
    reasons = []
    for key, label in (
        ("tables", "tables"),
        ("table_rows", "table_rows"),
        ("merged_cells", "merged"),
        ("images_ooxml", "images"),
        ("charts_ooxml", "charts"),
        ("diagrams_ooxml", "smartart_diagrams"),
        ("drawings_ooxml", "drawings"),
        ("comments_ooxml", "comments"),
        ("notes_ooxml", "notes"),
        ("formulas", "formulas"),
        ("lists", "lists"),
        ("headings", "headings"),
    ):
        value = _num(row, key)
        if value:
            reasons.append(f"{label}={int(value)}")
    return "; ".join(reasons)


def _balanced_selection(rows: List[Dict[str, Any]], *, limit: int) -> List[Dict[str, Any]]:
    ok_rows = [row for row in rows if row.get("status") == "OK" and float(row.get("complexity_score") or 0) > 0]
    selected: List[Dict[str, Any]] = []
    selected_ids = set()

    targets = {"deco-xlsx": 32, "pandoc-pptx": 10, "pandoc-docx": 8}
    for dataset, target in targets.items():
        for row in [item for item in ok_rows if item.get("dataset") == dataset][:target]:
            selected.append(row)
            selected_ids.add((row.get("dataset"), row.get("doc_id")))
    for row in ok_rows:
        key = (row.get("dataset"), row.get("doc_id"))
        if len(selected) >= limit:
            break
        if key in selected_ids:
            continue
        selected.append(row)
        selected_ids.add(key)
    return selected[:limit]


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    fields = [
        "dataset",
        "format",
        "file",
        "doc_id",
        "status",
        "complexity_score",
        "complexity_reasons",
        "tables",
        "table_rows",
        "merged_cells",
        "images_ooxml",
        "images_gt",
        "charts_ooxml",
        "diagrams_ooxml",
        "drawings_ooxml",
        "comments_ooxml",
        "notes_ooxml",
        "speaker_notes",
        "sheets_or_slides",
        "formulas",
        "headings",
        "lists",
        "hyperlinks",
        "source_path",
        "native_path",
        "annotation_path",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _count_by(rows: Iterable[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _num(row: Dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0)
    except Exception:
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
