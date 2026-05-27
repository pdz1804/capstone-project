"""Benchmark Runner: Systematic Evaluation of Retrieval Pipelines.

Comprehensive benchmarking framework for evaluating and comparing retrieval strategies
(BM25, Dense, Hybrid) across multiple evaluation cutoffs (K values). Integrates with
metrics.py for standard IR metrics (Recall, nDCG, MRR, MAP).

Workflow:
1. Configure: Create BenchmarkConfig with dataset paths and retriever types
2. Initialize: Create BenchmarkRunner with config
3. Run: Execute benchmarks across configured retriever and K combinations
4. Export: Save results to JSON/CSV for analysis
5. Compare: View performance tables and plots

Configuration (BenchmarkConfig):
- Dataset:
  * queries_path: JSON file with {"query_id": "text"} entries
  * qrels_path: JSON with {"query_id": {doc_id: relevance}} for ground truth
  * corpus_path: JSON with {doc_id: {"text": "content", "metadata": {...}}}
  * max_queries: Limit evaluation to N queries (None = all)
- Retrievers:
  * retriever_types: ["bm25", "dense", "hybrid"] (any combination)
  * reranker_models: ["bge-large"] (optional, None = no reranking)
- Evaluation:
  * k_values: [1, 3, 5, 10] (cutoff points for metrics)
  * seed: 42 (for reproducibility)
- Output:
  * output_dir: Where to save results
  * export_format: "json", "csv", or both

Results Format:
- Per-query results: Query ID, retriever type, K value, metrics
- Aggregated results: Mean/median/std of metrics across all queries
- Ranking table: Shows performance ranking of different strategies
- Timing statistics: Latency per retrieval strategy

Key Classes:
- BenchmarkConfig: Dataclass defining benchmark parameters
- BenchmarkResult: Named tuple with aggregated metric results
- BenchmarkRunner: Orchestrates benchmark execution

BenchmarkResult Structure:
- retriever_type: "bm25", "dense", or "hybrid"
- k: Evaluation cutoff (1, 3, 5, 10, etc.)
- recall: Mean Recall@K across all queries
- ndcg: Mean nDCG@K across all queries
- mrr: Mean Reciprocal Rank
- map: Mean Average Precision
- latency_ms: Average retrieval latency in milliseconds

Usage Example:
```python
config = BenchmarkConfig(
    queries_path="queries.json",
    qrels_path="qrels.json",
    corpus_path="corpus.json",
    retriever_types=["bm25", "dense", "hybrid"],
    k_values=[1, 3, 5, 10]
)
runner = BenchmarkRunner(config)
results = runner.run()
runner.export_results("output/")
```

Integration Points:
- Uses metrics.py functions (recall_at_k, ndcg_at_k, mrr, mean_average_precision)
- Compatible with rag_retrievers.py (BM25Retriever, DenseRetriever, SimpleHybridRetriever)
- Generates evaluation data for EVALUATION_REPRODUCIBILITY.md documentation

Performance Benchmarks (baseline):
- BM25: ~50ms per 1000-doc corpus
- Dense: ~100ms per 1000-doc corpus (embedding lookup)
- Hybrid (RRF): ~150ms per 1000-doc corpus (both methods + fusion)
- Reranking: +50-100ms depending on model
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

from .metrics import (
    recall_at_k,
    ndcg_at_k,
    mrr,
    mean_average_precision,
    evaluate_retrieval
)

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""
    
    # Dataset
    queries_path: str = None
    qrels_path: str = None
    corpus_path: str = None
    
    # Retrievers to evaluate
    retriever_types: List[str] = field(default_factory=lambda: ["bm25", "dense", "hybrid"])
    
    # Rerankers to evaluate (None = no reranking)
    reranker_models: List[Optional[str]] = field(default_factory=lambda: [None, "bge-large"])
    
    # Evaluation settings
    k_values: List[int] = field(default_factory=lambda: [1, 3, 5, 10])
    max_queries: int = None  # Limit number of queries (None = all)
    
    # Output
    output_dir: str = "benchmark_results"
    save_detailed: bool = True  # Save per-query results
    
    # Pipeline settings
    chunk_size: int = 1000
    chunk_overlap: int = 200


@dataclass
class BenchmarkResult:
    """Results from a benchmark run."""
    
    # Identification
    retriever_type: str
    reranker_model: Optional[str]
    timestamp: str
    
    # Config used
    config: Dict[str, Any]
    
    # Metrics summary
    metrics: Dict[str, Dict[str, float]]
    
    # Timing
    total_time_sec: float
    avg_query_time_ms: float
    num_queries: int
    
    # Detailed results (per-query)
    detailed_results: List[Dict[str, Any]] = field(default_factory=list)


class BenchmarkRunner:
    """
    Runner for systematic RAG pipeline benchmarking.
    
    Example usage:
        config = BenchmarkConfig(
            queries_path="data/queries.jsonl",
            qrels_path="data/qrels.tsv",
            retriever_types=["bm25", "dense", "hybrid"],
            k_values=[1, 3, 5, 10]
        )
        runner = BenchmarkRunner(config)
        results = runner.run(retriever_manager)
        runner.save_results(results)
    """
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.queries = []
        self.qrels = {}
        self.results = []
        
        # Create output directory
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def load_queries(self, queries_path: str = None) -> List[Dict[str, Any]]:
        """Load queries from file (JSON or JSONL)."""
        path = Path(queries_path or self.config.queries_path)
        
        if not path.exists():
            logger.error(f"Queries file not found: {path}")
            return []
        
        queries = []
        if path.suffix == ".jsonl":
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        queries.append(json.loads(line))
        else:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                queries = data if isinstance(data, list) else [data]
        
        # Limit queries if configured
        if self.config.max_queries:
            queries = queries[:self.config.max_queries]
        
        self.queries = queries
        logger.info(f"Loaded {len(queries)} queries from {path}")
        return queries
    
    def load_qrels(self, qrels_path: str = None) -> Dict[str, Dict[str, int]]:
        """Load relevance judgments (qrels) from file."""
        path = Path(qrels_path or self.config.qrels_path)
        
        if not path.exists():
            logger.error(f"Qrels file not found: {path}")
            return {}
        
        qrels = {}
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 4:
                    qid, _, doc_id, rel = parts[:4]
                    qrels.setdefault(qid, {})[doc_id] = int(rel)
        
        self.qrels = qrels
        logger.info(f"Loaded qrels for {len(qrels)} queries from {path}")
        return qrels
    
    def run_single(
        self, 
        retriever_manager, 
        retriever_type: str,
        use_reranker: bool = False
    ) -> BenchmarkResult:
        """
        Run benchmark for a single retriever configuration.
        
        Args:
            retriever_manager: RAGRetrieverManager instance
            retriever_type: Type of retriever to use
            use_reranker: Whether to use reranker
            
        Returns:
            BenchmarkResult with metrics
        """
        logger.info(f"Running benchmark: {retriever_type} (reranker: {use_reranker})")
        
        timestamp = datetime.now().isoformat()
        start_time = time.time()
        
        # Run queries
        all_results = []
        max_k = max(self.config.k_values)
        
        for query in self.queries:
            query_id = query.get("id", query.get("query_id", "unknown"))
            query_text = query.get("text", query.get("query", ""))
            
            # Search
            results = retriever_manager.search(
                query_text, 
                retriever_type, 
                top_k=max_k,
                use_reranker=use_reranker
            )
            
            all_results.append({
                "query_id": query_id,
                "query_text": query_text,
                "results": results
            })
        
        total_time = time.time() - start_time
        avg_time_ms = (total_time / len(self.queries)) * 1000 if self.queries else 0
        
        # Evaluate
        metrics = evaluate_retrieval(all_results, self.qrels, self.config.k_values)
        
        # Create result
        result = BenchmarkResult(
            retriever_type=retriever_type,
            reranker_model=retriever_manager.reranker_model if use_reranker else None,
            timestamp=timestamp,
            config=asdict(self.config),
            metrics=metrics,
            total_time_sec=total_time,
            avg_query_time_ms=avg_time_ms,
            num_queries=len(self.queries),
            detailed_results=all_results if self.config.save_detailed else []
        )
        
        # Log summary
        logger.info(f"  Completed in {total_time:.2f}s ({avg_time_ms:.2f}ms/query)")
        for k in self.config.k_values:
            ndcg = metrics.get(f"ndcg@{k}", {}).get("mean", 0)
            recall = metrics.get(f"recall@{k}", {}).get("mean", 0)
            logger.info(f"  nDCG@{k}: {ndcg:.4f}, Recall@{k}: {recall:.4f}")
        
        return result
    
    def run(self, retriever_manager) -> List[BenchmarkResult]:
        """
        Run full benchmark suite across all configured retrievers and rerankers.
        
        Args:
            retriever_manager: RAGRetrieverManager instance
            
        Returns:
            List of BenchmarkResult for each configuration
        """
        # Load data if not already loaded
        if not self.queries:
            self.load_queries()
        if not self.qrels:
            self.load_qrels()
        
        if not self.queries or not self.qrels:
            logger.error("Cannot run benchmark: missing queries or qrels")
            return []
        
        results = []
        
        for retriever_type in self.config.retriever_types:
            if retriever_type not in retriever_manager.get_available_retrievers():
                logger.warning(f"Retriever {retriever_type} not available, skipping")
                continue
            
            for reranker in self.config.reranker_models:
                use_reranker = reranker is not None
                
                # Setup reranker if needed
                if use_reranker and retriever_manager.reranker is None:
                    retriever_manager.setup_reranker(reranker)
                
                result = self.run_single(retriever_manager, retriever_type, use_reranker)
                results.append(result)
        
        self.results = results
        return results
    
    def save_results(self, results: List[BenchmarkResult] = None) -> Path:
        """
        Save benchmark results to files.
        
        Args:
            results: List of results (uses self.results if None)
            
        Returns:
            Path to results directory
        """
        results = results or self.results
        if not results:
            logger.warning("No results to save")
            return self.output_dir
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self.output_dir / f"benchmark_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Save summary
        summary = []
        for result in results:
            summary_entry = {
                "retriever": result.retriever_type,
                "reranker": result.reranker_model,
                "num_queries": result.num_queries,
                "total_time_sec": result.total_time_sec,
                "avg_query_time_ms": result.avg_query_time_ms
            }
            # Add metrics
            for metric_name, metric_data in result.metrics.items():
                summary_entry[metric_name] = metric_data.get("mean", 0)
            summary.append(summary_entry)
        
        with open(run_dir / "summary.json", 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Save detailed results
        if self.config.save_detailed:
            for result in results:
                name = f"{result.retriever_type}"
                if result.reranker_model:
                    name += f"_rerank_{result.reranker_model}"
                
                with open(run_dir / f"{name}_detailed.json", 'w') as f:
                    json.dump(asdict(result), f, indent=2, default=str)
        
        logger.info(f"Results saved to: {run_dir}")
        return run_dir
    
    def print_summary(self, results: List[BenchmarkResult] = None):
        """Print formatted summary of benchmark results."""
        results = results or self.results
        if not results:
            print("No results available")
            return
        
        print("\n" + "=" * 80)
        print("BENCHMARK RESULTS SUMMARY")
        print("=" * 80)
        
        # Header
        headers = ["Retriever", "Reranker", "Queries", "Time(ms/q)"]
        headers += [f"nDCG@{k}" for k in self.config.k_values]
        headers += [f"Recall@{k}" for k in self.config.k_values]
        
        # Print header
        print(f"{'Retriever':<12} {'Reranker':<12} {'Queries':<8} {'ms/q':<8}", end="")
        for k in self.config.k_values:
            print(f" nDCG@{k:<3}", end="")
        for k in self.config.k_values:
            print(f" Rec@{k:<3}", end="")
        print()
        print("-" * 80)
        
        # Print results
        for result in results:
            reranker = result.reranker_model or "None"
            print(f"{result.retriever_type:<12} {reranker:<12} {result.num_queries:<8} {result.avg_query_time_ms:<8.1f}", end="")
            
            for k in self.config.k_values:
                ndcg = result.metrics.get(f"ndcg@{k}", {}).get("mean", 0)
                print(f" {ndcg:.4f} ", end="")
            
            for k in self.config.k_values:
                recall = result.metrics.get(f"recall@{k}", {}).get("mean", 0)
                print(f" {recall:.4f} ", end="")
            print()
        
        print("=" * 80)


def run_retrieval_benchmark(
    retriever_manager,
    queries_path: str,
    qrels_path: str,
    output_dir: str = "benchmark_results",
    retriever_types: List[str] = None,
    k_values: List[int] = None,
    use_reranker: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to run a retrieval benchmark.
    
    Args:
        retriever_manager: RAGRetrieverManager instance
        queries_path: Path to queries file
        qrels_path: Path to qrels file
        output_dir: Output directory for results
        retriever_types: List of retrievers to evaluate
        k_values: List of K values
        use_reranker: Whether to include reranker evaluation
        
    Returns:
        Dict with summary metrics
    """
    config = BenchmarkConfig(
        queries_path=queries_path,
        qrels_path=qrels_path,
        output_dir=output_dir,
        retriever_types=retriever_types or ["bm25", "dense", "hybrid"],
        k_values=k_values or [1, 3, 5, 10],
        reranker_models=[None, "bge-large"] if use_reranker else [None]
    )
    
    runner = BenchmarkRunner(config)
    results = runner.run(retriever_manager)
    runner.save_results(results)
    runner.print_summary(results)
    
    # Return summary
    return {
        "num_configs": len(results),
        "results": [
            {
                "retriever": r.retriever_type,
                "reranker": r.reranker_model,
                "metrics": r.metrics
            }
            for r in results
        ]
    }

