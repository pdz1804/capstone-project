"""Shared schemas for parsing information-loss evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EvalConfig:
    """Runtime config for parsing info-loss evaluation."""

    original_root: str
    parsed_root: str
    output_dir: str
    doc_id: Optional[str] = None
    modalities: List[str] = field(default_factory=lambda: ["docx", "xlsx", "xls", "pptx", "ppt", "pdf"])
    max_documents: Optional[int] = None
    pdf_reference: str = "weak"
    omnidocbench_gt: Optional[str] = None
    omnidocbench_image_root: Optional[str] = None
    weak_gt_policy: str = "separate"
    missing_group_policy: str = "renormalize"
    group_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "text": 30.0,
            "table": 25.0,
            "read_order": 15.0,
            "section_hierarchy": 15.0,
            "figure_captioning": 15.0,
        }
    )
    enabled_groups: Dict[str, bool] = field(
        default_factory=lambda: {
            "text": True,
            "table": True,
            "read_order": True,
            "section_hierarchy": True,
            "figure_captioning": True,
        }
    )
    table_teds_weight: float = 0.7
    table_edit_weight: float = 0.3
    emit_debug_html: bool = True
    max_examples_per_metric: int = 20


@dataclass
class SectionNode:
    id: str
    text: str
    level: int
    parent_id: Optional[str]
    path: List[str]
    order: int
    scope_id: str


@dataclass
class Component:
    id: str
    type: str
    text: str = ""
    order: int = 0
    scope_id: str = "document"
    section_path: List[str] = field(default_factory=list)
    html: str = ""
    media_path: str = ""
    bbox: Optional[List[float]] = None
    relation_id: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentComponents:
    doc_id: str
    modality: str
    source_path: str = ""
    reference_type: str = ""
    gt_strength: str = "strong"
    sections: List[SectionNode] = field(default_factory=list)
    components: List[Component] = field(default_factory=list)

    def by_type(self, component_type: str) -> List[Component]:
        return [c for c in self.components if c.type == component_type]


@dataclass
class MatchResult:
    gt_id: str
    pred_id: str
    score: float
    reason: str = ""


@dataclass
class GroupScore:
    name: str
    score: Optional[float]
    applicable: bool
    weight: float
    details: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DocumentScore:
    doc_id: str
    modality: str
    original_path: str
    parsed_path: str
    reference_type: str
    gt_strength: str
    overall_score: Optional[float]
    group_scores: Dict[str, GroupScore]

