"""Runner for parsing information-loss evaluation."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .metrics import aggregate_overall, score_document
from .prediction import load_prediction_json
from .reference import build_office_reference, build_pdf_weak_reference, load_omnidocbench_reference
from .schemas import DocumentComponents, DocumentScore, EvalConfig, GroupScore


MODALITY_BY_EXT = {
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".xlsm": "xlsx",
    ".xls": "xls",
    ".pptx": "pptx",
    ".ppt": "ppt",
    ".pdf": "pdf",
}


def load_eval_config(
    *,
    config_path: Optional[str],
    original_root: str,
    parsed_root: str,
    output_dir: str,
    doc_id: Optional[str] = None,
    modalities: Optional[Sequence[str]] = None,
    max_documents: Optional[int] = None,
    pdf_reference: Optional[str] = None,
    omnidocbench_gt: Optional[str] = None,
    omnidocbench_image_root: Optional[str] = None,
    weights: Optional[Dict[str, float]] = None,
    disabled_groups: Optional[Sequence[str]] = None,
) -> EvalConfig:
    cfg = EvalConfig(original_root=original_root, parsed_root=parsed_root, output_dir=output_dir)
    payload: Dict[str, Any] = {}
    if config_path:
        try:
            import yaml

            payload = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
        except Exception:
            payload = {}
    root = payload.get("parsing_info_loss_eval") or payload
    scoring = root.get("scoring") or {}
    groups = scoring.get("groups") or {}
    for name, group in groups.items():
        if "weight" in group:
            cfg.group_weights[name] = float(group["weight"])
        if "enabled" in group:
            cfg.enabled_groups[name] = bool(group["enabled"])
    if "weak_gt_policy" in scoring:
        cfg.weak_gt_policy = str(scoring["weak_gt_policy"])
    if "missing_group_policy" in scoring:
        cfg.missing_group_policy = str(scoring["missing_group_policy"])
    table_group = groups.get("table") or {}
    cfg.table_teds_weight = float(table_group.get("teds_weight", cfg.table_teds_weight))
    cfg.table_edit_weight = float(table_group.get("edit_weight", cfg.table_edit_weight))
    table_conversion = root.get("table_conversion") or {}
    cfg.emit_debug_html = bool(table_conversion.get("emit_debug_html", cfg.emit_debug_html))
    gt = root.get("gt") or {}
    pdf_cfg = gt.get("pdf") or root.get("pdf_reference") or {}
    if isinstance(pdf_cfg, dict):
        cfg.pdf_reference = str(pdf_cfg.get("mode", cfg.pdf_reference))
        cfg.omnidocbench_gt = pdf_cfg.get("omnidocbench_gt_json", cfg.omnidocbench_gt)
        cfg.omnidocbench_image_root = pdf_cfg.get("omnidocbench_image_root", cfg.omnidocbench_image_root)
    if original_root:
        cfg.original_root = original_root
    if parsed_root:
        cfg.parsed_root = parsed_root
    if output_dir:
        cfg.output_dir = output_dir
    cfg.doc_id = doc_id
    if modalities:
        cfg.modalities = list(modalities)
    cfg.max_documents = max_documents
    if pdf_reference:
        cfg.pdf_reference = pdf_reference
    if omnidocbench_gt:
        cfg.omnidocbench_gt = omnidocbench_gt
    if omnidocbench_image_root:
        cfg.omnidocbench_image_root = omnidocbench_image_root
    for key, value in (weights or {}).items():
        cfg.group_weights[key] = value
    for group in disabled_groups or []:
        cfg.enabled_groups[group] = False
    return cfg


def run_parsing_info_loss_eval(config: EvalConfig) -> Dict[str, Path]:
    out_dir = Path(config.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    documents: List[DocumentScore] = []
    debug_payloads: Dict[str, Any] = {"tables": [], "components": []}

    for original_path, modality, doc_id in discover_documents(config):
        parsed_path = resolve_parsed_path(Path(config.parsed_root), doc_id, modality)
        if parsed_path is None:
            continue
        gt = build_reference(original_path, modality, doc_id, config)
        if gt is None:
            continue
        pred = load_prediction_json(parsed_path, doc_id, _normalize_modality(modality))
        group_scores = score_document(gt, pred, config)
        overall = aggregate_overall(group_scores)
        documents.append(
            DocumentScore(
                doc_id=doc_id,
                modality=_normalize_modality(modality),
                original_path=str(original_path),
                parsed_path=str(parsed_path),
                reference_type=gt.reference_type,
                gt_strength=gt.gt_strength,
                overall_score=overall,
                group_scores=group_scores,
            )
        )
        debug_payloads["components"].append(
            {
                "doc_id": doc_id,
                "gt_counts": _component_counts(gt),
                "prediction_counts": _component_counts(pred),
            }
        )
        table_score = group_scores.get("table")
        if table_score:
            debug_payloads["tables"].append({"doc_id": doc_id, "examples": table_score.examples})

    summary = build_summary(documents, config)
    written = {
        "summary": out_dir / "summary.json",
        "documents": out_dir / "documents.json",
        "csv": out_dir / "document_scores.csv",
        "components": out_dir / "component_counts.json",
        "tables": out_dir / "table_scores.json",
    }
    if config.emit_debug_html:
        table_html_dir = out_dir / "table_generated_html"
        table_html_dir.mkdir(parents=True, exist_ok=True)
        for doc_tables in debug_payloads["tables"]:
            safe_doc = _safe_filename(str(doc_tables["doc_id"]))
            for idx, example in enumerate(doc_tables.get("examples") or [], 1):
                pred_html = example.get("prediction_html")
                gt_html = example.get("gt_html")
                if pred_html:
                    (table_html_dir / f"{safe_doc}_table_{idx:03d}_prediction.html").write_text(pred_html, encoding="utf-8")
                if gt_html:
                    (table_html_dir / f"{safe_doc}_table_{idx:03d}_gt.html").write_text(gt_html, encoding="utf-8")
        written["table_html_dir"] = table_html_dir
    written["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    written["documents"].write_text(json.dumps([_document_score_to_dict(d) for d in documents], ensure_ascii=False, indent=2), encoding="utf-8")
    written["components"].write_text(json.dumps(debug_payloads["components"], ensure_ascii=False, indent=2), encoding="utf-8")
    written["tables"].write_text(json.dumps(debug_payloads["tables"], ensure_ascii=False, indent=2), encoding="utf-8")
    write_scores_csv(written["csv"], documents)
    return written


def discover_documents(config: EvalConfig) -> List[Tuple[Path, str, str]]:
    original_root = Path(config.original_root)
    items: List[Tuple[Path, str, str]] = []
    if not original_root.exists():
        return items
    allowed = {m.lower() for m in config.modalities}
    for path in sorted(original_root.iterdir()):
        if not path.is_file():
            continue
        modality = MODALITY_BY_EXT.get(path.suffix.lower())
        if not modality or modality not in allowed:
            continue
        doc_id = path.stem
        if config.doc_id and doc_id != config.doc_id:
            continue
        items.append((path, modality, doc_id))
        if config.max_documents and len(items) >= config.max_documents:
            break
    return items


def resolve_parsed_path(parsed_root: Path, doc_id: str, modality: str) -> Optional[Path]:
    norm = _normalize_modality(modality)
    candidates = [
        parsed_root / f"{doc_id}.json",
        parsed_root / f"{norm}_parsed" / f"{doc_id}.json",
    ]
    if norm == "xlsx":
        candidates.append(parsed_root / "excel_parsed" / f"{doc_id}.json")
    if norm == "docx":
        candidates.append(parsed_root / "docx_parsed" / f"{doc_id}.json")
    if norm == "pptx":
        candidates.append(parsed_root / "pptx_parsed" / f"{doc_id}.json")
    if norm == "pdf":
        candidates.append(parsed_root / "pdf_parsed" / f"{doc_id}.json")
    for path in candidates:
        if path.exists():
            return path
    return None


def build_reference(original_path: Path, modality: str, doc_id: str, config: EvalConfig) -> Optional[DocumentComponents]:
    norm = _normalize_modality(modality)
    if norm == "pdf":
        if config.pdf_reference == "omnidocbench" and config.omnidocbench_gt:
            docs = load_omnidocbench_reference(Path(config.omnidocbench_gt), doc_id=doc_id)
            return docs[0] if docs else None
        return build_pdf_weak_reference(original_path, doc_id)
    if modality in {"xls", "ppt"}:
        # Legacy binary conversion is intentionally not run in this read-only evaluator.
        return None
    return build_office_reference(original_path, doc_id, norm)


def build_summary(documents: List[DocumentScore], config: EvalConfig) -> Dict[str, Any]:
    group_names = ["text", "table", "read_order", "section_hierarchy", "figure_captioning"]
    by_group = {}
    for group in group_names:
        values = [d.group_scores[group].score for d in documents if group in d.group_scores and d.group_scores[group].applicable and d.group_scores[group].score is not None]
        by_group[group] = sum(values) / len(values) if values else None
    by_modality: Dict[str, List[float]] = {}
    for doc in documents:
        if doc.overall_score is not None:
            by_modality.setdefault(doc.modality, []).append(doc.overall_score)
    return {
        "document_count": len(documents),
        "overall_score": sum(d.overall_score for d in documents if d.overall_score is not None) / max(1, len([d for d in documents if d.overall_score is not None])),
        "group_scores": by_group,
        "by_modality": {k: sum(v) / len(v) for k, v in by_modality.items()},
        "config": asdict(config),
    }


def write_scores_csv(path: Path, documents: List[DocumentScore]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["doc_id", "modality", "overall", "text", "table", "read_order", "section_hierarchy", "figure_captioning", "reference_type", "gt_strength"])
        for doc in documents:
            writer.writerow(
                [
                    doc.doc_id,
                    doc.modality,
                    _fmt(doc.overall_score),
                    _fmt(doc.group_scores["text"].score),
                    _fmt(doc.group_scores["table"].score),
                    _fmt(doc.group_scores["read_order"].score),
                    _fmt(doc.group_scores["section_hierarchy"].score),
                    _fmt(doc.group_scores["figure_captioning"].score),
                    doc.reference_type,
                    doc.gt_strength,
                ]
            )


def _document_score_to_dict(doc: DocumentScore) -> Dict[str, Any]:
    payload = asdict(doc)
    payload["group_scores"] = {name: asdict(score) for name, score in doc.group_scores.items()}
    return payload


def _component_counts(doc: DocumentComponents) -> Dict[str, int]:
    counts: Dict[str, int] = {"sections": len(doc.sections)}
    for component in doc.components:
        counts[component.type] = counts.get(component.type, 0) + 1
    return counts


def _normalize_modality(modality: str) -> str:
    if modality in {"xls", "xlsx", "xlsm"}:
        return "xlsx"
    if modality in {"ppt", "pptx"}:
        return "pptx"
    return modality


def _fmt(value: Optional[float]) -> str:
    return "" if value is None else f"{value:.6f}"


def _safe_filename(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "document"
