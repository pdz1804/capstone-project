"""
Retrieval Evaluation Metrics

Standard metrics for evaluating retrieval quality:
- Recall@K: Proportion of relevant documents retrieved in top K
- nDCG@K: Normalized Discounted Cumulative Gain
- MRR: Mean Reciprocal Rank
- MAP: Mean Average Precision
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

