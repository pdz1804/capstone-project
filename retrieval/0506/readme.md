# Nghiên cứu và Đánh giá các Pipeline Truy xuất Thông tin (Information Retrieval Pipelines)

## Tóm tắt

Nghiên cứu này đánh giá hiệu suất của các pipeline truy xuất thông tin khác nhau, bao gồm các phương pháp dựa trên từ khóa (lexical), ngữ nghĩa (dense), lai (hybrid), reranker và multi-modal. Tất cả các thử nghiệm được thực hiện trên Google Colab với GPU T4, sử dụng tập dữ liệu MS MARCO được rút gọn (50,000 tài liệu và 556 truy vấn).

## Kiến trúc các Model

### 1. BM25 (Sparse Retriever)
- **Kiến trúc**: Mô hình tìm kiếm dựa trên từ khóa sử dụng thuật toán Okapi BM25
- **Cách hoạt động**: Tính điểm tương đồng dựa trên tần suất xuất hiện của các từ trong truy vấn và tài liệu
- **Ưu điểm**: Nhanh, nhẹ, hiệu quả với từ khóa chính xác
- **Nhược điểm**: Không hiểu ngữ nghĩa, không xử lý được từ đồng nghĩa

### 2. Dense Retrievers
#### MiniLM-L6 (`sentence-transformers/all-MiniLM-L6-v2`)
- **Kiến trúc**: Transformer-based với 6 lớp, embedding 384 chiều
- **Cách hoạt động**: Mã hóa văn bản thành vector ngữ nghĩa, tính cosine similarity
- **Ưu điểm**: Cân bằng giữa hiệu suất và tốc độ

#### BGE-Small (`BAAI/bge-small-en-v1.5`)
- **Kiến trúc**: Transformer-based với embedding 384 chiều
- **Cách hoạt động**: Tương tự MiniLM nhưng được huấn luyện chuyên biệt cho retrieval
- **Ưu điểm**: Hiệu suất cao hơn MiniLM
- **Nhược điểm**: Chỉ hỗ trợ tiếng Anh, thời gian embedding lâu hơn

### 3. Hybrid Retrievers
#### RRF (Reciprocal Rank Fusion)
- **Kiến trúc**: Kết hợp kết quả từ BM25 và Dense retriever
- **Cách hoạt động**: Tính điểm dựa trên thứ hạng nghịch đảo: `score = 1/(k + rank_bm25) + 1/(k + rank_dense)`
- **Ưu điểm**: Ổn định, không phụ thuộc vào thang điểm

#### Weighted Sum
- **Kiến trúc**: Kết hợp có trọng số giữa BM25 và Dense
- **Cách hoạt động**: `final_score = alpha * dense_score + (1-alpha) * bm25_score`
- **Ưu điểm**: Linh hoạt trong điều chỉnh trọng số

### 4. Rerankers
#### BGE-Large Reranker (`BAAI/bge-reranker-large`)
- **Kiến trúc**: Cross-encoder với kiến trúc transformer lớn
- **Cách hoạt động**: Xử lý đồng thời query và document trong một mô hình duy nhất
- **Ưu điểm**: Độ chính xác cao
- **Nhược điểm**: Thời gian xử lý lâu

#### MiniLM-L12 Reranker (`cross-encoder/ms-marco-MiniLM-L-12-v2`)
- **Kiến trúc**: Cross-encoder với 12 lớp transformer
- **Cách hoạt động**: Tương tự BGE-Large nhưng nhẹ hơn
- **Ưu điểm**: Cân bằng giữa hiệu suất và tốc độ

### 5. ColBERTv2 (`colbert-ir/colbertv2.0`)
- **Kiến trúc**: Late-interaction multi-vector với RAGatouille
- **Cách hoạt động**: Mã hóa từng token thành vector riêng, tính MaxSim giữa query và document tokens
- **Ưu điểm**: Khả năng khớp chi tiết ở mức token, không bị giới hạn bởi giai đoạn đầu
- **Nhược điểm**: Indexing nặng, tốn tài nguyên

### 6. ColQwen (Multi-modal)
- **Kiến trúc**: Multi-modal retriever dựa trên Colpali Engine
- **Cách hoạt động**: Xử lý cả hình ảnh và văn bản, mã hóa thành vector đa phương thức
- **Ưu điểm**: Hiểu được ngữ cảnh trực quan từ slide
- **Nhược điểm**: Rất nặng, phụ thuộc vào chất lượng hình ảnh

## Kết quả Sơ bộ

### Metrics Explanation
- **Recall@k**: Tỷ lệ tài liệu đúng được tìm thấy trong top k kết quả
- **nDCG@k**: Chất lượng xếp hạng, có tính đến vị trí của tài liệu đúng

### Bảng Đánh giá Hiệu suất

| Pipeline | nDCG@3 | Recall@3 | Thời gian (s) |
|----------|--------|----------|---------------|
| **BM25 Raw** | 0.2821 | 0.3085 | ~180 |
| **Dense MiniLM Raw** | 0.8658 | 0.9125 | ~60 |
| **Dense BGE-Small Raw** | 0.8855 | 0.9257 | ~150 |
| **Hybrid MiniLM RRF** | 0.5786 | 0.6885 | ~1 |
| **Hybrid BGE-Small RRF** | 0.5830 | 0.6787 | ~1 |
| **BM25 + BGE-L Rerank** | 0.4469 | 0.4592 | 103.12 |
| **MiniLM + BGE-L Rerank** | 0.9196 | 0.9526 | 103.54 |
| **BGE-Small + BGE-L Rerank** | 0.9248 | 0.9598 | 103.37 |
| **ColBERTv2** | **0.9638** | **0.9412** | 2087 |

## Giải thích Kết quả

### 1. Sự vượt trội của Dense Retrievers
- **Nguyên nhân**: Tập dữ liệu MS MARCO được thiết kế ưu ái dense retrievers với các câu hỏi tự nhiên đòi hỏi hiểu ngữ nghĩa
- **Vấn đề từ vựng không khớp**: BM25 không xử lý được từ đồng nghĩa và cách diễn đạt khác nhau

### 2. Hiệu quả của Rerankers
- **Cross-encoder**: Xử lý đồng thời query và document cho độ chính xác cao
- **Giới hạn**: Phụ thuộc vào chất lượng của giai đoạn retrieval đầu tiên

### 3. ColBERTv2 - Pipeline tốt nhất
- **Late-interaction**: Không bị giới hạn bởi giai đoạn retrieval đầu tiên
- **Multi-vector**: Khả năng khớp chi tiết ở mức token
- **Ưu điểm**: Tìm được tài liệu ngay cả khi chỉ một phần nhỏ khớp với query

### 4. Multi-modal với ColQwen
- **Ưu điểm**: Hiểu được ngữ cảnh trực quan từ slide (hình ảnh, sơ đồ, bố cục)
- **Không phụ thuộc OCR**: Vẫn tìm được trang slide ngay cả khi OCR thất bại

## Kết luận

1. **Retriever tốt nhất (không rerank)**: Dense BGE-Small (nDCG@3: 0.8855)
2. **Reranker tốt nhất**: BGE-Large Reranker
3. **Pipeline tốt nhất (không ColBERT)**: BGE-Small + BGE-Large Rerank (nDCG@3: 0.9248)
4. **Pipeline tốt nhất tổng thể**: ColBERTv2 (nDCG@3: 0.9638)

ColBERTv2 chứng minh hiệu quả vượt trội nhờ kiến trúc late-interaction cho phép khớp chi tiết ở mức token, vượt qua hạn chế của các pipeline 2 giai đoạn truyền thống.
