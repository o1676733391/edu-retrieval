# BÀI TẬP KIỂM THỬ, DỮ LIỆU MẪU VÀ KỊCH BẢN ĐÀO TẠO
## Tài Liệu Hướng Dẫn Vận Hành Sư Phạm Cho Hệ Thống LMS Mini

Tài liệu này cung cấp các kịch bản thực tế, cấu trúc dữ liệu mẫu (JSON) và các câu hỏi kiểm thử tiêu chuẩn giúp xác minh khả năng giải quyết các thách thức sư phạm của hệ thống LMS Mini.

---

## 1. DỮ LIỆU SÁCH GIÁO KHOA MẪU (REFERENCE TEXTBOOK SAMPLES)

Trong thư mục [`data-samples/`](file:///d:/Project%20Local/OCR-STEM/data-samples/) của dự án, hệ thống lưu trữ hai cuốn sách giáo khoa Toán 3 chính thức để huấn luyện và kiểm thử RAG:
* `toan-3-tap-1.pdf`: Sách Toán lớp 3, tập 1 (Bộ sách Kết nối tri thức với cuộc sống).
* `toan-3-tap-2.pdf`: Sách Toán lớp 3, tập 2.

Học sinh hoặc giáo viên có thể nạp các trang sách này vào hệ thống qua giao diện **OCR Ingestion Tab** bằng cách chỉ định số trang thực tế (Physical Page) hoặc số trang PDF.

---

## 2. KỊCH BẢN THỰC TẾ GIẢI QUYẾT 3 PHÂN KHÚC HỌC SINH (STUDENT SEGMENTS CASE STUDY)

### Kịch bản: Học sinh hỏi giải "Bài tập 2 trang 6" sách giáo khoa Toán lớp 3
* **Dữ liệu RAG trích xuất từ trang 6 SGK:**
 ```text
 2 Viết số rồi đọc số, biết số đó gồm:
 a) 4 chục nghìn, 2 nghìn, 5 trăm và 3 chục.
 b) 8 nghìn, 8 trăm, 8 chục và 8 đơn vị...
 ```

#### Kịch bản 1: Học sinh thuộc nhóm CẦN HỖ TRỢ (Học chậm, rụt rè)
* **Mô-đun hoạt động:** `suggestive_tutor` (Gia sư Socratic)
* **Phản hồi của AI:**
 > "*Chào con! Thầy/Cô rất vui được đồng hành cùng con ôn tập hôm nay. Thầy/Cô đã thấy bài tập 2 trang 6 yêu cầu chúng ta viết và đọc các số rồi.*
 >
 > *Ở câu a, đề bài cho chúng ta biết số này gồm: **4 chục nghìn, 2 nghìn, 5 trăm và 3 chục**.*
 > *Con hãy nhìn kỹ xem, ở hàng chục nghìn là chữ số mấy nhỉ? Và số này có chữ số đơn vị nào không con?*
 > *Con thử suy nghĩ và viết lại chữ số hàng chục nghìn và hàng nghìn trước cho thầy cô xem nhé! Cố lên con, con làm được mà!*"
* **Mục tiêu sư phạm:** Không cho kết quả ngay, chia nhỏ độ khó, động viên tinh thần để học sinh tự tin tương tác, loại bỏ cảm giác sợ bài toán khó.

#### Kịch bản 2: Học sinh thuộc nhóm XUẤT SẮC (Nhanh nhạy, dễ nản)
* **Mô-đun hoạt động:** `exercise_generator` (Biên soạn bài tập thách thức)
* **Phản hồi của AI:**
 > "*Chào con! Con đã nắm bắt rất nhanh bài tập 2 trang 6 rồi đấy. Để thử thách năng lực tư duy xuất sắc của con, thầy cô đã thiết kế riêng cho con 3 bài toán nâng cao dưới đây:*
 >
 > **Bài 1 (Nhận biết):** Viết số gồm: 9 chục nghìn, 3 nghìn, 7 trăm, 2 chục và 5 đơn vị.
 > **Bài 2 (Vận dụng):** Viết số lớn nhất có 5 chữ số khác nhau biết chữ số hàng chục nghìn là 4 và hàng trăm là 5.
 > **Bài 3 (Thử thách logic):** Tìm số tự nhiên có 5 chữ số, biết rằng nếu viết thêm chữ số 2 vào trước số đó ta được số mới gấp 3 lần số cũ.
 >
 > *Lời giải chi tiết và đáp số thầy cô đã ẩn ở nút bên dưới. Con hãy tự mình giải hết ra nháp rồi click vào để đối chiếu xem mình đúng bao nhiêu bài nhé!*
 > <details><summary>Xem gợi ý giải và Đáp án</summary>...[Chi tiết giải nâng cao]...</details>"
* **Mục tiêu sư phạm:** Kích thích tư duy chinh phục, cá nhân hóa độ khó bằng cách cung cấp thử thách mở rộng, tránh để học sinh xuất sắc lãng phí thời gian vào bài tập quá dễ.

---

## 3. DỮ LIỆU MẪU CHẤM ĐỀ THI TỰ LUẬN NHẤT QUÁN (RUBRIC-BASED GRADING JSON)

Dưới đây là một kịch bản dữ liệu hoàn chỉnh để kiểm thử chức năng **Grade & Feedback** nhất quán cho phần thi tự luận và trắc nghiệm của phân hệ **Mentor Studio**.

### A. Dữ liệu Barem Điểm Chi Tiết (Barem JSON)
```json
{
 "test_id": "TEST_MATH4_SAMPLE_E2E",
 "total_score": 10.0,
 "mcq_answers": [
 {"question_id": "MCQ_1", "correct_option": "B", "score": 1.0, "explanation": "45 000 + 35 000 = 80 000"},
 {"question_id": "MCQ_2", "correct_option": "A", "score": 1.0, "explanation": "Số 56 789 nhỏ nhất"}
 ],
 "essay_answers": [
 {
 "question_id": "ESSAY_1",
 "score": 2.0,
 "solution_steps": [
 {"step": 1, "description": "Đặt tính đúng hàng và thực hiện phép cộng các hàng đơn vị, chục, trăm, nghìn: 34 567 + 23 412 = 57 979", "score": 2.0}
 ]
 },
 {
 "question_id": "ESSAY_2",
 "score": 2.0,
 "solution_steps": [
 {"step": 1, "description": "Tìm số kg gạo có trong mỗi bao: 45 : 5 = 9 (kg)", "score": 1.0},
 {"step": 2, "description": "Tìm số kg gạo trong 8 bao: 9 x 8 = 72 (kg)", "score": 1.0}
 ]
 }
 ]
}
```

### B. Bài Làm Thực Tế Của Học Sinh Nộp Lên (Student Submission Text)
```text
HỌC SINH: Trần Văn C - Lớp 4A
MÃ ĐỀ THI: TEST_MATH4_SAMPLE_E2E

PHẦN I: TRẮC NGHIỆM
Câu 1: B
Câu 2: A

PHẦN II: TỰ LUẬN
Câu tự luận 1 (ESSAY_1):
Lời giải:
34567 + 23412 = 57979. Con đặt tính ngoài nháp ra đúng kết quả này ạ.

Câu tự luận 2 (ESSAY_2):
Lời giải:
- Số kg gạo trong mỗi bao là: 45 : 5 = 9 kg.
- Số kg gạo của 8 bao là: 9 x 8 = 72 kg.
Đáp số: 72 kg.
```

---

## 4. KẾT QUẢ PHẢN HỒI VÀ CHẨN ĐOÁN CHỦ ĐỀ YẾU (AI DIAGNOSTICS REPORT)

Sau khi nộp bài làm mẫu trên qua cổng Mentor Studio, hệ thống tự động sinh ra báo cáo chấm điểm và đề xuất học tập mang tính cá nhân hóa cao:

### Báo cáo kết quả phản hồi của AI (AI Grading Feedback)
* **Tổng số điểm:** **10.0 / 10.0** (Tỷ lệ chính xác 100%)
* **Đánh giá chung:** "*Con đã hoàn thành bài thi một cách xuất sắc! Đặt tính toán và suy luận các bước của bài toán đố rút về đơn vị vô cùng rõ ràng và chuẩn xác. Hãy tiếp tục phát huy phong độ này con nhé!*"

* **Nếu học sinh làm sai bước 2 câu ESSAY_2 (Ví dụ viết phép tính thành `9 + 8 = 17 kg`):**
 * **Điểm chấm được:** **9.0 / 10.0**
 * **Báo cáo Chẩn đoán lỗi hổng kiến thức tự động (Weak Topics Diagnostics):**
 ```json
 {
 "weak_topics": [
 {
 "topic": "Bài toán rút về đơn vị (Phép toán gấp lên nhiều lần)",
 "severity": "Trung bình",
 "description": "Học sinh đã thực hiện đúng bước 1 (rút về đơn vị: 45:5=9), nhưng ở bước 2 học sinh bị nhầm lẫn giữa phép toán cộng dồn (+ 8) và phép toán gấp lên nhiều lần (nhân với 8), dẫn đến kết quả sai (9+8=17 thay vì 9x8=72).",
 "recommendation": "Phụ huynh nên cho con ôn tập lại các dạng toán có lời văn liên quan đến khái niệm 'gấp một số lên nhiều lần'. Thực hành làm lại bài tập trang 20 sách bài tập Toán lớp 4 tập 1."
 }
 ]
 }
 ```

---
*Tài liệu này là một phần của bộ hồ sơ kịch bản sư phạm nền tảng LMS Mini.*