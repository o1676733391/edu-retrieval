# BỘ CÂU HỎI KIỂM THỬ PHÂN HỆ TẠO ĐỀ VÀ CHẤM BÀI (EXAM GENERATION & GRADING TEST SUITE)
## HỆ THỐNG TỰ ĐỘNG BIÊN SOẠN BÀI TẬP VÀ CHẤM ĐIỂM SƯ PHẠM

Tài liệu này quy định danh sách các trường hợp kiểm thử (Test Cases), quy chuẩn Payload Request gửi lên và Payload Response trả về chi tiết cho phân hệ Tạo đề (Exercise Generator) và Chấm bài (Barem Review).

---

## 1. QUY CHUẨN CẤU TRÚC PAYLOAD (API SCHEMA)

### 1.1. API Tạo Đề Bài Tập (Exercise Generator API - agent: "exercise_generator")

#### Request Payload (Payload Gửi lên Backend):
| Tên Field | Kiểu Dữ Liệu | Bắt Buộc | Giá Trị Mặc Định | Mô Tả Chức Năng |
| :--- | :---: | :---: | :---: | :--- |
| `message` | `string` | Có | — | Yêu cầu tạo đề bài tập hoặc chủ đề bài tập từ người dùng. |
| `agent_name` | `string` | Có | `"exercise_generator"` | Tên chuyên gia xử lý tạo đề. |
| `conversation_id` | `string` | Không | `null` | ID phiên hội thoại. |

#### Response Payload (Payload Trả về từ Backend):
| Tên Field | Kiểu Dữ Liệu | Mô Tả Chức Năng |
| :--- | :---: | :--- |
| `status` | `string` | Trạng thái xử lý ("success"). |
| `agent` | `string` | Trả về "exercise_generator". |
| `data.exercises` | `array[object]` | Mảng chứa đúng 3 bài tập theo 3 mức độ phân hóa. |
| `data.exercises[].index` | `integer` | Thứ tự bài tập (1, 2, 3). |
| `data.exercises[].level` | `string` | Mức độ bài tập ("Nhận biết/Thông hiểu", "Vận dụng", "Vận dụng cao - Thử thách"). |
| `data.exercises[].question` | `string` | Đề bài đầy đủ của bài tập (không chứa lời giải). |
| `data.exercises[].solution` | `object` | Hướng dẫn và đáp án chi tiết. |
| `data.exercises[].solution.steps` | `array[object]` | Mảng các bước giải chi tiết. |
| `data.exercises[].solution.steps[].step` | `integer` | Thứ tự bước giải. |
| `data.exercises[].solution.steps[].title` | `string` | Tên ngắn gọn của bước giải. |
| `data.exercises[].solution.steps[].expression` | `string` | Câu lời giải kèm phép tính và đơn vị. |
| `data.exercises[].solution.steps[].explanation` | `string` | Giải thích lý do/công thức áp dụng. |
| `data.exercises[].solution.conclusion` | `string` | Kết luận hoặc đáp số đầy đủ của bài tập. |

---

### 1.2. API Chấm Bài và Nhận Xét (Barem Review API - agent: "barem_review")

#### Request Payload (Payload Gửi lên Backend):
| Tên Field | Kiểu Dữ Liệu | Bắt Buộc | Giá Trị Mặc Định | Mô Tả Chức Năng |
| :--- | :---: | :---: | :---: | :--- |
| `message` | `string` | Có | — | Đề bài, barem điểm chuẩn và bài làm thực tế của học sinh. |
| `agent_name` | `string` | Có | `"barem_review"` | Tên chuyên gia xử lý chấm bài. |
| `conversation_id` | `string` | Không | `null` | ID phiên hội thoại. |

#### Response Payload (Payload Trả về từ Backend):
| Tên Field | Kiểu Dữ Liệu | Mô Tả Chức Năng |
| :--- | :---: | :--- |
| `status` | `string` | Trạng thái xử lý ("success"). |
| `agent` | `string` | Trả về "barem_review". |
| `data.greeting` | `string` | Lời chào và động viên ban đầu của giáo viên. |
| `data.score_rows` | `array[object]` | Bảng chấm điểm chi tiết từng phần theo barem. |
| `data.score_rows[].section` | `string` | Tên phần hoặc bước giải được chấm. |
| `data.score_rows[].barem_requirement` | `string` | Yêu cầu tương ứng trong barem điểm. |
| `data.score_rows[].student_work` | `string` | Đánh giá bài làm thực tế của học sinh ở phần này. |
| `data.score_rows[].score` | `string` | Điểm đạt được / Điểm tối đa của phần này (dạng "1.5 / 2"). |
| `data.total_score` | `string` | Tổng điểm đạt được / Tổng điểm tối đa (dạng "9.0 / 10"). |
| `data.advice` | `string` | Giải thích chi tiết phần làm sai và hướng dẫn từng bước làm đúng. |
| `data.encouragement` | `string` | Lời chúc và động viên để học sinh tiếp tục cố gắng. |

---

## 2. DANH SÁCH TEST CASES KIỂM THỬ PHÂN HỆ TẠO ĐỀ VÀ CHẤM BÀI

### Test Case 1: Tạo bộ bài tập phân hóa 3 mức độ về Phép nhân và Phép chia
* **Mục đích:** Kiểm tra khả năng tự động biên soạn 3 bài tập có độ khó tăng dần theo đúng định dạng JSON Schema.
* **Agent:** `exercise_generator`

* **Request Payload gửi lên:**
```json
{
  "agent_name": "exercise_generator",
  "message": "Hãy tạo cho tôi 3 bài tập về phép nhân và phép chia số có 2 chữ số phân hóa theo 3 mức độ.",
  "conversation_id": "test_gen_001"
}
```

* **Response Payload trả về:**
```json
{
  "status": "success",
  "agent": "exercise_generator",
  "conversation_id": "test_gen_001",
  "data": {
    "exercises": [
      {
        "index": 1,
        "level": "Nhận biết/Thông hiểu",
        "question": "Đặt tính rồi tính: 24 x 3 và 84 : 4.",
        "solution": {
          "steps": [
            {
              "step": 1,
              "title": "Thực hiện phép tính nhân",
              "expression": "24 x 3 = 72",
              "explanation": "Ta lấy 3 nhân 4 bằng 12, viết 2 nhớ 1. 3 nhân 2 bằng 6 thêm 1 bằng 7."
            },
            {
              "step": 2,
              "title": "Thực hiện phép tính chia",
              "expression": "84 : 4 = 21",
              "explanation": "Ta lấy 8 chia 4 được 2. 4 chia 4 được 1."
            }
          ],
          "conclusion": "Đáp số: 24 x 3 = 72 và 84 : 4 = 21"
        }
      },
      {
        "index": 2,
        "level": "Vận dụng",
        "question": "Một cửa hàng có 5 thùng táo, mỗi thùng chứa 18 kg táo. Hỏi cửa hàng đó có tất cả bao nhiêu ki-lô-gam táo?",
        "solution": {
          "steps": [
            {
              "step": 1,
              "title": "Tính tổng số ki-lô-gam táo",
              "expression": "Số ki-lô-gam táo cửa hàng có là: 18 x 5 = 90 (kg)",
              "explanation": "Lấy số ki-lô-gam táo trong một thùng nhân với tổng số thùng táo."
            }
          ],
          "conclusion": "Đáp số: 90 kg táo"
        }
      },
      {
        "index": 3,
        "level": "Vận dụng cao - Thử thách",
        "question": "Lớp 3A có 36 học sinh. Cô giáo chia đều học sinh thành 4 tổ, sau đó mỗi tổ lại chia thành 3 nhóm nhỏ. Hỏi mỗi nhóm nhỏ có bao nhiêu học sinh?",
        "solution": {
          "steps": [
            {
              "step": 1,
              "title": "Tính số học sinh trong mỗi tổ",
              "expression": "Số học sinh của mỗi tổ là: 36 : 4 = 9 (học sinh)",
              "explanation": "Lấy tổng số học sinh chia cho số tổ."
            },
            {
              "step": 2,
              "title": "Tính số học sinh trong mỗi nhóm nhỏ",
              "expression": "Số học sinh của mỗi nhóm nhỏ là: 9 : 3 = 3 (học sinh)",
              "explanation": "Lấy số học sinh một tổ chia cho số nhóm trong một tổ."
            }
          ],
          "conclusion": "Đáp số: 3 học sinh"
        }
      }
    ]
  }
}
```

---

### Test Case 2: Tạo bài tập Hình học (Chu vi và Diện tích) theo ngữ cảnh
* **Mục đích:** Kiểm tra khả năng tạo đề thi toán hình học bám sát nội dung chương trình học.
* **Agent:** `exercise_generator`

* **Request Payload gửi lên:**
```json
{
  "agent_name": "exercise_generator",
  "message": "Cho tôi đề bài tập ôn luyện tính chu vi và diện tích hình chữ nhật lớp 3.",
  "conversation_id": "test_gen_002"
}
```

* **Response Payload trả về:**
```json
{
  "status": "success",
  "agent": "exercise_generator",
  "conversation_id": "test_gen_002",
  "data": {
    "exercises": [
      {
        "index": 1,
        "level": "Nhận biết/Thông hiểu",
        "question": "Tính diện tích một hình chữ nhật có chiều dài 8 cm và chiều rộng 5 cm.",
        "solution": {
          "steps": [
            {
              "step": 1,
              "title": "Tính diện tích hình chữ nhật",
              "expression": "Diện tích hình chữ nhật là: 8 x 5 = 40 (cm²)",
              "explanation": "Áp dụng công thức lấy chiều dài nhân với chiều rộng cùng đơn vị đo."
            }
          ],
          "conclusion": "Đáp số: 40 cm²"
        }
      },
      {
        "index": 2,
        "level": "Vận dụng",
        "question": "Một mảnh vườn hình chữ nhật có chiều dài 15 m, chiều rộng kém chiều dài 6 m. Tính chu vi mảnh vườn đó.",
        "solution": {
          "steps": [
            {
              "step": 1,
              "title": "Tính chiều rộng mảnh vườn",
              "expression": "Chiều rộng mảnh vườn là: 15 - 6 = 9 (m)",
              "explanation": "Lấy chiều dài trừ đi phần chiều rộng kém."
            },
            {
              "step": 2,
              "title": "Tính chu vi mảnh vườn",
              "expression": "Chu vi mảnh vườn là: (15 + 9) x 2 = 48 (m)",
              "explanation": "Lấy chiều dài cộng chiều rộng rồi nhân với 2."
            }
          ],
          "conclusion": "Đáp số: 48 m"
        }
      },
      {
        "index": 3,
        "level": "Vận dụng cao - Thử thách",
        "question": "Một ô đất hình chữ nhật có chu vi 36 cm. Biết chiều dài gấp 2 lần chiều rộng. Tính diện tích ô đất đó.",
        "solution": {
          "steps": [
            {
              "step": 1,
              "title": "Tính nửa chu vi (tổng chiều dài và chiều rộng)",
              "expression": "Nửa chu vi ô đất là: 36 : 2 = 18 (cm)",
              "expression": "Lấy chu vi chia cho 2."
            },
            {
              "step": 2,
              "title": "Tính chiều rộng và chiều dài",
              "expression": "Chiều rộng là: 18 : (1 + 2) = 6 (cm), Chiều dài là: 6 x 2 = 12 (cm)",
              "explanation": "Áp dụng bài toán tìm hai số khi biết tổng và tỉ số."
            },
            {
              "step": 3,
              "title": "Tính diện tích ô đất",
              "expression": "Diện tích ô đất là: 12 x 6 = 72 (cm²)",
              "explanation": "Lấy chiều dài nhân với chiều rộng."
            }
          ],
          "conclusion": "Đáp số: 72 cm²"
        }
      }
    ]
  }
}
```

---

### Test Case 3: Chấm bài học sinh đạt điểm tối đa (Full Score Barem Review)
* **Mục đích:** Kiểm tra khả năng đánh giá bài làm đúng 100% các bước theo Barem điểm.
* **Agent:** `barem_review`

* **Request Payload gửi lên:**
```json
{
  "agent_name": "barem_review",
  "message": "Nhờ cô chấm bài cho con.\nĐề bài: Bác An nuôi 45 con gà. Bác đã bán đi 1/5 số gà đó. Hỏi bác An còn lại bao nhiêu con gà?\nBarem điểm:\n- Bước 1: Tính số gà đã bán (45 : 5 = 9 con) - 1.0 điểm\n- Bước 2: Tính số gà còn lại (45 - 9 = 36 con) - 1.0 điểm\nBài làm học sinh:\nSố gà bác An đã bán là: 45 : 5 = 9 (con)\nSố gà bác An còn lại là: 45 - 9 = 36 (con)\nĐáp số: 36 con gà",
  "conversation_id": "test_grade_001"
}
```

* **Response Payload trả về:**
```json
{
  "status": "success",
  "agent": "barem_review",
  "conversation_id": "test_grade_001",
  "data": {
    "greeting": "Chào con, cô rất khen ngợi bài làm rất xuất sắc và chỉn chu của con!",
    "score_rows": [
      {
        "section": "Bước 1: Tính số gà đã bán",
        "barem_requirement": "Viết đúng lời giải và phép tính 45 : 5 = 9 (con)",
        "student_work": "Con trình bày đúng câu lời giải và tính chính xác 45 : 5 = 9 con.",
        "score": "1.0 / 1.0"
      },
      {
        "section": "Bước 2: Tính số gà còn lại",
        "barem_requirement": "Viết đúng lời giải và phép tính 45 - 9 = 36 (con)",
        "student_work": "Con viết đúng câu lời giải và thực hiện phép trừ 45 - 9 = 36 con rất chuẩn xác.",
        "score": "1.0 / 1.0"
      }
    ],
    "total_score": "2.0 / 2.0",
    "advice": "Bài làm của con hoàn hảo cả về lời giải, phép tính lẫn đáp số.",
    "encouragement": "Con hãy giữ vững phong độ học tập tuyệt vời này nhé!"
  }
}
```

---

### Test Case 4: Chấm bài học sinh tính sai phép tính (Partial Score Barem Review)
* **Mục đích:** Kiểm tra khả năng phát hiện lỗi tính toán sai, trừ điểm chính xác theo phần và đưa ra lời khuyên sư phạm dịu dàng.
* **Agent:** `barem_review`

* **Request Payload gửi lên:**
```json
{
  "agent_name": "barem_review",
  "message": "Nhờ thầy chấm giúp bài toán này.\nĐề bài: Có 36 quả cam chia đều vào 4 đĩa. Hỏi 3 đĩa như thế có bao nhiêu quả cam?\nBarem điểm:\n- Tìm số cam trong 1 đĩa: 36 : 4 = 9 (quả) (1.0 điểm)\n- Tìm số cam trong 3 đĩa: 9 x 3 = 27 (quả) (1.0 điểm)\nBài làm học sinh:\nSố quả cam trong 1 đĩa là: 36 : 4 = 9 (quả)\nSố quả cam trong 3 đĩa là: 9 x 3 = 24 (quả)\nĐáp số: 24 quả cam",
  "conversation_id": "test_grade_002"
}
```

* **Response Payload trả về:**
```json
{
  "status": "success",
  "agent": "barem_review",
  "conversation_id": "test_grade_002",
  "data": {
    "greeting": "Thầy chào con! Thầy thấy con đã nắm rất tốt các bước làm bài toán rút về đơn vị.",
    "score_rows": [
      {
        "section": "Bước 1: Tìm số cam trong 1 đĩa",
        "barem_requirement": "Tính số cam trong 1 đĩa: 36 : 4 = 9 (quả)",
        "student_work": "Con làm rất đúng bước 1, tìm ra 9 quả cam trong mỗi đĩa.",
        "score": "1.0 / 1.0"
      },
      {
        "section": "Bước 2: Tìm số cam trong 3 đĩa",
        "barem_requirement": "Tính số cam trong 3 đĩa: 9 x 3 = 27 (quả)",
        "student_work": "Con đã xác định đúng phép nhân 9 x 3 nhưng bị tính nhầm kết quả thành 24 thay vì 27.",
        "score": "0.0 / 1.0"
      }
    ],
    "total_score": "1.0 / 2.0",
    "advice": "Ở bước thứ 2, phép tính 9 x 3 cho kết quả là 27 quả cam chứ không phải 24. Lần sau con chú ý nhẩm kỹ lại bảng nhân 9 nhé!",
    "encouragement": "Con làm bài tư duy rất tốt, chỉ cần cẩn thận hơn ở khâu tính toán là sẽ đạt điểm tối đa!"
  }
}
```

---

### Test Case 5: Chấm bài học sinh bỏ trống hoặc thiếu bước
* **Mục đích:** Đánh giá phản ứng của hệ thống khi bài làm học sinh bị thiếu bước hoặc bỏ trống.
* **Agent:** `barem_review`

* **Request Payload gửi lên:**
```json
{
  "agent_name": "barem_review",
  "message": "Chấm bài giúp em:\nĐề bài: Tìm X biết X x 4 = 32.\nBarem: X = 32 : 4 (1.0 điểm), X = 8 (1.0 điểm).\nBài làm học sinh: X = 8",
  "conversation_id": "test_grade_003"
}
```

* **Response Payload trả về:**
```json
{
  "status": "success",
  "agent": "barem_review",
  "conversation_id": "test_grade_003",
  "data": {
    "greeting": "Cô chào con! Cô khen con đã tìm ra kết quả X = 8 đúng rồi nhé.",
    "score_rows": [
      {
        "section": "Bước 1: Lập luận chuyển vế",
        "barem_requirement": "Viết bước biến đổi X = 32 : 4",
        "student_work": "Con bỏ sót chưa trình bày bước biến đổi X = 32 : 4.",
        "score": "0.0 / 1.0"
      },
      {
        "section": "Bước 2: Đáp số X",
        "barem_requirement": "Ghi đúng kết quả X = 8",
        "student_work": "Con ghi đúng đáp số X = 8.",
        "score": "1.0 / 1.0"
      }
    ],
    "total_score": "1.0 / 2.0",
    "advice": "Khi làm bài tìm X, con nhớ trình bày đầy đủ bước tính X = 32 : 4 trước khi ghi đáp số X = 8 để được tính trọn vẹn điểm số nhé.",
    "encouragement": "Con học toán rất thông minh, cố gắng trình bày đầy đủ các bước nhé!"
  }
}
```

---

### Test Case 6: Kiểm tra tính tuân thủ tuyệt đối quy tắc Không Icon / Emoji
* **Mục đích:** Đảm bảo toàn bộ văn bản phản hồi và dữ liệu JSON không xuất hiện bất kỳ ký tự icon hay emoji nào.

* **Quy chuẩn kiểm tra (Assertion Rule):**
1. Kiểm tra chuỗi JSON trả về không chứa các dải unicode emoji (U+1F600 đến U+1F64F, U+1F300 đến U+1F5FF, U+1F680 đến U+1F6FF, U+2600 đến U+26FF, U+2700 đến U+27BF).
2. Không sử dụng các emoji như tệp tin, bút chì, tích xanh, dấu x đỏ, ngôi sao trong tất cả các trường chuỗi (`greeting`, `advice`, `encouragement`, `question`, `title`).
