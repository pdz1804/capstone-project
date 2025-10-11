# Evaluation and Conclusion

## Evaluation Table
| Method | Index/Embedding Time | Inference Time (1000 queries) | nDCG@10 | Recall@10 |
| :--- | :--- | :--- | :--- | :--- |
| **BM25** | Very fast (a few minutes, tokenization only) | **44 min 29 s** – 1 CPU core | 0.0663 | 0.1133 |
| **Dense** | Very slow (≈20 min for the first time – assuming GPU T4) | **~6 seconds** | **0.2411** | **0.3557** |
| **Hybrid (Weighted Sum)** | None (reused existing indexes) | ~1 second (score fusion only) | 0.2348 | 0.3427 |
| **Hybrid (RRF)** | None (reused existing indexes) | ~1 second (rank fusion only) | 0.1949 | 0.3207 |

---

## Metric Explanation

### 1. Recall@10

* Recall measures **how many relevant documents were retrieved**.  
  It answers: “Out of all relevant documents, what percentage did the model find in the top 10 results?”
* **Example:** Suppose a query has 5 relevant documents in total.
  - The system returns 10 results, of which 2 are relevant.
  - Recall@10 = `2 / 5 = 0.4` (or 40%).
* `Recall@10 = 0.3557` for Dense is the highest, meaning that on average it retrieves around 35.6% of relevant documents within the top 10 results.

---

### 2. nDCG@10 (Normalized Discounted Cumulative Gain)

* This is the most important metric, measuring **ranking quality**. It doesn’t just check whether relevant documents were retrieved but **how well they were ranked**.
* **Example:** Think of Google search — a relevant result in position #1 is far more valuable than one in position #10. nDCG reflects this.
  - **Gain:** You earn points for retrieving relevant documents.
  - **Cumulative:** Points accumulate for all relevant documents in the top 10.
  - **Discounted:** Points are discounted the lower a document ranks (#1 gets full points, #2 gets less, and so on).
  - **Normalized:** The final score is divided by the score of a perfect ranking to bring it to a [0, 1] scale, allowing fair comparison across queries.
* `nDCG@10 = 0.2411` for Dense is the highest, indicating not only that it retrieved more relevant documents (as Recall shows), but also that it ranked them much higher in the results.

---

## Hybrid Methods Explained

Both hybrid methods combine results from BM25 (sparse) and Dense retrieval to produce a single, improved ranked list.

### 1. Weighted Sum Fusion

* **How it works:** Like a scale.
  1. Take BM25 and Dense scores.
  2. Since their scales differ (BM25 can be >20 while Dense is between -1 and 1), both are **normalized** to a common [0, 1] range.
  3. Final score is computed as:  
     `Final = α * Dense_score + (1 - α) * BM25_score`
* **Pros:** Simple and intuitive. The parameter `α` acts like a dial to control how much weight is given to Dense vs BM25. If Dense is better, increase α (e.g., to 0.8).
* **Cons:** Very sensitive to normalization. If normalization is poor, one retriever can dominate unfairly.  
  The result (`0.2348`) shows that normalization worked reasonably well here.

---

### 2. Reciprocal Rank Fusion (RRF)

* **How it works:** Ignores scores entirely and relies on **ranks**.
  1. It doesn’t look at actual scores (e.g., 0.9 vs 25.0). It only considers positions: “Document A is #1 in Dense and #5 in BM25”.
  2. It computes RRF score as:  
     \[
     \text{RRF}(d) = \frac{1}{k + \text{rank}_{\text{dense}}(d)} + \frac{1}{k + \text{rank}_{\text{bm25}}(d)}
     \]
  3. The constant `k` (typically 60) prevents top-ranked documents from overpowering others too much.
* **Pros:** Extremely stable. Since it ignores scores, it’s immune to scale differences between BM25 and Dense. This is often a safe and effective choice when score calibration is uncertain.
* **Cons:** It ignores confidence information. For example, Dense may be far more confident in its top-1 result (0.99) than top-2 (0.7), but RRF only sees them as ranks #1 and #2. Here, RRF’s result (`0.1949`) was lower than Weighted Sum, possibly because the Weighted Sum’s normalization worked well or RRF discarded some useful score information.

---

## Explaining the Results

BM25 performed poorly to the point that it introduced “noise” into the hybrid results.

BM25’s failure here can be attributed to two main reasons:

### 1. The Dataset Favors Dense Retrievers

The MS MARCO dataset is inherently designed to **favor dense retrievers**:

- **Nature of the questions:** MS MARCO queries are often natural language questions like “What is the capital of France?”. These require semantic understanding, synonyms, and conceptual relationships. Dense retrievers can embed queries and documents in semantic space to capture this, even when there’s no direct keyword overlap. BM25, relying purely on exact keyword matching, struggles to understand the underlying intent.

- **Characteristics of the passages:** MS MARCO passages are short and focused. This makes semantic embeddings more effective, while BM25 can fail if query keywords don’t appear exactly in the text.

### 2. Vocabulary Mismatch Problem

Even without synonyms, people can use different words to describe the same thing:

- Query: “how to fix leaking pipes”  
- Document 1: “guide to repairing water pipe issues”  
- Document 2: “leaking pipes”

BM25 would rank Document 2 higher due to exact keyword matches, even though Document 1 is actually the more useful answer. Dense retrievers can understand that “fixing” and “repairing” are semantically related, and score both documents appropriately.

---

## Potential Improvements

- **Improve BM25 Retriever:** We’re judging a fish by its ability to climb a tree. The dataset is biased toward dense retrievers. Choosing or curating a more balanced dataset can help evaluate sparse retrievers more fairly. Tools like Pyserini or search-enabled databases (e.g., Elasticsearch) can also improve BM25 performance.

- **Improve Dense Retriever:** Use vector databases like Milvus to optimize dense retrieval speed and scalability.

- **Improve Hybrid Retriever:**
  - Tune α in Weighted Sum (e.g., 0.8 or 0.9) to give Dense more weight and reduce BM25’s negative influence.
  - Use BM25 as a **filter**: retrieve top 100 with Dense, then re-rank with BM25. This confines BM25’s influence to a smaller set and reduces noise.

---

## Conclusion

This is not a “failure” of BM25 — it’s a difference in approach.  
For domains like technical document search where keywords are critical, BM25 can still perform well.  
But on MS MARCO, with its natural and diverse questions, BM25’s lexical limitations are fully exposed, giving Dense retrievers a clear advantage.
