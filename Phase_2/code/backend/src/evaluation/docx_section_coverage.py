"""DOCX-first parsing/chunking evaluation for section coverage.

This module evaluates whether the existing DOCX parser/chunker preserves:

1. section structure well enough for deterministic downstream mapping
2. section content well enough for question-answer coverage against the
   section's full chunk set

V1 explicitly does not benchmark retrieval ranking.
"""

from __future__ import annotations

import abc
import asyncio
import csv
import json
import logging
import math
import os
import random
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.generation.providers.bedrock_provider import BedrockProvider
from src.generation.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)
_QUESTION_LABELS = ("answerable", "partially_answerable", "not_answerable")
_TABLE_MARKER = "[START_TABLE_CONTENT]"


@dataclass(frozen=True)
class SectionEvalSample:
    """A single parsed section plus its mapped chunks."""

    document_id: str
    section_id: str
    section_index: int
    heading_text: str
    heading_level: int
    heading_breadcrumb: List[str]
    source_text: str
    chunk_ids: List[str]
    chunk_texts: List[str]
    chunk_indexes: List[int]
    is_table_heavy: bool


@dataclass(frozen=True)
class QuestionCoverageResult:
    """Judgment for one generated question against one section's chunk set."""

    question_index: int
    question: str
    label: str
    rationale: str


@dataclass(frozen=True)
class SectionEvalResult:
    """Aggregated parsing/chunking result for one parsed section."""

    sample: SectionEvalSample
    skipped: bool = False
    skip_reason: str = ""
    questions: List[str] = field(default_factory=list)
    question_results: List[QuestionCoverageResult] = field(default_factory=list)
    answerable_count: int = 0
    partially_answerable_count: int = 0
    not_answerable_count: int = 0
    # V1 plan called these out explicitly. ``question_coverage`` and
    # ``strict_coverage`` intentionally track the same strict answerable ratio.
    question_coverage: float = 0.0
    strict_coverage: float = 0.0
    partial_coverage: float = 0.0
    supported_coverage: float = 0.0
    section_pass: bool = False


@dataclass(frozen=True)
class DocumentEvalResult:
    """Deterministic parsing metrics plus section coverage for one document."""

    document_id: str
    source: str
    parsed_tree_path: str
    chunks_path: str
    section_count: int
    total_chunks: int
    mapped_chunk_count: int
    orphan_chunk_count: int
    ambiguous_chunk_count: int
    chunk_assignment_coverage: float
    orphan_chunk_rate: float
    duplicate_section_mapping_rate: float
    section_metadata_consistency_rate: float
    section_order_preservation_rate: float
    section_results: List[SectionEvalResult] = field(default_factory=list)
    evaluated_section_count: int = 0
    skipped_section_count: int = 0
    section_pass_rate: float = 0.0
    question_coverage: float = 0.0
    strict_coverage: float = 0.0
    partial_coverage: float = 0.0
    supported_coverage: float = 0.0


@dataclass(frozen=True)
class CalibrationResult:
    """Human calibration report on a sampled subset."""

    sample_size: int
    sampled_section_ids: List[str]
    human_labels_path: Optional[str]
    compared_questions: int
    exact_match_rate: float
    disagreements: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "not_requested"


@dataclass(frozen=True)
class DocxSectionCoverageConfig:
    """Runtime settings for the evaluator."""

    input_path: str
    output_dir: str
    parsed_root: Optional[str] = None
    max_documents: Optional[int] = None
    max_sections_per_document: Optional[int] = None
    questions_per_section: int = 20
    min_section_chars: int = 120
    section_pass_threshold: float = 0.8
    provider: str = "openai"
    model: Optional[str] = None
    calibration_sample_size: int = 0
    human_labels_path: Optional[str] = None
    random_seed: int = 7


@dataclass(frozen=True)
class _FlattenedSection:
    """Internal parsed section record derived from the DOCX tree."""

    section_id: str
    section_index: int
    heading_text: str
    heading_level: int
    heading_breadcrumb: List[str]
    source_text: str


@dataclass(frozen=True)
class _ChunkAssignment:
    """Internal chunk assignment diagnostic."""

    chunk: Dict[str, Any]
    matched_section_index: Optional[int]
    candidate_section_indexes: List[int]
    exact_metadata_match: bool


class BaseSectionCoverageJudge(abc.ABC):
    """Injectable interface for question generation and chunk sufficiency judgment."""

    @abc.abstractmethod
    async def generate_questions(
        self,
        section_text: str,
        *,
        heading_text: str,
        heading_breadcrumb: Sequence[str],
        question_count: int,
    ) -> List[str]:
        raise NotImplementedError

    @abc.abstractmethod
    async def judge_question(
        self,
        question: str,
        *,
        chunk_texts: Sequence[str],
        heading_text: str,
        heading_breadcrumb: Sequence[str],
    ) -> QuestionCoverageResult:
        raise NotImplementedError


class LLMSectionCoverageJudge(BaseSectionCoverageJudge):
    """LLM-backed judge with narrow JSON-only prompts."""

    def __init__(self, provider: str = "openai", model: Optional[str] = None):
        self.provider_name = (provider or "openai").strip().lower()
        self.model = (model or "").strip() or None
        self._provider = self._build_provider(self.provider_name, self.model)

    @staticmethod
    def _build_provider(provider: str, model: Optional[str]):
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            default_model = model or os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
            return OpenAIProvider(api_key=api_key, default_model=default_model)
        if provider in {"bedrock", "aws_bedrock"}:
            default_model = model or os.getenv(
                "AWS_LLM_MODEL",
                os.getenv("BEDROCK_MODEL_ID", "mistral.mistral-small-2402-v1:0"),
            )
            region = (
                os.getenv("AWS_LLM_REGION")
                or os.getenv("BEDROCK_REGION")
                or os.getenv("AWS_REGION")
                or "us-west-2"
            )
            return BedrockProvider(
                access_key=os.getenv("AWS_LLM_ACCESS_KEY_ID"),
                secret_key=os.getenv("AWS_LLM_SECRET_ACCESS_KEY"),
                region=region,
                default_model=default_model,
            )
        raise ValueError(f"Unsupported judge provider: {provider}")

    async def _complete(self, instructions: str, prompt: str) -> str:
        resp = await self._provider.create(
            instructions=instructions,
            input=prompt,
            model=self.model,
            temperature=0.0,
            max_tokens=1800,
        )
        return str(resp or "")

    async def generate_questions(
        self,
        section_text: str,
        *,
        heading_text: str,
        heading_breadcrumb: Sequence[str],
        question_count: int,
    ) -> List[str]:
        instructions = (
            "You generate factual, section-grounded evaluation questions. "
            "Use only the provided section text. Return JSON only."
        )
        prompt = f"""
Generate exactly {question_count} factual questions from the section below.

Rules:
- Use only information explicitly present in the section text.
- Questions must be answerable from the section text alone.
- Avoid opinion, stylistic, or open-ended questions.
- Prefer short, precise questions.
- Do not ask duplicate or near-duplicate questions.
- Return ONLY a JSON object with this schema:
  {{"questions": ["q1", "q2", "..."]}}

Section heading: {heading_text}
Section breadcrumb: {" > ".join(heading_breadcrumb)}

Section text:
{section_text}
""".strip()
        raw = await self._complete(instructions, prompt)
        parsed = _extract_json_payload(raw)
        questions = []
        if isinstance(parsed, dict):
            data = parsed.get("questions")
            if isinstance(data, list):
                questions = [str(q).strip() for q in data if str(q).strip()]
        if not questions:
            raise ValueError(f"Judge returned no valid questions: {raw[:300]}")
        return questions[:question_count]

    async def judge_question(
        self,
        question: str,
        *,
        chunk_texts: Sequence[str],
        heading_text: str,
        heading_breadcrumb: Sequence[str],
    ) -> QuestionCoverageResult:
        instructions = (
            "You evaluate whether a question can be answered strictly from the provided chunks. "
            "Never use outside knowledge. Return JSON only."
        )
        joined_chunks = "\n\n".join(
            f"[Chunk {idx + 1}]\n{chunk}" for idx, chunk in enumerate(chunk_texts)
        )
        prompt = f"""
Judge whether the question can be answered strictly from the provided chunks.

Labels:
- answerable: the chunks contain enough information to answer fully and directly
- partially_answerable: the chunks contain some supporting information but not enough for a full answer
- not_answerable: the chunks do not contain enough information

Rules:
- Use only the provided chunks.
- Do not infer from outside knowledge.
- Return ONLY a JSON object with this schema:
  {{"label": "answerable|partially_answerable|not_answerable", "rationale": "short explanation"}}

Section heading: {heading_text}
Section breadcrumb: {" > ".join(heading_breadcrumb)}

Question:
{question}

Chunks:
{joined_chunks}
""".strip()
        raw = await self._complete(instructions, prompt)
        parsed = _extract_json_payload(raw)
        label = "not_answerable"
        rationale = "Judge response could not be parsed."
        if isinstance(parsed, dict):
            candidate = str(parsed.get("label", "")).strip().lower()
            if candidate in _QUESTION_LABELS:
                label = candidate
            reason = str(parsed.get("rationale", "")).strip()
            if reason:
                rationale = reason
        return QuestionCoverageResult(
            question_index=-1,
            question=question,
            label=label,
            rationale=rationale,
        )


class DocxSectionCoverageRunner:
    """Main reusable evaluation runner."""

    def __init__(
        self,
        config: DocxSectionCoverageConfig,
        judge: BaseSectionCoverageJudge,
    ):
        self.config = config
        self.judge = judge
        self._rng = random.Random(config.random_seed)

    async def run(self) -> Tuple[List[DocumentEvalResult], CalibrationResult]:
        doc_inputs = self._discover_doc_inputs()
        if self.config.max_documents is not None:
            doc_inputs = doc_inputs[: self.config.max_documents]
        results: List[DocumentEvalResult] = []
        for doc_id, parsed_path, chunks_path in doc_inputs:
            results.append(await self.evaluate_document(doc_id, parsed_path, chunks_path))

        calibration = self._build_calibration_report(results)
        self._export_reports(results, calibration)
        return results, calibration

    async def evaluate_document(
        self,
        doc_id: str,
        parsed_tree_path: Path,
        chunks_path: Path,
    ) -> DocumentEvalResult:
        tree = _load_json(parsed_tree_path)
        chunks_data = _load_json(chunks_path)
        chunks = list(chunks_data.get("chunks") or [])
        flattened = flatten_docx_sections(tree, doc_id)
        assignments, section_chunks = map_chunks_to_sections(flattened, chunks)
        parsing = compute_parsing_metrics(flattened, assignments)

        section_results: List[SectionEvalResult] = []
        sections_to_eval = flattened
        if self.config.max_sections_per_document is not None:
            sections_to_eval = sections_to_eval[: self.config.max_sections_per_document]

        for section in sections_to_eval:
            section_results.append(
                await self.evaluate_section(
                    section,
                    section_chunks.get(section.section_index, []),
                )
            )

        evaluated = [r for r in section_results if not r.skipped]
        skipped = [r for r in section_results if r.skipped]
        section_pass_rate = _safe_div(sum(1 for r in evaluated if r.section_pass), len(evaluated))
        macro_question = _mean([r.question_coverage for r in evaluated])
        macro_strict = _mean([r.strict_coverage for r in evaluated])
        macro_partial = _mean([r.partial_coverage for r in evaluated])
        macro_supported = _mean([r.supported_coverage for r in evaluated])

        return DocumentEvalResult(
            document_id=doc_id,
            source=str(chunks_data.get("metadata", {}).get("source", "")),
            parsed_tree_path=str(parsed_tree_path),
            chunks_path=str(chunks_path),
            section_count=len(flattened),
            total_chunks=len(chunks),
            mapped_chunk_count=parsing["mapped_chunk_count"],
            orphan_chunk_count=parsing["orphan_chunk_count"],
            ambiguous_chunk_count=parsing["ambiguous_chunk_count"],
            chunk_assignment_coverage=parsing["chunk_assignment_coverage"],
            orphan_chunk_rate=parsing["orphan_chunk_rate"],
            duplicate_section_mapping_rate=parsing["duplicate_section_mapping_rate"],
            section_metadata_consistency_rate=parsing["section_metadata_consistency_rate"],
            section_order_preservation_rate=parsing["section_order_preservation_rate"],
            section_results=section_results,
            evaluated_section_count=len(evaluated),
            skipped_section_count=len(skipped),
            section_pass_rate=section_pass_rate,
            question_coverage=macro_question,
            strict_coverage=macro_strict,
            partial_coverage=macro_partial,
            supported_coverage=macro_supported,
        )

    async def evaluate_section(
        self,
        section: _FlattenedSection,
        chunks: Sequence[Dict[str, Any]],
    ) -> SectionEvalResult:
        chunk_texts = [str(chunk.get("text", "") or "").strip() for chunk in chunks if str(chunk.get("text", "") or "").strip()]
        sample = SectionEvalSample(
            document_id=_doc_id_from_section_id(section.section_id),
            section_id=section.section_id,
            section_index=section.section_index,
            heading_text=section.heading_text,
            heading_level=section.heading_level,
            heading_breadcrumb=list(section.heading_breadcrumb),
            source_text=section.source_text,
            chunk_ids=[str(chunk.get("id", "")) for chunk in chunks],
            chunk_texts=chunk_texts,
            chunk_indexes=[int(chunk.get("chunk_index", -1)) for chunk in chunks],
            is_table_heavy=_section_is_table_heavy(section.source_text, chunks),
        )

        if len(section.source_text.strip()) < self.config.min_section_chars:
            return SectionEvalResult(
                sample=sample,
                skipped=True,
                skip_reason=f"section shorter than min_section_chars={self.config.min_section_chars}",
            )
        if not chunk_texts:
            return SectionEvalResult(
                sample=sample,
                skipped=True,
                skip_reason="no mapped chunks for section",
            )

        questions = await self.judge.generate_questions(
            section.source_text,
            heading_text=section.heading_text,
            heading_breadcrumb=section.heading_breadcrumb,
            question_count=self.config.questions_per_section,
        )

        question_results: List[QuestionCoverageResult] = []
        for idx, question in enumerate(questions):
            judgment = await self.judge.judge_question(
                question,
                chunk_texts=chunk_texts,
                heading_text=section.heading_text,
                heading_breadcrumb=section.heading_breadcrumb,
            )
            question_results.append(
                QuestionCoverageResult(
                    question_index=idx,
                    question=question,
                    label=judgment.label,
                    rationale=judgment.rationale,
                )
            )

        answerable_count = sum(1 for item in question_results if item.label == "answerable")
        partially_count = sum(1 for item in question_results if item.label == "partially_answerable")
        not_answerable_count = sum(1 for item in question_results if item.label == "not_answerable")
        strict_ratio = _safe_div(answerable_count, len(question_results))
        partial_ratio = _safe_div(partially_count, len(question_results))
        supported_ratio = _safe_div(answerable_count + partially_count, len(question_results))

        return SectionEvalResult(
            sample=sample,
            questions=questions,
            question_results=question_results,
            answerable_count=answerable_count,
            partially_answerable_count=partially_count,
            not_answerable_count=not_answerable_count,
            question_coverage=strict_ratio,
            strict_coverage=strict_ratio,
            partial_coverage=partial_ratio,
            supported_coverage=supported_ratio,
            section_pass=strict_ratio >= self.config.section_pass_threshold,
        )

    def _discover_doc_inputs(self) -> List[Tuple[str, Path, Path]]:
        input_path = Path(self.config.input_path).resolve()
        parsed_root = Path(self.config.parsed_root).resolve() if self.config.parsed_root else None
        docs: List[Tuple[str, Path, Path]] = []

        if input_path.is_file() and input_path.name == "docx_chunks.json":
            doc_dir = input_path.parent
            doc_id = doc_dir.name
            parsed_path = self._resolve_parsed_path(doc_id, doc_dir, parsed_root)
            docs.append((doc_id, parsed_path, input_path))
            return docs

        if input_path.is_dir() and (input_path / "docx_chunks.json").exists():
            doc_id = input_path.name
            parsed_path = self._resolve_parsed_path(doc_id, input_path, parsed_root)
            docs.append((doc_id, parsed_path, input_path / "docx_chunks.json"))
            return docs

        candidates = sorted(input_path.rglob("docx_chunks.json")) if input_path.is_dir() else []
        for chunks_path in candidates:
            doc_dir = chunks_path.parent
            doc_id = doc_dir.name
            try:
                parsed_path = self._resolve_parsed_path(doc_id, doc_dir, parsed_root)
            except FileNotFoundError:
                logger.warning("Skipping %s because parsed DOCX JSON could not be found", doc_id)
                continue
            docs.append((doc_id, parsed_path, chunks_path))
        return docs

    def _resolve_parsed_path(
        self,
        doc_id: str,
        doc_dir: Path,
        parsed_root: Optional[Path],
    ) -> Path:
        candidates: List[Path] = []
        if parsed_root is not None:
            candidates.append(parsed_root / f"{doc_id}.json")
        if doc_dir.parent.name == "stage4_rag_ready":
            stage4_root = doc_dir.parent
            stage1_root = stage4_root.parent.parent / "stage1_normalized" / "docx_parsed"
            candidates.append(stage1_root / f"{doc_id}.json")
        candidates.append(doc_dir / f"{doc_id}.json")
        for path in candidates:
            if path.exists():
                return path
        raise FileNotFoundError(f"Parsed DOCX JSON not found for {doc_id}: {candidates}")

    def _build_calibration_report(self, results: Sequence[DocumentEvalResult]) -> CalibrationResult:
        sample_ids = _sample_calibration_section_ids(results, self.config.calibration_sample_size, self._rng)
        if self.config.calibration_sample_size <= 0:
            return CalibrationResult(
                sample_size=0,
                sampled_section_ids=[],
                human_labels_path=self.config.human_labels_path,
                compared_questions=0,
                exact_match_rate=0.0,
                status="not_requested",
            )

        human_path = Path(self.config.human_labels_path).resolve() if self.config.human_labels_path else None
        if human_path is None or not human_path.exists():
            return CalibrationResult(
                sample_size=len(sample_ids),
                sampled_section_ids=sample_ids,
                human_labels_path=str(human_path) if human_path else None,
                compared_questions=0,
                exact_match_rate=0.0,
                status="awaiting_human_labels",
            )

        llm_map = _collect_llm_labels(results, set(sample_ids))
        human_map = _load_human_labels(human_path)
        compared = 0
        matches = 0
        disagreements: List[Dict[str, Any]] = []
        for key, llm_label in llm_map.items():
            human_label = human_map.get(key)
            if human_label is None:
                continue
            compared += 1
            if human_label == llm_label:
                matches += 1
            else:
                section_id, question_index = key
                disagreements.append(
                    {
                        "section_id": section_id,
                        "question_index": question_index,
                        "llm_label": llm_label,
                        "human_label": human_label,
                    }
                )
        status = "completed" if compared > 0 else "awaiting_matching_labels"
        return CalibrationResult(
            sample_size=len(sample_ids),
            sampled_section_ids=sample_ids,
            human_labels_path=str(human_path),
            compared_questions=compared,
            exact_match_rate=_safe_div(matches, compared),
            disagreements=disagreements,
            status=status,
        )

    def _export_reports(
        self,
        results: Sequence[DocumentEvalResult],
        calibration: CalibrationResult,
    ) -> None:
        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "config": asdict(self.config),
            "documents": [asdict(result) for result in results],
            "summary": build_run_summary(results),
            "calibration": asdict(calibration),
        }
        (out_dir / "docx_section_eval_report.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out_dir / "docx_section_eval_summary.json").write_text(
            json.dumps(build_run_summary(results), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _write_summary_csv(out_dir / "docx_section_eval_summary.csv", results)
        if calibration.sample_size > 0:
            sample_payload = build_calibration_sample_payload(results, calibration.sampled_section_ids)
            (out_dir / "docx_section_eval_calibration_sample.json").write_text(
                json.dumps(sample_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        (out_dir / "docx_section_eval_calibration_report.json").write_text(
            json.dumps(asdict(calibration), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def flatten_docx_sections(tree: Sequence[Dict[str, Any]], doc_id: str) -> List[_FlattenedSection]:
    """Depth-first flattening with stable section ids based on traversal order."""

    sections: List[_FlattenedSection] = []

    def _walk(nodes: Sequence[Dict[str, Any]], breadcrumb: Sequence[str]) -> None:
        for node in nodes:
            heading = str(node.get("heading_text", "") or "").strip()
            level_raw = node.get("heading_level", 0)
            try:
                level = int(level_raw)
            except Exception:
                level = 0
            content = str(node.get("content", "") or "")
            children = list(node.get("children") or [])
            current_breadcrumb = list(breadcrumb) + ([heading] if heading else [])
            if content.strip():
                idx = len(sections)
                sections.append(
                    _FlattenedSection(
                        section_id=f"{doc_id}:section:{idx:04d}",
                        section_index=idx,
                        heading_text=heading,
                        heading_level=level,
                        heading_breadcrumb=current_breadcrumb,
                        source_text=content,
                    )
                )
            if children:
                _walk(children, current_breadcrumb)

    _walk(tree, [])
    return sections


def map_chunks_to_sections(
    sections: Sequence[_FlattenedSection],
    chunks: Sequence[Dict[str, Any]],
) -> Tuple[List[_ChunkAssignment], Dict[int, List[Dict[str, Any]]]]:
    """Map chunks to parsed sections using exact key first, then safe fallbacks."""

    by_exact: Dict[Tuple[Tuple[str, ...], str, int], List[int]] = {}
    by_breadcrumb: Dict[Tuple[str, ...], List[int]] = {}
    by_heading_level: Dict[Tuple[str, int], List[int]] = {}
    for section in sections:
        key = (tuple(section.heading_breadcrumb), section.heading_text, section.heading_level)
        by_exact.setdefault(key, []).append(section.section_index)
        by_breadcrumb.setdefault(tuple(section.heading_breadcrumb), []).append(section.section_index)
        by_heading_level.setdefault((section.heading_text, section.heading_level), []).append(section.section_index)

    assignments: List[_ChunkAssignment] = []
    section_chunks: Dict[int, List[Dict[str, Any]]] = {section.section_index: [] for section in sections}
    for chunk in chunks:
        meta = dict(chunk.get("metadata") or {})
        breadcrumb = tuple(meta.get("heading_breadcrumb") or [])
        heading_text = str(meta.get("heading_text", "") or "").strip()
        heading_level = _coerce_int(meta.get("heading_level"), default=0)
        exact_key = (breadcrumb, heading_text, heading_level)

        candidates = list(by_exact.get(exact_key, []))
        exact = True
        if not candidates and breadcrumb:
            candidates = list(by_breadcrumb.get(breadcrumb, []))
            exact = False
        if not candidates and heading_text:
            candidates = list(by_heading_level.get((heading_text, heading_level), []))
            exact = False

        matched_index: Optional[int] = candidates[0] if len(candidates) == 1 else None
        assignment = _ChunkAssignment(
            chunk=dict(chunk),
            matched_section_index=matched_index,
            candidate_section_indexes=candidates,
            exact_metadata_match=exact and matched_index is not None,
        )
        assignments.append(assignment)
        if matched_index is not None:
            section_chunks.setdefault(matched_index, []).append(dict(chunk))

    for chunk_list in section_chunks.values():
        chunk_list.sort(key=lambda item: _coerce_int(item.get("chunk_index"), default=-1))
    return assignments, section_chunks


def compute_parsing_metrics(
    sections: Sequence[_FlattenedSection],
    assignments: Sequence[_ChunkAssignment],
) -> Dict[str, Any]:
    """Deterministic structural metrics before any LLM judging."""

    total_chunks = len(assignments)
    mapped = [item for item in assignments if item.matched_section_index is not None]
    orphan = [item for item in assignments if item.matched_section_index is None and not item.candidate_section_indexes]
    ambiguous = [item for item in assignments if item.matched_section_index is None and len(item.candidate_section_indexes) > 1]
    consistency = _safe_div(sum(1 for item in mapped if item.exact_metadata_match), len(mapped))

    mapped_sorted = sorted(
        mapped,
        key=lambda item: _coerce_int(item.chunk.get("chunk_index"), default=-1),
    )
    order_checks = 0
    order_passes = 0
    for prev, cur in zip(mapped_sorted, mapped_sorted[1:]):
        if prev.matched_section_index is None or cur.matched_section_index is None:
            continue
        order_checks += 1
        if cur.matched_section_index >= prev.matched_section_index:
            order_passes += 1

    return {
        "section_count": len(sections),
        "total_chunks": total_chunks,
        "mapped_chunk_count": len(mapped),
        "orphan_chunk_count": len(orphan),
        "ambiguous_chunk_count": len(ambiguous),
        "chunk_assignment_coverage": _safe_div(len(mapped), total_chunks),
        "orphan_chunk_rate": _safe_div(len(orphan), total_chunks),
        "duplicate_section_mapping_rate": _safe_div(len(ambiguous), total_chunks),
        "section_metadata_consistency_rate": consistency,
        "section_order_preservation_rate": _safe_div(order_passes, order_checks) if order_checks else 1.0,
    }


def build_run_summary(results: Sequence[DocumentEvalResult]) -> Dict[str, Any]:
    """Aggregate summary that keeps actionable diagnostics close to the top."""

    evaluated_sections = sum(result.evaluated_section_count for result in results)
    skipped_sections = sum(result.skipped_section_count for result in results)

    all_section_results: List[SectionEvalResult] = []
    for result in results:
        all_section_results.extend(result.section_results)

    evaluated = [item for item in all_section_results if not item.skipped]
    answerable_total = sum(item.answerable_count for item in evaluated)
    partially_total = sum(item.partially_answerable_count for item in evaluated)
    not_answerable_total = sum(item.not_answerable_count for item in evaluated)
    total_questions = answerable_total + partially_total + not_answerable_total

    problematic_sections = sorted(
        (
            item for item in evaluated
            if item.not_answerable_count > 0 or item.partially_answerable_count > 0
        ),
        key=lambda item: (
            item.strict_coverage,
            -item.not_answerable_count,
            -item.partially_answerable_count,
        ),
    )

    worst_sections: List[Dict[str, Any]] = []
    for item in problematic_sections[:5]:
        problem_questions = [
            {
                "question_index": q.question_index,
                "label": q.label,
                "question": q.question,
                "rationale": q.rationale,
            }
            for q in item.question_results
            if q.label != "answerable"
        ]
        worst_sections.append(
            {
                "document_id": item.sample.document_id,
                "section_id": item.sample.section_id,
                "heading_text": item.sample.heading_text,
                "heading_breadcrumb": item.sample.heading_breadcrumb,
                "strict_coverage": item.strict_coverage,
                "partial_coverage": item.partial_coverage,
                "supported_coverage": item.supported_coverage,
                "answerable_count": item.answerable_count,
                "partially_answerable_count": item.partially_answerable_count,
                "not_answerable_count": item.not_answerable_count,
                "problem_questions": problem_questions,
            }
        )

    document_summaries = []
    for result in results:
        doc_problem_sections = [
            item for item in result.section_results
            if (not item.skipped) and (item.not_answerable_count > 0 or item.partially_answerable_count > 0)
        ]
        document_summaries.append(
            {
                "document_id": result.document_id,
                "section_count": result.section_count,
                "evaluated_section_count": result.evaluated_section_count,
                "skipped_section_count": result.skipped_section_count,
                "chunk_assignment_coverage": result.chunk_assignment_coverage,
                "orphan_chunk_rate": result.orphan_chunk_rate,
                "duplicate_section_mapping_rate": result.duplicate_section_mapping_rate,
                "section_metadata_consistency_rate": result.section_metadata_consistency_rate,
                "section_order_preservation_rate": result.section_order_preservation_rate,
                "section_pass_rate": result.section_pass_rate,
                "strict_coverage": result.strict_coverage,
                "partial_coverage": result.partial_coverage,
                "supported_coverage": result.supported_coverage,
                "problem_section_count": len(doc_problem_sections),
            }
        )

    return {
        "document_count": len(results),
        "evaluated_section_count": evaluated_sections,
        "skipped_section_count": skipped_sections,
        "avg_chunk_assignment_coverage": _mean([r.chunk_assignment_coverage for r in results]),
        "avg_orphan_chunk_rate": _mean([r.orphan_chunk_rate for r in results]),
        "avg_duplicate_section_mapping_rate": _mean([r.duplicate_section_mapping_rate for r in results]),
        "avg_section_metadata_consistency_rate": _mean([r.section_metadata_consistency_rate for r in results]),
        "avg_section_order_preservation_rate": _mean([r.section_order_preservation_rate for r in results]),
        "avg_section_pass_rate": _mean([r.section_pass_rate for r in results]),
        "avg_question_coverage": _mean([r.question_coverage for r in results]),
        "avg_strict_coverage": _mean([r.strict_coverage for r in results]),
        "avg_partial_coverage": _mean([r.partial_coverage for r in results]),
        "avg_supported_coverage": _mean([r.supported_coverage for r in results]),
        "question_label_counts": {
            "answerable": answerable_total,
            "partially_answerable": partially_total,
            "not_answerable": not_answerable_total,
            "total": total_questions,
        },
        "quality_readout": {
            "parsing": (
                "This summary only measures internal parser/chunker consistency "
                "against the parsed section tree. It does not prove the parser is "
                "correct against the original document."
            ),
            "chunking": (
                "Focus on worst_sections below. Those are the concrete places where "
                "the evaluator found partial or missing support after chunking."
            ),
        },
        "documents": document_summaries,
        "worst_sections": worst_sections,
    }


def build_calibration_sample_payload(
    results: Sequence[DocumentEvalResult],
    sampled_section_ids: Sequence[str],
) -> Dict[str, Any]:
    """Emit sampled questions/judgments for human review."""

    keep = set(sampled_section_ids)
    samples: List[Dict[str, Any]] = []
    for document in results:
        for section in document.section_results:
            if section.sample.section_id not in keep:
                continue
            samples.append(
                {
                    "document_id": document.document_id,
                    "section_id": section.sample.section_id,
                    "heading_text": section.sample.heading_text,
                    "heading_breadcrumb": section.sample.heading_breadcrumb,
                    "is_table_heavy": section.sample.is_table_heavy,
                    "questions": [asdict(item) for item in section.question_results],
                }
            )
    return {"sections": samples}


def run_docx_section_coverage(
    config: DocxSectionCoverageConfig,
    judge: Optional[BaseSectionCoverageJudge] = None,
) -> Tuple[List[DocumentEvalResult], CalibrationResult]:
    """Synchronous convenience wrapper used by the CLI and tests."""

    runner = DocxSectionCoverageRunner(
        config=config,
        judge=judge or LLMSectionCoverageJudge(config.provider, config.model),
    )
    return asyncio.run(runner.run())


def _extract_json_payload(raw: str) -> Any:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_summary_csv(path: Path, results: Sequence[DocumentEvalResult]) -> None:
    rows = [
        {
            "document_id": result.document_id,
            "section_count": result.section_count,
            "evaluated_section_count": result.evaluated_section_count,
            "skipped_section_count": result.skipped_section_count,
            "chunk_assignment_coverage": result.chunk_assignment_coverage,
            "orphan_chunk_rate": result.orphan_chunk_rate,
            "duplicate_section_mapping_rate": result.duplicate_section_mapping_rate,
            "section_metadata_consistency_rate": result.section_metadata_consistency_rate,
            "section_order_preservation_rate": result.section_order_preservation_rate,
            "section_pass_rate": result.section_pass_rate,
            "question_coverage": result.question_coverage,
            "strict_coverage": result.strict_coverage,
            "partial_coverage": result.partial_coverage,
            "supported_coverage": result.supported_coverage,
        }
        for result in results
    ]
    fieldnames = list(rows[0].keys()) if rows else [
        "document_id",
        "section_count",
        "evaluated_section_count",
        "skipped_section_count",
        "chunk_assignment_coverage",
        "orphan_chunk_rate",
        "duplicate_section_mapping_rate",
        "section_metadata_consistency_rate",
        "section_order_preservation_rate",
        "section_pass_rate",
        "question_coverage",
        "strict_coverage",
        "partial_coverage",
        "supported_coverage",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _sample_calibration_section_ids(
    results: Sequence[DocumentEvalResult],
    sample_size: int,
    rng: random.Random,
) -> List[str]:
    if sample_size <= 0:
        return []
    short_sections: List[str] = []
    medium_sections: List[str] = []
    table_sections: List[str] = []
    for document in results:
        for section in document.section_results:
            if section.skipped:
                continue
            if section.sample.is_table_heavy:
                table_sections.append(section.sample.section_id)
            elif len(section.sample.source_text) < 600:
                short_sections.append(section.sample.section_id)
            else:
                medium_sections.append(section.sample.section_id)

    buckets = [bucket for bucket in (short_sections, medium_sections, table_sections) if bucket]
    if not buckets:
        return []
    allocation = max(1, math.floor(sample_size / len(buckets)))
    sampled: List[str] = []
    for bucket in buckets:
        count = min(len(bucket), allocation)
        sampled.extend(rng.sample(bucket, count))
    if len(sampled) < sample_size:
        remainder_pool = [
            section_id
            for bucket in buckets
            for section_id in bucket
            if section_id not in sampled
        ]
        if remainder_pool:
            sampled.extend(rng.sample(remainder_pool, min(sample_size - len(sampled), len(remainder_pool))))
    return sampled[:sample_size]


def _collect_llm_labels(
    results: Sequence[DocumentEvalResult],
    sampled_section_ids: set[str],
) -> Dict[Tuple[str, int], str]:
    out: Dict[Tuple[str, int], str] = {}
    for document in results:
        for section in document.section_results:
            if section.sample.section_id not in sampled_section_ids:
                continue
            for question in section.question_results:
                out[(section.sample.section_id, question.question_index)] = question.label
    return out


def _load_human_labels(path: Path) -> Dict[Tuple[str, int], str]:
    payload = _load_json(path)
    records = payload.get("labels") if isinstance(payload, dict) else payload
    out: Dict[Tuple[str, int], str] = {}
    for item in records or []:
        section_id = str(item.get("section_id", "")).strip()
        question_index = _coerce_int(item.get("question_index"), default=-1)
        label = str(item.get("human_label", item.get("label", ""))).strip().lower()
        if not section_id or question_index < 0 or label not in _QUESTION_LABELS:
            continue
        out[(section_id, question_index)] = label
    return out


def _safe_div(numerator: int | float, denominator: int | float) -> float:
    try:
        if not denominator:
            return 0.0
        return float(numerator) / float(denominator)
    except Exception:
        return 0.0


def _mean(values: Iterable[float]) -> float:
    vals = list(values)
    if not vals:
        return 0.0
    return float(sum(vals) / len(vals))


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _section_is_table_heavy(source_text: str, chunks: Sequence[Dict[str, Any]]) -> bool:
    if _TABLE_MARKER in (source_text or ""):
        return True
    for chunk in chunks:
        if bool(chunk.get("is_table")):
            return True
        meta = dict(chunk.get("metadata") or {})
        if str(meta.get("chunk_type", "")).strip().lower() == "table":
            return True
    return False


def _doc_id_from_section_id(section_id: str) -> str:
    return section_id.split(":section:", 1)[0]
