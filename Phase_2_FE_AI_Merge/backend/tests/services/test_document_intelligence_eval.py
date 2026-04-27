from __future__ import annotations

import json
from pathlib import Path

from src.evaluation.document_intelligence import (
    BaseDocumentIntelligenceJudge,
    BaseQAExecutor,
    DocumentIntelligenceEvalConfig,
    QAEvalItem,
    SectionSample,
    build_local_corpus_index,
    discover_document_samples,
    run_document_intelligence_eval,
)


class _FakeJudge(BaseDocumentIntelligenceJudge):
    def __init__(self) -> None:
        self.qa_judge_calls = []
        self.qa_gen_sections = []

    async def generate_qa_pairs(self, section: SectionSample, question_count: int):
        self.qa_gen_sections.append(section.section_id)
        return [
            {
                "question": f"What is stated in {section.heading_text} #{idx}?",
                "reference_answer": f"Reference answer {idx}",
            }
            for idx in range(question_count)
        ]

    async def judge_qa(
        self,
        *,
        question: str,
        reference_answer: str,
        retrieved_context,
        generated_answer: str,
    ):
        self.qa_judge_calls.append(
            {
                "question": question,
                "reference_answer": reference_answer,
                "retrieved_context": retrieved_context,
                "generated_answer": generated_answer,
            }
        )
        return {
            "correctness": "correct",
            "faithfulness": "faithful",
            "answer_support": "fully_supported",
            "judge_rationale": "answer is supported",
        }


class _FixedQAExecutor(BaseQAExecutor):
    def __init__(self, *, doc_id: str, section_key: str, chunk_id: str, generated_answer: str = "Generated answer") -> None:
        self.doc_id = doc_id
        self.section_key = section_key
        self.chunk_id = chunk_id
        self.generated_answer = generated_answer

    async def run(self, question: str):
        return (
            [
                {
                    "id": self.chunk_id,
                    "source": "demo",
                    "score": 1.0,
                    "retrieval_type": "local_bm25",
                    "text": "Retrieved context supports the generated answer.",
                    "metadata": {
                        "doc_id": self.doc_id,
                        "mapped_section_key": self.section_key,
                    },
                }
            ],
            f"{self.generated_answer} for: {question}",
        )


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_discover_samples_extracts_sections() -> None:
    backend_root = _backend_root()
    config = DocumentIntelligenceEvalConfig(
        input_path=str(backend_root / "output" / "processing" / "stage4_rag_ready" / "SRS_CNPM"),
        parsed_root=str(backend_root / "output" / "processing" / "stage1_normalized"),
        output_dir=str(backend_root / "output" / "evaluation" / "unused"),
        max_documents=1,
    )

    samples = discover_document_samples(config)

    assert len(samples) == 1
    sample = samples[0]
    assert sample.doc_id == "SRS_CNPM"
    assert sample.sections


def test_local_corpus_loader_only_uses_docs_under_input_folder() -> None:
    backend_root = _backend_root()
    config = DocumentIntelligenceEvalConfig(
        input_path=str(backend_root / "output" / "processing" / "stage4_rag_ready" / "SRS_CNPM"),
        parsed_root=str(backend_root / "output" / "processing" / "stage1_normalized"),
        output_dir=str(backend_root / "output" / "evaluation" / "unused"),
    )
    samples = discover_document_samples(config)
    corpus = build_local_corpus_index(config, samples)

    assert corpus.doc_ids == ["SRS_CNPM"]
    assert all(chunk.doc_id == "SRS_CNPM" for chunk in corpus.chunks)


def test_chunk_mapping_builds_target_chunk_ids_from_heading_metadata() -> None:
    backend_root = _backend_root()
    config = DocumentIntelligenceEvalConfig(
        input_path=str(backend_root / "output" / "processing" / "stage4_rag_ready" / "SRS_CNPM"),
        parsed_root=str(backend_root / "output" / "processing" / "stage1_normalized"),
        output_dir=str(backend_root / "output" / "evaluation" / "unused"),
        max_documents=1,
    )
    sample = discover_document_samples(config)[0]
    corpus = build_local_corpus_index(config, [sample])

    first_section = sample.sections[0]
    target_chunks = [chunk for chunk in corpus.chunks if chunk.mapped_section_id == first_section.section_id]

    assert target_chunks
    assert all(chunk.doc_id == sample.doc_id for chunk in target_chunks)
    assert any("1.1 Domain Context" in (chunk.mapped_section_key or "") for chunk in target_chunks)


def test_all_phases_write_one_report_with_retrieval_trace(tmp_path: Path) -> None:
    backend_root = _backend_root()
    judge = _FakeJudge()
    config = DocumentIntelligenceEvalConfig(
        input_path=str(backend_root / "output" / "processing" / "stage4_rag_ready"),
        parsed_root=str(backend_root / "output" / "processing" / "stage1_normalized"),
        output_dir=str(tmp_path),
        phase="all",
        max_documents=1,
        max_sections_per_document=1,
        questions_per_section=2,
    )
    sample = discover_document_samples(config)[0]
    corpus = build_local_corpus_index(config, [sample])
    section = sample.sections[0]
    target_chunk = next(chunk for chunk in corpus.chunks if chunk.doc_id == sample.doc_id and chunk.mapped_section_id == section.section_id)
    executor = _FixedQAExecutor(
        doc_id=sample.doc_id,
        section_key=target_chunk.mapped_section_key,
        chunk_id=target_chunk.chunk_id,
    )

    run_document_intelligence_eval(config, judge=judge, qa_executor=executor)

    qa_path = tmp_path / "e2e_qa_eval_report.json"
    assert qa_path.exists()

    qa_payload = json.loads(qa_path.read_text(encoding="utf-8"))
    assert qa_payload["corpus"]["doc_ids"] == ["2412.19437v2", "SRS_CNPM", "recblr(1)"]
    result = qa_payload["documents"][0]["results"][0]
    assert set(result["judge_result"].keys()) == {
        "correctness",
        "faithfulness",
        "answer_support",
        "judge_rationale",
    }
    assert result["retrieval_trace"]["doc_hit_in_top_k"] is True
    assert result["retrieval_trace"]["section_hit_in_top_k"] is True
    assert result["retrieval_trace"]["chunk_hit_in_top_k"] is True
    assert qa_payload["summary"]["retrieval_trace_summary"]["doc_hit_in_top_k"] == 2
    assert len(judge.qa_judge_calls) == 2


def test_single_phase_writes_only_selected_report(tmp_path: Path) -> None:
    backend_root = _backend_root()
    config = DocumentIntelligenceEvalConfig(
        input_path=str(backend_root / "output" / "processing" / "stage4_rag_ready" / "SRS_CNPM"),
        parsed_root=str(backend_root / "output" / "processing" / "stage1_normalized"),
        output_dir=str(tmp_path),
        phase="e2e_qa",
        max_documents=1,
        max_sections_per_document=1,
        questions_per_section=1,
    )

    sample = discover_document_samples(config)[0]
    corpus = build_local_corpus_index(config, [sample])
    section = sample.sections[0]
    target_chunk = next(chunk for chunk in corpus.chunks if chunk.doc_id == sample.doc_id and chunk.mapped_section_id == section.section_id)
    executor = _FixedQAExecutor(
        doc_id=sample.doc_id,
        section_key=target_chunk.mapped_section_key,
        chunk_id=target_chunk.chunk_id,
    )
    run_document_intelligence_eval(config, judge=_FakeJudge(), qa_executor=executor)

    assert not (tmp_path / "structure_eval_report.json").exists()
    assert not (tmp_path / "element_eval_report.json").exists()
    assert (tmp_path / "e2e_qa_eval_report.json").exists()


def test_qa_item_schema_has_section_traceability() -> None:
    item = QAEvalItem(
        doc_id="doc",
        section_id="doc:section:0001",
        question_index=0,
        question="What is the fact?",
        reference_answer="The fact.",
        source_section_text="The fact appears here.",
        target_section_key="Doc > Section",
        target_chunk_ids=("chunk-1", "chunk-2"),
    )

    assert item.doc_id == "doc"
    assert item.section_id == "doc:section:0001"
    assert item.target_section_key == "Doc > Section"
    assert item.target_chunk_ids == ("chunk-1", "chunk-2")
