# DANH SÁCH CÔNG CỤ, MÔ HÌNH, API VÀ NGUỒN THAM KHẢO CHÍNH
## Tài Liệu Kỹ Thuật LMS Mini AI

Tài liệu này tổng hợp toàn bộ các công nghệ, mô hình học máy, các hàm API dịch vụ, và các cơ sở lý luận sư phạm cốt lõi đứng sau hệ thống LMS Mini.

---

## 1. AI MODELS

Nền tảng sử dụng các mô hình ngôn ngữ lớn và mô hình nhúng từ Google:
1. **Gemini 2.5 Flash (`gemini-2.5-flash`):**
* *Lý do lựa chọn:* Tốc độ phản hồi cực nhanh, khả năng đa phương thức (Multimodal Vision) xuất sắc hỗ trợ đọc ảnh quét/ảnh chụp PDF sách giáo khoa, và ngữ cảnh lớn (Context Window lên tới 1 triệu tokens) giúp xử lý mượt mà lịch sử trò chuyện dài của học viên.
* *Nhiệm vụ:* Đóng vai trò làm bộ não phân tích ý định (Planner Agent), các Agent sư phạm chuyên gia (Tutor, Solver, Reviewer), và bộ thẩm định grounding (Verifier Agent).
2. **Gemini Embeddings (`text-embedding-004`):**
* *Nhiệm vụ:* Sinh vector đại diện cho các đoạn văn bản (Dung lượng 768 chiều) để thực hiện tìm kiếm ngữ nghĩa tương đồng (Semantic Search) trong cơ sở dữ liệu Vector DB.

---

## 2. QUẢN TRỊ HẠ TẦNG VÀ LƯU LƯỢNG TRÊN HỆ SINH THÁI GCP (GCP ECOSYSTEM & VERTEX AI MANAGEMENT)

Hệ thống được thiết kế để tích hợp trực tiếp vào **Hệ sinh thái Google Cloud Platform (GCP) thông qua Vertex AI** nhằm quản trị hạ tầng, kiểm soát hạn mức và bảo mật tài nguyên:

### A. Billing & Budget Control
*   **GCP Billing Console:** Toàn bộ chi phí gọi mô hình Gemini 2.5 Flash và Text-Embedding-004 được tổng hợp tập trung. Hệ thống cho phép thiết lập hạn mức ngân sách (**Budget Thresholds**) và tự động gửi cảnh báo qua Email/Slack khi chi phí tiệm cận ngưỡng giới hạn, ngăn ngừa việc cạn kiệt ngân sách ngoài ý muốn.
*   **Cost Allocation Tags:** Gán nhãn tài nguyên để phân bổ chi phí chi tiết theo từng Tenant (trường học hoặc doanh nghiệp cụ thể), giúp tính toán chính xác chi phí vận hành trên mỗi học viên.

### B. Quotas & Rate Limitations
*   **Vertex AI Quota Management:** Cho phép cấu hình giới hạn cứng về Số lượng yêu cầu trên phút (**Requests Per Minute - RPM**), Số lượng tokens trên phút (**Tokens Per Minute - TPM**), và Số lượng cuộc gọi đồng thời (**Concurrent Requests**). Điều này bảo vệ API khỏi các cuộc tấn công từ chối dịch vụ (DDoS) hoặc lỗi vòng lặp vô hạn ở phía Client làm tiêu hao tín dụng.
*   **Quotas Extension:** Dễ dàng gửi yêu cầu nâng hạn mức sử dụng (Quota Increase Requests) trực tiếp trên GCP Console khi số lượng người dùng đồng thời tăng cao tại các trường học hoặc doanh nghiệp lớn.

### C. Identity & Access Management - IAM
*   **Least-Privilege Service Account:** Không sử dụng API Key dạng chuỗi tĩnh dễ bị rò rỉ. Hệ thống xác thực thông qua file khóa dịch vụ Service Account (`GOOGLE_APPLICATION_CREDENTIALS`) được phân quyền tối thiểu và nghiêm ngặt (chỉ gán vai trò `roles/aiplatform.user` để gọi Vertex AI), loại bỏ hoàn toàn rủi ro lộ lọt khóa quản trị toàn phần của hệ thống.

### D. Cloud Monitoring & Audit Logging
*   **Cloud Logging:** Ghi nhận nhật ký thời gian thực của mọi lượt gọi mô hình LLM, số lượng input/output tokens tiêu thụ, mã trạng thái HTTP phản hồi và độ trễ (latency).
*   **Cloud Monitoring:** Thiết lập biểu đồ theo dõi sức khỏe hệ thống (System Health), đo lường hiệu năng của LLM và tự động phát hiện các lượt gọi API bất thường hoặc các lỗi phát sinh (như lỗi timeout hoặc quá hạn ngạch) để kỹ sư hạ tầng can thiệp kịp thời.

---

## 3. HỆ QUẢN TRỊ CHỈ MỤC VECTOR (VECTOR DATABASE BACKENDS)

Hệ thống hỗ trợ cơ chế chuyển đổi linh hoạt (`switchable backend`) giữa hai công nghệ cơ sở dữ liệu vector phổ biến nhất hiện nay thông qua biến môi trường `VECTOR_DB_BACKEND`:
1. **Qdrant Vector DB:**
* *Phạm vi sử dụng:* Dùng cho production nhờ hiệu năng tìm kiếm thời gian thực cực cao, hỗ trợ phân chuỗi dữ liệu mạnh mẽ, có giao diện Dashboard giám sát trực quan ở cổng `6333`.
2. **ChromaDB:**
* *Phạm vi sử dụng:* Cơ sở dữ liệu gọn nhẹ, lưu trữ dạng tệp tin cục bộ (`sqlite-based storage`), thích hợp cho triển khai nhanh tại môi trường thử nghiệm hoặc máy tính cá nhân.

---

## 4. THƯ VIỆN LẬP TRÌNH & FRAMEWORKS (CORE TECHNOLOGY STACK)

* **FastAPI (Python):** Framework xây dựng REST API hiệu năng cao, tự động sinh tài liệu OpenAPI/Swagger UI, quản lý bất đồng bộ (Async/Await) giúp tăng tốc xử lý đồng thời.
* **Streamlit (Python):** Công cụ xây dựng giao diện người dùng LMS trực quan, hiện đại, thích hợp cho việc demo sản phẩm mà không cần viết mã nguồn HTML/CSS/JS phức tạp.
* **n8n Orchestrator:** Công cụ tự động hóa luồng Agent (Agent workflow), giúp trực quan hóa mối quan hệ giữa các Agent dưới dạng đồ thị, cho phép live-reload prompts tức thời từ DB SQLite.
* **PyMuPDF (`fitz`):** Thư viện kết xuất tệp PDF sách giáo khoa thành ảnh PNG chất lượng cao (150 DPI) để chạy OCR Multimodal.
* **PyVi (Vietnamese Tokenizer):** Hỗ trợ tách từ tiếng Việt để tối ưu chỉ mục tìm kiếm văn bản.
* **Rank_BM25:** Thư viện chạy thuật toán tìm kiếm từ khóa Sparse Search (BM25Okapi), kết hợp cùng Dense Embeddings tạo nên quy trình **Hybrid Search** hoàn hảo.

---

## 5. DANH SÁCH API CỐT LÕI (API ENDPOINTS SPECS)

FastAPI Backend cung cấp các API endpoints nghiệp vụ chính sau:

### A. Nạp và Xử lý Sách Giáo Khoa (PDF Ingestion)
* **Endpoint:** `POST /api/ingestion`
* **Chức năng:** Nhận PDF, gọi Vision OCR trích xuất nội dung, sinh embeddings và lưu vào Vector DB theo phân quyền.
* **Tham số chính:**
```json
{
"file_path": "đường_dẫn_pdf",
"tag_name_uuid": "mã_môn_học_cách_ly",
"volume": "tập_sách",
"visibility": "public | teacher_only",
"mode": "update | override"
}
```

### B. Tra cứu Ngữ Cảnh Bảo Mật RAG
* **Endpoint:** `POST /api/retrieval`
* **Chức năng:** Trích xuất hint trang, thực hiện lọc RBAC theo vai trò và truy xuất văn bản SGK tương đồng nhất sử dụng thuật toán Reciprocal Rank Fusion (RRF).
* **Tham số chính:**
```json
{
"text": "truy_vấn_của_học_sinh",
"tag_name_uuids": ["mã_môn_học"],
"type": "doc | qa",
"top_k": 3
}
```

### C. Quản lý prompts tập trung (Prompt Registry)
* **Endpoint:** `GET /api/prompts/active` -> Lấy danh sách prompts đang hoạt động.
* **Endpoint:** `POST /api/prompts` -> Xuất bản phiên bản prompt mới.
* **Endpoint:** `POST /api/prompts/activate` -> Kích hoạt hoặc rollback phiên bản prompt cũ.

---

## 6. NGUỒN THAM KHẢO & CƠ SỞ LÝ LUẬN SƯ PHẠM (PEDAGOGICAL REFERENCES)

Hệ thống LMS Mini được thiết kế dựa trên một số nguyên lý khoa học giáo dục thực tiễn:
1. **Phương pháp Gợi Mở Socratic (Socratic Questioning):**
* *Mô tả:* Không trực tiếp giải bài thay cho học sinh, mà đặt các câu hỏi dẫn dắt mang tính gợi mở liên tục để người học tự tìm ra đáp án. Được áp dụng trực tiếp vào cấu hình prompt của `suggestive_tutor`.
2. **Thang Đo Nhận Thức Bloom (Bloom's Taxonomy):**
* *Mô tả:* Định hình bộ bài tập từ mức độ cơ bản (Nhận biết/Thông hiểu) đến nâng cao (Vận dụng/Thách thức sáng tạo). Áp dụng vào cơ chế sinh đề bài của `exercise_generator`.
3. **Thuyết Kiến Tạo Trong Giáo Dục (Constructivism):**
* *Mô tả:* Xem người học là chủ thể tích cực tự xây dựng kiến thức cho mình dựa trên các trải nghiệm và gợi ý, thay vì tiếp thu kiến thức một chiều thụ động.

---
