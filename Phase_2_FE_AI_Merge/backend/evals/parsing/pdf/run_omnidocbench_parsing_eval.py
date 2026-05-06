#!/usr/bin/env python3
"""Run parsing information-loss eval on OmniDocBench pages.

This uses OmniDocBench page images + OmniDocBench.json as the PDF/image ground
truth. Predictions are cached as the project's normalized parsed-JSON shape:
[{heading_text, heading_level, content, children}].
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys
import types
import warnings
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.evaluation.parsing_info_loss import load_eval_config
from src.evaluation.parsing_info_loss.metrics import aggregate_overall, score_document
from src.evaluation.parsing_info_loss.prediction import load_prediction_json
from src.evaluation.parsing_info_loss.reference import _omni_category_to_type, _strip_tags
from src.evaluation.parsing_info_loss.runner import _component_counts
from src.evaluation.parsing_info_loss.schemas import Component, DocumentComponents, DocumentScore, SectionNode
from src.evaluation.parsing_info_loss.utils import normalize_text, stable_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gt", default=str(REPO_ROOT / "data" / "omnidocbench" / "OmniDocBench.json"))
    parser.add_argument("--image-root", default=str(REPO_ROOT / "data" / "omnidocbench" / "images"))
    parser.add_argument("--output-dir", default=str(BACKEND_ROOT / "output" / "evaluation" / "parsing_info_loss_omnidocbench"))
    parser.add_argument("--config", default=str(BACKEND_ROOT / "config" / "parsing_info_loss_eval.yaml"))
    parser.add_argument("--predictions-root", default=None, help="Existing/cached parsed JSON prediction directory.")
    parser.add_argument("--parse-missing", action="store_true", help="Parse missing page images with Docling.")
    parser.add_argument(
        "--max-parse-pixels",
        type=int,
        default=None,
        help="Skip parsing missing images above this pixel count. Already cached predictions are still scored.",
    )
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--subset", default=None, help="Filter page_attribute.subset, e.g. table_hard or v1.5.")
    parser.add_argument("--data-source", default=None, help="Filter page_attribute.data_source.")
    parser.add_argument("--doc-id", action="append", default=[], help="Evaluate only image stems. Can be repeated.")
    parser.add_argument(
        "--enable-section-hierarchy",
        action="store_true",
        help="Enable shallow title-based section proxy scoring for OmniDocBench pages.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gt_path = Path(args.gt)
    image_root = Path(args.image_root)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_root = Path(args.predictions_root) if args.predictions_root else out_dir / "predictions_json"
    pred_root.mkdir(parents=True, exist_ok=True)
    markdown_root = out_dir / "predictions_markdown"
    markdown_root.mkdir(parents=True, exist_ok=True)

    config = load_eval_config(
        config_path=args.config,
        original_root=str(image_root.resolve()),
        parsed_root=str(pred_root.resolve()),
        output_dir=str(out_dir.resolve()),
        modalities=["pdf"],
        pdf_reference="omnidocbench",
        omnidocbench_gt=str(gt_path.resolve()),
        omnidocbench_image_root=str(image_root.resolve()),
    )
    config.enabled_groups["section_hierarchy"] = bool(args.enable_section_hierarchy)

    pages = select_pages(json.loads(gt_path.read_text(encoding="utf-8")), args)
    documents: List[DocumentScore] = []
    skipped: List[Dict[str, str]] = []
    table_debug: List[Dict[str, Any]] = []
    component_debug: List[Dict[str, Any]] = []
    processor = make_document_processor_v2(out_dir / "document_processor_v2") if args.parse_missing else None

    for idx, page in enumerate(pages, 1):
        page_info = page.get("page_info") or {}
        image_name = Path(str(page_info.get("image_path") or "")).name
        if not image_name:
            skipped.append({"doc_id": "", "reason": "missing image_path"})
            continue
        image_path = image_root / image_name
        doc_id = image_path.stem
        if not image_path.exists():
            skipped.append({"doc_id": doc_id, "reason": f"missing image file: {image_name}"})
            continue
        pred_path = pred_root / f"{doc_id}.json"
        if not pred_path.exists():
            if not args.parse_missing:
                skipped.append({"doc_id": doc_id, "reason": "missing prediction json"})
                continue
            if args.max_parse_pixels:
                pixel_count = get_image_pixel_count(image_path)
                if pixel_count is None:
                    skipped.append({"doc_id": doc_id, "reason": "could not read image dimensions"})
                    continue
                if pixel_count > args.max_parse_pixels:
                    skipped.append(
                        {
                            "doc_id": doc_id,
                            "reason": f"image too large to parse: {pixel_count} pixels > {args.max_parse_pixels}",
                        }
                    )
                    continue
            try:
                markdown = parse_image_with_document_processor_v2(image_path, processor)
            except Exception as exc:
                skipped.append({"doc_id": doc_id, "reason": f"parse failed: {type(exc).__name__}: {exc}"})
                continue
            (markdown_root / f"{doc_id}.md").write_text(markdown, encoding="utf-8")
            write_prediction_json(pred_path, markdown)

        gt = build_omni_page_reference(page, doc_id, str(image_path), enable_section_hierarchy=args.enable_section_hierarchy)
        pred = load_prediction_json(pred_path, doc_id, "pdf")
        group_scores = score_document(gt, pred, config)
        overall = aggregate_overall(group_scores)
        doc_score = DocumentScore(
            doc_id=doc_id,
            modality="pdf",
            original_path=str(image_path),
            parsed_path=str(pred_path),
            reference_type=gt.reference_type,
            gt_strength=gt.gt_strength,
            overall_score=overall,
            group_scores=group_scores,
        )
        documents.append(doc_score)
        component_debug.append({"doc_id": doc_id, "gt_counts": _component_counts(gt), "prediction_counts": _component_counts(pred)})
        table_debug.append({"doc_id": doc_id, "examples": group_scores["table"].examples})
        if idx % 10 == 0:
            print(f"processed {idx}/{len(pages)} pages; scored={len(documents)} skipped={len(skipped)}", flush=True)

    written = write_outputs(out_dir, documents, skipped, table_debug, component_debug, config)
    print(json.dumps({k: str(v) for k, v in written.items()}, indent=2, ensure_ascii=False))
    return 0


def select_pages(pages: List[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    wanted = {x for x in args.doc_id}
    selected: List[Dict[str, Any]] = []
    for page in pages:
        page_info = page.get("page_info") or {}
        attrs = page_info.get("page_attribute") or {}
        image_stem = Path(str(page_info.get("image_path") or "")).stem
        if wanted and image_stem not in wanted:
            continue
        if args.subset and attrs.get("subset") != args.subset:
            continue
        if args.data_source and attrs.get("data_source") != args.data_source:
            continue
        selected.append(page)
        if args.max_pages and len(selected) >= args.max_pages:
            break
    return selected


def build_omni_page_reference(page: Dict[str, Any], doc_id: str, image_path: str, *, enable_section_hierarchy: bool = False) -> DocumentComponents:
    doc = DocumentComponents(
        doc_id=doc_id,
        modality="pdf",
        source_path=image_path,
        reference_type="omnidocbench_annotation",
        gt_strength="strong",
    )
    idx = 0
    section_idx = 0
    for det in sorted(page.get("layout_dets") or [], key=lambda d: d.get("order") if d.get("order") is not None else 10**9):
        if det.get("ignore"):
            continue
        category = str(det.get("category_type") or "")
        comp_type = _omni_category_to_type(category)
        if comp_type is None:
            continue
        idx += 1
        html_value = str(det.get("html") or "")
        text = normalize_text(str(det.get("text") or det.get("latex") or ""))
        if not text and html_value:
            text = normalize_text(_strip_tags(html_value))
        order_value = det.get("order")
        if enable_section_hierarchy and comp_type == "heading" and "title" in category.lower() and text:
            section_idx += 1
            section_id = stable_id("gt_sec", section_idx)
            doc.sections.append(
                SectionNode(
                    id=section_id,
                    text=text,
                    level=1,
                    parent_id=None,
                    path=[text],
                    order=int(order_value if order_value is not None else idx),
                    scope_id=section_id,
                )
            )
        doc.components.append(
            Component(
                id=stable_id("gt", idx),
                type=comp_type,
                text=text,
                html=html_value,
                order=int(order_value if order_value is not None else idx),
                scope_id="document",
                section_path=[],
                bbox=det.get("poly"),
                meta={"category_type": category, "anno_id": det.get("anno_id")},
            )
        )
    return doc


def make_document_processor_v2(output_dir: Path):
    """Parse one OmniDocBench page through DocumentProcessorV2.

    For image inputs V2 intentionally routes to its Docling path, but it still
    goes through the project's smart-router/export layer instead of calling
    Docling directly.
    """

    DocumentProcessorV2, ProcessingConfigV2 = load_document_processor_v2()
    os.environ["USE_AWS_SAGEMAKER_DOCLING"] = "0"
    cfg = ProcessingConfigV2(
        prefer_custom_readers=True,
        runtime_yaml={
            "inference": {"use_aws_sagemaker_docling": False},
            "processing": {"document": {"docling_backend": "local", "docling_remote": "0"}},
        },
        docling_config=SimpleNamespace(
            enable_ocr=True,
            enable_vlm=False,
            export_images=False,
            export_tables=True,
            ocr_languages=["eng"],
        ),
    )
    return DocumentProcessorV2(input_dir=REPO_ROOT / "data" / "omnidocbench" / "images", output_dir=output_dir, config=cfg)


def get_image_pixel_count(image_path: Path) -> Optional[int]:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with Image.open(image_path) as image:
                width, height = image.size
    except Exception:
        return None
    return int(width) * int(height)


def parse_image_with_document_processor_v2(image_path: Path, processor: Any) -> str:
    if processor is None:
        raise RuntimeError("DocumentProcessorV2 was not initialized")
    info = processor.process_single_file(image_path)
    if not info.get("success"):
        raise RuntimeError(info.get("error") or "DocumentProcessorV2 failed")
    exported = processor.export_processed_document(info)
    md_path = exported.get("markdown")
    if md_path and Path(md_path).exists():
        return Path(md_path).read_text(encoding="utf-8")
    doc = info.get("doc_object")
    if doc is not None and hasattr(doc, "export_to_markdown"):
        return doc.export_to_markdown()
    content_tree = info.get("content_tree")
    if content_tree:
        return processor._build_custom_markdown(content_tree=content_tree, excel_sheets=None, title=image_path.stem)
    raise RuntimeError("DocumentProcessorV2 produced no markdown/content output")


def load_document_processor_v2():
    """Load DocumentProcessorV2 without executing processor/__init__.py."""

    package_name = "src.processor"
    if package_name not in sys.modules:
        pkg = types.ModuleType(package_name)
        pkg.__path__ = [str(BACKEND_ROOT / "src" / "processor")]
        sys.modules[package_name] = pkg
    module_name = "src.processor.document_processor_v2"
    if module_name in sys.modules:
        module = sys.modules[module_name]
    else:
        module_path = BACKEND_ROOT / "src" / "processor" / "document_processor_v2.py"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return module.DocumentProcessorV2, module.ProcessingConfigV2


def write_prediction_json(path: Path, markdown: str) -> None:
    payload = [{"heading_text": "", "heading_level": 1, "content": markdown, "children": []}]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_outputs(
    out_dir: Path,
    documents: List[DocumentScore],
    skipped: List[Dict[str, str]],
    table_debug: List[Dict[str, Any]],
    component_debug: List[Dict[str, Any]],
    config: Any,
) -> Dict[str, Path]:
    summary = build_summary(documents, skipped, config)
    paths = {
        "summary": out_dir / "summary.json",
        "documents": out_dir / "documents.json",
        "csv": out_dir / "document_scores.csv",
        "components": out_dir / "component_counts.json",
        "tables": out_dir / "table_scores.json",
        "skipped": out_dir / "skipped.json",
    }
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["documents"].write_text(json.dumps([document_to_dict(d) for d in documents], ensure_ascii=False, indent=2), encoding="utf-8")
    paths["components"].write_text(json.dumps(component_debug, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["tables"].write_text(json.dumps(table_debug, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["skipped"].write_text(json.dumps(skipped, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(paths["csv"], documents)
    return paths


def build_summary(documents: List[DocumentScore], skipped: List[Dict[str, str]], config: Any) -> Dict[str, Any]:
    groups = ["text", "table", "read_order", "section_hierarchy", "figure_captioning"]
    group_scores = {}
    for group in groups:
        vals = [d.group_scores[group].score for d in documents if d.group_scores[group].applicable and d.group_scores[group].score is not None]
        group_scores[group] = sum(vals) / len(vals) if vals else None
    overall_vals = [d.overall_score for d in documents if d.overall_score is not None]
    return {
        "document_count": len(documents),
        "skipped_count": len(skipped),
        "overall_score": sum(overall_vals) / len(overall_vals) if overall_vals else None,
        "group_scores": group_scores,
        "config": asdict(config),
    }


def document_to_dict(doc: DocumentScore) -> Dict[str, Any]:
    return {
        "doc_id": doc.doc_id,
        "modality": doc.modality,
        "original_path": doc.original_path,
        "parsed_path": doc.parsed_path,
        "reference_type": doc.reference_type,
        "gt_strength": doc.gt_strength,
        "overall_score": doc.overall_score,
        "group_scores": {k: asdict(v) for k, v in doc.group_scores.items()},
    }


def write_csv(path: Path, documents: Iterable[DocumentScore]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["doc_id", "overall", "text", "table", "read_order", "section_hierarchy", "figure_captioning", "reference_type", "gt_strength"])
        for doc in documents:
            writer.writerow(
                [
                    doc.doc_id,
                    fmt(doc.overall_score),
                    fmt(doc.group_scores["text"].score),
                    fmt(doc.group_scores["table"].score),
                    fmt(doc.group_scores["read_order"].score),
                    fmt(doc.group_scores["section_hierarchy"].score),
                    fmt(doc.group_scores["figure_captioning"].score),
                    doc.reference_type,
                    doc.gt_strength,
                ]
            )


def fmt(value: Optional[float]) -> str:
    return "" if value is None else f"{value:.6f}"


if __name__ == "__main__":
    raise SystemExit(main())
