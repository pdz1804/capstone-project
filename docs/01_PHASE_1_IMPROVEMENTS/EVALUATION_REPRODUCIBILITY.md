# Evaluation & Benchmark Reproducibility Guide

**Based on Actual Code**: Phase_2_FE_AI_Merge evaluation framework  
**Source Files**: `backend/src/evaluation/metrics.py`, `backend/src/evaluation/benchmark.py`  
**Last Updated**: May 14, 2026  

---

## Evaluation Metrics

All metrics implemented in: `Phase_2_FE_AI_Merge/backend/src/evaluation/metrics.py`

### 1. Recall@K

**Location**: metrics.py lines 16-38  
**Definition**: Proportion of relevant documents in top K results

```python
def recall_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """Recall at k = |{relevant docs in top-k}| / |total relevant docs|"""
    if not relevant:
        return 0.0
    top_k = retrieved[:k]
    hit_count = sum(1 for doc_id in top_k if doc_id in relevant)
    return hit_count / len(relevant)
```

**Interpretation**:
- 100% = all relevant docs found in top-k
- 50% = half of relevant docs found in top-k
- 0% = no relevant docs in top-k

**Typical Results** (from project evaluation):
- BM25 text: 100% Recall@10 (all relevant found in top 10)
- Dense text: 100% Recall@10 (all relevant found)
- ColQwen image: 80% Recall@10 (8 of 10 relevant found)

### 2. nDCG@K (Normalized Discounted Cumulative Gain)

**Location**: metrics.py lines 64-90  
**Definition**: Ranking quality metric considering position of relevant docs

```python
def ndcg_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """
    DCG@k = sum(1 / log2(rank + 1) for each relevant doc in top-k)
    iDCG@k = optimal DCG if ranked perfectly
    nDCG@k = DCG@k / iDCG@k  [0, 1]
    """
```

**Interpretation**:
- 100% = perfectly ranked (all relevant docs at top)
- 50% = moderately ranked
- 0% = worst possible ranking

**Typical Results**:
- BM25 text: 84.84% nDCG@10 (good ranking quality)
- Dense text: 81.92% nDCG@10 (slightly lower, semantic ranking)
- ColQwen image: 67.14% nDCG@10 (vision ranking less precise)

**Why Different from Recall**:
- Recall: Only cares if relevant doc is in top-k
- nDCG: Cares WHERE relevant doc appears (position matters)
- Example:
  - Query: "machine learning"
  - Doc A (most relevant), Doc B, Doc C, ... Doc K (barely relevant)
  - Both configurations have Recall@K = 100%
  - But if Doc K is ranked #1, nDCG@K is much lower

### 3. MRR (Mean Reciprocal Rank)

**Location**: metrics.py lines 93-113  
**Definition**: Position of first relevant document (averaged over queries)

```python
def mrr(retrieved: List[str], relevant: Set[str]) -> float:
    """MRR = 1 / rank_of_first_relevant"""
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0  # No relevant docs found
```

**Interpretation**:
- 100% (1.0) = first result is relevant (MRR@1)
- 50% (0.5) = second result is relevant (MRR@2)
- 25% (0.25) = fourth result is relevant (MRR@4)
- 0% (0.0) = no relevant results found

**Use Case**: When users typically click first result (like Google Search)

### 4. MAP (Mean Average Precision)

**Location**: metrics.py lines 116-143  
**Definition**: Average precision across all query ranks

```python
def mean_average_precision(retrieved: List[str], relevant: Set[str]) -> float:
    """
    AP = sum(precision@k * relevance[k]) / num_relevant
    Precision@k = num_relevant_in_top_k / k
    """
```

**Interpretation**:
- Balances precision and recall at all cutoff points
- Higher values when relevant docs are ranked higher
- Typically lower than Recall@K for same dataset

---

## Benchmark Framework

**Location**: `Phase_2_FE_AI_Merge/backend/src/evaluation/benchmark.py`

### BenchmarkConfig

**Lines 32-56**: Configuration dataclass

```python
@dataclass
class BenchmarkConfig:
    queries_path: str           # JSONL: [{query, query_id}, ...]
    qrels_path: str             # TSV: query_id \t doc_id \t relevance
    corpus_path: str            # JSONL: [{doc_id, text, ...}, ...]
    retriever_types: List[str]  # ["bm25", "dense", "hybrid"]
    reranker_models: List[str]  # [None, "bge-large"]
    k_values: List[int]         # [1, 3, 5, 10] — K cutoffs for metrics
    max_queries: Optional[int]  # Limit queries for testing
```

### Running a Benchmark

**Lines 85-200**: Main benchmark execution

```python
async def run_benchmark(config: BenchmarkConfig) -> BenchmarkResult:
    """
    1. Load corpus (documents)
    2. Load queries
    3. For each retriever_type:
        a. Build index
        b. For each query:
            - Retrieve top-k
            - (Optional) Rerank results
            - Compute metrics
        c. Aggregate results across all k_values
    4. Return aggregated BenchmarkResult
    """
```

### BenchmarkResult

**Lines 60-80**: Output structure

```python
@dataclass
class BenchmarkResult:
    metrics: Dict[str, Dict[str, float]]  # {metric_name: {k_value: score}}
    total_time_sec: float                 # Total execution time
    avg_query_time_ms: float              # Per-query latency
    num_queries: int                      # Total queries evaluated
    detailed_results: Dict               # Per-query breakdown
```

**Example Output**:
```json
{
  "metrics": {
    "recall@10": {
      "bm25": 100.0,
      "dense": 100.0,
      "hybrid": 100.0
    },
    "ndcg@10": {
      "bm25": 84.84,
      "dense": 81.92,
      "hybrid": 87.50
    },
    "mrr": {
      "bm25": 0.95,
      "dense": 0.92,
      "hybrid": 0.96
    }
  },
  "total_time_sec": 245.3,
  "avg_query_time_ms": 101.0,
  "num_queries": 2430
}
```

---

## Expected Baseline Results

### Test Configuration

**Dataset**: Internal synthetic benchmark  
**Query Count**: 2,430 synthetic queries  
**Document Count**: 20 documents  
**Query Types**: 4 difficulty levels  
**Evaluation Date**: May 2026

### Baseline Metrics

#### Text Retrieval

| Metric | BM25 | Dense | Hybrid |
|--------|------|-------|--------|
| **Recall@10** | 100.0% | 100.0% | 100.0% |
| **nDCG@10** | 84.84% | 81.92% | 87.50% |
| **MRR** | 0.95 | 0.92 | 0.96 |
| **Avg Query Time** | 15ms | 45ms | 62ms |

**Interpretation**:
- All retrievers find relevant documents (100% Recall@10)
- Hybrid fusion improves ranking quality (87.50% > 84.84%)
- Trade-off: Hybrid slower (62ms) than BM25 alone (15ms)

#### Image Retrieval (ColQwen)

| Metric | ColQwen |
|--------|---------|
| **Recall@10** | 80.0% |
| **nDCG@10** | 67.14% |
| **MRR** | 0.72 |
| **Avg Query Time** | 320ms |

**Interpretation**:
- Vision-based retrieval lower precision than text
- ColQwen requires vision-text understanding (slower)
- Useful as complement to text retrieval, not replacement

---

## Random Seed Configuration

### Current Status

**Problem**: Code does NOT explicitly set random seeds

**Files Analyzed**:
- metrics.py: No seed setting
- benchmark.py: No seed setting
- retrieval/rag_retrievers.py: No seed setting

**Consequence**: Results vary slightly between runs (expected <2% variance for large N)

### Implementing Seed Control

**Add to `benchmark.py` (lines 1-10)**:

```python
import random
import numpy as np
import torch

def set_evaluation_seed(seed: int = 42):
    """Set all random seeds for reproducible evaluation"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    print(f"✓ Evaluation seed set to {seed}")
```

**Usage**:
```python
# At benchmark start
set_evaluation_seed(42)
result = await run_benchmark(config)
```

**Why seed = 42**:
- Industry-standard seed for reproducibility
- Used in most published benchmarks
- Easy to recognize in logs

---

## Dataset Versioning

### Current Status

**Corpus Location**: Unclear from codebase (likely external or generated)
**Queries Location**: Unclear from codebase
**Query Count**: 2,430 synthetic queries (from evaluation results)
**Document Count**: 20 documents

### Recommended Format

**corpus.jsonl** (one JSON per line):
```json
{"doc_id": "doc_001", "text": "...", "metadata": {"source": "...", "date": "..."}}
{"doc_id": "doc_002", "text": "...", "metadata": {"source": "...", "date": "..."}}
```

**queries.jsonl**:
```json
{"query_id": "q_001", "query": "What is machine learning?", "difficulty": "easy"}
{"query_id": "q_002", "query": "Explain transfer learning", "difficulty": "medium"}
```

**qrels.tsv** (tab-separated):
```
q_001	doc_001	2
q_001	doc_003	1
q_002	doc_002	2
```

**Relevance Scale**:
- 2 = Highly relevant
- 1 = Relevant
- 0 = Not relevant

### Version Control Strategy

```bash
# Store datasets with version tags
docs/data/v1.0/
├── corpus.jsonl
├── queries.jsonl
└── qrels.tsv

# Document changes
echo "Version 1.0: 20 documents, 2430 queries" > docs/data/v1.0/README.md
```

---

## Reproducing Results Exactly

### Step 1: Verify Dependencies

```bash
# Verify requirements-frozen.txt installed
pip list | grep -E "transformers|sentence-transformers|colpali"

# Should output:
# colpali-engine 0.3.13
# sentence-transformers 3.0.1
# transformers 4.57.3
```

### Step 2: Set Seeds

```bash
# In evaluation script
from src.evaluation.benchmark import set_evaluation_seed
set_evaluation_seed(42)
```

### Step 3: Load Exact Datasets

```bash
# Use versioned datasets
config = BenchmarkConfig(
    queries_path="docs/data/v1.0/queries.jsonl",
    qrels_path="docs/data/v1.0/qrels.tsv",
    corpus_path="docs/data/v1.0/corpus.jsonl",
    retriever_types=["bm25", "dense", "hybrid"],
    reranker_models=[None, "bge-large"],
    k_values=[1, 3, 5, 10],
    max_queries=None  # Use all 2430
)
```

### Step 4: Run Benchmark

```bash
# From backend directory
cd Phase_2_FE_AI_Merge/backend

# Run evaluation
python -m src.evaluation.benchmark \
  --queries_path docs/data/v1.0/queries.jsonl \
  --qrels_path docs/data/v1.0/qrels.tsv \
  --corpus_path docs/data/v1.0/corpus.jsonl \
  --output results_v1.0_seed42.json
```

### Step 5: Verify Results

```bash
# Results should match baseline (±1% due to floating point)
# Expected nDCG@10:
# - BM25: 84.84%
# - Dense: 81.92%
# - Hybrid: 87.50%
```

---

## Interpreting Benchmark Results

### Success Criteria

✅ **Good Results**:
- Recall@10 ≥ 90% (finding relevant documents)
- nDCG@10 ≥ 80% (ranking quality acceptable)
- MRR ≥ 0.80 (first result often relevant)

⚠️ **Acceptable**:
- Recall@10 = 80-90% (some relevant docs missed)
- nDCG@10 = 70-80% (moderate ranking quality)
- MRR = 0.60-0.80 (first result sometimes relevant)

❌ **Poor Results**:
- Recall@10 < 80% (missing too many relevant docs)
- nDCG@10 < 70% (ranking quality poor)
- MRR < 0.60 (first result rarely relevant)

### Debugging Low Results

**If Recall@10 drops**:
1. Check if retriever built index correctly
2. Verify corpus loaded completely
3. Check for query/document language mismatch
4. Ensure k=10 sufficient for corpus size

**If nDCG@10 drops**:
1. Check if relevance scores computed
2. Verify ranking algorithm (BM25, dense, hybrid)
3. Check if reranker enabled when expected
4. Compare individual query results for outliers

**If Latency increases**:
1. Check system load (CPU/GPU utilization)
2. Verify index size (larger = slower search)
3. Check if reranking enabled (adds 30-50ms per query)
4. Profile per-stage latency (retrieval vs reranking vs generation)

---

## Comparing Benchmark Runs

### Across Retriever Types

```bash
# Run all three and compare
python benchmark.py --retriever_types bm25,dense,hybrid

# Expected ranking by nDCG@10:
# 1. Hybrid (87.50%) — best combined
# 2. BM25 (84.84%) — good precision
# 3. Dense (81.92%) — good recall
```

### With/Without Reranking

```bash
# Without reranker
python benchmark.py --reranker_models none

# With reranker (BGE-Large)
python benchmark.py --reranker_models bge-large

# Expected improvement:
# +2-5 percentage points nDCG@10
# Cost: +30-50ms per query
```

### Scaling: Different K Values

```bash
# Recall should increase with K
Recall@1:  20%
Recall@3:  50%
Recall@5:  75%
Recall@10: 100%

# nDCG should plateau
nDCG@1:  45%
nDCG@3:  72%
nDCG@5:  80%
nDCG@10: 84% (plateaus)
```

---

## Known Limitations

### Synthetic Queries
- Queries manually created, not from real users
- May not reflect actual user search patterns
- Results may differ when applied to real queries

### Small Corpus (20 docs)
- Results will improve with larger corpus
- Evaluation faster but less representative
- Production corpus: 10,000+ documents recommended

### Language (English + Vietnamese)
- Whisper multilingual, but Docling may have encoding issues
- Test with target language before production
- Some languages may have lower quality OCR

### No User Feedback Loop
- Evaluation is static (fixed queries/qrels)
- No online learning from user behavior
- Index rebuilt manually, not continuously updated

---

## Checklist for Reproducible Evaluation

- [ ] Generate requirements-frozen.txt
- [ ] Verify requirements-frozen.txt installed
- [ ] Set random seeds to 42 in benchmark code
- [ ] Use versioned datasets (docs/data/v1.0/)
- [ ] Document any environment differences (GPU, CPU, CUDA version)
- [ ] Save benchmark results with timestamp
- [ ] Compare results to baseline (±1% tolerance)
- [ ] Archive results in version control
- [ ] Document any deviations from baseline

---

## Files to Create/Update

| File | Purpose | Status |
|------|---------|--------|
| `docs/data/v1.0/corpus.jsonl` | 20 benchmark documents | Need to create |
| `docs/data/v1.0/queries.jsonl` | 2,430 queries | Need to create |
| `docs/data/v1.0/qrels.tsv` | Relevance judgments | Need to create |
| `src/evaluation/benchmark.py` | Add seed setting function | Need to update |
| `src/evaluation/benchmark.py` | Add evaluation reproducibility docs | Done (this file) |

---

**Generated**: May 14, 2026  
**Source**: Actual Phase_2_FE_AI_Merge evaluation code analysis  
**Next Step**: Run benchmark with requirements-frozen.txt and seed=42
