# Chunking Strategy Evaluation Summary

## 1. Overview
This document summarizes the methodology and evaluation framework for document chunking strategies within the project. The framework is heavily inspired by Chroma's research on chunking evaluation ([Evaluating Chunking](https://www.trychroma.com/research/evaluating-chunking)) and the `chunking_evaluation` repository by Brandon Starxel.

The traditional way to evaluate RAG systems often focuses merely on document-level retrieval (whether the correct document was retrieved). However, this evaluation framework focuses on **Span-level Metrics** to explicitly measure how well a chunking strategy isolates the *exact* piece of information needed to answer a query without pulling in unnecessary context.

## 2. Evaluation Data (Ground Truth)
The evaluation utilizes a **span-level pseudo ground-truth** dataset generated automatically from the project's cleaned document corpus (`stage4_rag_ready` markdown files).

**Generation Process (`backend/evals/chunking/generate_chunking_eval_set.py`):**
1. **Synthetic QA Generation**: An LLM is used to generate realistic user queries paired with specific text excerpts natively found in the documents.
2. **Span Exact-Matching**: The generated excerpts are mapped back to the original `stage4_rag_ready` markdown files to extract precise character indices.
3. **Dataset Format**: The final evaluation set consists of rows containing:
   - `query`: The synthetic question.
   - `doc_id`: The document identifier.
   - `relevant_excerpt`: The exact target text.
   - `start_char` & `end_char`: The character boundaries of the target text within the document.

## 3. Evaluated Strategies
The pipeline currently compares two primary chunking approaches (`backend/evals/chunking/evaluate_chunking_strategies.py`):

1. **`recursive_markdown` (Baseline)**: A standard recursive character text chunker overlapping at fixed sizes (e.g., 1000 chars size, 200 chars overlap).
2. **`chroma_cluster_semantic` (Experimental)**: A global semantic packing chunker algorithm that groups text dynamically based on semantic similarity and token limits, aiming to keep contextual boundaries intact.

## 4. Evaluation Metrics
For a given strategy and a parameter $K$ (top-K chunks retrieved), the following **character-level span metrics** are computed:

- **Hit Rate (`hit_rate`)**: The percentage of queries where the retrieved chunks have at least 1 character of overlap with the ground-truth span. (Did we find *any* of the answer?)
- **Mean Span Recall (`mean_span_recall`)**: The average ratio of target characters successfully retrieved. 
  $$\text{Recall} = \frac{\text{Overlap Chars}}{\text{Ground-Truth Length}}$$
- **Mean Span Precision (`mean_span_precision`)**: The average ratio of retrieved characters that are actually part of the target span. This penalizes chunks that are too large.
  $$\text{Precision} = \frac{\text{Overlap Chars}}{\text{Total Retrieved Chars}}$$
- **Mean Span IoU (`mean_span_iou`)**: Intersection over Union of the character spans. This is the ultimate balancing metric between recall and precision.
  $$\text{IoU} = \frac{\text{Overlap Chars}}{\text{Ground-Truth Length} + \text{Total Retrieved Chars} - \text{Overlap Chars}}$$
- **Mean Retrieved Characters**: A raw measure of how much context is being fed into the LLM. Lower is better for LLM cost/attention, provided Recall remains high.

## 5. Results & Observations
> **Note:** Run `python backend/evals/chunking/evaluate_chunking_strategies.py --stage4-dir <dir> --eval-jsonl <eval_file> --output-dir <out>` to generate exact numbers. 

**Recent Evaluation Results** (Sample Size: 111 queries, Local Markdown Source, Hybrid Retrieval):

| Strategy | Top-K | Hit Rate | Span Recall | Span Precision | Span IoU | Retrieved Chars |
|----------|-------|----------|-------------|----------------|----------|-----------------|
| **Recursive Markdown** | @1 | 72.07% | 69.43% | 19.00% | 18.71% | 755 |
| | @3 | 87.38% | 86.66% | 8.23% | 8.15% | 2091 |
| | @5 | 89.18% | 88.46% | 5.12% | 5.08% | 3412 |
| | @10 | 94.59% | 93.87% | 2.71% | 2.70% | 6572 |
| **Chroma Cluster Semantic** | @1 | 72.97% | 71.07% | 15.95% | 15.89% | 1006 |
| | @3 | 89.18% | 87.98% | 6.98% | 6.97% | 2621 |
| | @5 | 91.89% | 91.23% | 4.76% | 4.76% | 4096 |
| | @10 | 94.59% | 93.85% | 2.50% | 2.50% | 7682 |

**Analysis:**
- **Semantic Chunking (Chroma Cluster)** provides a slight edge in **Hit Rate** and **Span Recall** across @1, @3, and @5, demonstrating that grouping chunks by semantic similarity ensures that information limits don't arbitrarily crack concepts.
- **Recursive Chunking** currently retains better Span Precision & IoU specifically at @1, largely because the semantic chunker in this test pulled roughly ~33% more average characters per retrieved item (1006 vs 755 at @1), leading to lower precision mathematically. 
- Over larger K-values (@5, @10), both perform identically (~94% hit rate) but Recall and Hit Rate metrics converge tightly.

**Trade-offs:**
- **Recursive Chunking** is faster and typically pulls fewer raw characters randomly, but risks missing information that falls squarely on a breakpoint.
- **Semantic/Cluster Chunking** maximizes the probability that a concept enters the context window intact, at the expense of marginally larger chunks.

## 6. Commands Reference
- **Generate Eval Set**:
  ```bash
  python backend/evals/chunking/generate_chunking_eval_set.py ...
  ```
- **Run Evaluation**:
  ```bash
  python backend/evals/chunking/evaluate_chunking_strategies.py --stage4-dir <docs_path> --eval-jsonl <eval_file> --output-dir <results_path>
  ```
