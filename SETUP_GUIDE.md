# HƯỚNG DẪN CÀI ĐẶT VÀ KHỞI CHẠY HỆ THỐNG
## TRỢ LÝ GIÁO DỤC TIỂU HỌC THÔNG MINH (AI PEDAGOGICAL ASSISTANT - TRACK A)

Tài liệu này cung cấp hướng dẫn từng bước chi tiết để thiết lập môi trường, cấu hình chìa khóa bảo mật, khởi chạy dịch vụ bằng Docker Compose hoặc Python cục bộ, nạp dữ liệu sách giáo khoa và kiểm thử toàn bộ hệ thống.

---

## 1. YÊU CẦU HẠ TẦNG VÀ MÔI TRƯỜNG (PREREQUISITES)

### Môi trường khuyến nghị:
*   **Hệ điều hành:** Windows 10/11 (PowerShell / WSL2), Ubuntu 20.04+, hoặc macOS (Apple Silicon / Intel).
*   **Docker & Docker Compose:** Docker Engine v20.10+ và Docker Compose v2.0+.
*   **Python (khi chạy không dùng Docker):** Python 3.10 trở lên (khuyên dùng Python 3.12).
*   **Chìa khóa Google Cloud / Vertex AI:** Tệp JSON Service Account (`.json`) được cấp quyền truy cập Vertex AI API hoặc Gemini API Key từ Google AI Studio.

---

## 2. CẤU HÌNH BẢO MẬT & TỆP MÔI TRƯỜNG (.ENV)

### Bước 1: Lưu tệp GCP Service Account Key ngoài thư mục dự án
> **Quy tắc bảo mật:** Để tránh rò rỉ chìa khóa lên Git, tệp JSON Key phải được lưu tại một thư mục cục bộ **nằm ngoài thư mục dự án code**.

Tạo thư mục riêng và lưu tệp key, ví dụ:
*   **Trên Windows:** `C:\gcp-keys\your-gcp-key.json`
*   **Trên Linux / macOS:** `/home/username/gcp-keys/your-gcp-key.json`

### Bước 2: Khởi tạo và cấu hình tệp `.env`
Tạo tệp `.env` tại thư mục gốc của dự án từ tệp mẫu `.env.template`:

```env
# -----------------------------------------------------------------------------
# CẤU HÌNH NỀN TẢNG AI (GOOGLE CLOUD VERTEX AI / GEMINI API)
# -----------------------------------------------------------------------------
USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=YOUR_GCP_PROJECT_ID
GOOGLE_CLOUD_LOCATION=asia-southeast1

# Đường dẫn tuyệt đối tới tệp JSON Key trên máy của bạn (ngoài dự án Git):
GOOGLE_APPLICATION_CREDENTIALS=C:\gcp-keys\your-gcp-key.json

# (Để trống khi đã bật USE_VERTEXAI=true)
GEMINI_API_KEY=
OPENAI_API_KEY=

# -----------------------------------------------------------------------------
# CẤU HÌNH BỘ LƯU TRỮ VECTOR (QDRANT / CHROMADB)
# -----------------------------------------------------------------------------
VECTOR_DB_BACKEND=qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

CHROMA_HOST=localhost
CHROMA_PORT=8000
```

---

## 3. KHỞI CHẠY BẰNG DOCKER COMPOSE (KHUYÊN DÙNG - 1 CLICK)

Phương pháp khởi chạy bằng Docker Compose giúp tự động đóng gói toàn bộ FastAPI Backend, Streamlit UI, Qdrant/ChromaDB và n8n Multi-Agent Workflow Engine.

### Bước 1: Khởi chạy các Dịch vụ Cốt lõi (FastAPI, Streamlit, Vector DBs)
Mở terminal tại thư mục gốc của dự án và chạy lệnh:

```powershell
docker compose up -d --build
```

*Lệnh trên sẽ tự động mount tệp GCP Key từ đường dẫn ngoài máy vào container theo chế độ Read-Only.*

### Bước 2: Khởi chạy n8n Multi-Agent Workflow Engine
Chuyển sang thư mục `n8n-docker/` và khởi chạy n8n container:

```powershell
cd n8n-docker
docker compose up -d --force-recreate
cd ..
```

*Container n8n sẽ tự động đọc chung các thông số cấu hình từ tệp `.env` thư mục gốc.*

---

### DANH SÁCH CÁC CỔNG DỊCH VỤ DỰ ÁN:

| Dịch vụ | Địa chỉ URL truy cập | Chức năng |
| :--- | :--- | :--- |
| **Streamlit Testing Studio** | [http://localhost:8501](http://localhost:8501) | Giao diện Chatbot sư phạm, Ingestion OCR & Mentor Studio. |
| **FastAPI REST API Docs** | [http://localhost:8080/docs](http://localhost:8080/docs) | Tài liệu Swagger UI cho các API Backend. |
| **n8n Workflow Dashboard** | [http://localhost:5678](http://localhost:5678) | Giao diện trực quan hóa và quản lý luồng Multi-Agent. |
| **Qdrant Vector Storage UI** | [http://localhost:6333/dashboard](http://localhost:6333/dashboard) | Giao diện xem dữ liệu Vector & Payload. |

---

## 4. KHỞI CHẠY BẰNG PYTHON CỤC BỘ (TỦY CHỌN LOCAL RUN)

Nếu muốn phát triển hoặc gỡ lỗi trực tiếp mã nguồn Python mà không dùng Docker cho ứng dụng:

### Bước 1: Tạo môi trường ảo và cài đặt thư viện
```powershell
python -m venv .venv
# Activate môi trường ảo:
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### Bước 2: Khởi chạy Vector DB (Qdrant) bằng Docker
```powershell
docker run -d --name qdrant_server -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
```

### Bước 3: Khởi chạy FastAPI Backend
```powershell
uvicorn src.api.main:app --host 0.0.0.0 --port 8080 --reload
```

### Bước 4: Khởi chạy Streamlit Web App (Terminal thứ 2)
```powershell
streamlit run streamlit_app.py
```

---

## 5. NẠP VÀ ĐÁNH CHỈ MỤC SÁCH GIÁO KHOA (DATA INGESTION)

Hệ thống cung cấp tệp script tự động nạp toàn bộ dữ liệu SGK Toán 3 (Tập 1, Tập 2) và Khoa học Lớp 4 vào CSDL Vector Qdrant/ChromaDB.

### Cách 1: Chạy script nạp tự động qua Terminal
```powershell
python run_ingest.py
```

### Cách 2: Nạp trực tiếp qua Giao diện Streamlit UI
1. Truy cập [http://localhost:8501](http://localhost:8501).
2. Chuyển sang Tab **Nạp tài liệu & OCR**.
3. Tải tệp PDF SGK mới lên, chọn Môn học (`math` / `science`) và bấm nút Kích hoạt OCR & Ingestion.

---

## 6. KIỂM THỬ VÀ XÁC MINH HỆ THỐNG (TESTING & VERIFICATION)

### 1. Kiểm thử Luồng Tạo Đề Thi & Chấm Bài Thi Mentor (End-to-End Test)
Chạy script kiểm thử toàn trình quy trình sinh đề thi Toán 4, sinh bài làm 50% điểm và chấm bài chẩn đoán lỗi sai:

```powershell
python scratch/test_math4_e2e.py
```

*Kết quả chẩn đoán lỗi sai `weak_topics` và điểm số sẽ được xuất ra tệp `scratch/grading_result.json`.*

### 2. Kiểm thử Manual trên Streamlit Mentor Studio
1. Truy cập [http://localhost:8501](http://localhost:8501).
2. Vào Tab **Thiết kế đề thi (Mentor)** -> Chuyển sang Sub-tab **2. Chấm Bài & Phân Tích Chủ Đề Yếu**.
3. Nhấp vào nút **Nạp Đề Thi, Barem & Bài Làm Mẫu (Lớp 4 - 50% Điểm)** để tự động điền dữ liệu test mẫu 1-click.
4. Bấm nút **Chấm Bài Thi & Phân Tích Lỗi Sai** để xem điểm số, nhận xét và các thẻ chẩn đoán `weak_topics`.

### 3. Kiểm thử n8n RAG Webhook qua cURL
```powershell
curl -X POST http://localhost:5678/webhook/rag-math-assistant `
  -H "Content-Type: application/json" `
  -d '{"prompt": "Giải thích cho em khái niệm hình vuông"}'
```

---

## 7. XỬ LÝ SỰ CỐ THƯỜNG GẶP (TROUBLESHOOTING)

| Hiện tượng / Lỗi | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| **`401 / 403 Invalid Grant: account not found`** | Chìa khóa GCP Service Account bị hủy hoặc vô hiệu hóa trên GCP Console. | Cấp chìa khóa JSON mới từ Google Cloud Console, lưu ngoài thư mục code và trỏ lại biến `GOOGLE_APPLICATION_CREDENTIALS` trong `.env`. |
| **`File /app/gcp-key.json was not found`** | Đường dẫn `GOOGLE_APPLICATION_CREDENTIALS` trong `.env` bị sai hoặc tệp không tồn tại. | Kiểm tra lại đường dẫn tệp JSON key trên máy host và chạy `docker compose up -d --force-recreate` để mount lại. |
| **`Connection Refused: host.docker.internal:8080`** | Container FastAPI backend chưa khởi chạy hoặc bị lỗi. | Chạy `docker ps` kiểm tra container `math_assistant_app`. Xem log bằng `docker logs math_assistant_app`. |
| **`429 Resource Exhausted`** | Vượt quá giới hạn Rate Limit của Gemini API. | Thuật toán Exponential Backoff tự động retry sau vài giây. Hoặc nâng cấp Quota GCP. |
