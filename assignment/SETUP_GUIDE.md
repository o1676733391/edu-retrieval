# HƯỚNG DẪN CÀI ĐẶT VÀ KHỞI CHẠY HỆ THỐNG MINI-LMS
## Trợ Lý Giáo Dục Multi-Agent (Multi-Agent RAG System) - Hướng Dẫn Kỹ Thuật Chi Tiết

Tài liệu này hướng dẫn từng bước để thiết lập môi trường, cấu hình khóa bảo mật, khởi chạy nền tảng LMS tích hợp AI bằng Docker Compose hoặc Python cục bộ.

---

## 1. YÊU CẦU HẠ TẦNG VÀ MÔI TRƯỜNG (PREREQUISITES)

### Hệ điều hành được hỗ trợ:
* **Windows 10/11** (Sử dụng PowerShell hoặc WSL2).
* **Linux** (Ubuntu 20.04 trở lên).
* **macOS** (Cả phiên bản chip Intel và Apple Silicon).

### Các công cụ cần cài đặt sẵn:
* **Docker & Docker Compose** (Docker Desktop v20.10+ trở lên).
* **Python 3.10+** trở lên (Nếu chạy local không qua Docker, khuyên dùng Python 3.12).
* **Khóa API AI (Một trong hai loại):**
 * **GCP Service Account JSON Key** (Được cấp quyền sử dụng Vertex AI API).
 * **Gemini API Key** (Lấy từ Google AI Studio - nhanh chóng và miễn phí).

---

## 2. CẤU HÌNH KHÓA BẢO MẬT & TỆP MÔI TRƯỜNG (.ENV)

### Bước 1: Bảo vệ file khóa dịch vụ (GCP Service Account Key)
Để đảm bảo an ninh, tránh việc vô tình đẩy khóa bảo mật lên các kho mã nguồn công khai (GitHub/GitLab):
1. Tạo một thư mục riêng biệt **nằm ngoài thư mục dự án**, ví dụ:
 * Windows: `C:\gcp-keys\your-gcp-key.json`
 * Linux / macOS: `/home/username/gcp-keys/your-gcp-key.json`
2. Lưu tệp JSON Key được cấp từ Google Cloud Console vào thư mục này.

### Bước 2: Tạo tệp cấu hình `.env`
Tạo tệp `.env` tại thư mục gốc của dự án bằng cách sao chép tệp mẫu `.env.template` và thay đổi các giá trị:

```env
# -----------------------------------------------------------------------------
# CẤU HÌNH NỀN TẢNG AI (GCP VERTEX AI HOẶC GOOGLE AI STUDIO)
# -----------------------------------------------------------------------------
USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=asia-southeast1

# Đường dẫn tuyệt đối tới file JSON Key (ở ngoài thư mục git):
GOOGLE_APPLICATION_CREDENTIALS=C:\gcp-keys\your-gcp-key.json

# (Nếu dùng Google AI Studio, đặt USE_VERTEXAI=false và điền API Key vào đây):
GEMINI_API_KEY=your-gemini-api-key-from-ai-studio

# -----------------------------------------------------------------------------
# CẤU HÌNH LƯU TRỮ CHỈ MỤC VECTOR (QDRANT HOẶC CHROMADB)
# -----------------------------------------------------------------------------
VECTOR_DB_BACKEND=qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

CHROMA_HOST=localhost
CHROMA_PORT=8000
```

---

## 3. KHỞI CHẠY TỰ ĐỘNG BẰNG DOCKER COMPOSE (RECOMMENDED)

Phương pháp khởi chạy bằng Docker Compose giúp đóng gói toàn bộ các cấu phần (FastAPI Backend, Streamlit Frontend, các Vector DBs và n8n Engine) chỉ với **1 lệnh duy nhất**.

### Bước 1: Khởi chạy các dịch vụ LMS & Vector DB
Mở terminal tại thư mục gốc của dự án và chạy:

```bash
docker compose up -d --build
```
*Lưu ý: Docker-Compose tự động nạp đường dẫn khóa Service Account từ máy host và mount an toàn vào bên trong Container dưới quyền Read-Only (`:ro`).*

### Bước 2: Khởi chạy n8n Multi-Agent Workflow Engine
Chuyển sang thư mục `n8n-docker/` chứa tệp compose riêng biệt cho n8n và khởi động:

```bash
cd n8n-docker
docker compose up -d --force-recreate
cd ..
```

---

## 4. DANH SÁCH ĐỊA CHỈ TRUY CẬP CÁC CỔNG DỊCH VỤ (PORT MAPPING)

Sau khi khởi chạy thành công, bạn có thể truy cập các cổng dịch vụ trực tiếp qua trình duyệt web:

| Dịch vụ LMS | URL Truy cập cục bộ | Chức năng chi tiết |
| :--- | :--- | :--- |
| **Streamlit LMS Dashboard** | [http://localhost:8501](http://localhost:8501) | Giao diện tương tác Chatbot sư phạm, nạp sách OCR, và studio chấm bài tự luận của Mentor. |
| **n8n Workflow Dashboard** | ️ [http://localhost:5678](http://localhost:5678) | Thiết lập, theo dõi và cấu hình kéo thả sơ đồ Multi-Agent Sư Phạm. |
| **FastAPI REST API Docs** | [http://localhost:8080/docs](http://localhost:8080/docs) | Tài liệu Swagger UI để kiểm thử độc lập các API Vector, Ingestion và LLM Proxy. |
| **Qdrant Dashboard UI** | [http://localhost:6333/dashboard](http://localhost:6333/dashboard) | Giao diện trực quan xem các vector embeddings và trường metadata đã nạp. |

---

## 5. THIẾT LẬP LUỒNG MULTI-AGENT TRÊN N8N (WORKFLOW CONFIGURATION)

Để n8n bắt đầu nhận diện và điều khiển các Agent học tập:
1. Truy cập vào giao diện n8n: [http://localhost:5678](http://localhost:5678).
2. Tạo một Workflow mới trống.
3. Click vào menu góc trên cùng bên phải -> chọn **Import from File**.
4. Chọn tệp [`n8n-docker/rag_pedagogical_workflow.json`](file:///d:/Project%20Local/OCR-STEM/n8n-docker/rag_pedagogical_workflow.json) từ máy tính của bạn để nhập luồng.
5. Gạt nút **"Active"** ở góc trên bên phải n8n sang trạng thái màu xanh để kích hoạt Webhook chính thức.

---

## 6. KHỞI CHẠY BẰNG PYTHON CỤC BỘ (LOCAL RUN - KHÔNG DÙNG DOCKER)

Nếu muốn chạy trực tiếp trên máy chủ vật lý phục vụ phát triển hoặc debug mã nguồn:

### Bước 1: Cài đặt và kích hoạt môi trường ảo Python
```bash
python -m venv .venv
# Trên Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Trên Linux / macOS:
source .venv/bin/activate
```

### Bước 2: Cài đặt thư viện phụ thuộc
```bash
pip install -r requirements.txt
```

### Bước 3: Khởi chạy FastAPI Backend Server
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8080 --reload
```

### Bước 4: Khởi chạy Streamlit LMS UI Frontend (Trong một terminal mới)
```bash
streamlit run streamlit_app.py
```

---
*Tài liệu này thuộc bộ hồ sơ kỹ thuật LMS Mini.*