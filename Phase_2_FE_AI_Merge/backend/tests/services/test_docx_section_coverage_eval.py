from __future__ import annotations

import json
from pathlib import Path

from src.evaluation.docx_section_coverage import (
    BaseSectionCoverageJudge,
    DocxSectionCoverageConfig,
    QuestionCoverageResult,
    compute_parsing_metrics,
    flatten_docx_sections,
    map_chunks_to_sections,
    run_docx_section_coverage,
)


class _FakeJudge(BaseSectionCoverageJudge):
    async def generate_questions(
        self,
        section_text: str,
        *,
        heading_text: str,
        heading_breadcrumb,
        question_count: int,
    ):
        return [f"{heading_text or 'section'} question {idx}" for idx in range(question_count)]

    async def judge_question(
        self,
        question: str,
        *,
        chunk_texts,
        heading_text: str,
        heading_breadcrumb,
    ) -> QuestionCoverageResult:
        match = question.rsplit(" ", 1)[-1]
        idx = int(match)
        labels = ("answerable", "partially_answerable", "not_answerable")
        return QuestionCoverageResult(
            question_index=-1,
            question=question,
            label=labels[idx % len(labels)],
            rationale=f"deterministic label for {heading_text}",
        )


def test_flatten_docx_sections_stable_ids_and_breadcrumbs() -> None:
    tree = [
        {
            "heading_text": "1 Parent",
            "heading_level": 1,
            "content": "Parent content " * 10,
            "children": [
                {
                    "heading_text": "1.1 Child",
                    "heading_level": 2,
                    "content": "Child content " * 12,
                    "children": [],
                }
            ],
        },
        {
            "heading_text": "2 Next",
            "heading_level": 1,
            "content": "Next content " * 10,
            "children": [],
        },
    ]

    first = flatten_docx_sections(tree, "demo")
    second = flatten_docx_sections(tree, "demo")

    assert [item.section_id for item in first] == [item.section_id for item in second]
    assert [item.section_id for item in first] == [
        "demo:section:0000",
        "demo:section:0001",
        "demo:section:0002",
    ]
    assert first[0].heading_breadcrumb == ["1 Parent"]
    assert first[1].heading_breadcrumb == ["1 Parent", "1.1 Child"]
    assert first[2].heading_breadcrumb == ["2 Next"]


def test_chunk_mapping_and_parsing_metrics_cover_fallbacks_and_orphans() -> None:
    tree = [
        {
            "heading_text": "Parent A",
            "heading_level": 1,
            "content": "",
            "children": [
                {
                    "heading_text": "Repeated",
                    "heading_level": 2,
                    "content": "A" * 160,
                    "children": [],
                }
            ],
        },
        {
            "heading_text": "Parent B",
            "heading_level": 1,
            "content": "",
            "children": [
                {
                    "heading_text": "Repeated",
                    "heading_level": 2,
                    "content": "B" * 160,
                    "children": [],
                }
            ],
        },
    ]
    sections = flatten_docx_sections(tree, "demo")
    chunks = [
        {
            "id": "c0",
            "chunk_index": 0,
            "text": "exact",
            "metadata": {
                "heading_breadcrumb": ["Parent A", "Repeated"],
                "heading_text": "Repeated",
                "heading_level": 2,
            },
        },
        {
            "id": "c1",
            "chunk_index": 1,
            "text": "fallback by breadcrumb",
            "metadata": {
                "heading_breadcrumb": ["Parent A", "Repeated"],
                "heading_text": "Different",
                "heading_level": 9,
            },
        },
        {
            "id": "c2",
            "chunk_index": 2,
            "text": "ambiguous by heading",
            "metadata": {
                "heading_breadcrumb": [],
                "heading_text": "Repeated",
                "heading_level": 2,
            },
        },
        {
            "id": "c3",
            "chunk_index": 3,
            "text": "orphan",
            "metadata": {
                "heading_breadcrumb": [],
                "heading_text": "Missing",
                "heading_level": 1,
            },
        },
    ]

    assignments, _ = map_chunks_to_sections(sections, chunks)
    metrics = compute_parsing_metrics(sections, assignments)

    assert metrics["mapped_chunk_count"] == 2
    assert metrics["orphan_chunk_count"] == 1
    assert metrics["ambiguous_chunk_count"] == 1
    assert metrics["chunk_assignment_coverage"] == 0.5
    assert metrics["orphan_chunk_rate"] == 0.25
    assert metrics["duplicate_section_mapping_rate"] == 0.25
    assert metrics["section_metadata_consistency_rate"] == 0.5


def test_section_pass_threshold_and_skip_behavior(tmp_path: Path) -> None:
    tree = [
        {
            "heading_text": "Enough",
            "heading_level": 1,
            "content": "Long enough content. " * 20,
            "children": [],
        },
        {
            "heading_text": "Short",
            "heading_level": 1,
            "content": "tiny",
            "children": [],
        },
    ]
    parsed = tmp_path / "parsed.json"
    parsed = tmp_path / "doc.json"
    parsed.write_text(json.dumps(tree), encoding="utf-8")

    chunk_payload = {
        "metadata": {"source": "demo.docx"},
        "chunks": [
            {
                "id": "chunk0",
                "chunk_index": 0,
                "text": "Long enough content. " * 5,
                "metadata": {
                    "heading_breadcrumb": ["Enough"],
                    "heading_text": "Enough",
                    "heading_level": 1,
                },
            },
            {
                "id": "chunk1",
                "chunk_index": 1,
                "text": "tiny",
                "metadata": {
                    "heading_breadcrumb": ["Short"],
                    "heading_text": "Short",
                    "heading_level": 1,
                },
            },
        ],
    }
    doc_dir = tmp_path / "doc"
    doc_dir.mkdir()
    chunks_path = doc_dir / "docx_chunks.json"
    chunks_path.write_text(json.dumps(chunk_payload), encoding="utf-8")

    config = DocxSectionCoverageConfig(
        input_path=str(doc_dir),
        parsed_root=str(tmp_path),
        output_dir=str(tmp_path / "out"),
        questions_per_section=4,
        section_pass_threshold=0.6,
        min_section_chars=20,
    )
    results, _ = run_docx_section_coverage(config, judge=_FakeJudge())

    result = results[0]
    assert result.evaluated_section_count == 1
    assert result.skipped_section_count == 1
    evaluated = [item for item in result.section_results if not item.skipped][0]
    skipped = [item for item in result.section_results if item.skipped][0]
    assert evaluated.answerable_count == 2
    assert evaluated.partially_answerable_count == 1
    assert evaluated.not_answerable_count == 1
    assert evaluated.strict_coverage == 0.5
    assert evaluated.partial_coverage == 0.25
    assert evaluated.section_pass is False
    assert "min_section_chars" in skipped.skip_reason


def test_smoke_run_on_sample_docx_artifacts_writes_reports(tmp_path: Path) -> None:
    backend_root = Path(__file__).resolve().parents[2]
    stage4_doc_dir = backend_root / "output" / "processing" / "stage4_rag_ready" / "SRS_CNPM"
    parsed_root = backend_root / "output" / "processing" / "stage1_normalized" / "docx_parsed"

    config = DocxSectionCoverageConfig(
        input_path=str(stage4_doc_dir),
        parsed_root=str(parsed_root),
        output_dir=str(tmp_path / "reports"),
        max_documents=1,
        max_sections_per_document=3,
        questions_per_section=3,
        calibration_sample_size=2,
        min_section_chars=80,
    )

    results, calibration = run_docx_section_coverage(config, judge=_FakeJudge())

    assert len(results) == 1
    document = results[0]
    assert document.document_id == "SRS_CNPM"
    assert document.section_count >= 3
    assert document.evaluated_section_count >= 1
    first_evaluated = next(item for item in document.section_results if not item.skipped)
    assert len(first_evaluated.questions) == 3
    assert len(first_evaluated.question_results) == 3

    report_path = Path(config.output_dir) / "docx_section_eval_report.json"
    summary_path = Path(config.output_dir) / "docx_section_eval_summary.json"
    csv_path = Path(config.output_dir) / "docx_section_eval_summary.csv"
    calibration_sample_path = Path(config.output_dir) / "docx_section_eval_calibration_sample.json"
    calibration_report_path = Path(config.output_dir) / "docx_section_eval_calibration_report.json"

    assert report_path.exists()
    assert summary_path.exists()
    assert csv_path.exists()
    assert calibration_sample_path.exists()
    assert calibration_report_path.exists()

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert set(payload.keys()) == {"config", "documents", "summary", "calibration"}
    assert payload["documents"][0]["document_id"] == "SRS_CNPM"
    assert payload["documents"][0]["section_results"][0]["sample"]["section_id"].startswith("SRS_CNPM:section:")
    assert payload["summary"]["document_count"] == 1
    assert payload["calibration"]["sample_size"] == calibration.sample_size
