# Báo cáo Phân tích Score và Phương pháp Đánh giá các Pipeline RAG

Báo cáo này trình bày công thức toán học cơ bản được sử dụng để tính điểm (Score) trong mỗi pipeline retrieval, cùng với phương pháp luận để so sánh hiệu suất giữa các pipeline này, do điểm số không đồng nhất.

---

## 1. Công thức tính Score cho từng Pipeline

Mỗi pipeline sử dụng một mô hình tính điểm khác nhau, phản ánh mục tiêu và cơ chế hoạt động của thuật toán retrieval.

### Pipeline A: OCR + BM25 (Lexical Search)

- **Công thức**: BM25 là một công thức thống kê kết hợp Tần suất từ (TF), Độ hiếm tài liệu nghịch đảo (IDF), và Chuẩn hóa độ dài tài liệu.
$$\text{Score}_{\text{BM25}}(Q, D) = \sum_{t \in Q} \text{IDF}(t) \cdot \frac{\text{TF}(t, D) \cdot (k_1 + 1)}{\text{TF}(t, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$
- **Mục tiêu**: Đo lường mức độ khớp **từ khóa** giữa truy vấn và tài liệu.
- **Phạm vi**: Không có giới hạn trên cố định (Điểm tuyệt đối). 

### Pipeline C: OCR + MiniLM-L6 (Semantic Search)
- **Công thức**: Sử dụng **Cosine Similarity** giữa hai vector embedding đã được mô hình MiniLM tạo ra.
$$\text{Score}_{\text{MiniLM}}(Q, D) = \text{CosineSimilarity}(\vec{V}_{Q}, \vec{V}_{D}) = \frac{\vec{V}_{Q} \cdot \vec{V}_{D}}{|\vec{V}_{Q}| \cdot |\vec{V}_{D}|}$$
- **Mục tiêu**: Đo lường mức độ **tương đồng ngữ nghĩa** giữa vector truy vấn và vector tài liệu.
- **Phạm vi**: Luôn nằm trong khoảng $[-1, 1]$.

### Pipeline B: ColQwen / Colpali (Multi-modal Multi-vector Search)
- **Mục tiêu**: Đo lường mức độ **khớp chi tiết (fine-grained matching)** giữa các vector từ khóa của truy vấn và các vector mảnh ảnh (patch) trên trang tài liệu.
- **Cơ chế**: Dựa trên kiến trúc ColBERT, tính tổng điểm tương đồng lớn nhất cho mỗi vector truy vấn so với tất cả các vector ảnh.
- **Công thức**: 
$$\text{Score}_{\text{ColQwen}}(Q, D) = \sum_{q \in \vec{Q}} \max_{d \in \vec{D}} (\text{CosineSimilarity}(q, d))$$
- **Phạm vi**: Không có giới hạn trên cố định (Điểm tuyệt đối).
---

## 2. Phương pháp So sánh và Đánh giá Hiệu suất

Vì các điểm số (Score) trên **không thể so sánh trực tiếp** (ví dụ: Score 5.0 của BM25 không có ý nghĩa gì so với Score 0.75 của MiniLM), việc đánh giá pipeline nào tốt hơn phải dựa trên **Chất lượng Đầu ra Cuối cùng** (end-to-end quality) thông qua các chỉ số độc lập.

### Phương pháp Thủ công (Phù hợp với thử nghiệm hiện tại)

1.  **Đánh giá Độ chính xác của Retrieval (Retrieval Accuracy):**
    * **Mục tiêu:** Kiểm tra xem trang tài liệu chứa câu trả lời đúng có nằm trong các kết quả **Top K** (ví dụ: Top 3 hoặc Top 5) của mỗi pipeline hay không.
    * **Vấn đề:** Cần Golden Dataset (ground truth labels)
    * **Tiêu chí chấm điểm:**
        * **Hit Rate:** Tỷ lệ số truy vấn mà pipeline tìm thấy tài liệu đúng.
        * **Rank (Thứ hạng):** Pipeline nào đưa tài liệu đúng lên thứ hạng cao hơn (thứ hạng càng nhỏ càng tốt) là pipeline chiến thắng.

2.  **Đánh giá Chất lượng Tổng hợp của LLM (RAG Quality):**
    * Sau khi LLM (GPT-4o Mini) tổng hợp câu trả lời từ ngữ cảnh được cung cấp, đánh giá chất lượng của câu trả lời đó:
        * **Tính xác thực (Groundedness/Faithfulness):** Câu trả lời của LLM có được **hỗ trợ hoàn toàn** bởi ngữ cảnh (text snippet hoặc hình ảnh) mà retriever cung cấp hay không? (Nếu LLM bịa thêm thông tin ngoài ngữ cảnh, pipeline đó bị trừ điểm).
        * **Tính liên quan (Answer Relevance):** Câu trả lời có trả lời **đúng và đầy đủ** câu hỏi của người dùng hay không?

### Kết luận Đánh giá (Dựa trên bản chất mô hình)

Dựa trên cơ chế hoạt động, thứ hạng dự kiến về hiệu suất thường là:

| Hạng | Pipeline | Lý do |
| :--- | :--- | :--- |
| **1** | **B: ColQwen (Multi-modal)** | Thường tốt nhất vì nó **không bị ảnh hưởng bởi lỗi OCR** và hiểu ngữ cảnh trực quan (sơ đồ, bố cục slide). |
| **2** | **C: MiniLM (Semantic)** | Tốt thứ hai vì nó hiểu **ý nghĩa** của câu truy vấn và có thể tìm thấy từ đồng nghĩa, nhưng vẫn phụ thuộc vào chất lượng OCR. |
| **3** | **A: BM25 (Lexical)** | Yếu nhất vì nó chỉ khớp **từ khóa** chính xác. Thích hợp cho các truy vấn về tên riêng hoặc thuật ngữ chính xác. |