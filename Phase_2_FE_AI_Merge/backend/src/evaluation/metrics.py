"""Retrieval Evaluation Metrics for RAG Pipeline Assessment.

Standard information retrieval metrics for quantifying retrieval quality across
multiple evaluation cutoffs (K values). Used in benchmark.py for systematic
evaluation of BM25, Dense, and Hybrid retrieval strategies.

Metrics (all computed per query, then averaged):

Recall@K (Binary Relevance):
- Proportion of all relevant documents retrieved in top K results
- Formula: |relevant ∩ retrieved@K| / |all relevant|
- Range: [0, 1] (1.0 = perfect, 0.0 = none found)
- Use case: "Did we find all relevant documents?"
- Interpretation: Higher is better, but K-dependent

nDCG@K (Ranked Relevance with Position Discount):
- Normalized Discounted Cumulative Gain at K
- Rewards relevant documents ranked higher, penalizes lower positions
- Formula: DCG@K / IDCG@K (normalized by ideal ranking)
- DCG@K = Σ(relevance_i / log2(i+1)) for i in 1..K
- Range: [0, 1] (1.0 = perfect ranking)
- Use case: "How well-ranked are relevant documents?"
- Interpretation: Position-aware metric, preferred for ranking quality

MRR (Mean Reciprocal Rank):
- Average of (1 / rank of first relevant result) across all queries
- Formula: (1/N) * Σ(1 / rank_of_first_relevant)
- Range: (0, 1] (1.0 = always first result is relevant, 0.0 = never found)
- Use case: "How quickly do we find the first relevant result?"
- Interpretation: Good for answering questions (need one good result)

MAP (Mean Average Precision):
- Average precision computed at each relevant document position
- AP = (1/R) * Σ(precision@k where result_k is relevant)
- Precision@K = |relevant ∩ retrieved@K| / K
- Range: [0, 1] (1.0 = all relevant docs ranked first)
- Use case: "Overall ranking quality with multiple relevant docs?"
- Interpretation: Balances recall and ranking quality

Evaluation Setup:
- queries_path: JSON file with query texts
- qrels_path: JSON file with {query_id: {doc_id: relevance}} (0=not relevant, 1+=relevant)
- Multiple K values: Typically [1, 3, 5, 10, 20] for comprehensive evaluation
- Seed control: Set random.seed(42) for reproducible result ordering

Usage Pattern:
1. Execute retrieval (get ranked list of doc IDs with scores)
2. Compute metrics using functions in this module
3. Aggregate per-query metrics by averaging across all queries
4. Report by K and by retriever type

Key Functions:
- recall_at_k: Binary relevance metric
- dcg_at_k: Discount cumulative gain (component of nDCG)
- ndcg_at_k: Normalized DCG metric
- mrr: Mean reciprocal rank
- mean_average_precision: MAP metric
- evaluate_retrieval: Batch evaluation across multiple queries
"""

import math
import numpy as np
from typing import List, Dict, Any, Tuple


def recall_at_k(
    retrieved: List[Tuple[str, float]], 
    relevant: Dict[str, int], 
    k: int
) -> float:
    """
    Calculate Recall@K.
    
    Args:
        retrieved: List of (doc_id, score) tuples, sorted by score descending
        relevant: Dict of {doc_id: relevance_score} where relevance > 0 means relevant
        k: Number of top results to consider
        
    Returns:
        Recall@K score (0.0 to 1.0)
    """
    relevant_docs = {doc_id for doc_id, rel in relevant.items() if rel > 0}
    retrieved_docs = {doc_id for doc_id, _ in retrieved[:k]}
    
    if not relevant_docs:
        return 0.0
    
    return len(relevant_docs & retrieved_docs) / len(relevant_docs)


def dcg_at_k(
    retrieved: List[Tuple[str, float]], 
    relevant: Dict[str, int], 
    k: int
) -> float:
    """
    Calculate Discounted Cumulative Gain at K.
    
    Args:
        retrieved: List of (doc_id, score) tuples
        relevant: Dict of {doc_id: relevance_score}
        k: Number of top results to consider
        
    Returns:
        DCG@K score
    """
    dcg = 0.0
    for idx, (doc_id, _) in enumerate(retrieved[:k]):
        rel = relevant.get(doc_id, 0)
        dcg += (2 ** rel - 1) / math.log2(idx + 2)
    return dcg


def ndcg_at_k(
    retrieved: List[Tuple[str, float]], 
    relevant: Dict[str, int], 
    k: int
) -> float:
    """
    Calculate Normalized Discounted Cumulative Gain at K.
    
    Args:
        retrieved: List of (doc_id, score) tuples
        relevant: Dict of {doc_id: relevance_score}
        k: Number of top results to consider
        
    Returns:
        nDCG@K score (0.0 to 1.0)
    """
    # Calculate DCG
    dcg = dcg_at_k(retrieved, relevant, k)
    
    # Calculate ideal DCG (with perfect ranking)
    ideal_rels = sorted(relevant.values(), reverse=True)[:k]
    idcg = sum((2 ** rel - 1) / math.log2(idx + 2) for idx, rel in enumerate(ideal_rels))
    
    if idcg == 0:
        return 0.0
    
    return dcg / idcg


def mrr(
    retrieved: List[Tuple[str, float]], 
    relevant: Dict[str, int]
) -> float:
    """
    Calculate Mean Reciprocal Rank.
    
    Args:
        retrieved: List of (doc_id, score) tuples
        relevant: Dict of {doc_id: relevance_score}
        
    Returns:
        MRR score (0.0 to 1.0)
    """
    relevant_docs = {doc_id for doc_id, rel in relevant.items() if rel > 0}
    
    for idx, (doc_id, _) in enumerate(retrieved, 1):
        if doc_id in relevant_docs:
            return 1.0 / idx
    
    return 0.0


def mean_average_precision(
    retrieved: List[Tuple[str, float]], 
    relevant: Dict[str, int]
) -> float:
    """
    Calculate Mean Average Precision.
    
    Args:
        retrieved: List of (doc_id, score) tuples
        relevant: Dict of {doc_id: relevance_score}
        
    Returns:
        MAP score (0.0 to 1.0)
    """
    relevant_docs = {doc_id for doc_id, rel in relevant.items() if rel > 0}
    
    if not relevant_docs:
        return 0.0
    
    precision_sum = 0.0
    num_relevant_found = 0
    
    for idx, (doc_id, _) in enumerate(retrieved, 1):
        if doc_id in relevant_docs:
            num_relevant_found += 1
            precision_sum += num_relevant_found / idx
    
    return precision_sum / len(relevant_docs)


def normalize_scores(scores_dict: Dict[str, float]) -> Dict[str, float]:
    """
    Normalize scores to [0, 1] range using min-max normalization.
    
    Args:
        scores_dict: Dict of {doc_id: score}
        
    Returns:
        Dict of {doc_id: normalized_score}
    """
    if not scores_dict:
        return {}
    
    values = list(scores_dict.values())
    min_val, max_val = min(values), max(values)
    range_val = max_val - min_val
    
    if range_val == 0:
        return {k: 0.5 for k in scores_dict}
    
    return {k: (v - min_val) / range_val for k, v in scores_dict.items()}


def evaluate_retrieval(
    retrieved_results: List[Dict[str, Any]],
    qrels: Dict[str, Dict[str, int]],
    k_values: List[int] = [1, 3, 5, 10]
) -> Dict[str, Dict[str, float]]:
    """
    Evaluate retrieval results across multiple metrics and K values.
    
    Args:
        retrieved_results: List of dicts with 'query_id' and 'results' (list of (doc_id, score))
        qrels: Dict of {query_id: {doc_id: relevance}}
        k_values: List of K values to evaluate at
        
    Returns:
        Dict of {metric_name: {query_id: score}}
    """
    metrics = {
        f"recall@{k}": [] for k in k_values
    }
    metrics.update({f"ndcg@{k}": [] for k in k_values})
    metrics["mrr"] = []
    metrics["map"] = []
    
    for result in retrieved_results:
        query_id = result.get("query_id")
        retrieved = [(r.get("doc_id") or r.get("id"), r.get("score", 0)) for r in result.get("results", [])]
        relevant = qrels.get(query_id, {})
        
        # Calculate metrics for each K
        for k in k_values:
            metrics[f"recall@{k}"].append(recall_at_k(retrieved, relevant, k))
            metrics[f"ndcg@{k}"].append(ndcg_at_k(retrieved, relevant, k))
        
        metrics["mrr"].append(mrr(retrieved, relevant))
        metrics["map"].append(mean_average_precision(retrieved, relevant))
    
    # Calculate means
    summary = {}
    for metric_name, values in metrics.items():
        summary[metric_name] = {
            "mean": float(np.mean(values)) if values else 0.0,
            "std": float(np.std(values)) if values else 0.0,
            "min": float(np.min(values)) if values else 0.0,
            "max": float(np.max(values)) if values else 0.0
        }
    
    return summary

