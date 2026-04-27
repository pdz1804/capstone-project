"""
Evaluation Module for RAG Pipeline Benchmarking

This module provides utilities for evaluating retrieval and generation quality:
- Retrieval metrics: nDCG, Recall, MRR, MAP
- Generation metrics: BLEU, ROUGE, BERTScore
- Benchmark runners for systematic evaluation
"""

from .metrics import (
    recall_at_k,
    ndcg_at_k,
    mrr,
    mean_average_precision,
    normalize_scores
)

from .benchmark import (
    BenchmarkConfig,
    BenchmarkRunner,
    run_retrieval_benchmark
)
from .docx_section_coverage import (
    BaseSectionCoverageJudge,
    CalibrationResult,
    DocumentEvalResult,
    DocxSectionCoverageConfig,
    DocxSectionCoverageRunner,
    LLMSectionCoverageJudge,
    QuestionCoverageResult,
    SectionEvalResult,
    SectionEvalSample,
    compute_parsing_metrics,
    flatten_docx_sections,
    map_chunks_to_sections,
    run_docx_section_coverage,
)
from .document_intelligence import (
    BaseDocumentIntelligenceJudge,
    BaseQAExecutor,
    DocumentEvalSample,
    DocumentIntelligenceEvalConfig,
    DocumentIntelligenceRunner,
    DocumentQAEvalResult,
    LLMDocumentIntelligenceJudge,
    QAEvalItem,
    QAEvalResult,
    SearchOrchestratorQAExecutor,
    SectionSample,
    discover_document_samples,
    run_document_intelligence_eval,
)

__all__ = [
    # Metrics
    "recall_at_k",
    "ndcg_at_k", 
    "mrr",
    "mean_average_precision",
    "normalize_scores",
    # Benchmark
    "BenchmarkConfig",
    "BenchmarkRunner",
    "run_retrieval_benchmark",
    # DOCX section coverage evaluation
    "BaseSectionCoverageJudge",
    "CalibrationResult",
    "DocumentEvalResult",
    "DocxSectionCoverageConfig",
    "DocxSectionCoverageRunner",
    "LLMSectionCoverageJudge",
    "QuestionCoverageResult",
    "SectionEvalResult",
    "SectionEvalSample",
    "compute_parsing_metrics",
    "flatten_docx_sections",
    "map_chunks_to_sections",
    "run_docx_section_coverage",
    # Document Intelligence evaluation
    "BaseDocumentIntelligenceJudge",
    "BaseQAExecutor",
    "DocumentEvalSample",
    "DocumentIntelligenceEvalConfig",
    "DocumentIntelligenceRunner",
    "DocumentQAEvalResult",
    "LLMDocumentIntelligenceJudge",
    "QAEvalItem",
    "QAEvalResult",
    "SearchOrchestratorQAExecutor",
    "SectionSample",
    "discover_document_samples",
    "run_document_intelligence_eval",
]
