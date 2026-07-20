# Hướng Dẫn Vận Hành Toàn Bộ Pipeline Bằng Docker

Tài liệu này hướng dẫn chi tiết cách chạy toàn bộ hệ thống Trợ lý Học tập SGK Toán 3 (bao gồm quy trình OCR sách, nạp cơ sở dữ liệu Vector và chạy chatbot) thông qua các container Docker.

---

## 1. Yêu Cầu Chuẩn Bị (Prerequisites)

1.  **Cài đặt Docker & Docker Compose** trên máy của bạn.
2.  **Thông tin xác thực Google Cloud (Vertex AI):**
    *   Tải về tệp khoá JSON của Service Account có vai trò **Vertex AI User** trong dự án Google Cloud của bạn.
    *   Lưu tệp này vào thư mục `data/` với tên: **`gcp-key.json`** (đường dẫn: `data/gcp-key.json`).
3.  **Cấu hình tệp môi trường `.env`:**
    *   Đảm bảo tệp `.env` ở thư mục gốc có các khai báo sau:
        ```env
        USE_VERTEXAI=true
        GOOGLE_CLOUD_PROJECT=gemini-chatbot-436001
        GOOGLE_CLOUD_LOCATION=asia-southeast1  # Hoặc khu vực của bạn (ví dụ: us-central1)
        ```

---

## 2. Quy Trình Vận Hành Từng Bước (Step-by-Step Guide)

### Bước 1: Khởi động cơ sở dữ liệu ChromaDB
Chạy lệnh sau để khởi động container ChromaDB server chạy ngầm:
```powershell
docker compose up -d
```
*Lưu ý: Lệnh này cũng sẽ khởi động ứng dụng chatbot ngầm, bạn có thể kiểm tra trạng thái các dịch vụ bằng lệnh `docker compose ps`.*

### Bước 2: Chạy kiểm thử đơn vị (Unit Tests)
Trước khi chạy nạp dữ liệu, bạn nên kiểm tra xem cấu hình mã nguồn và môi trường container đã chuẩn chưa:
```powershell
docker compose exec math-assistant python -m unittest tests/test_agent.py
```
*Đảm bảo kết quả hiển thị `OK` (10 tests passed).*

### Bước 3: Chạy Ingestion (Nạp dữ liệu Sách giáo khoa)
Tiến hành chạy OCR các hình ảnh trang sách từ tệp PDF bằng Vertex AI, tạo vector nhúng (embedding) và nạp vào ChromaDB:
```powershell
docker compose exec math-assistant python run_ingest.py
```
*   **Chế độ mặc định:** Tiến trình sẽ ưu tiên tải dữ liệu từ cache `data/processed_book_data.json` nếu đã có sẵn từ trước để tiết kiệm quota API.
*   **Chế độ nạp lại từ đầu (Force OCR):** Nếu bạn thay đổi file PDF hoặc muốn quét lại OCR toàn bộ sách giáo khoa từ đầu, hãy chạy lệnh kèm tham số `--force`:
    ```powershell
    docker compose exec math-assistant python run_ingest.py --force
    ```

### Bước 4: Kiểm tra trạng thái Cơ sở dữ liệu Vector
Chạy công cụ chẩn đoán nhanh để xem dữ liệu đã được index thành công vào ChromaDB chưa:
```powershell
docker compose exec math-assistant python data/inspect_db.py
```

### Bước 5: Trò chuyện trực tiếp với Chatbot (Interactive Chat)
Khởi chạy giao diện dòng lệnh trò chuyện tương tác với cô giáo ảo:
```powershell

```docker compose run math-assistant
Tại giao diện này, bạn có thể đặt các câu hỏi tiếng Việt, ví dụ:
*   *Bạn:* `Giải bài 2 trang 15 tập 1`
*   *Cô giáo:* [Phản hồi lý giải từng bước và trích dẫn nguồn sách]
*   *(Nhập `/exit` hoặc `/quit` để thoát khỏi chế độ chat).*

---

## 3. Các Lệnh Hữu Ích Khác (Utility Commands)

*   **Xây dựng lại (Build) Image:** Sau khi bạn chỉnh sửa bất kỳ tệp mã nguồn nào (như `requirements.txt` hoặc code trong thư mục `src/`), hãy build lại container:
    ```powershell
    docker compose build
    ```
*   **Dừng các dịch vụ đang chạy ngầm:**
    ```powershell
    docker compose down
    ```
*   **Xem logs hoạt động của các container:**
    ```powershell
    docker compose logs -f
    ```
*   **Kiểm tra API của ChromaDB trực tiếp từ trình duyệt máy cá nhân:**
    *   Heartbeat: [http://localhost:8000/api/v2/heartbeat](http://localhost:8000/api/v2/heartbeat)
    *   Collections: [http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database/collections](http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database/collections)
*   **Giao diện quản lý trực quan (ChromaDB Web UI):**
    *   Hệ thống đã tích hợp sẵn giao diện quản trị **ChromaDB Admin**.
    *   Truy cập qua trình duyệt của bạn tại địa chỉ: **[http://localhost:3000](http://localhost:3000)**.
    *   *Hướng dẫn kết nối:* Khi trang web hiển thị, hãy điền địa chỉ máy chủ ChromaDB của bạn là **`http://localhost:8000`** vào ô kết nối để hiển thị toàn bộ collection và dữ liệu.
