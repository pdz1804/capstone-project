"""Matching and scoring for parsing information-loss evaluation."""

from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .schemas import Component, DocumentComponents, EvalConfig, GroupScore, MatchResult, SectionNode
from .omnidocbench_table import official_table_scores
from .utils import (
    average,
    combined_similarity,
    edit_similarity_from_tokens,
    html_to_text,
    html_tree_tokens,
    normalize_text,
)


def score_document(gt: DocumentComponents, pred: DocumentComponents, config: EvalConfig) -> Dict[str, GroupScore]:
    scores: Dict[str, GroupScore] = {}
    scores["text"] = score_text(gt, pred, config)
    scores["table"] = score_tables(gt, pred, config)
    scores["read_order"] = score_read_order(gt, pred, config)
    scores["section_hierarchy"] = score_section_hierarchy(gt, pred, config)
    scores["figure_captioning"] = score_figure_captioning(gt, pred, config)
    for name, score in scores.items():
        if not config.enabled_groups.get(name, True):
            score.applicable = False
            score.score = None
    return scores


def aggregate_overall(scores: Dict[str, GroupScore]) -> float | None:
    total_weight = 0.0
    weighted = 0.0
    for item in scores.values():
        if not item.applicable or item.score is None:
            continue
        total_weight += item.weight
        weighted += item.score * item.weight
    if total_weight <= 0:
        return None
    return weighted / total_weight


def score_text(gt: DocumentComponents, pred: DocumentComponents, config: EvalConfig) -> GroupScore:
    gt_items = [c for c in gt.components if c.type == "text"]
    pred_items = [c for c in pred.components if c.type == "text"]
    matches = greedy_match(gt_items, pred_items, threshold=0.55, same_scope=False)
    applicable = bool(gt_items)
    token_precision, token_recall, token_f1_score = _token_multiset_prf(
        " ".join(c.text for c in gt_items),
        " ".join(c.text for c in pred_items),
    )
    score = token_f1_score if applicable else None
    return GroupScore(
        name="text",
        score=score,
        applicable=applicable,
        weight=config.group_weights.get("text", 30.0),
        details={
            "gt_count": len(gt_items),
            "prediction_count": len(pred_items),
            "matched_count": len(matches),
            "token_precision": token_precision,
            "token_recall": token_recall,
            "token_f1": token_f1_score,
            "block_precision_proxy": len(matches) / len(pred_items) if pred_items else (1.0 if not gt_items else 0.0),
            "block_recall_proxy": len(matches) / len(gt_items) if gt_items else (1.0 if not pred_items else 0.0),
        },
        examples=_missing_extra_examples(gt_items, pred_items, matches, "text", config.max_examples_per_metric),
    )


def score_tables(gt: DocumentComponents, pred: DocumentComponents, config: EvalConfig) -> GroupScore:
    gt_items = [c for c in gt.components if c.type == "table"]
    pred_items = [c for c in pred.components if c.type == "table"]
    matches = greedy_match(gt_items, pred_items, threshold=0.2, similarity_fn=table_similarity, same_scope=False)
    table_scores: List[float] = []
    examples: List[Dict[str, Any]] = []
    for match in matches:
        gt_c = _by_id(gt_items, match.gt_id)
        pred_c = _by_id(pred_items, match.pred_id)
        if not gt_c or not pred_c:
            continue
        official_teds, official_error = official_table_scores(pred_c.html, gt_c.html)
        teds = official_teds if official_teds is not None else teds_like_similarity(gt_c.html, pred_c.html)
        edit = combined_similarity(html_to_text(gt_c.html), html_to_text(pred_c.html))
        score = config.table_teds_weight * teds + config.table_edit_weight * edit
        table_scores.append(score)
        examples.append(
            {
                "gt_id": gt_c.id,
                "pred_id": pred_c.id,
                "score": score,
                "teds": teds,
                "teds_source": "omnidocbench_official" if official_teds is not None else "internal_fallback",
                "teds_error": official_error,
                "edit_similarity": edit,
                "gt_html": gt_c.html[:1000],
                "prediction_html": pred_c.html[:1000],
            }
        )
    applicable = bool(gt_items)
    coverage = _f1(len(matches), len(gt_items), len(pred_items)) if applicable else None
    content_score = average(table_scores) if table_scores else (0.0 if applicable else None)
    if applicable:
        score = 0.5 * (coverage or 0.0) + 0.5 * (content_score or 0.0)
    else:
        score = None
    return GroupScore(
        name="table",
        score=score,
        applicable=applicable,
        weight=config.group_weights.get("table", 25.0),
        details={
            "gt_count": len(gt_items),
            "prediction_count": len(pred_items),
            "matched_count": len(matches),
            "coverage_f1": coverage,
            "mean_table_content_score": content_score,
        },
        examples=(examples + _missing_extra_examples(gt_items, pred_items, matches, "table", config.max_examples_per_metric))[: config.max_examples_per_metric],
    )


def score_read_order(gt: DocumentComponents, pred: DocumentComponents, config: EvalConfig) -> GroupScore:
    gt_items = [c for c in gt.components if c.type in {"text", "table", "figure", "caption", "heading"}]
    pred_items = [c for c in pred.components if c.type in {"text", "table", "figure", "caption", "heading"}]
    matches = greedy_match(gt_items, pred_items, threshold=0.45, same_scope=False)
    applicable = len(matches) >= 2
    if not applicable:
        return GroupScore("read_order", None, False, config.group_weights.get("read_order", 15.0), {"matched_count": len(matches)})
    gt_pos = {m.gt_id: _by_id(gt_items, m.gt_id).order for m in matches if _by_id(gt_items, m.gt_id)}
    pred_pos = {m.gt_id: _by_id(pred_items, m.pred_id).order for m in matches if _by_id(pred_items, m.pred_id)}
    correct = 0
    total = 0
    inversions: List[Dict[str, Any]] = []
    ids = list(gt_pos)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            gt_before = gt_pos[a] < gt_pos[b]
            pred_before = pred_pos[a] < pred_pos[b]
            total += 1
            if gt_before == pred_before:
                correct += 1
            elif len(inversions) < config.max_examples_per_metric:
                inversions.append({"gt_a": a, "gt_b": b, "gt_order": [gt_pos[a], gt_pos[b]], "prediction_order": [pred_pos[a], pred_pos[b]]})
    return GroupScore(
        "read_order",
        correct / total if total else None,
        True,
        config.group_weights.get("read_order", 15.0),
        {"matched_count": len(matches), "pair_count": total, "correct_pairs": correct},
        inversions,
    )


def score_section_hierarchy(gt: DocumentComponents, pred: DocumentComponents, config: EvalConfig) -> GroupScore:
    gt_nodes = gt.sections
    pred_nodes = pred.sections
    if not gt_nodes:
        return GroupScore("section_hierarchy", None, False, config.group_weights.get("section_hierarchy", 15.0))
    matches = match_sections(gt_nodes, pred_nodes)
    node_recall = len(matches) / len(gt_nodes) if gt_nodes else (1.0 if not pred_nodes else 0.0)
    path_scores = []
    examples: List[Dict[str, Any]] = []
    for match in matches:
        gt_s = _section_by_id(gt_nodes, match.gt_id)
        pred_s = _section_by_id(pred_nodes, match.pred_id)
        if not gt_s or not pred_s:
            continue
        path_score = combined_similarity(" > ".join(gt_s.path), " > ".join(pred_s.path))
        level_score = 1.0 if gt_s.level == pred_s.level else 0.0
        path_scores.append(0.7 * path_score + 0.3 * level_score)
        if path_score < 0.9 or level_score < 1.0:
            examples.append({"gt_path": gt_s.path, "pred_path": pred_s.path, "gt_level": gt_s.level, "pred_level": pred_s.level})
    path_accuracy = average(path_scores) if path_scores else 0.0
    score = 0.6 * node_recall + 0.4 * path_accuracy
    missing = [
        {"missing_node": s.path, "level": s.level}
        for s in gt_nodes
        if s.id not in {m.gt_id for m in matches}
    ][: config.max_examples_per_metric]
    return GroupScore(
        "section_hierarchy",
        score,
        True,
        config.group_weights.get("section_hierarchy", 15.0),
        {"gt_count": len(gt_nodes), "prediction_count": len(pred_nodes), "matched_count": len(matches), "node_recall": node_recall, "path_accuracy": path_accuracy},
        (examples + missing)[: config.max_examples_per_metric],
    )


def score_figure_captioning(gt: DocumentComponents, pred: DocumentComponents, config: EvalConfig) -> GroupScore:
    gt_figs = [c for c in gt.components if c.type == "figure"]
    pred_figs = [c for c in pred.components if c.type == "figure"]
    gt_caps = [c for c in gt.components if c.type == "caption"]
    pred_caps = [c for c in pred.components if c.type == "caption"]
    applicable = bool(gt_figs or gt_caps)
    if not applicable:
        return GroupScore("figure_captioning", None, False, config.group_weights.get("figure_captioning", 15.0))
    fig_matches = greedy_match(gt_figs, pred_figs, threshold=0.0, similarity_fn=lambda a, b: 1.0 if a.order == b.order else 0.5, same_scope=False)
    cap_matches = greedy_match(gt_caps, pred_caps, threshold=0.5, same_scope=False)
    fig_f1 = _f1(len(fig_matches), len(gt_figs), len(pred_figs)) if (gt_figs or pred_figs) else 1.0
    cap_f1 = _f1(len(cap_matches), len(gt_caps), len(pred_caps)) if (gt_caps or pred_caps) else 1.0
    # Association is approximated by caption order proximity in v1.
    assoc = cap_f1 if gt_figs or pred_figs else 1.0
    score = 0.4 * fig_f1 + 0.3 * cap_f1 + 0.3 * assoc
    return GroupScore(
        "figure_captioning",
        score,
        True,
        config.group_weights.get("figure_captioning", 15.0),
        {"figure_f1": fig_f1, "caption_f1": cap_f1, "association_proxy": assoc, "gt_figures": len(gt_figs), "prediction_figures": len(pred_figs), "gt_captions": len(gt_caps), "prediction_captions": len(pred_caps)},
        _missing_extra_examples(gt_figs + gt_caps, pred_figs + pred_caps, fig_matches + cap_matches, "figure_caption", config.max_examples_per_metric),
    )


def greedy_match(
    gt_items: Sequence[Component],
    pred_items: Sequence[Component],
    threshold: float = 0.5,
    similarity_fn=None,
    same_scope: bool = True,
) -> List[MatchResult]:
    similarity_fn = similarity_fn or component_similarity
    candidates: List[Tuple[float, Component, Component]] = []
    for gt in gt_items:
        for pred in pred_items:
            if same_scope and gt.scope_id != pred.scope_id:
                continue
            if gt.type != pred.type and {gt.type, pred.type} != {"heading", "text"}:
                continue
            score = similarity_fn(gt, pred)
            if score >= threshold:
                candidates.append((score, gt, pred))
    candidates.sort(key=lambda x: x[0], reverse=True)
    used_gt = set()
    used_pred = set()
    matches: List[MatchResult] = []
    for score, gt, pred in candidates:
        if gt.id in used_gt or pred.id in used_pred:
            continue
        used_gt.add(gt.id)
        used_pred.add(pred.id)
        matches.append(MatchResult(gt.id, pred.id, score))
    return matches


def component_similarity(gt: Component, pred: Component) -> float:
    if gt.type == "table" or pred.type == "table":
        return table_similarity(gt, pred)
    if gt.type == "figure" and pred.type == "figure":
        if gt.meta.get("sha256") and gt.meta.get("sha256") == pred.meta.get("sha256"):
            return 1.0
        return 1.0 / (1.0 + abs(gt.order - pred.order))
    gt_text = normalize_text(gt.text).lower()
    pred_text = normalize_text(pred.text).lower()
    if gt_text and pred_text and (gt_text in pred_text or pred_text in gt_text):
        shorter = min(len(gt_text), len(pred_text))
        longer = max(len(gt_text), len(pred_text))
        return max(combined_similarity(gt.text, pred.text), shorter / longer)
    return combined_similarity(gt.text, pred.text)


def table_similarity(gt: Component, pred: Component) -> float:
    html_score = teds_like_similarity(gt.html, pred.html)
    text_score = combined_similarity(html_to_text(gt.html), html_to_text(pred.html))
    return 0.6 * html_score + 0.4 * text_score


def teds_like_similarity(gt_html: str, pred_html: str) -> float:
    return edit_similarity_from_tokens(html_tree_tokens(gt_html), html_tree_tokens(pred_html))


def match_sections(gt_nodes: Sequence[SectionNode], pred_nodes: Sequence[SectionNode]) -> List[MatchResult]:
    candidates: List[Tuple[float, SectionNode, SectionNode]] = []
    for gt in gt_nodes:
        for pred in pred_nodes:
            score = 0.7 * combined_similarity(gt.text, pred.text) + 0.3 * (1.0 / (1.0 + abs(gt.order - pred.order)))
            if score >= 0.45:
                candidates.append((score, gt, pred))
    candidates.sort(key=lambda x: x[0], reverse=True)
    used_gt = set()
    used_pred = set()
    out: List[MatchResult] = []
    for score, gt, pred in candidates:
        if gt.id in used_gt or pred.id in used_pred:
            continue
        used_gt.add(gt.id)
        used_pred.add(pred.id)
        out.append(MatchResult(gt.id, pred.id, score))
    return out


def _f1(matches: int, gt_count: int, pred_count: int) -> float:
    if gt_count == 0 and pred_count == 0:
        return 1.0
    if matches == 0:
        return 0.0
    precision = matches / pred_count if pred_count else 0.0
    recall = matches / gt_count if gt_count else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _token_multiset_prf(gt_text: str, pred_text: str) -> Tuple[float, float, float]:
    gt_tokens = _tokens(gt_text)
    pred_tokens = _tokens(pred_text)
    if not gt_tokens and not pred_tokens:
        return 1.0, 1.0, 1.0
    if not gt_tokens or not pred_tokens:
        return 0.0, 0.0, 0.0
    gt_counter = Counter(gt_tokens)
    pred_counter = Counter(pred_tokens)
    overlap = sum((gt_counter & pred_counter).values())
    precision = overlap / len(pred_tokens)
    recall = overlap / len(gt_tokens)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def _tokens(value: str) -> List[str]:
    import re

    return re.findall(r"[\w']+", normalize_text(value).lower())


def _missing_extra_examples(
    gt_items: Sequence[Component],
    pred_items: Sequence[Component],
    matches: Sequence[MatchResult],
    label: str,
    limit: int,
) -> List[Dict[str, Any]]:
    matched_gt = {m.gt_id for m in matches}
    matched_pred = {m.pred_id for m in matches}
    examples: List[Dict[str, Any]] = []
    for item in gt_items:
        if item.id not in matched_gt:
            examples.append({"kind": f"missing_{label}", "id": item.id, "type": item.type, "text": (item.text or html_to_text(item.html))[:500], "scope": item.scope_id})
            if len(examples) >= limit:
                return examples
    for item in pred_items:
        if item.id not in matched_pred:
            examples.append({"kind": f"extra_{label}", "id": item.id, "type": item.type, "text": (item.text or html_to_text(item.html))[:500], "scope": item.scope_id})
            if len(examples) >= limit:
                return examples
    return examples


def _by_id(items: Sequence[Component], item_id: str) -> Component | None:
    return next((item for item in items if item.id == item_id), None)


def _section_by_id(items: Sequence[SectionNode], item_id: str) -> SectionNode | None:
    return next((item for item in items if item.id == item_id), None)
