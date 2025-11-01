# Report đánh giá các pipeline

**General Note:**
* **Nền tảng:** Cả hai notebook đều chạy trên Google Colab với **GPU T4**.
* **Dữ liệu:** Dữ liệu thử nghiệm được rút gọn còn **50,000 tài liệu** aka corpus (thay vì 1,000,985) và **556 truy vấn** aka queries.
* **Thời gian (Rerank):** Đối với các pipeline Rerank, "Thời gian Retrieve" thực chất là **Thời gian Rerank** cho 556 truy vấn, dựa trên 30 ứng viên hàng đầu (`retrieval_k=30`).

---

## Metric Explanation

### 1. Recall@k

* Recall measures **how many relevant documents were retrieved**.  
  It answers: “Out of all relevant documents, what percentage did the model find in the top k results?”
* **Example:** Suppose a query has 5 relevant documents in total.
  - The system returns k=10 results, of which 2 are relevant.
  - Recall@10 = `2 / 5 = 0.4` (or 40%).

---

### 2. nDCG@k (Normalized Discounted Cumulative Gain)

* This is the most important metric, measuring **ranking quality**. It doesn’t just check whether relevant documents were retrieved but **how well they were ranked**.
* **Example:** Think of Google search — a relevant result in position #1 is far more valuable than one in position #k. nDCG reflects this.
  - **Gain:** You earn points for retrieving relevant documents.
  - **Cumulative:** Points accumulate for all relevant documents in the top 10.
  - **Discounted:** Points are discounted the lower a document ranks (#1 gets full points, #2 gets less, and so on).
  - **Normalized:** The final score is divided by the score of a perfect ranking to bring it to a [0, 1] scale, allowing fair comparison across queries.


### Bảng Đánh giá Pipeline Retriever

| Pipeline | Config (Model / Index) | Thời gian Index | Thời gian Embed | Thời gian Retrieve/Rerank | Tổng Thời gian | nDCG@3 | Recall@3 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BM25 (Raw)** | `rank-bm25` (Okapi) | ~1s | N/A |  3 min | 3 min | 0.2821 | 0.3085 |
| **Dense (MiniLM-L6 Raw)** | `s-t/all-MiniLM-L6-v2` / Flat (Numpy) | Không index (N/A) | 1 min | ~1s | ~1s | 0.8658 | 0.9125 |
| **Dense (BGE-Small Raw)** | `BAAI/bge-small-en-v1.5` / Flat (Numpy) | Không index (N/A) | 2.5 min | ~1s | ~1s | **0.8855** | **0.9257** |
| **Hybrid (BM25+MiniLM RRF)** | RRF (`rrf_k=60`) | N/A | N/A | ~1s | ~1s | 0.5786 | 0.6885 |
| **Hybrid (BM25+BGE RRF)** | RRF (`rrf_k=60`) | N/A | N/A | ~1s | ~1s | 0.5830 | 0.6787 |
| **BM25 + Rerank (BGE-L)** | `BAAI/bge-reranker-large` (Top 30) | N/A | N/A | 103.12s | 103.12s | 0.4469 | 0.4592 |
| **MiniLM + Rerank (BGE-L)** | `BAAI/bge-reranker-large` (Top 30) | N/A | N/A | 103.54s | 103.54s | 0.9196 | 0.9526 |
| **BGE-S + Rerank (BGE-L)** | `BAAI/bge-reranker-large` (Top 30) | N/A | N/A | 103.37s | 103.37s | **0.9248** | **0.9598** |
| **Hy(MiniLM) + Rerank (BGE-L)** | `BAAI/bge-reranker-large` (Top 30) | N/A | N/A | 103.97s | 103.97s | 0.9176 | 0.9490 |
| **Hy(BGE-S) + Rerank (BGE-L)** | `BAAI/bge-reranker-large` (Top 30) | N/A | N/A | 103.58s | 103.58s | 0.9234 | 0.9562 |
| **BM25 + Rerank (MiniLM-12)** | `cross-encoder/ms-marco-MiniLM-L-12-v2` (Top 30) | N/A | N/A | 17.81s | 17.81s | 0.4459 | 0.4574 |
| **MiniLM + Rerank (MiniLM-12)** | `cross-encoder/ms-marco-MiniLM-L-12-v2` (Top 30) | N/A | N/A | 18.33s | 18.33s | 0.9089 | 0.9460 |
| **BGE-S + Rerank (MiniLM-12)** | `cross-encoder/ms-marco-MiniLM-L-12-v2` (Top 30) | N/A | N/A | 18.07s | 18.07s | 0.9107 | 0.9496 |
| **Hy(MiniLM) + Rerank (MiniLM-12)** | `cross-encoder/ms-marco-MiniLM-L-12-v2` (Top 30) | N/A | N/A | 17.90s | 17.90s | 0.9092 | 0.9460 |
| **Hy(BGE-S) + Rerank (MiniLM-12)** | `cross-encoder/ms-marco-MiniLM-L-12-v2` (Top 30) | N/A | N/A | 18.69s | 18.69s | 0.9112 | 0.9496 |
| **ColBERTv2 (RAGatouille)** | `colbert-ir/colbertv2.0` / FAISS (`nbits=2`, `doc_maxlen=80`, **faiss-cpu**) | 34m47s | (Kết hợp với index) | 6.5s | 34m53s | **0.9638** | **0.9412** |
---

# Kết luận
## Retriever tốt nhất (Không Rerank)
- Dense (BGE-Small Raw) là retriever thô (raw) tốt nhất (nDCG@3 là 0.8855), nó mang lại chất lượng xếp hạng cao hơn so với MiniLM-L6 (0.8658).
- Cả hai mô hình Dense (BGE và MiniLM) đều vượt trội hoàn toàn so với BM25 (0.2821) trên bộ dữ liệu này. 
    - Giải thích: The dataset is biased toward dense retrievers.
- Nhược điểm:
    - Thời gian embedding của BGE-Small-en-1.5 gấp 2.5 lần so với MiniLM
    - BGE-Small-en-1.5 chỉ hỗ trợ tiếng Anh (có model BGE-M3 viết tắt của Multilingual; nhưng model này quá nặng để bỏ vào Colab; sẽ test model này trên các VM instance của Google).

## Reranker tốt nhất
- Cả 2 reranker đều là cross-encoder. Cách hoạt động của cross-encoder:
    - Chúng lấy cả câu truy vấn (query) và tài liệu (document) làm một đầu vào duy nhất.
    - Chúng xử lý đồng thời cả hai trong một mô hình Transformer.
    - Cuối cùng, chúng đưa ra một điểm số duy nhất (logit) cho biết mức độ liên quan.

- BGE-Large (BAAI/bge-reranker-large) là reranker tốt hơn MiniLM-L12. Trong mọi thử nghiệm so sánh (khi cùng rerank BM25, MiniLM, BGE-Small, hoặc Hybrid), BGE-Large luôn cho điểm nDCG@3 cao hơn so với MiniLM-L12.
- Nhược điểm: thời gian rerank gấp 5-6 lần MiniLM-L12.

## Pipeline tốt nhất (Không tính ColBERT)
- Pipeline tốt nhất là Dense (BGE-Small) + Rerank (BGE-Large) với nDCG@3 = 0.9248 và Recall@3 = 0.9598.

-> Sự kết hợp này (retriever BGE-Small tốt nhất + reranker BGE-Large tốt nhất) đã chứng minh hiệu quả cao nhất trong số các pipeline 2 giai đoạn (retrieve-then-rerank).

## So sánh với ColBERT. Multi-vector embedding VS. Single-vector embedding
ColBERTv2 (nDCG@3: 0.9638) vượt trội hơn cả pipeline tốt nhất (nDCG@3: 0.9248). Giải thích:

- Pipeline 2 Giai đoạn (Retrieve-then-Rerank): Pipeline BGE-Small + Rerank (BGE-L) là một quy trình 2 giai đoạn.
    - Giai đoạn 1 (Retrieve): BGE-Small tìm kiếm 30 tài liệu (ứng viên) hàng đầu từ 50,000 tài liệu.
    - Giai đoạn 2 (Rerank): BGE-Large (một cross-encoder) chỉ xem xét và xếp hạng lại 30 ứng viên đó.
Điểm yếu: Nếu tài liệu trả lời đúng (ground truth) không nằm trong top 30 mà BGE-Small tìm thấy ở Giai đoạn 1, thì BGE-Large Reranker sẽ không bao giờ có cơ hội nhìn thấy nó. Toàn bộ pipeline bị giới hạn bởi chất lượng của Giai đoạn 1.

- ColBERTv2 (Late Interaction): ColBERT không phải là một pipeline 2 giai đoạn. Nó là một mô hình tương tác muộn (late-interaction).
    - Index: Nó mã hóa (encode) từng token trong 50,000 tài liệu thành các vector riêng lẻ (thay vì 1 vector cho cả tài liệu).
    - Search: Khi có truy vấn, nó cũng mã hóa từng token của truy vấn. Sau đó, nó tính toán độ tương đồng tối đa (MaxSim) giữa các token của truy vấn và các token của tài liệu.
Điểm mạnh: ColBERT có khả năng "khớp" ở mức độ chi tiết (token-level). Nó có thể tìm thấy một tài liệu ngay cả khi chỉ một phần nhỏ của tài liệu đó khớp chính xác với một phần của truy vấn. Nó không "vứt bỏ" các ứng viên tiềm năng ở Giai đoạn 1 như pipeline 2 giai đoạn.

Kết luận: ColBERT (0.9638) thắng vì kiến trúc của nó (late-interaction) vốn đã vượt trội hơn trong việc tìm kiếm chi tiết so với kiến trúc 2 giai đoạn (0.9248) trên bộ dữ liệu này.

# Disclaimer

**ColBERTv2 (faiss-cpu):** Mặc dù pipeline ColBERT được chạy trên T4 GPU, log output (`colbert_latest.ipynb`, cell 11) hiển thị cảnh báo: `WARNING! You have a GPU available, but only faiss-cpu is currently installed... Will continue with CPU indexing...`. Do đó, quá trình index + embedding (34 phút 47 giây) được thực hiện trên **CPU** (ngốn khoảng 6.1GB RAM), trong khi quá trình retrieve (6.49 giây) được thực hiện trên GPU T4.