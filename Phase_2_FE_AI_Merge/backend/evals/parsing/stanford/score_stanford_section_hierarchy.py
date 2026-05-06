#!/usr/bin/env python3
"""Score parsed section hierarchy against Stanford PDF/PPTX pseudo-GT.

This script expects:
1. pseudo-GT from generate_stanford_section_hierarchy.py
2. parsed outputs from the document pipeline, usually stage4_rag_ready

It does not call an LLM. Matching is deterministic over normalized titles and
folder/document context. Use an LLM later only to refine pseudo-GT or adjudicate
borderline semantic matches.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class PredNode:
    title: str
    level: int
    source: str
    order: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gt",
        default="backend/output/evaluation/stanford_section_hierarchy_pdf_pptx/section_hierarchy_pseudo_gt.json",
    )
    parser.add_argument(
        "--parsed-root",
        action="append",
        default=["backend/output/processing/stage4_rag_ready"],
        help="Parsed output root. Can be repeated.",
    )
    parser.add_argument(
        "--processing-manifest",
        default="backend/output/evaluation/stanford_pdf_pptx_v2_processing/processing_manifest.json",
        help="Optional V2 processing manifest mapping source paths to markdown outputs.",
    )
    parser.add_argument(
        "--output-dir",
        default="backend/output/evaluation/stanford_section_hierarchy_pdf_pptx_score",
    )
    parser.add_argument("--match-threshold", type=float, default=0.72)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gt_path = Path(args.gt)
    parsed_roots = [Path(root) for root in args.parsed_root]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    gt_payload = json.loads(gt_path.read_text(encoding="utf-8"))
    parsed_index = build_parsed_index(parsed_roots)
    manifest_path = Path(args.processing_manifest) if args.processing_manifest else None
    manifest_index = build_manifest_index(manifest_path) if manifest_path and manifest_path.exists() else {}

    document_scores: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    for document in gt_payload.get("documents", []):
        parsed = find_prediction(document, parsed_index, manifest_index)
        if not parsed:
            unmatched.append(
                {
                    "doc_id": document.get("doc_id"),
                    "source_path": document.get("source_path"),
                    "reason": "no parsed output found",
                }
            )
            continue
        score = score_document(document, parsed, threshold=args.match_threshold)
        document_scores.append(score)

    summary = build_summary(
        gt_payload,
        document_scores,
        unmatched,
        parsed_roots,
        args.match_threshold,
        manifest_path=manifest_path if manifest_index else None,
    )
    write_outputs(out_dir, summary, document_scores, unmatched)
    print(
        json.dumps(
            {
                "summary": str(out_dir / "summary.json"),
                "documents": str(out_dir / "document_scores.json"),
                "csv": str(out_dir / "document_scores.csv"),
                "unmatched": str(out_dir / "unmatched.json"),
            },
            indent=2,
        )
    )
    return 0


def build_parsed_index(parsed_roots: Sequence[Path]) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = {}
    for root in parsed_roots:
        if not root.exists():
            continue
        for md_path in sorted(root.rglob("*.md")):
            nodes = extract_markdown_nodes(md_path)
            if not nodes:
                continue
            record = {"path": str(md_path), "nodes": nodes}
            add_index_key(index, md_path.stem, record)
            add_index_key(index, md_path.parent.name, record)
        for chunks_path in sorted(root.rglob("*chunks.json")):
            nodes = extract_chunk_nodes(chunks_path)
            if not nodes:
                continue
            record = {"path": str(chunks_path), "nodes": nodes}
            add_index_key(index, chunks_path.parent.name, record)
            add_index_key(index, chunks_path.stem.replace("_chunks", ""), record)
    return index


def add_index_key(index: Dict[str, List[Dict[str, Any]]], key: str, record: Dict[str, Any]) -> None:
    normalized = normalize_key(key)
    if not normalized:
        return
    bucket = index.setdefault(normalized, [])
    if all(item["path"] != record["path"] for item in bucket):
        bucket.append(record)


def build_manifest_index(manifest_path: Path) -> Dict[str, Dict[str, Any]]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for source_path, record in (manifest.get("documents") or {}).items():
        if not record.get("success"):
            continue
        markdown = record.get("markdown")
        if not markdown or not Path(markdown).exists():
            continue
        nodes = extract_markdown_nodes(Path(markdown))
        if not nodes:
            parsed_json = record.get("parsed_json")
            if parsed_json and Path(parsed_json).exists():
                nodes = extract_parsed_json_nodes(Path(parsed_json))
        out[str(Path(source_path).resolve())] = {"path": markdown, "nodes": nodes}
    return out


def find_prediction(
    document: Dict[str, Any],
    parsed_index: Dict[str, List[Dict[str, Any]]],
    manifest_index: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    source_path = Path(str(document.get("source_path") or ""))
    manifest_record = manifest_index.get(str(source_path.resolve()))
    if manifest_record:
        return manifest_record
    candidates = [
        source_path.stem,
        safe_stem(source_path.stem),
        str(document.get("doc_id") or ""),
    ]
    for key in candidates:
        records = parsed_index.get(normalize_key(key))
        if records:
            return records[0]
    return None


def extract_parsed_json_nodes(path: Path) -> List[PredNode]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    nodes: List[PredNode] = []

    def walk(items: Any, order_base: List[int]) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            title = clean_title(str(item.get("heading_text") or item.get("title") or ""))
            if useful_title(title):
                order_base[0] += 1
                nodes.append(
                    PredNode(
                        title=title,
                        level=coerce_int(item.get("heading_level") or item.get("level"), 1),
                        source="parsed_json_heading",
                        order=order_base[0],
                    )
                )
            walk(item.get("children"), order_base)

    walk(payload, [0])
    return nodes


def extract_markdown_nodes(path: Path) -> List[PredNode]:
    nodes: List[PredNode] = []
    order = 0
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return nodes
    for line in lines:
        match = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue
        title = clean_title(match.group(2))
        if not useful_title(title):
            continue
        order += 1
        nodes.append(PredNode(title, len(match.group(1)), "markdown_heading", order))
    if nodes:
        return nodes

    # Fallback for parser markdown without headings: use short prominent lines.
    for line in lines:
        title = clean_title(line)
        if not useful_title(title):
            continue
        if len(title.split()) > 14:
            continue
        order += 1
        nodes.append(PredNode(title, 1, "markdown_line_fallback", order))
        if len(nodes) >= 80:
            break
    return nodes


def extract_chunk_nodes(path: Path) -> List[PredNode]:
    nodes: List[PredNode] = []
    seen = set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return nodes
    chunks = payload.get("chunks") if isinstance(payload, dict) else payload
    if not isinstance(chunks, list):
        return nodes
    for chunk in chunks:
        meta = chunk.get("metadata") or {}
        title = clean_title(str(meta.get("heading_text") or chunk.get("heading_text") or ""))
        if not useful_title(title):
            continue
        key = normalize_text(title)
        if key in seen:
            continue
        seen.add(key)
        nodes.append(
            PredNode(
                title=title,
                level=coerce_int(meta.get("heading_level") or chunk.get("heading_level"), 1),
                source="chunk_heading_metadata",
                order=coerce_int(meta.get("chunk_index") or chunk.get("chunk_index"), len(nodes)),
            )
        )
    return nodes


def score_document(document: Dict[str, Any], prediction: Dict[str, Any], *, threshold: float) -> Dict[str, Any]:
    gt_nodes = [
        node
        for node in document.get("nodes", [])
        if node.get("source") not in {"folder", "filename"} and useful_title(str(node.get("title") or ""))
    ]
    pred_nodes = prediction["nodes"]
    matches = greedy_match(gt_nodes, pred_nodes, threshold)
    recall = len(matches) / len(gt_nodes) if gt_nodes else None
    precision = len(matches) / len(pred_nodes) if pred_nodes else (1.0 if not gt_nodes else 0.0)
    f1 = harmonic(precision, recall) if recall is not None else None
    order_score = order_preservation(matches)
    level_score = level_accuracy(matches)
    overall = weighted_average(
        [
            (f1, 0.65),
            (order_score, 0.20),
            (level_score, 0.15),
        ]
    )
    return {
        "doc_id": document.get("doc_id"),
        "source_path": document.get("source_path"),
        "parsed_path": prediction["path"],
        "file_type": document.get("file_type"),
        "extraction_method": document.get("extraction_method"),
        "gt_section_count": len(gt_nodes),
        "pred_section_count": len(pred_nodes),
        "matched_count": len(matches),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "order_score": order_score,
        "level_score": level_score,
        "overall_score": overall,
        "matches": matches[:50],
    }


def greedy_match(gt_nodes: Sequence[Dict[str, Any]], pred_nodes: Sequence[PredNode], threshold: float) -> List[Dict[str, Any]]:
    candidates: List[Tuple[float, int, int]] = []
    for gt_idx, gt in enumerate(gt_nodes):
        gt_title = str(gt.get("title") or "")
        for pred_idx, pred in enumerate(pred_nodes):
            score = title_similarity(gt_title, pred.title)
            if score >= threshold:
                candidates.append((score, gt_idx, pred_idx))
    candidates.sort(reverse=True)
    used_gt = set()
    used_pred = set()
    matches = []
    for score, gt_idx, pred_idx in candidates:
        if gt_idx in used_gt or pred_idx in used_pred:
            continue
        used_gt.add(gt_idx)
        used_pred.add(pred_idx)
        gt = gt_nodes[gt_idx]
        pred = pred_nodes[pred_idx]
        matches.append(
            {
                "gt_index": gt_idx,
                "pred_index": pred_idx,
                "score": score,
                "gt_title": gt.get("title"),
                "pred_title": pred.title,
                "gt_level": gt.get("level"),
                "pred_level": pred.level,
                "gt_page_start": gt.get("page_start"),
                "gt_slide_start": gt.get("slide_start"),
            }
        )
    matches.sort(key=lambda item: item["gt_index"])
    return matches


def order_preservation(matches: Sequence[Dict[str, Any]]) -> Optional[float]:
    if len(matches) < 2:
        return None
    correct = 0
    total = 0
    for i in range(len(matches)):
        for j in range(i + 1, len(matches)):
            total += 1
            gt_before = matches[i]["gt_index"] < matches[j]["gt_index"]
            pred_before = matches[i]["pred_index"] < matches[j]["pred_index"]
            if gt_before == pred_before:
                correct += 1
    return correct / total if total else None


def level_accuracy(matches: Sequence[Dict[str, Any]]) -> Optional[float]:
    if not matches:
        return None
    vals = []
    for match in matches:
        gt_level = coerce_int(match.get("gt_level"), 1)
        pred_level = coerce_int(match.get("pred_level"), 1)
        vals.append(1.0 / (1.0 + abs(gt_level - pred_level)))
    return sum(vals) / len(vals) if vals else None


def title_similarity(a: str, b: str) -> float:
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    if a_norm in b_norm or b_norm in a_norm:
        return min(len(a_norm), len(b_norm)) / max(len(a_norm), len(b_norm))
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def build_summary(
    gt_payload: Dict[str, Any],
    scores: Sequence[Dict[str, Any]],
    unmatched: Sequence[Dict[str, Any]],
    parsed_roots: Sequence[Path],
    threshold: float,
    manifest_path: Optional[Path] = None,
) -> Dict[str, Any]:
    def avg(key: str) -> Optional[float]:
        vals = [float(item[key]) for item in scores if item.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    matched_docs = len(scores)
    total_docs = len(gt_payload.get("documents", []))
    by_type: Dict[str, int] = {}
    for score in scores:
        file_type = str(score.get("file_type") or "")
        by_type[file_type] = by_type.get(file_type, 0) + 1
    return {
        "gt_document_count": total_docs,
        "scored_document_count": matched_docs,
        "unmatched_document_count": len(unmatched),
        "parsed_coverage": matched_docs / total_docs if total_docs else 0.0,
        "parsed_roots": [str(root) for root in parsed_roots],
        "processing_manifest": str(manifest_path) if manifest_path else None,
        "match_threshold": threshold,
        "by_type_scored": by_type,
        "overall_score": avg("overall_score"),
        "f1": avg("f1"),
        "precision": avg("precision"),
        "recall": avg("recall"),
        "order_score": avg("order_score"),
        "level_score": avg("level_score"),
        "median_gt_sections": median([s["gt_section_count"] for s in scores]) if scores else None,
        "median_pred_sections": median([s["pred_section_count"] for s in scores]) if scores else None,
    }


def write_outputs(out_dir: Path, summary: Dict[str, Any], scores: Sequence[Dict[str, Any]], unmatched: Sequence[Dict[str, Any]]) -> None:
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "document_scores.json").write_text(json.dumps(list(scores), ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "unmatched.json").write_text(json.dumps(list(unmatched), ensure_ascii=False, indent=2), encoding="utf-8")
    with (out_dir / "document_scores.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["doc_id", "file_type", "overall", "f1", "precision", "recall", "order", "level", "gt_sections", "pred_sections", "matched", "source_path", "parsed_path"])
        for item in scores:
            writer.writerow(
                [
                    item.get("doc_id"),
                    item.get("file_type"),
                    fmt(item.get("overall_score")),
                    fmt(item.get("f1")),
                    fmt(item.get("precision")),
                    fmt(item.get("recall")),
                    fmt(item.get("order_score")),
                    fmt(item.get("level_score")),
                    item.get("gt_section_count"),
                    item.get("pred_section_count"),
                    item.get("matched_count"),
                    item.get("source_path"),
                    item.get("parsed_path"),
                ]
            )


def fmt(value: Any) -> str:
    return "" if value is None else f"{float(value):.6f}"


def harmonic(precision: Optional[float], recall: Optional[float]) -> Optional[float]:
    if precision is None or recall is None:
        return None
    if precision + recall <= 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def weighted_average(items: Sequence[Tuple[Optional[float], float]]) -> Optional[float]:
    total = 0.0
    value = 0.0
    for score, weight in items:
        if score is None:
            continue
        total += weight
        value += score * weight
    return value / total if total else None


def clean_title(value: str) -> str:
    value = value or ""
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip(" \t\r\n#*-:|")


def useful_title(text: str) -> bool:
    text = clean_title(text)
    if len(text) < 3 or len(text) > 220:
        return False
    if re.fullmatch(r"[\d\s./:-]+", text):
        return False
    return bool(re.search(r"[A-Za-z\u4e00-\u9fff]", text))


def normalize_text(value: str) -> str:
    value = clean_title(value).lower()
    value = re.sub(r"[_\\-]+", " ", value)
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_key(value: str) -> str:
    return normalize_text(value)


def safe_stem(value: str) -> str:
    value = re.sub(r"[^\w]+", "_", value).strip("_")
    return value[:50]


def coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


if __name__ == "__main__":
    raise SystemExit(main())
