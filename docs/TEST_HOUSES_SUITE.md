# BỘ CÂU HỎI KIỂM THỬ PHÂN HỆ TƯ VẤN BẤT ĐỘNG SẢN (REAL ESTATE CONSULTANT TEST SUITE)
## HỆ THỐNG TRA CỨU & TƯ VẤN NHÀ RIÊNG TRỰC QUAN (HOUSES MULTIMODAL RAG)

Tài liệu này quy định danh sách các trường hợp kiểm thử (Test Cases), quy chuẩn **Payload Request gửi lên** và **Payload Response trả về** chi tiết cho phân hệ Tư vấn Bất động sản (Real Estate House Consultant).

---

## 📌 1. QUY CHUẨN CẤU TRÚC PAYLOAD (API & WEBHOOK SCHEMA)

### 1.1. API Tra cứu Bất động sản (House Search API - `POST /api/houses/search`)

#### 🔴 Request Payload (Payload Gửi lên Backend):
| Tên Field | Kiểu Dữ Liệu | Bắt Buộc | Giá Trị Mặc Định | Mô Tả Chức Năng |
| :--- | :---: | :---: | :---: | :--- |
| `query` | `string` | **Có** | — | Câu hỏi/nhu cầu tìm kiếm nhà của khách hàng bằng ngôn ngữ tự nhiên. |
| `collection_name` | `string` | Không | `"houses"` | Tên collection lưu trữ vector bất động sản. |
| `top_k` | `integer` | Không | `5` | Số lượng kết quả bất động sản phù hợp nhất cần trả về. |

#### 🟢 Response Payload (Payload Trả về từ Backend):
| Tên Field | Kiểu Dữ Liệu | Mô Tả Chức Năng |
| :--- | :---: | :--- |
| `query` | `string` | Thắc mắc/yêu cầu tìm kiếm của người dùng. |
| `collection_name` | `string` | Tên collection được truy vấn. |
| `results` | `array[object]` | Danh sách các căn nhà thỏa mãn kèm theo điểm khoảng cách `distance`, `metadata`, và `unified_description`. |
| `results[].id` | `string` | ID căn nhà dạng `house_{id}`. |
| `results[].distance` | `float` | Khoảng cách vector similarity (càng nhỏ càng khớp). |
| `results[].metadata` | `object` | Chứa thông số kỹ thuật: `house_id`, `placeName`, `streetName`, `area`, `actualArea`, `floors`, `wide`, `depth`, `offeringPrice`, `bedrooms`, `bathrooms`, `hasCarParking`. |
| `results[].unified_description` | `string` | Bài giới thiệu căn nhà được tổng hợp từ thông số kỹ thuật + Vision OCR hình ảnh. |

---

### 1.2. API Ingest Bất động sản (House Ingest API - `POST /api/houses/ingest`)

#### 🔴 Request Payload (Payload Gửi lên Backend):
| Tên Field | Kiểu Dữ Liệu | Bắt Buộc | Giá Trị Mặc Định | Mô Tả Chức Năng |
| :--- | :---: | :---: | :---: | :--- |
| `houses_json_path` | `string` | Không | `null` | Đường dẫn file `houses.json` (mặc định lấy `data-samples/houses/houses.json`). |
| `images_dir` | `string` | Không | `null` | Thư mục chứa hình ảnh thực tế của nhà. |
| `collection_name` | `string` | Không | `"houses"` | Tên collection target trong Vector DB. |
| `force` | `boolean` | Không | `false` | Nếu `true`, ép chạy lại Gemini Vision API OCR hình ảnh. |
| `batch_size` | `integer` | Không | `5` | Kích thước batch xử lý ảnh đồng thời. |

#### 🟢 Response Payload (Payload Trả về từ Backend):
| Tên Field | Kiểu Dữ Liệu | Mô Tả Chức Năng |
| :--- | :---: | :--- |
| `status` | `string` | Trạng thái nạp dữ liệu (`"success"`). |
| `total_houses` | `integer` | Tổng số lượng căn nhà trong tệp dữ liệu. |
| `processed_houses` | `array[string]` | Danh sách ID nhà đã xử lý thành công. |
| `errors` | `array[string]` | Danh sách thông báo lỗi (nếu có). |

---

### 1.3. Webhook Tư vấn Bất động sản n8n (Real Estate Consultant Webhook - `POST /webhook/real-estate-consultant`)

#### 🔴 Request Payload (Payload Gửi lên Webhook):
| Tên Field | Kiểu Dữ Liệu | Bắt Buộc | Giá Trị Mặc Định | Mô Tả Chức Năng |
| :--- | :---: | :---: | :---: | :--- |
| `prompt` | `string` | **Có** | — | Nhu cầu tư vấn mua/thuê nhà của khách hàng. |
| `conversation_id` | `string` | Không | `null` | ID phiên hội thoại tư vấn. |

#### 🟢 Response Payload (Payload Trả về từ Webhook):
| Tên Field | Kiểu Dữ Liệu | Mô Tả Chức Năng |
| :--- | :---: | :--- |
| `status` | `string` | Trạng thái tư vấn (`"success"`). |
| `agent` | `string` | Trả về `"real_estate_consultant"`. |
| `conversation_id` | `string` | ID phiên hội thoại. |
| `output` | `string` | Lời tư vấn chi tiết, lịch sự bằng Markdown giới thiệu các căn nhà phù hợp kèm giá bán và điểm nổi bật. |
| `data.houses_found` | `integer` | Số lượng căn nhà được tìm thấy và tư vấn. |

---

## 📊 2. BẢNG TỔNG HỢP TRƯỜNG HỢP KIỂM THỬ (TEST MATRIX OVERVIEW)

| STT | Phân loại Intent / Use Case | Nhu cầu của khách hàng | Câu hỏi mẫu nhập vào System | Kết quả kỳ vọng (Expected Output) |
| :---: | :--- | :--- | :--- | :--- |
| **1** | **Tra cứu theo Vị trí / Đường phố** | Khách hàng tìm nhà ở khu vực cụ thể | `"Tìm cho anh nhà riêng ở khu vực đường Bát Khối"` | Trả về các căn nhà thuộc đường Bát Khối (VD: House ID 118, 122). |
| **2** | **Tra cứu theo Mức giá / Ngân sách** | Khách hàng tìm nhà trong tầm giá | `"Anh cần tìm căn hộ chung cư tầm giá khoảng 5 tỷ VNĐ"` | Trả về căn hộ Northern Diamond (House ID 120, giá 5.2 tỷ). |
| **3** | **Tra cứu theo Tiện ích (Bãi đỗ ô tô)** | Khách hàng yêu cầu ô tô vào nhà / đỗ cửa | `"Tìm nhà riêng có chỗ đỗ xe ô tô, mặt tiền rộng"` | Ưu tiên các căn nhà có `hasCarParking = true` (VD: House ID 118, 122). |
| **4** | **Tra cứu Tiêu chí Kết hợp Phức tạp** | Vị trí + Giá + Diện tích + Số phòng | `"Tìm nhà khu Long Biên tầm 10-12 tỷ, diện tích trên 40m2, có 5 phòng ngủ"` | Định tuyến tới các căn nhà phù hợp nhất thỏa mãn đồng thời các tiêu chí. |
| **5** | **Xử lý Không có Căn phù hợp** | Tìm kiếm thông số vượt quá dữ liệu | `"Tìm biệt thự 500m2 giá 2 tỷ ở Bát Khối"` | Trợ lý tư vấn lịch sự báo không tìm thấy căn chính xác và đề xuất căn gần nhất. |
| **6** | **Kiểm thử Nạp Dữ liệu Multimodal OCR** | Tác vụ Quản trị hệ thống (Ingest) | Gọi API `POST /api/houses/ingest` | Phân tích ảnh phòng/sổ đỏ qua Vision OCR, tạo `unified_description` và lưu Vector DB. |
| **7** | **Kiểm thử n8n Webhook Workflow** | Tác vụ Tư vấn toàn trình | Gọi Webhook `POST /webhook/real-estate-consultant` | Luồng n8n chạy thông suốt từ Webhook -> Search API -> Format Context -> LLM Consultant. |

---

## 🧪 3. KỊCH BẢN KIỂM THỬ CHI TIẾT VỚI PAYLOAD MẪU (DETAILED TEST SCENARIOS)

### Test Case 1: Tra cứu theo Vị trí / Đường phố
* **Prompt đầu vào:** `"Tìm cho anh nhà riêng ở khu vực đường Bát Khối"`
* **Routing mong đợi:** Trả về danh sách nhà thuộc đường Bát Khối.

* 🔴 **Payload Request gửi lên (`POST /api/houses/search`):**
```json
{
  "query": "Tìm cho anh nhà riêng ở khu vực đường Bát Khối",
  "collection_name": "houses",
  "top_k": 3
}
```

* 🟢 **Payload Response trả về:**
```json
{
  "query": "Tìm cho anh nhà riêng ở khu vực đường Bát Khối",
  "collection_name": "houses",
  "results": [
    {
      "id": "house_118",
      "distance": 0.125,
      "metadata": {
        "house_id": 118,
        "placeName": "Nhà riêng Bát Khối",
        "streetName": "Đường Bát Khối",
        "area": 40.0,
        "actualArea": 45.0,
        "floors": 6,
        "offeringPrice": 11.5,
        "bedrooms": 5,
        "hasCarParking": true
      },
      "unified_description": "Căn nhà riêng tuyệt đẹp 6 tầng tại đường Bát Khối, diện tích 40 m², thiết kế hiện đại, ô tô đỗ cửa..."
    }
  ]
}
```

---

### Test Case 2: Tra cứu theo Mức giá / Ngân sách
* **Prompt đầu vào:** `"Anh cần tìm căn hộ chung cư tầm giá khoảng 5 tỷ VNĐ"`

* 🔴 **Payload Request gửi lên (`POST /api/houses/search`):**
```json
{
  "query": "Anh cần tìm căn hộ chung cư tầm giá khoảng 5 tỷ VNĐ",
  "collection_name": "houses",
  "top_k": 3
}
```

* 🟢 **Payload Response trả về:**
```json
{
  "query": "Anh cần tìm căn hộ chung cư tầm giá khoảng 5 tỷ VNĐ",
  "collection_name": "houses",
  "results": [
    {
      "id": "house_120",
      "distance": 0.142,
      "metadata": {
        "house_id": 120,
        "placeName": "Chung cư Northern Diamond",
        "streetName": "Đường Cổ Linh",
        "area": 107.0,
        "offeringPrice": 5.2,
        "bedrooms": 3,
        "bathrooms": 2,
        "hasCarParking": true
      },
      "unified_description": "Căn hộ cao cấp tại chung cư Northern Diamond, Đường Cổ Linh, diện tích 107 m², 3 phòng ngủ, giá 5.2 tỷ VNĐ..."
    }
  ]
}
```

---

### Test Case 3: Tra cứu theo Tiện ích (Bãi đỗ ô tô)
* **Prompt đầu vào:** `"Tìm nhà riêng có chỗ đỗ xe ô tô, mặt tiền rộng"`

* 🔴 **Payload Request gửi lên (`POST /api/houses/search`):**
```json
{
  "query": "Tìm nhà riêng có chỗ đỗ xe ô tô, mặt tiền rộng",
  "collection_name": "houses",
  "top_k": 3
}
```

* 🟢 **Payload Response trả về:**
```json
{
  "query": "Tìm nhà riêng có chỗ đỗ xe ô tô, mặt tiền rộng",
  "collection_name": "houses",
  "results": [
    {
      "id": "house_122",
      "distance": 0.138,
      "metadata": {
        "house_id": 122,
        "placeName": "Nhà riêng Ngõ Bát Khối",
        "streetName": "Đường Bát Khối",
        "wide": 4.8,
        "offeringPrice": 9.8,
        "hasCarParking": true
      },
      "unified_description": "Căn nhà nằm trong ngõ rộng Bát Khối, ô tô vào nhà, mặt tiền 4.8 m, giá 9.8 tỷ VNĐ..."
    }
  ]
}
```

---

### Test Case 4: Tra cứu n8n Webhook Tư vấn Bất động sản Toàn trình
* **Webhook URL:** `POST /webhook/real-estate-consultant`

* 🔴 **Payload Request gửi lên Webhook:**
```json
{
  "prompt": "Chào em, anh muốn tìm nhà quanh khu vực Bát Khối tầm 10 đến 12 tỷ, có ô tô đỗ cửa và ít nhất 4 phòng ngủ.",
  "conversation_id": "real_estate_conv_001"
}
```

* 🟢 **Payload Response trả về từ API / Webhook:**
```json
{
  "status": "success",
  "agent": "real_estate_consultant",
  "conversation_id": "real_estate_conv_001",
  "output": "{\n  \"greeting\": \"Dạ chào Anh/Chị! Em xin gửi tới Anh/Chị danh sách tư vấn bất động sản nhà ở theo đúng nhu cầu.\",\n  \"summary\": \"Tìm thấy 1 căn nhà tại đường Bát Khối thỏa mãn hoàn hảo tiêu chí ngân sách 10-12 tỷ, 5 phòng ngủ và ô tô đỗ cửa.\",\n  \"recommended_properties\": [\n    {\n      \"house_id\": 118,\n      \"title\": \"Nhà riêng Bát Khối 6 tầng\",\n      \"address\": \"Đường Bát Khối\",\n      \"offering_price\": \"11.5 tỷ VNĐ\",\n      \"specs\": {\n        \"area_land\": \"40 m²\",\n        \"area_actual\": \"45 m²\",\n        \"floors\": 6,\n        \"bedrooms\": 5,\n        \"bathrooms\": 1,\n        \"facade_width\": \"5.0 m\",\n        \"car_parking\": true\n      },\n      \"highlights\": [\n        \"Thiết kế 6 tầng hiện đại, 5 phòng ngủ thoáng mát\",\n        \"Ô tô đỗ cửa, ngõ nông vị trí đắc địa Bát Khối\"\n      ],\n      \"match_analysis\": \"Đáp ứng 100% nhu cầu tìm nhà Bát Khối, tầm giá 11.5 tỷ nằm trong khoảng 10-12 tỷ, có 5 phòng ngủ và ô tô đỗ cửa.\"\n    }\n  ],\n  \"alternative_suggestions\": [],\n  \"consultant_advice\": \"Căn nhà ID 118 có pháp lý sổ đỏ hoàn chỉnh và mức giá hợp lý so với mặt bằng khu vực Bát Khối.\",\n  \"follow_up_questions\": [],\n  \"call_to_action\": \"Anh/Chị có muốn xếp lịch đi xem thực tế căn nhà này vào cuối tuần không ạ?\"\n}",
  "data": {
    "user_query": "Chào em, anh muốn tìm nhà quanh khu vực Bát Khối tầm 10 đến 12 tỷ, có ô tô đỗ cửa và ít nhất 4 phòng ngủ.",
    "houses_found": 1,
    "consultation_json": {
      "greeting": "Dạ chào Anh/Chị!",
      "summary": "Tìm thấy 1 căn nhà tại đường Bát Khối thỏa mãn hoàn hảo tiêu chí...",
      "recommended_properties": [ ... ]
    }
  }
}
```

---

### Test Case 5: Tác vụ Ingest Bất động sản Multimodal OCR
* **API Endpoint:** `POST /api/houses/ingest`

* 🔴 **Payload Request gửi lên:**
```json
{
  "houses_json_path": "data-samples/houses/houses.json",
  "images_dir": "data-samples/houses",
  "collection_name": "houses",
  "force": false,
  "batch_size": 5
}
```

* 🟢 **Payload Response trả về:**
```json
{
  "status": "success",
  "total_houses": 3,
  "processed_houses": ["118", "120", "122"],
  "errors": []
}
```
