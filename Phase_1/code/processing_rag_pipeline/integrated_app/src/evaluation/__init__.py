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
]

