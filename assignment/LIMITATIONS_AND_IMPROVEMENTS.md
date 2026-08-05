# BÁO CÁO TỔNG KẾT, NHẬN DIỆN GIỚI HẠN VÀ HƯỚNG CẢI TIẾN HỆ THỐNG
## Tài Liệu Đánh Giá Năng Lực Thực Thi Và Lộ Trình Phát Triển Sản Phẩm LMS Mini

Tài liệu này trình bày một cách trung thực và khách quan về các nội dung đã hoàn thành, các nội dung chưa hoàn thành, các giới hạn kỹ thuật hiện tại của hệ thống LMS Mini, cùng với định hướng phát triển sản phẩm hướng tới mô hình Multi-tenant phục vụ giáo dục phổ thông và đào tạo doanh nghiệp.

---

## 1. TỔNG QUAN VÀ MỤC TIÊU CHIẾN LƯỢC (STRATEGIC GOALS)

Hệ thống LMS Mini tích hợp trí tuệ nhân tạo được định vị không chỉ là một cổng thông tin hỏi đáp thông thường, mà hướng tới trở thành một **Nền tảng quản lý học tập Multi-tenant (Multi-tenant LMS)** thế hệ mới.

### Đối tượng khách hàng mục tiêu:
1.  **Môi trường Giáo dục Phổ thông (K-12):** Nơi các trường học, sở giáo dục có nhu cầu quản lý chương trình học chuẩn của Bộ Giáo dục và Đào tạo, phân quyền tài liệu chặt chẽ giữa Ban giám hiệu, Giáo viên và các khối lớp Học sinh, đồng thời hỗ trợ giáo viên giảm tải áp lực chấm bài tự luận.
2.  **Môi trường Doanh nghiệp (Corporate Training):** Nơi các công ty, tổ chức có nhu cầu đào tạo nội bộ, quản lý các tài liệu quy trình, tiêu chuẩn kỹ thuật có tính bảo mật cao (chỉ lưu hành nội bộ), yêu cầu phân quyền chi tiết theo phòng ban (Department-level Isolation) và kiểm tra năng lực nhân viên tự động.

---

## 2. NỘI DUNG ĐÃ HOÀN THÀNH (PROJECT ACHIEVEMENTS)

Với triết lý thiết kế **"Đơn giản - Rõ ràng - Hoạt động ổn định"**, dự án đã hoàn thành vượt trội các cấu phần cốt lõi mang tính nền tảng, giải quyết trực diện 3 bài toán sư phạm đặt ra:

### A. Hạ tầng kỹ thuật và Core RAG ổn định
*   Xây dựng thành công bộ dịch vụ REST API bằng FastAPI hỗ trợ chuyển đổi linh hoạt cơ sở dữ liệu vector (`VECTOR_DB_BACKEND = qdrant | chromadb`) hoạt động chính xác và có hiệu năng cao.
*   Thiết kế hoàn chỉnh quy trình nạp tài liệu tự động (`Ingestion Pipeline`) tích hợp mô hình đa phương thức `gemini-2.5-flash` để xử lý triệt để ảnh quét sách giáo khoa, tự động trích xuất cấu trúc chương học, bài học và số trang thực tế.
*   Phát triển thuật toán tìm kiếm lai nâng cao (`Hybrid Search`) kết hợp tìm kiếm ngữ nghĩa Dense Semantic và tìm kiếm từ khóa Sparse BM25, nâng cao độ chính xác của ngữ cảnh RAG bằng cơ chế hợp nhất thứ hạng nghịch đảo Reciprocal Rank Fusion (RRF) và reranking theo gợi ý trang vật lý.

### B. Bộ não điều phối Multi-Agent trên n8n
*   Thiết lập hoàn chỉnh luồng xử lý Multi-Agent trên n8n để tối ưu hóa context window và cá nhân hóa phong cách giảng dạy thông qua các Agent chuyên gia (`suggestive_tutor`, `direct_solver`, `barem_review`, `theory_explanation`, `exercise_generator`).
*   Tích hợp thành công cơ chế quản lý prompts tập trung (`Prompt Registry`) sử dụng SQLite làm bộ nhớ lưu trữ phiên bản, hỗ trợ cập nhật thay đổi tức thời (hot-reload) và rollback phiên bản prompt của các Agent mà không cần tắt hệ thống hoặc sửa file workflow n8n.
*   Xây dựng thành công rào chắn kiểm định chất lượng bám sát ngữ cảnh gốc (`Verifier QA Agent`) ở bước cuối cùng để rà soát lỗi học thuật và triệt tiêu hoàn toàn hiện tượng ảo giác học thuật (hallucination) của AI trước khi trả về cho người dùng.

### C. Giao diện LMS Testing Studio trực quan (Mức độ Prototype/Demo)
*   *Hiện trạng thực tế:* Hệ thống hiện đã xây dựng hoàn chỉnh giao diện thử nghiệm tương tác thông qua công cụ Streamlit. Giao diện này tích hợp hoàn hảo khu vực chatbot tương tác trực tiếp với luồng Multi-Agent của n8n, hỗ trợ hộp thoại lựa chọn phong cách hỗ trợ (intent selection popup) khi gặp câu hỏi mơ hồ (`no_intent`). Ngoài ra, Streamlit cũng cung cấp phân hệ **Mentor Studio** để thử nghiệm tạo đề thi và chấm điểm tự luận theo barem có chẩn đoán tự động.
*   *Định hướng thực thi sản phẩm:* Cần làm rõ rằng giao diện Streamlit hiện tại **chỉ đóng vai trò làm phiên bản thử nghiệm chức năng (Prototype/Demo)** để xác minh nhanh các kịch bản sử dụng. Để đưa vào vận hành thương mại hóa thực tế, hệ thống bắt buộc phải được xây dựng lại thành một **ứng dụng Web chi tiết và hoàn chỉnh hơn** sử dụng các framework phát triển Frontend hiện đại (như React, Angular hoặc Vue.js) kết hợp với thư viện quản lý trạng thái tập trung (State Management), xây dựng các bảng điều khiển trực quan (Dashboard) đa dạng cho từng nhóm vai trò Học sinh, Giáo viên và Quản trị viên của trường học/doanh nghiệp.

---

## 3. NỘI DUNG CHƯA HOÀN THÀNH VÀ NGUYÊN NHÂN QUYẾT ĐỊNH (TECHNICAL DECISIONS)

Trong quá trình thực hiện, một số tính năng nâng cao đã được tạm hoãn hoặc đơn giản hóa để ưu tiên tính ổn định tối đa của hệ thống:

### A. Phân tách vật lý cơ sở dữ liệu Multi-tenant (Physical Multi-tenant Database Partitioning)
*   *Hiện trạng:* Hệ thống hiện tại đang hỗ trợ cô lập dữ liệu ở mức độ logic thông qua siêu dữ liệu `org_id` và tách biệt collection theo môn học (`subject_field`), chưa thực hiện phân tách vật lý hoàn toàn cơ sở dữ liệu (tách riêng server database vật lý cho từng trường học/doanh nghiệp).
*   *Nguyên nhân:* Để đảm bảo một giải pháp hoạt động ổn định và hiệu quả về mặt chi phí đầu tư hạ tầng trong giai đoạn thử nghiệm đầu tiên, việc cách ly logic bằng metadata filter trong Qdrant là phương án tối ưu nhất. Cơ chế này vừa đảm bảo an toàn phân quyền, vừa tránh được độ phức tạp khi phải quản lý và đồng bộ hóa hàng trăm kết nối database vật lý khác nhau cùng lúc.

### B. Tự động đồng bộ hóa lịch sử trò chuyện dài hạn vào bộ nhớ ngoài (External Database Session Persistence)
*   *Hiện trạng:* Lịch sử trò chuyện của Chatbot hiện tại được lưu trữ tạm thời trong Streamlit Session State và n8n context memory theo từng phiên chạy (Temporary Context Session), tự động làm mới khi người dùng bấm nút xóa lịch sử hoặc khởi tạo lại trang.
*   *Nguyên nhân:* Việc sử dụng Session State tạm thời giúp bảo vệ quyền riêng tư của người học theo tiêu chuẩn an toàn thông tin học đường, đồng thời tăng tốc độ phản hồi đáng kể của chatbot do không phải thực hiện các tác vụ đọc/ghi đè liên tục xuống ổ đĩa cứng hoặc database ngoài trong giai đoạn MVP.
*   *Yêu cầu hạ tầng nâng cấp:* Cần làm rõ rằng để thực hiện được cơ chế lưu trữ lịch sử trò chuyện dài hạn (Session Persistence) xuống cơ sở dữ liệu ngoài (như PostgreSQL, MongoDB hoặc Redis), hệ thống **bắt buộc phải có một tầng quản lý toàn diện bao bọc ở phía trên**. Tầng quản lý này bao gồm các cấu phần kiến trúc phức tạp sau:
    *   **Kiến trúc phần mềm bao phủ (Software Architecture Wrapper):** Tầng trung gian kết nối lưu trữ giữa LLM Engine, Workflow n8n và Database ngoài để điều phối việc đồng bộ hóa dữ liệu bất đồng bộ mà không gây nghẽn luồng chatbot.
    *   **Hệ thống quản trị và định danh người dùng (User Identity & Access Management - IAM):** Các dịch vụ xác thực, đăng nhập/đăng xuất (như JWT, Auth0, Keycloak) để liên kết chính xác Session ID với tài khoản của từng học viên cụ thể trong trường học hoặc doanh nghiệp.
    *   **Cơ chế kiểm soát an toàn thông tin và vòng đời phiên (Session Lifecycle & Security Controls):** Bộ lọc mã hóa phiên truyền tải (Session Encryption), chính sách tự động hủy phiên khi hết hạn (TTL - Time to Live) và tuân thủ các quy định pháp lý về bảo vệ dữ liệu người dùng (như GDPR hoặc luật bảo vệ thông tin trẻ em).

---

## 4. NHẬN DIỆN GIỚI HẠN HIỆN TẠI (SYSTEM LIMITATIONS)

1.  **Giới hạn về mô hình chẩn đoán tiến trình tĩnh:** Cơ chế phân tích lỗi sai và chẩn đoán chủ đề yếu của học sinh trong phân hệ chấm điểm hiện tại đang được thực hiện theo lượt nộp bài đơn lẻ, chưa tự động liên kết kết quả của nhiều bài kiểm tra khác nhau trong quá khứ để vẽ biểu đồ xu hướng tiến bộ dài hạn.
2.  **Sự phụ thuộc vào cấu trúc tài liệu đầu vào:** RAG Hybrid Search hoạt động tốt nhất khi các trang sách giáo khoa được phân chia rõ ràng. Đối với các tài liệu có cấu trúc phi tuyến tính phức tạp (ví dụ: các trang sách bài tập có định dạng chia cột lồng nhau nhiều tầng), độ chính xác của việc trích xuất ngữ cảnh thô đôi khi vẫn bị ảnh hưởng bởi thứ tự đọc của OCR.

---

## 5. HƯỚNG CẢI TIẾN VÀ KẾ HOẠCH PHÁT TRIỂN (PRODUCT ROADMAP)

Để đưa hệ thống LMS Mini trở thành một nền tảng thương mại hóa mạnh mẽ, kế hoạch cải tiến trong phiên bản tiếp theo sẽ tập trung vào các nội dung trọng tâm sau:

### A. Kiến trúc Multi-tenant hoàn chỉnh (Complete Multi-tenant Isolation)
*   Nâng cấp tầng FastAPI Side để hỗ trợ tự động định tuyến truy vấn đến các Qdrant Namespaces biệt lập hoặc khởi tạo các cụm cơ sở dữ liệu nhỏ (Lite Database Instances) riêng biệt cho từng doanh nghiệp hoặc trường học khách hàng.
*   Xây dựng giao diện quản trị Admin Tenant Dashboard để các tổ chức tự quản lý danh mục tài liệu nội bộ, tự cấu hình quyền truy cập và tự kiểm soát hạn ngạch sử dụng API của đơn vị mình.

### B. Cá nhân hóa tài liệu và lộ trình học tập dựa trên kết quả kiểm tra (Data-Driven Personalized Learning Paths)
Đây là tính năng đột phá sẽ được ưu tiên triển khai ngay trong giai đoạn tiếp theo:
1.  **Cá nhân hóa tài liệu học tập theo người dùng (User-Level Document Personalization):**
    *   Sau mỗi bài kiểm tra tự luận/trắc nghiệm trên LMS, hệ thống sẽ lưu vết lịch sử điểm số và các nhãn chủ đề yếu (`weak_topics`) của riêng từng học viên vào cơ sở dữ liệu tiến trình.
    *   Khi học viên truy cập vào thư viện tài liệu, AI Agent sẽ tự động tạo sinh hoặc tùy biến lại nội dung tài liệu học tập chuẩn để tập trung giải thích kỹ hơn các mảng kiến thức học viên đó đang bị hổng, giúp tối ưu hóa thời gian tự học của từng cá nhân.
2.  **Tự động đề xuất lộ trình học tập riêng biệt (Dynamic Individual Learning Paths):**
    *   Phát triển mô-đun **Pathways Agent** chuyên biệt. Agent này sẽ đọc biểu đồ năng lực thời gian thực của học viên để tự động đề xuất lộ trình học tập tiếp theo.
    *   Ví dụ: Học sinh A đạt điểm yếu ở mảng Phép nhân sẽ được đề xuất quay lại học lại bài lý thuyết Khái niệm Phép nhân (Trang 10 SGK) kết hợp làm 5 bài tập gợi mở cấp độ Nhận biết; trong khi học sinh B đạt điểm tuyệt đối sẽ được hệ thống đề xuất thẳng tới lộ trình nâng cao học Phép chia và thử thách các bài toán Logic vận dụng cao.

---
*Tài liệu này đúc kết đánh giá năng lực thực thi và định hướng chiến lược phát triển hệ thống LMS Mini.*