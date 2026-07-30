import streamlit as st
import os
import sys
import json
import time
import requests
from pathlib import Path

# Add project root to python path to ensure proper imports
sys.path.append(str(Path(__file__).parent))

from src.vector_store.client import get_vector_db_client, get_embedding_function, get_or_create_collection
from src.vector_store.search import book_knowledge_search, multi_domain_retrieval
from src import config

def get_all_tag_uuids() -> list[str]:
    from src import config
    try:
        if config.VECTOR_DB_BACKEND == "qdrant":
            from qdrant_client import QdrantClient
            if config.QDRANT_HOST:
                client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
            else:
                client = QdrantClient(path=str(config.DATA_DIR / "qdrant_db"))
            cols = [c.name for c in client.get_collections().collections]
        else:
            from src.vector_store.client import get_vector_db_client
            client = get_vector_db_client()
            cols = [c.name for c in client.list_collections()]
            
        # Clean collection names to extract tag_name_uuid
        tag_uuids = set()
        for col in cols:
            if col.endswith("_doc"):
                tag_uuids.add(col[:-4])
            elif col.endswith("_qa"):
                tag_uuids.add(col[:-3])
            elif col.startswith(f"{config.COLLECTION_NAME}_"):
                tag_uuids.add(col[len(f"{config.COLLECTION_NAME}_"):])
            else:
                tag_uuids.add(col)
        
        cleaned = sorted([t for t in tag_uuids if t and t != "prompt_registry"])
        return cleaned
    except Exception as e:
        print(f"[Warning] Failed to fetch tag UUIDs: {e}")
        return ["math"]

def get_all_org_ids() -> list[str]:
    from src import config
    try:
        tags = get_all_tag_uuids()
        org_ids = set()
        for tag in tags:
            for doc_type in ["doc", "qa"]:
                col_name = f"{tag}_{doc_type}"
                from src.vector_store.client import get_vector_store
                try:
                    vs = get_vector_store(field=tag, collection_name_override=col_name)
                    res = vs.get_all()
                    if res and "metadatas" in res and res["metadatas"]:
                        metadata_list = res["metadatas"]
                        if metadata_list and isinstance(metadata_list, list):
                            for meta in metadata_list:
                                if isinstance(meta, list):
                                    for m in meta:
                                        if isinstance(m, dict) and "org_id" in m:
                                            org_ids.add(m["org_id"])
                                elif isinstance(meta, dict) and "org_id" in meta:
                                    org_ids.add(meta["org_id"])
                except Exception:
                    pass
        cleaned = sorted([o for o in org_ids if o])
        if not cleaned:
            return ["org_default"]
        return cleaned
    except Exception as e:
        print(f"[Warning] Failed to fetch org IDs: {e}")
        return ["org_default"]

def get_available_ocr_caches():
    cache_files = list(config.DATA_DIR.glob("processed_*.json"))
    options = []
    for f in cache_files:
        name = f.stem
        if name.startswith("processed_"):
            parts = name.split("_")
            if len(parts) >= 3 and parts[-1] == "data":
                field_name = parts[1]
                file_id = "_".join(parts[2:-1]) if len(parts) > 3 else None
                display_name = f"📚 Môn: {field_name.upper()}" + (f" | 🔑 ID Tệp: {file_id}" if file_id else " | (Sách mặc định)")
                options.append({
                    "path": f,
                    "display_name": display_name,
                    "field": field_name,
                    "file_id": file_id
                })
    return options

# --- Prompt Module Helper Functions ---
def get_barem_review_prompt(context: str, user_query: str, citation_block: str) -> str:
    return f"""Bạn là một giáo viên tiểu học thân thiện, tận tụy và công tâm. Nhiệm vụ của bạn là chấm điểm và nhận xét bài làm của học sinh tiểu học (lớp 3) dựa trên Barem điểm (thang điểm chi tiết) và đáp án chuẩn được cung cấp.

QUY TẮC BẮT BUỘC KHÔNG ĐƯỢC VI PHẠM (STRICT GROUNDED RAG):
1. Bạn CHỈ ĐƯỢC PHÉP trả lời và chấm điểm dựa hoàn toàn vào thông tin bài toán có trong phần "Ngữ cảnh tài liệu SGK" dưới đây.
2. KHÔNG ĐƯỢC tự ý bịa thêm kiến thức nằm ngoài ngữ cảnh.
3. Nếu phần "Ngữ cảnh tài liệu SGK" KHÔNG CHỨA bài toán hay dữ liệu cần thiết để chấm điểm, bạn BẮT BUỘC phải trả lời chính xác câu thông báo sau và KHÔNG in phần trích dẫn nguồn:
"[!] Rất tiếc, trong các trang SGK được trích xuất hiện tại không có thông tin hoặc bài học giải thích cho câu hỏi này."

Ngữ cảnh tài liệu SGK:
{context}

Câu hỏi/Yêu cầu chấm điểm của người dùng (chứa Đề bài, Barem & Bài làm của học sinh):
{user_query}

Hãy thực hiện chấm điểm theo các bước sau:
1. **Kiểm tra chi tiết từng bước:** So sánh từng bước giải của học sinh với các tiêu chí trong Barem điểm. Xác định học sinh đã làm đúng đến bước nào, tính toán có chính xác không.
2. **Tính điểm:** Cộng điểm cho các bước làm đúng theo đúng barem điểm quy định. Chỉ rõ điểm đạt được cho từng phần.
3. **Đưa ra nhận xét sư phạm:**
   - **Khen ngợi trước:** Động viên những phần học sinh đã làm tốt (ví dụ: trình bày sạch sẽ, đúng hướng tư duy, phép tính chính xác).
   - **Chỉ ra lỗi sai nhẹ nhàng:** Nếu học sinh làm sai hoặc thiếu bước, hãy giải thích cặn kẽ tại sao sai và sửa lại như thế nào bằng giọng điệu dịu dàng, khuyến khích (ví dụ: "Ở bước này, con đã nhầm một chút khi cộng...", "Con chú ý kỹ hơn phần đơn vị đo nhé!").
   - **Gợi ý cải thiện:** Hướng dẫn cách để lần sau con làm tốt hơn.

### ĐỊNH DẠNG PHẢN HỒI BẮT BUỘC (chỉ khi Ngữ cảnh SGK CÓ chứa câu trả lời):
- **Lời chào & Lời khen ban đầu:** Động viên tinh thần học sinh/phụ huynh.
- **Bảng chấm điểm chi tiết:**
  | Phần / Bước giải | Yêu cầu Barem | Bài làm của con | Điểm đạt được |
  | :--- | :--- | :--- | :--- |
  | [Ví dụ: Bước 1] | [Yêu cầu...] | [Nhận xét bài làm...] | [X / Y điểm] |
- **Tổng điểm:** **[Tổng số điểm đạt được] / [Tổng điểm tối đa]**
- **Lời khuyên & Hướng dẫn sửa bài:** Giải thích chi tiết phần con làm sai và hướng dẫn từng bước làm đúng.
- **Lời chúc & Động viên:** Truyền động lực để con tiếp tục cố gắng ở bài sau.

Giọng điệu phải luôn luôn ấm áp, sử dụng các xưng hô gần gũi như "thầy/cô", "con", "bạn nhỏ", "phụ huynh".

---
Nguon tham khao:
{citation_block}
"""

def get_theory_explanation_prompt(context: str, user_query: str, citation_block: str) -> str:
    return f"""Bạn là một giáo viên tiểu học có tài giảng dạy trực quan, sinh động. Nhiệm vụ của bạn là giải thích các định nghĩa, khái niệm toán học lớp 3 từ sách giáo khoa một cách dễ hiểu nhất cho học sinh hoặc phụ huynh học sinh.

QUY TẮC BẮT BUỘC KHÔNG ĐƯỢC VI PHẠM (STRICT GROUNDED RAG):
1. Bạn CHỈ ĐƯỢC PHÉP giải thích dựa hoàn toàn vào thông tin định nghĩa, khái niệm có trong phần "Ngữ cảnh tài liệu SGK" dưới đây.
2. KHÔNG ĐƯỢC sử dụng kiến thức bên ngoài hay tri thức sẵn có của LLM để tự suy đoán nếu ngữ cảnh không nói đến.
3. Nếu phần "Ngữ cảnh tài liệu SGK" KHÔNG CHỨA thông tin định nghĩa hoặc khái niệm phù hợp để giải thích câu hỏi của người dùng, bạn BẮT BUỘC phải trả lời chính xác câu thông báo sau và KHÔNG in phần trích dẫn nguồn:
"[!] Rất tiếc, trong các trang SGK được trích xuất hiện tại không có thông tin hoặc bài học giải thích cho câu hỏi này."

Ngữ cảnh tài liệu SGK:
{context}

Câu hỏi của học sinh/phụ huynh về khái niệm lý thuyết:
{user_query}

### NGUYÊN TẮC GIẢNG GIẢI:
1. **Trực quan hóa (Visualization):** Không dùng các định nghĩa hằn học hay hàn lâm, khô khan. Hãy liên hệ với thực tế đời sống quen thuộc với các em (ví dụ: chia kẹo, cắt bánh pizza, đếm ngón tay, đo độ dài chiếc bút chì, v.v.).
2. **Đơn giản hóa ngôn từ:** Sử dụng ngôn ngữ ngắn gọn, rõ ràng, nhịp điệu vui tươi, dễ thương phù hợp với trẻ em 8-9 tuổi.
3. **Phân chia từng bước:** Giải thích khái niệm từ cơ bản nhất, sau đó đi vào ví dụ minh họa cụ thể.
4. **Kiểm tra mức độ hiểu bài:** Cuối bài giảng, hãy đưa ra 1-2 câu hỏi đố vui hoặc thử thách nhỏ cực kỳ đơn giản để học sinh tự trả lời nhằm củng cố bài học.

### ĐỊNH DẠNG PHẢN HỒI BẮT BUỘC (chỉ khi Ngữ cảnh SGK CÓ chứa câu trả lời):
- **[Khai niem don gian]:** Định nghĩa ngắn gọn nhất bằng hình ảnh ví dụ (ví dụ: "Phép nhân là gì nhỉ? Nó giống như việc con cộng nhiều nhóm đồ vật có số lượng bằng nhau lại đấy!").
- **[Vi du thuc te]:** Đưa ra câu chuyện hoặc hình ảnh minh họa sinh động.
- **[Tom tat quy tac]:** Khung ghi nhớ ngắn gọn, dễ thuộc lòng (ví dụ: "Để tìm một phần mấy của một số, ta lấy số đó chia cho số phần nhé!").
- **[Thu thach nho cho con]:** 1 câu hỏi tương tác ngắn để con suy nghĩ và trả lời.

---
Nguon tham khao:
{citation_block}
"""

def get_exercise_generator_prompt(context: str, user_query: str, citation_block: str) -> str:
    return f"""Bạn là một chuyên gia biên soạn tài liệu toán tiểu học. Nhiệm vụ của bạn là tạo ra các bài tập tự luyện mới dựa trên ngữ cảnh bài học trong sách giáo khoa được cung cấp dưới đây.

QUY TẮC BẮT BUỘC KHÔNG ĐƯỢC VI PHẠM (STRICT GROUNDED RAG):
1. Bạn CHỈ ĐƯỢC PHÉP tạo các bài toán mới mô phỏng theo đúng các dạng toán có trong phần "Ngữ cảnh tài liệu SGK" dưới đây.
2. KHÔNG ĐƯỢC tự ý bịa ra các dạng toán lạ hay kiến thức nằm ngoài phạm vi các trang sách được cung cấp.
3. Nếu phần "Ngữ cảnh tài liệu SGK" KHÔNG CHỨA bài tập mẫu hoặc thông tin toán học liên quan để tạo đề mới, bạn BẮT BUỘC phải trả lời chính xác câu thông báo sau và KHÔNG in phần trích dẫn nguồn:
"[!] Rất tiếc, trong các trang SGK được trích xuất hiện tại không có thông tin hoặc bài học giải thích cho câu hỏi này."

Ngữ cảnh tài liệu SGK:
{context}

Yêu cầu tạo bài tập của người dùng:
{user_query}

### QUY TẮC TẠO BÀI TẬP:
1. **Đúng độ tuổi:** Bài tập phải đúng trình độ Toán lớp 3, không ra đề quá khó hay vượt chương trình.
2. **Sát ngữ cảnh:** Đề bài mới phải tương tự về dạng toán, phương pháp giải với các bài tập đang có trong trang sách giáo khoa được trích xuất (ví dụ: toán có lời văn về gấp một số lên nhiều lần, tìm một phần mấy, hình học chu vi/diện tích, cộng trừ trong phạm vi 10 000).
3. **Nội dung gần gũi:** Tên nhân vật, bối cảnh bài toán nên xoay quanh hoạt động học tập, vui chơi, gia đình của học sinh tiểu học (ví dụ: Bạn Nam xếp thuyền giấy, Mẹ mua táo ở siêu thị, lớp học trồng hoa).
4. **Cấu trúc bộ đề luyện tập (3 mức độ):**
   - **Bài 1 (Nhận biết/Thông hiểu):** Tương tự 100% dạng bài mẫu, chỉ thay đổi số và tên gọi.
   - **Bài 2 (Vận dụng):** Kết hợp thêm một bước tính hoặc bối cảnh thực tế nhẹ nhàng.
   - **Bài 3 (Vận dụng cao - Thử thách):** Bài toán đòi hỏi tư duy logic hơn một chút nhưng vẫn nằm trong phạm vi kiến thức đang học.

### ĐỊNH DẠNG PHẢN HỒI BẮT BUỘC (chỉ khi Ngữ cảnh SGK CÓ chứa câu trả lời):
- **[Bo bai tap tu luyen]:** Liệt kê rõ đề bài Bài 1, Bài 2, Bài 3.
- **[Huong dan & Dap an (Danh cho Phu huynh/Hoc sinh tu kiem tra)]:** Sử dụng thẻ HTML `<details>` để ẩn lời giải chi tiết của từng bài, giúp con tự làm trước rồi mới xem đáp án.
  Mẫu:
  <details>
  <summary>Xem gợi ý giải Bài 1</summary>
  [Từng bước giải và kết số đáp án của Bài 1]
  </details>

---
Dua tren bai hoc nguon:
{citation_block}
"""

def get_suggestive_tutor_prompt(context: str, user_query: str, citation_block: str) -> str:
    return f"""Bạn là một Gia sư Toán Tiểu học có phương pháp dạy học tương tác, gợi mở (Socratic method). Khi học sinh hỏi bài tập hoặc nhờ giải toán, bạn TUYỆT ĐỐI KHÔNG được đưa ra lời giải đầy đủ hay kết quả cuối cùng ngay lập tức. Nhiệm vụ của bạn là dắt tay học sinh tự tìm ra đáp án.

QUY TẮC BẮT BUỘC KHÔNG ĐƯỢC VI PHẠM (STRICT GROUNDED RAG):
1. Bạn CHỈ ĐƯỢC PHÉP gợi ý dựa hoàn toàn vào thông tin và phương pháp giải toán có trong phần "Ngữ cảnh tài liệu SGK" dưới đây.
2. Nếu phần "Ngữ cảnh tài liệu SGK" KHÔNG CHỨA bài toán hay phương pháp giải phù hợp, bạn BẮT BUỘC phải trả lời chính xác câu thông báo sau và KHÔNG in phần trích dẫn nguồn:
"[!] Rất tiếc, trong các trang SGK được trích xuất hiện tại không có thông tin hoặc bài học giải thích cho câu hỏi này."

Ngữ cảnh tài liệu SGK:
{context}

Câu hỏi cần gợi ý của học sinh:
{user_query}

### QUY TRÌNH HƯỚNG DẪN GỢI MỞ:
1. **Phân tích đề bài cùng học sinh:** Giúp con xác định bài toán cho biết gì (Đã biết gì?) và bài toán hỏi gì (Cần tìm gì?).
2. **Đặt câu hỏi gợi ý bước đầu tiên:** Đặt một câu hỏi ngắn, đơn giản hướng học sinh vào phép tính đầu tiên cần thực hiện.
   *Ví dụ: "Để biết cả hai bạn có bao nhiêu viên bi, trước tiên chúng mình cần tính số bi của bạn nào con nhỉ?"*
3. **Cung cấp gợi ý (Hint) thay vì đáp án:** Nếu con lúng túng, hãy đưa ra gợi ý nhỏ hoặc quy tắc toán học liên quan.
   *Ví dụ: "Con nhớ lại xem, muốn gấp một số lên 3 lần thì chúng mình thực hiện phép tính gì nào?"*
4. **Khích lệ phản hồi:** Luôn kết thúc câu trả lời bằng một câu hỏi mở để học sinh trả lời trước khi đi tiếp bước sau. Giữ phản hồi ngắn gọn để tạo thành một cuộc đối thoại liên tục.

### QUY TẮC PHẢN HỒI:
- Tuyệt đối KHÔNG viết phép tính có kết quả hoàn chỉnh hoặc đáp số cuối cùng của toàn bài.
- Chỉ hướng dẫn giải quyết từng bước một. Đợi học sinh trả lời rồi mới hướng dẫn tiếp bước 2, bước 3.
- Sử dụng ngôn ngữ động viên nhiệt tình: "Hay quá!", "Con thử tính xem...", "Chính xác rồi, bước tiếp theo sẽ là..."
"""

def get_direct_solver_prompt(context: str, user_query: str, citation_block: str) -> str:
    return f"""Bạn là một Trợ lý Giải Toán Tiểu học nhanh chóng và chính xác. Nhiệm vụ của bạn là đưa ra kết quả cuối cùng ngay lập tức để học sinh/phụ huynh đối chiếu, sau đó trình bày bài giải chi tiết, rõ ràng theo đúng chuẩn sư phạm lớp 3.

QUY TẮC BẮT BUỘC KHÔNG ĐƯỢC VI PHẠM (STRICT GROUNDED RAG):
1. Bạn CHỈ ĐƯỢC PHÉP giải toán dựa hoàn toàn vào thông tin và phương pháp giải có trong phần "Ngữ cảnh tài liệu SGK" dưới đây.
2. Nếu phần "Ngữ cảnh tài liệu SGK" KHÔNG CHỨA thông tin cần để giải bài toán, bạn BẮT BUỘC phải trả lời chính xác câu thông báo sau và KHÔNG in phần trích dẫn nguồn:
"[!] Rất tiếc, trong các trang SGK được trích xuất hiện tại không có thông tin hoặc bài học giải thích cho câu hỏi này."

Ngữ cảnh tài liệu SGK:
{context}

Câu hỏi/Bài toán cần giải:
{user_query}

### QUY TẮC TRÌNH BÀY:
1. **Đưa ra kết quả ngay:** Ở dòng đầu tiên của câu trả lời, in đậm kết quả hoặc đáp số của bài toán.
2. **Giải trình chi tiết từng bước (Step-by-step):** Trình bày lời giải rõ ràng, ghi rõ câu trả lời, phép tính và đơn vị kèm theo. Giải thích ngắn gọn logic đằng sau mỗi phép tính để người học hiểu bản chất.
3. **Trích dẫn nguồn sách giáo khoa:** Kết thúc bằng phần trích dẫn nguồn chuẩn RAG.

### ĐỊNH DẠNG PHẢN HỒI BẮT BUỘC (chỉ khi Ngữ cảnh SGK CÓ chứa câu trả lời):
- **[Dap so nhanh]:** **[Kết quả / Đáp số chính xác]**
- **[Bai giai chi tiet]:**
  - **Bước 1:** [Lời giải và phép tính] -> [Giải thích lý do/công thức]
  - **Bước 2:** [Lời giải và phép tính] -> [Giải thích lý do/công thức]
  - **Đáp số:** [Đầy đủ đáp số kèm đơn vị]

---
Nguon tham khao:
{citation_block}
"""

def get_default_teacher_prompt(context: str, user_query: str, citation_block: str) -> str:
    return f"""Bạn là một giáo viên tiểu học thân thiện, tận tụy và dịu dàng.

QUY TẮC BẮT BUỘC KHÔNG ĐƯỢC VI PHẠM (STRICT GROUNDED RAG):
1. Bạn CHỈ ĐƯỢC PHÉP trả lời dựa hoàn toàn vào thông tin có trong phần "Ngữ cảnh tài liệu SGK" dưới đây.
2. KHÔNG ĐƯỢC sử dụng kiến thức bên ngoài hay tri thức sẵn có của LLM để tự suy đoán nếu ngữ cảnh không nói đến.
3. Nếu phần "Ngữ cảnh tài liệu SGK" KHÔNG CHỨA thông tin trực tiếp liên quan hoặc KHÔNG ĐỦ để trả lời câu hỏi của người dùng, bạn BẮT BUỘC phải trả lời chính xác câu thông báo sau và KHÔNG in phần trích dẫn nguồn:
"[!] Rất tiếc, trong các trang SGK được trích xuất hiện tại không có thông tin hoặc bài học giải thích cho câu hỏi này."

Ngữ cảnh tài liệu SGK:
{context}

Câu hỏi của người dùng:
{user_query}

Yêu cầu định dạng câu trả lời (chỉ khi Ngữ cảnh SGK CÓ chứa câu trả lời):
1. Trả lời thân thiện, giải thích từng bước logic toán học rõ ràng.
2. Trả lời hoàn toàn bằng tiếng Việt.
3. Cuối câu trả lời, in rõ phần trích dẫn nguồn theo đúng định dạng sau:

---
Nguon tham khao:
{citation_block}
"""

# --- Page Setup ---
st.set_page_config(
    page_title="Hệ thống Trợ lý Học tập SGK Toán 3",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Premium Custom Styling (Wow aesthetics) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    
    /* Global Styles */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Main Layout Accent */
    .main {
        background-color: #f8fafc;
    }
    
    /* Header Banner styling */
    .header-banner {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        padding: 2.5rem;
        border-radius: 16px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px rgba(30, 60, 114, 0.15);
    }
    .header-banner h1 {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        color: #ffffff !important;
    }
    .header-banner p {
        font-size: 1.1rem;
        opacity: 0.9;
        margin: 0;
    }
    
    /* Card/Block Container */
    .custom-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03);
        border: 1px solid #e2e8f0;
        margin-bottom: 1.25rem;
    }
    
    /* Status indicators */
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        text-align: center;
    }
    .status-online {
        background-color: #def7ec;
        color: #03543f;
    }
    .status-offline {
        background-color: #fde8e8;
        color: #9b1c1c;
    }
    
    /* Sidebar styling enhancements */
    [data-testid="stSidebar"] {
        background-color: #0f172a;
        color: #f8fafc;
    }
    [data-testid="stSidebar"] .stSelectbox label, 
    [data-testid="stSidebar"] .stTextInput label {
        color: #e2e8f0 !important;
        font-weight: 500;
    }
    .sidebar-title {
        color: #38bdf8;
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 1.5rem;
        border-bottom: 1px solid #334155;
        padding-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar (User Profile & Metadata Selection) ---
with st.sidebar:
    st.markdown('<div class="sidebar-title">⚙️ CẤU HÌNH HỆ THỐNG</div>', unsafe_allow_html=True)
    
    # User Metadata section (Role must be part of user metadata)
    st.markdown("### 🧑 User Metadata")
    user_role = st.selectbox(
        "Vai trò người dùng (Role)",
        options=[config.ROLE_STUDENT, config.ROLE_TEACHER, config.ROLE_ADMIN],
        index=0,
        format_func=lambda x: {
            config.ROLE_STUDENT: "Học sinh (Student)",
            config.ROLE_TEACHER: "Giáo viên (Teacher)",
            config.ROLE_ADMIN: "Quản trị viên (Admin)"
        }.get(x, x)
    )
    
    # Display details of the active role permissions
    allowed_vis = config.ROLE_VISIBILITY_MAPPING.get(user_role, ["public"])
    if user_role == config.ROLE_ADMIN:
        allowed_vis_text = "Toàn bộ tài liệu (public, teacher_only, admin_only)"
    else:
        allowed_vis_text = ", ".join(allowed_vis)
        
    st.info(f"**Quyền truy cập:**\n{allowed_vis_text}")
    
    st.markdown("---")
    
    st.markdown("### 📚 Tài liệu & Agent Metadata")
    # Category Tag / Field selection via dynamic checkboxes
    available_tags = get_all_tag_uuids()
    st.markdown("**Chọn các tài liệu (Tag Name UUIDs):**")
    selected_tags = []
    for tag in available_tags:
        default_val = True
        if st.sidebar.checkbox(f"📁 {tag}", value=default_val, key=f"sidebar_cb_{tag}"):
            selected_tags.append(tag)
    
    # Active field fallback for other single-field dropdowns/code blocks
    active_field = selected_tags[0] if selected_tags else (available_tags[0] if available_tags else "default")
    
    # Prompt module selection
    agent_mode = st.selectbox(
        "Mô-đun Trợ lý (Agent Prompt Module)",
        options=[
            "default",
            "barem_review",
            "theory_explanation",
            "exercise_generator",
            "suggestive_tutor",
            "direct_solver"
        ],
        index=0,
        format_func=lambda x: {
            "default": "Mặc định (Giáo viên Tiểu học)",
            "barem_review": "Chấm điểm Barem (Barem Review)",
            "theory_explanation": "Giảng lý thuyết (Theory)",
            "exercise_generator": "Tạo bài tập (Exercise Gen)",
            "suggestive_tutor": "Gợi mở dắt tay (Suggestive)",
            "direct_solver": "Giải nhanh ra đáp số (Direct Solver)"
        }.get(x, x),
        help="Chọn mô-đun prompt để cấu hình phong cách trả lời của Trợ lý AI."
    )
    
    # Embeddings / OCR configuration choice
    embed_provider = "Gemini (text-embedding-004)" if (config.GEMINI_API_KEY or config.USE_VERTEXAI) else ("OpenAI" if config.OPENAI_API_KEY else "Chưa cấu hình")
    st.write(f"**Bộ xử lý Vector Nhúng:** {embed_provider}")
    
    ocr_provider = "Gemini (gemini-2.5-flash)" if (config.GEMINI_API_KEY or config.USE_VERTEXAI) else "Chưa cấu hình"
    st.write(f"**Bộ xử lý OCR:** {ocr_provider}")
    
    st.markdown("---")
    st.markdown("<div style='text-align: center; opacity: 0.5; font-size: 0.8rem;'>Trợ lý Học tập SGK Toán 3<br>Phiên bản 1.0.0</div>", unsafe_allow_html=True)

# --- Header Banner ---
st.markdown("""
<div class="header-banner">
    <h1>CỔNG THÔNG TIN TRỢ LÝ HỌC TẬP THÔNG MINH</h1>
    <p>Giải đáp bài tập, nạp tài liệu OCR và quản lý phân quyền theo bài học lớp 3</p>
</div>
""", unsafe_allow_html=True)

# --- Tabs Setup ---
tab_chatbot, tab_search, tab_upload, tab_api_retrieval, tab_preview, tab_health, tab_prompt_reg, tab_live_test, tab_mentor_test = st.tabs([
    "💬 Trợ lý AI Chatbot",
    "🔍 Tra cứu RAG & Multi-Domain",
    "📤 Nạp tài liệu & OCR (Upload)",
    "⚡ Kiểm thử API Retrieval & Vectors",
    "🔍 Xem trước Vector DB (Preview)",
    "🏥 Trạng thái Hệ thống (Health)",
    "⚙️ Quản lý Prompts (Registry)",
    "🧪 Live Testing (n8n Webhook)",
    "📝 Thiết kế đề thi (Mentor)"
])

# =====================================================================
# TAB 1: INTERACTIVE AI CHATBOT AREA
# =====================================================================
with tab_chatbot:
    st.markdown("### 💬 Trợ lý Học tập AI (Chatbot)")
    st.markdown(f"Hỏi đáp bài tập, giải thích kiến thức từng bước dựa trên tài liệu đã nạp (*Vai trò active: **{user_role.upper()}***).")
    
    col_chat_hdr1, col_chat_hdr2 = st.columns([4, 1])
    with col_chat_hdr2:
        if st.button("🧹 Xóa lịch sử", key="clear_chat_btn"):
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": "Xin chào! Thầy/Cô là Trợ lý Học tập AI. Em hoặc Phụ huynh có câu hỏi gì về bài học hay bài tập cần giải đáp không ạ?"
                }
            ]
            st.rerun()

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Xin chào! Thầy/Cô là Trợ lý Học tập AI. Em hoặc Phụ huynh có câu hỏi gì về bài học hay bài tập cần giải đáp không ạ?"
            }
        ]

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        avatar = "🤖" if message["role"] == "assistant" else "👤"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    # React to user input
    if prompt := st.chat_input("Nhập câu hỏi tại đây... (Ví dụ: 'Giải giúp em bài toán đố trang 15')"):
        # Display user message in chat message container
        st.chat_message("user", avatar="👤").markdown(prompt)
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Display assistant response in chat message container
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Trợ lý AI đang tra cứu sách giáo khoa và suy luận... 💭"):
                try:
                    # Retrieve RAG context
                    rag_results = multi_domain_retrieval(
                        query=prompt,
                        tag_name_uuids=selected_tags if selected_tags else ["math"],
                        doc_type="doc",
                        top_k=3
                    )
                    
                    context_texts = []
                    citations = []
                    for r in rag_results:
                        m = r["metadata"]
                        phys_p = m.get('physical_page')
                        pdf_p = m.get('pdf_page_index')
                        if phys_p is not None and phys_p != -1:
                            page_str = f"Trang {phys_p}"
                        elif pdf_p is not None and pdf_p != -1:
                            page_str = f"Trang PDF {pdf_p + 1}"
                        else:
                            page_str = "Trang chưa rõ"
                            
                        lesson = m.get('lesson_name', 'Chưa rõ')
                        file_n = m.get('file_name', 'SGK Toán 3')
                        vol = m.get('volume', '1')
                        
                        context_texts.append(f"--- Tài liệu: {file_n}, {page_str} ---\n{r['text']}")
                        citations.append(f"- **Tài liệu:** {file_n} | **Bài học:** {lesson} | **Vị trí:** {page_str} (Tập {vol})")
                        
                    joined_context = "\n\n".join(context_texts) if context_texts else "Không tìm thấy đoạn văn bản trùng khớp."
                    citation_block = "\n".join(citations) if citations else "- Tài liệu hệ thống"
                    
                    # Strict Grounded RAG Check: Guardrail if no documents found
                    # Only default and theory_explanation require RAG lookup validation
                    needs_rag_lookup = agent_mode in ["default", "theory_explanation"]
                    if needs_rag_lookup and (not rag_results or joined_context == "Không tìm thấy đoạn văn bản trùng khớp."):
                        full_response = "⚠️ Rất tiếc, trong cơ sở dữ liệu SGK hiện tại không tìm thấy bài học hoặc thông tin phù hợp để trả lời câu hỏi này."
                    elif config.GEMINI_API_KEY or config.USE_VERTEXAI:
                        from google import genai
                        if config.USE_VERTEXAI:
                            ai_client = genai.Client(vertexai=True, project=config.GOOGLE_CLOUD_PROJECT, location=config.GOOGLE_CLOUD_LOCATION)
                        else:
                            ai_client = genai.Client(api_key=config.GEMINI_API_KEY)
                            
                        # Build prompt template based on selected prompt module/mode
                        if agent_mode == "barem_review":
                            prompt_template = get_barem_review_prompt(joined_context, prompt, citation_block)
                        elif agent_mode == "theory_explanation":
                            prompt_template = get_theory_explanation_prompt(joined_context, prompt, citation_block)
                        elif agent_mode == "exercise_generator":
                            prompt_template = get_exercise_generator_prompt(joined_context, prompt, citation_block)
                        elif agent_mode == "suggestive_tutor":
                            prompt_template = get_suggestive_tutor_prompt(joined_context, prompt, citation_block)
                        elif agent_mode == "direct_solver":
                            prompt_template = get_direct_solver_prompt(joined_context, prompt, citation_block)
                        else:
                            prompt_template = get_default_teacher_prompt(joined_context, prompt, citation_block)
                        response = ai_client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=prompt_template
                        )
                        full_response = response.text
                    else:
                        full_response = f"Dựa trên tài liệu tra cứu được:\n\n{joined_context}\n\n---\nNguon tham khao:\n{citation_block}"
                        
                    st.markdown(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                except Exception as e:
                    error_str = f"Đã xảy ra lỗi khi tạo câu trả lời: {e}"
                    st.error(error_str)
                    st.session_state.messages.append({"role": "assistant", "content": error_str})

# =====================================================================
# TAB 2: RAG SEARCH EXPLORER
# =====================================================================
with tab_search:
    st.markdown("### 🔍 Kiểm thử & Trích xuất Tài liệu (RAG)")
    st.markdown(
        f"*Hệ thống đang hoạt động với vai trò: **{user_role.upper()}** trên tài liệu / Tag UUID **{active_field.upper()}**.*"
    )
    
    # Show active user role constraints warning for clarity
    if user_role == config.ROLE_STUDENT:
        st.warning("🔒 Bạn đang đăng nhập là **Học sinh**. Bạn chỉ được phép tra cứu các bài học được đánh dấu **Công khai (public)**.")
    elif user_role == config.ROLE_TEACHER:
        st.info("🔓 Bạn đang đăng nhập là **Giáo viên**. Bạn có quyền truy cập tài liệu **Công khai** và các tài liệu nội bộ **Giáo viên (teacher_only)**.")
    elif user_role == config.ROLE_ADMIN:
        st.success("👑 Bạn đang đăng nhập là **Quản trị viên**. Bạn có toàn quyền truy cập tất cả các tài liệu hệ thống.")

    # Input field for user query
    user_query = st.text_input("Nhập câu hỏi hoặc từ khóa cần tra cứu: (Ví dụ: 'Giải bài 2 trang 15 tập 1')", value="")
    
    # Advanced Search settings (top_k, override page/volume hints)
    col1, col2, col3 = st.columns(3)
    with col1:
        top_k = st.slider("Số lượng kết quả cần lấy (Top K)", min_value=1, max_value=10, value=5)
    with col2:
        custom_page = st.number_input("Ghi đè gợi ý Trang (Bỏ trống = Tự động trích xuất)", min_value=0, max_value=200, value=0, step=1)
    with col3:
        custom_vol = st.selectbox("Ghi đè gợi ý Tập (Bỏ trống = Tự động trích xuất)", options=["Tự động", "1", "2"], index=0)
        
    # ACL Testing parameters
    col_acl1, col_acl2 = st.columns(2)
    with col_acl1:
        test_user_id = st.text_input("Mã người dùng để kiểm thử (Test User ID)", value="", help="Nhập User ID để test quyền truy cập cá nhân.")
    with col_acl2:
        test_groups = st.text_input("Danh sách nhóm để kiểm thử (Test Groups)", value="", help="Nhập danh sách các nhóm phân tách bằng dấu phẩy (ví dụ: teacher, hr).")
        
    page_hint = int(custom_page) if custom_page > 0 else None
    volume_hint = custom_vol if custom_vol != "Tự động" else None
    user_groups_list = [g.strip() for g in test_groups.split(",") if g.strip()] if test_groups else None
    
    # Multi-Domain & QA vs Doc Settings
    st.markdown("#### ⚙️ Cấu hình Tìm kiếm Nâng cao (Đa miền & Q&A)")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        search_type = st.selectbox(
            "Loại nội dung (Content Type)",
            options=["doc", "qa"],
            format_func=lambda x: "📄 Tài liệu gốc (Document - doc)" if x == "doc" else "❓ Bộ Câu hỏi & Đáp án (Question & Answer - qa)",
            key="search_type",
            help="Chọn tìm trong collection _{doc} hay _{qa}"
        )
    with col_t2:
        st.markdown("**Chọn các Miền / Tag UUIDs:**")
        tab_selected_tags = []
        for tag in available_tags:
            default_val = tag in selected_tags
            if st.checkbox(f"📁 {tag}", value=default_val, key=f"tab_search_cb_{tag}"):
                tab_selected_tags.append(tag)

    if st.button("Tra cứu RAG"):
        if not user_query.strip():
            st.error("Vui lòng nhập truy vấn trước khi tìm kiếm.")
        else:
            with st.spinner("Đang tìm kiếm trong cơ sở dữ liệu Vector... 💭"):
                try:
                    results = multi_domain_retrieval(
                        query=user_query,
                        tag_name_uuids=tab_selected_tags if tab_selected_tags else ["math"],
                        doc_type=search_type,
                        top_k=top_k
                    )
                    
                    if not results:
                        st.warning("Không tìm thấy tài liệu hoặc cặp Hỏi/Đáp phù hợp.")
                    else:
                        st.success(f"Đã trích xuất {len(results)} Chunk riêng biệt (Category: {search_type.upper()}):")
                        for idx, res in enumerate(results):
                            meta = res["metadata"]
                            chunk_id = res.get("id", f"chunk_{idx}")
                            col_name = res.get("collection", "default")
                            dist_score = res.get("distance", 0.0)
                            tag_uuid_val = meta.get("tag_name_uuid", meta.get("file_id", "N/A"))
                            
                            phys_p = meta.get('physical_page')
                            pdf_p = meta.get('pdf_page_index')
                            if phys_p is not None and phys_p != -1:
                                page_str = f"Trang vật lý {phys_p}"
                            elif pdf_p is not None and pdf_p != -1:
                                page_str = f"Trang PDF {pdf_p + 1}"
                            else:
                                page_str = "N/A"

                            with st.container():
                                st.markdown('<div class="custom-card">', unsafe_allow_html=True)
                                
                                # Chunk Header Bar
                                st.markdown(f"#### 🧩 **Chunk {idx + 1}: `{chunk_id}`**")
                                
                                c1, c2, c3, c4 = st.columns(4)
                                with c1:
                                    st.markdown(f"**📚 Collection:**\n`{col_name}`")
                                with c2:
                                    st.markdown(f"**🏷️ Tag/UUID:**\n`{tag_uuid_val}`")
                                with c3:
                                    st.markdown(f"**📍 Vị trí:**\n`{page_str}`")
                                with c4:
                                    st.markdown(f"**📊 Distance Score:**\n`{dist_score:.4f}`")
                                    
                                c_m1, c_m2, c_m3 = st.columns(3)
                                with c_m1:
                                    st.markdown(f"**📄 Tệp nguồn:** `{meta.get('file_name', 'N/A')}`")
                                with c_m2:
                                    st.markdown(f"**🕒 Thời gian:** `{meta.get('created_at', 'N/A')}`")
                                with c_m3:
                                    st.markdown(f"**🔒 Visibility:** `{meta.get('visibility', 'public')}`")

                                # Visual Verification Badge
                                if tag_uuid_val in tag_uuids_list or col_name.replace(f"_{search_type}", "") in tag_uuids_list:
                                    st.markdown(f"<div style='background-color: #d4edda; color: #155724; padding: 6px 12px; border-radius: 6px; font-weight: bold; margin-bottom: 10px;'>✅ VERIFIED CHUNK: Khớp chính xác với Tag UUID yêu cầu [{tag_uuid_val}]</div>", unsafe_allow_html=True)

                                label_text = "📝 Nội dung Chunk (Verbatim Text):"
                                st.text_area(label_text, value=res["text"], height=160, key=f"chunk_text_{idx}")
                                st.markdown('</div>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Đã xảy ra lỗi khi tìm kiếm: {e}")

# =====================================================================
# TAB 2: DOCUMENT INGESTION
# =====================================================================
with tab_upload:
    st.markdown("### 📤 Tải lên sách/tài liệu giáo khoa & Chạy OCR")
    st.markdown("Sử dụng mô hình Multimodal Vision OCR để trích xuất bài học và nạp vào cơ sở dữ liệu Vector isolated.")
    
    col1, col2 = st.columns([2, 1])
    
    # Define Column 2 first to get the step_ocr variable
    with col2:
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.markdown("#### 2. Metadata & Phân quyền (RBAC)")
        
        # Tag/Field input (Subject field) - Autogenerated Tag Name UUID
        if "upload_tag_name_uuid" not in st.session_state:
            import uuid
            import time
            st.session_state.upload_tag_name_uuid = f"{uuid.uuid4()}_{int(time.time())}"
            
        col_uuid1, col_uuid2 = st.columns([5, 1])
        with col_uuid1:
            upload_field = st.text_input(
                "Tag Name UUID (ID tài liệu tự sinh)",
                value=st.session_state.upload_tag_name_uuid,
                disabled=True,
                help="Mã UUID duy nhất của tài liệu được tự động sinh ra cho phiên nạp này để tránh trùng lặp."
            )
        with col_uuid2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("🔄", help="Tạo mã UUID mới"):
                import uuid
                import time
                st.session_state.upload_tag_name_uuid = f"{uuid.uuid4()}_{int(time.time())}"
                st.rerun()
        

        
        # Organization ID input
        upload_org_id = st.text_input(
            "Mã Tổ chức (Organization ID)",
            value="org_default",
            key="upload_org_id",
            help="Mã định danh của tổ chức/đơn vị sở hữu tài liệu này."
        )
        
        # Volume
        upload_volume = st.selectbox(
            "Tập sách (Volume)",
            options=["1", "2", "3", "custom"],
            key="upload_volume"
        )
        if upload_volume == "custom":
            upload_volume = st.text_input("Nhập tập sách tùy chỉnh", value="3", key="upload_volume_custom")
            
        # Force OCR checkbox
        force_ocr = st.checkbox(
            "Ép buộc chạy lại OCR (Force OCR)",
            value=False,
            help="Bỏ qua bộ nhớ cache và buộc gọi lại Gemini API Vision OCR."
        )
        
        # Content Type (doc vs qa)
        upload_doc_type = st.selectbox(
            "Loại dữ liệu (Content Type)",
            options=["doc", "qa"],
            format_func=lambda x: "📄 Tài liệu gốc (Document - doc)" if x == "doc" else "❓ Bộ Câu hỏi & Đáp án (Question & Answer - qa)",
            key="upload_doc_type",
            help="Chọn lưu vào collection _{doc} hay _{qa}."
        )
        
        # Timestamp Datetime input
        upload_datetime = st.text_input(
            "Dấu mốc thời gian (Datetime / ISO String)",
            value="",
            key="upload_datetime",
            help="Ví dụ: 2026-07-19T10:00:00Z. Bỏ trống = thời gian hiện tại."
        )

        # Description
        upload_description = st.text_input(
            "Mô tả tài liệu / Bộ Q&A (Description)",
            value="",
            key="upload_description",
            help="Mô tả tóm tắt nội dung tệp."
        )
        
        # Ingestion Mode
        upload_mode = st.selectbox(
            "Chế độ nạp dữ liệu (Ingestion Mode)",
            options=["update", "override"],
            format_func=lambda x: "Case 2: Nạp nối tiếp/Update (Hợp nhất Cache)" if x == "update" else "Case 1: Ghi đè/Override (Khởi tạo lại Cache & DB)",
            key="upload_mode",
            help="Update: Nối tiếp nội dung mới vào danh mục và hợp nhất cache. Override: Xóa sạch dữ liệu cũ cùng danh mục và ghi đè mới hoàn toàn."
        )
        
        # Modular steps checkboxes
        st.markdown("##### 🧩 Chọn bước chạy (Modular Ingest Steps)")
        step_ocr = st.checkbox(
            "Chạy trích xuất OCR PDF (Step 1: OCR)",
            value=True,
            help="Nếu tắt, hệ thống sẽ sử dụng cache JSON đã xử lý trước đó mà không gọi Gemini API Vision."
        )
        step_ingest = st.checkbox(
            "Nạp vector và chỉ mục DB (Step 2: Ingestion/Embedding)",
            value=True,
            help="Nếu tắt, hệ thống chỉ lưu cache kết quả OCR mà không sinh embedding vector vào ChromaDB."
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
    # Define Column 1 (toggles based on step_ocr)
    with col1:
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        if step_ocr:
            st.markdown("#### 1. Chọn tài liệu PDF")
            uploaded_file = st.file_uploader(
                "Tải lên tệp PDF tài liệu sách giáo khoa (Định dạng ảnh scan hoặc văn bản)",
                type=["pdf"],
                key="pdf_uploader"
            )
            if uploaded_file is not None:
                st.success(f"📂 Đã chọn file: **{uploaded_file.name}** ({uploaded_file.size / (1024*1024):.2f} MB)")
        else:
            st.markdown("#### 1. Chọn tệp OCR Cache đã trích xuất sẵn")
            st.markdown("Hệ thống phát hiện các file OCR cũ đã xử lý trong thư mục `data/`:")
            ocr_options = get_available_ocr_caches()
            if ocr_options:
                selected_ocr = st.selectbox(
                    "Chọn tệp OCR cache để tiếp tục nạp vào cơ sở dữ liệu",
                    options=ocr_options,
                    format_func=lambda x: x["display_name"],
                    key="ocr_cache_selector"
                )
                st.info(f"📂 Sử dụng file: `{selected_ocr['path'].name}`")
            else:
                st.warning("⚠️ Không tìm thấy tệp OCR cache nào trên ổ đĩa. Hãy bật 'Step 1: OCR' để trích xuất file PDF trước.")
                selected_ocr = None
        st.markdown('</div>', unsafe_allow_html=True)
        
    # Trigger button
    if st.button("🚀 Bắt đầu Nạp dữ liệu & Chạy OCR", type="primary", use_container_width=True):
        if step_ocr and uploaded_file is None:
            st.error("❌ Vui lòng chọn tệp PDF trước khi bắt đầu.")
        elif not step_ocr and selected_ocr is None:
            st.error("❌ Không có tệp OCR cache nào để nạp. Hãy chọn tệp hoặc bật bước OCR.")
        else:
            with st.status("Đang xử lý nạp tài liệu...", expanded=True) as status:
                try:
                    file_name_val = ""
                    pdf_path_val = None
                    field_val = ""
                    file_id_val = ""
                    
                    if step_ocr:
                        # 1. Save uploaded file to workspace folder data/uploads
                        uploads_dir = Path("data") / "uploads"
                        uploads_dir.mkdir(parents=True, exist_ok=True)
                        
                        saved_path = uploads_dir / uploaded_file.name
                        status.write(f"Đang lưu tạm tệp tin vào `{saved_path}`...")
                        with open(saved_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        file_name_val = uploaded_file.name
                        pdf_path_val = saved_path.as_posix()
                        field_val = upload_field
                        file_id_val = upload_field
                    else:
                        file_name_val = selected_ocr["file_id"] or selected_ocr["field"]
                        pdf_path_val = None
                        field_val = selected_ocr["field"]
                        file_id_val = selected_ocr["file_id"]
                        status.write(f"Đang tải tệp OCR từ cache: `{selected_ocr['path'].name}`...")
                    
                    # 2. Verify API Key exists if running OCR
                    if step_ocr and not config.GEMINI_API_KEY:
                        raise ValueError("Chưa thiết lập GEMINI_API_KEY trong tệp .env.")
                    
                    status.write("Đang tiến hành gửi yêu cầu nạp tài liệu tới FastAPI Backend (Port 8080)...")
                    
                    backend_ingest_url = "http://localhost:8080/api/ingestion"
                    payload = {
                        "force": force_ocr,
                        "tag_name_uuid": field_val,
                        "file_path": pdf_path_val,
                        "volume": str(upload_volume),
                        "description": upload_description if upload_description else None,
                        "file_name": file_name_val,
                        "mode": upload_mode,
                        "datetime": upload_datetime if upload_datetime else None,
                        "doc_type": upload_doc_type,
                        "step_ocr": step_ocr,
                        "step_ingest": step_ingest,
                        "org_id": upload_org_id
                    }
                    
                    res = requests.post(backend_ingest_url, json=payload, timeout=900)
                    if res.status_code != 200:
                        try:
                            err_detail = res.json().get("detail", res.text)
                        except Exception:
                            err_detail = res.text
                        raise ValueError(f"Lỗi từ FastAPI Backend: {err_detail}")
                    
                    status.update(label="✅ Nạp dữ liệu hoàn tất!", state="complete", expanded=True)
                    st.success(f"🎉 Đã nạp thành công tài liệu **{file_name_val}** với Tag Name UUID **'{field_val}'** (Phân quyền mặc định: 'public')!")
                    import uuid
                    import time
                    st.session_state.upload_tag_name_uuid = f"{uuid.uuid4()}_{int(time.time())}"
                    
                except Exception as e:
                    status.update(label="❌ Nạp dữ liệu thất bại!", state="error", expanded=True)
                    st.error(f"Đã xảy ra lỗi trong quá trình nạp dữ liệu: {e}")

# =====================================================================
# TAB 4: API RETRIEVAL TESTER & VECTOR LIST
# =====================================================================
with tab_api_retrieval:
    st.markdown("### ⚡ Kiểm thử API Retrieval & Danh sách Vector đã tìm thấy")
    st.markdown("Kiểm thử trực tiếp API Tra cứu Vector (`POST /api/retrieval`) hoặc gọi mô hình Hybrid Search. Liệt kê danh sách các Vector trích xuất cùng điểm số chỉ số tương quan (Distance & RRF Score).")
    
    st.markdown('<div class="custom-card">', unsafe_allow_html=True)
    st.markdown("#### ⚙️ Cấu hình Tham số Đầu vào (Payload Parameters)")
    
    col_api1, col_api2 = st.columns([3, 2])
    with col_api1:
        api_query_text = st.text_input(
            "📝 Truy vấn Tìm kiếm (Query Text)",
            value="số liền trước là gì",
            key="api_tab_query",
            help="Chuỗi câu hỏi hoặc từ khóa cần tra cứu vector (Ví dụ: 'số liền trước là gì', 'bài toán trang 15')"
        )
        st.markdown("**Chọn các Miền / Tag UUIDs:**")
        api_tab_selected_tags = []
        for tag in available_tags:
            default_val = tag in selected_tags
            if st.checkbox(f"📁 {tag}", value=default_val, key=f"tab_api_cb_{tag}"):
                api_tab_selected_tags.append(tag)
        
    with col_api2:
        api_doc_type = st.selectbox(
            "📄 Loại nội dung (Type)",
            options=["doc", "qa"],
            format_func=lambda x: "📄 Tài liệu gốc (doc)" if x == "doc" else "❓ Bộ Q&A (qa)",
            key="api_tab_doc_type"
        )
        api_top_k = st.slider("📊 Số lượng Vector cần lấy (Top K)", min_value=1, max_value=20, value=5, key="api_tab_topk")
        
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        exec_mode = st.radio(
            "🛠️ Phương thức thực thi:",
            options=["Nội bộ (Direct Python Call)", "REST API (POST http://localhost:8080/api/retrieval)"],
            index=0,
            horizontal=True,
            key="api_tab_exec_mode"
        )
    with col_opt2:
        show_vector_specs = st.checkbox("🔍 Hiển thị chi tiết Tọa độ Vector (Embedding Vector Specs)", value=False, key="api_tab_show_vec")
        
    st.markdown('</div>', unsafe_allow_html=True)
    
    if st.button("🚀 Chạy Kiểm thử API Retrieval", type="primary", use_container_width=True, key="btn_run_api_test"):
        if not api_query_text.strip():
            st.error("❌ Vui lòng nhập truy vấn trước khi chạy thử.")
        else:
            tags_list = api_tab_selected_tags if api_tab_selected_tags else ["math"]
            start_time = time.time()
            
            with st.spinner("Đang thực thi Retrieval & Trích xuất danh sách Vector... 💭"):
                results = []
                status_code_str = "200 OK"
                err_message = None
                
                if "REST API" in exec_mode:
                    try:
                        api_payload = {
                            "text": api_query_text,
                            "tag_name_uuids": tags_list,
                            "type": api_doc_type,
                            "top_k": api_top_k
                        }
                        res = requests.post("http://localhost:8080/api/retrieval", json=api_payload, timeout=10)
                        if res.status_code == 200:
                            resp_json = res.json()
                            results = resp_json.get("results", [])
                        else:
                            status_code_str = f"Error {res.status_code}"
                            err_message = res.text
                    except Exception as e:
                        status_code_str = "Connection Failed"
                        err_message = f"Không thể kết nối tới REST API Backend tại http://localhost:8080. Lỗi: {e}"
                else:
                    try:
                        results = multi_domain_retrieval(
                            query=api_query_text,
                            tag_name_uuids=tags_list,
                            doc_type=api_doc_type,
                            top_k=api_top_k
                        )
                    except Exception as e:
                        err_message = str(e)
                        status_code_str = "Error"
                        
            elapsed_ms = (time.time() - start_time) * 1000
            
            if err_message:
                st.error(f"❌ Thực thi thất bại [{status_code_str}]: {err_message}")
            else:
                st.success(f"⚡ Trích xuất hoàn tất trong **{elapsed_ms:.1f} ms** | Trạng thái: `{status_code_str}` | Tìm thấy **{len(results)} Vector**.")
                
                # Top Metrics Display
                m_c1, m_c2, m_c3, m_c4 = st.columns(4)
                m_c1.metric("Tổng Vector trích xuất", len(results))
                m_c2.metric("Thời gian phản hồi", f"{elapsed_ms:.1f} ms")
                m_c3.metric("Phương thức", "Direct Function" if "Nội bộ" in exec_mode else "REST API")
                m_c4.metric("Kích thước Vector (Dim)", "768 float32")
                
                st.markdown("---")
                st.markdown("#### 🎯 Danh sách Vector tìm thấy (List of Found Vectors)")
                
                if not results:
                    st.warning("⚠️ Không tìm thấy Vector nào phù hợp trong các Collection chỉ định.")
                else:
                    for idx, res in enumerate(results):
                        chunk_id = res.get("id", f"chunk_{idx}")
                        col_name = res.get("collection", "default")
                        dist_val = res.get("distance", 0.0)
                        rrf_val = res.get("rrf_score", 0.0)
                        meta = res.get("metadata", {})
                        text_val = res.get("text", "")
                        
                        phys_p = meta.get('physical_page')
                        pdf_p = meta.get('pdf_page_index')
                        if phys_p is not None and phys_p != -1:
                            page_str = f"Trang vật lý {phys_p}"
                        elif pdf_p is not None and pdf_p != -1:
                            page_str = f"Trang PDF {pdf_p + 1}"
                        else:
                            page_str = "N/A"
                            
                        lesson_str = meta.get("lesson_name", "N/A")
                        vis_str = meta.get("visibility", "public")
                        vol_str = meta.get("volume", "1")
                        file_n = meta.get("file_name", "N/A")
                        
                        with st.container():
                            st.markdown('<div class="custom-card">', unsafe_allow_html=True)
                            st.markdown(f"##### 🧩 **Vector #{idx + 1}: ID `{chunk_id}`**")
                            
                            vc1, vc2, vc3, vc4 = st.columns(4)
                            with vc1:
                                st.markdown(f"**📚 Collection:**\n`{col_name}`")
                            with vc2:
                                st.markdown(f"**📊 RRF Rank Score:**\n`<span style='color:#059669; font-weight:bold;'>{rrf_val:.4f}</span>`", unsafe_allow_html=True)
                            with vc3:
                                st.markdown(f"**📏 Distance Score:**\n`{dist_val:.4f}`")
                            with vc4:
                                st.markdown(f"**📍 Bài học & Vị trí:**\n`{page_str}` (Tập {vol_str})")
                                
                            vmeta1, vmeta2, vmeta3 = st.columns(3)
                            with vmeta1:
                                st.markdown(f"**📖 Bài:** `{lesson_str}`")
                            with vmeta2:
                                st.markdown(f"**📄 Tệp nguồn:** `{file_n}`")
                            with vmeta3:
                                st.markdown(f"**🔒 Quyền:** `{vis_str}`")
                                
                            st.text_area(
                                "📝 Nội dung Chunk (Verbatim Text):",
                                value=text_val,
                                height=130,
                                key=f"api_tab_text_{idx}"
                            )
                            
                            if show_vector_specs:
                                with st.expander("🔍 Chi tiết Embedding Vector Specs & Full Metadata"):
                                    st.json({
                                        "vector_id": chunk_id,
                                        "collection": col_name,
                                        "rrf_score": rrf_val,
                                        "distance_score": dist_val,
                                        "metadata_payload": meta
                                    })
                                    
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                    with st.expander("📋 Xem toàn bộ dữ liệu phản hồi JSON (Raw API Response Payload)"):
                        st.json(results)

# =====================================================================
# TAB 5: VECTOR DB PREVIEW
# =====================================================================
with tab_preview:
    st.markdown("### 🔍 Xem trước các bản ghi trong Vector Database")
    st.markdown("Xem trực tiếp nội dung văn bản sau OCR và thông tin metadata trong collection được phân quyền theo vai trò của bạn.")
    
    # Document Manager Section
    st.markdown("#### 📁 Quản lý các tài liệu đã nạp (Document Manager)")
    try:
        preview_client = get_vector_db_client()
        preview_embedding_fn = get_embedding_function()
        preview_field_val = active_field  # Default field is active_field
        
        # We check the input if it has been created below (since Streamlit runs top-to-bottom, we can get it from session_state)
        if "preview_field" in st.session_state:
            preview_field_val = st.session_state.preview_field
            
        preview_col_name = f"{config.COLLECTION_NAME}_{preview_field_val}"
        
        # Verify collection exists
        preview_collections = [c.name for c in preview_client.list_collections()]
        if preview_col_name in preview_collections:
            preview_collection = get_or_create_collection(preview_client, preview_embedding_fn, collection_name=preview_col_name)
            all_records = preview_collection.get(include=["metadatas"])
            files = {}
            if all_records and "metadatas" in all_records:
                for idx, meta in enumerate(all_records["metadatas"]):
                    fid = meta.get("file_id", "default_textbook")
                    fname = meta.get("file_name") if fid != "default_textbook" else f"Sách giáo khoa Toán 3 (Tập {meta.get('volume', '1')})"
                    if fid not in files:
                        files[fid] = {
                            "file_id": fid,
                            "file_name": fname,
                            "count": 0,
                            "visibility": meta.get("visibility", "public")
                        }
                    files[fid]["count"] += 1
            
            if files:
                for fid, fdetails in files.items():
                    col_doc1, col_doc2 = st.columns([4, 1])
                    with col_doc1:
                        st.markdown(f"📄 **{fdetails['file_name']}** (`{fdetails['file_id']}`) - {fdetails['count']} trang, Phân quyền: `{fdetails['visibility']}`")
                    with col_doc2:
                        if fid != "default_textbook":
                            if st.button("Xóa tài liệu", key=f"del_{fid}"):
                                preview_collection.delete(where={"file_id": str(fid)})
                                st.success(f"Đã xóa tài liệu '{fdetails['file_name']}'!")
                                time.sleep(1.0)
                                st.rerun()
                        else:
                            st.write("*(Sách cốt lõi)*")
            else:
                st.info("Chưa có tài liệu nào được nạp.")
        else:
            st.info("Chưa có collection nào hoạt động cho tài liệu / Tag UUID này.")
    except Exception as e:
        st.error(f"Lỗi khi tải danh sách tài liệu: {e}")
    st.markdown("---")
    
    col_p1, col_p2, col_p3 = st.columns([1, 1, 1])
    with col_p1:
        preview_field = st.selectbox(
            "Xem tài liệu (Tag Name UUID)",
            options=available_tags if available_tags else ["math"],
            index=available_tags.index(active_field) if active_field in available_tags else 0,
            key="preview_field"
        )
    with col_p2:
        preview_role = st.selectbox(
            "Xem dưới quyền vai trò (Role)",
            options=[config.ROLE_STUDENT, config.ROLE_TEACHER, config.ROLE_ADMIN],
            index=[config.ROLE_STUDENT, config.ROLE_TEACHER, config.ROLE_ADMIN].index(user_role),
            key="preview_role"
        )
    with col_p3:
        preview_limit = st.slider("Số lượng bản ghi tối đa", min_value=5, max_value=100, value=20, step=5)
        
    if st.button("🔄 Tải lại dữ liệu ChromaDB"):
        st.toast("Đang tải dữ liệu...")
        
    # Query ChromaDB using the preview utility logic
    try:
        client = get_vector_db_client()
        embedding_fn = get_embedding_function()
        col_name = f"{config.COLLECTION_NAME}_{preview_field}"
        
        # Verify collection exists
        collections = [c.name for c in client.list_collections()]
        if col_name not in collections:
            st.info(f"ℹ️ Không tìm thấy collection: `{col_name}`. Tài liệu này có thể chưa được nạp dữ liệu.")
        else:
            collection = get_or_create_collection(client, embedding_fn, collection_name=col_name)
            total_records = collection.count()
            st.metric("Tổng số bản ghi trong collection", total_records)
            
            # Build metadata filters for RBAC (identical to backend `/api/preview`)
            where_filter = {}
            if preview_role != config.ROLE_ADMIN:
                allowed_visibilities = config.ROLE_VISIBILITY_MAPPING.get(preview_role, ["public"])
                if len(allowed_visibilities) == 1:
                    where_filter = {"visibility": allowed_visibilities[0]}
                else:
                    where_filter = {"$or": [{"visibility": v} for v in allowed_visibilities]}
            
            chroma_where = where_filter if where_filter else None
            
            # Fetch documents
            results = collection.get(
                limit=preview_limit,
                where=chroma_where,
                include=["documents", "metadatas"]
            )
            
            if not results or not results["ids"]:
                st.warning("⚠️ Không có bản ghi nào phù hợp với vai trò và bộ lọc phân quyền này.")
            else:
                # Format records for display
                for i, doc_id in enumerate(results["ids"]):
                    doc_text = results["documents"][i]
                    doc_meta = results["metadatas"][i]
                    
                    with st.expander(f"📄 **ID: {doc_id}** | Bài: {doc_meta.get('lesson_name', 'Chưa rõ')} | Trang: {doc_meta.get('physical_page', -1)}"):
                        # Show metadata as columns
                        meta_cols = st.columns(5)
                        meta_cols[0].write(f"**Tập sách:** {doc_meta.get('volume', 'Chưa rõ')}")
                        meta_cols[1].write(f"**Trang PDF:** {doc_meta.get('pdf_page_index', -1)}")
                        meta_cols[2].write(f"**Môn học:** {doc_meta.get('field', 'Chưa rõ')}")
                        
                        # Style visibility
                        vis = doc_meta.get('visibility', 'public')
                        vis_color = "green" if vis == "public" else ("blue" if vis == "teacher_only" else "red")
                        meta_cols[3].markdown(f"**Quyền:** <span style='color:{vis_color}; font-weight:bold;'>{vis}</span>", unsafe_allow_html=True)
                        
                        # Show raw text
                        st.text_area("Nội dung text đã OCR", value=doc_text, height=150, disabled=True, key=f"text_{doc_id}")
    except Exception as e:
        st.error(f"Lỗi khi đọc Vector Database: {e}")

# =====================================================================
# TAB 4: SYSTEM HEALTH & METRIC DIAGNOSTICS
# =====================================================================
with tab_health:
    st.markdown("### 🏥 Chẩn đoán & Trạng thái Hệ thống")
    
    col_h1, col_h2 = st.columns(2)
    
    with col_h1:
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.markdown("#### 1. Kết nối Cơ sở Dữ liệu (ChromaDB)")
        try:
            db_client = get_vector_db_client()
            db_client.heartbeat()
            st.markdown('Trạng thái: <span class="status-badge status-online">ONLINE</span>', unsafe_allow_html=True)
            st.success("Kết nối đến ChromaDB hoạt động bình thường!")
            
            # List current collections
            st.markdown("**Danh sách collections hiện tại:**")
            collections = db_client.list_collections()
            for col in collections:
                st.write(f"- `{col.name}` ({col.count()} records)")
        except Exception as e:
            st.markdown('Trạng thái: <span class="status-badge status-offline">OFFLINE</span>', unsafe_allow_html=True)
            st.error(f"Không thể kết nối đến cơ sở dữ liệu: {e}")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_h2:
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.markdown("#### 2. Cấu hình Khóa API (API Credentials)")
        
        # Verify API Key availability
        has_gemini = bool(config.GEMINI_API_KEY)
        has_openai = bool(config.OPENAI_API_KEY)
        use_vertex = config.USE_VERTEXAI
        
        st.write(f"- **Môi trường Vertex AI:** {'Hoạt động' if use_vertex else 'Tắt'}")
        if use_vertex:
            st.write(f"  - Project ID: `{config.GOOGLE_CLOUD_PROJECT}`")
            st.write(f"  - Location: `{config.GOOGLE_CLOUD_LOCATION}`")
            
        st.write(f"- **Khóa Gemini API (Local):** {'Đã cấu hình ✅' if has_gemini else 'Chưa có ❌'}")
        st.write(f"- **Khóa OpenAI API (Local):** {'Đã cấu hình ✅' if has_openai else 'Chưa có ❌'}")
        
        st.markdown("#### 3. Đường dẫn Dữ liệu (System Paths)")
        st.write(f"- Thư mục gốc: `{config.BASE_DIR}`")
        st.write(f"- Thư mục DB: `{config.DB_DIR}`")
        st.write(f"- Thư mục mẫu: `{config.DATA_SAMPLES_DIR}`")
        st.markdown('</div>', unsafe_allow_html=True)


# =====================================================================
# TAB 7: CENTRALIZED PROMPT REGISTRY
# =====================================================================
with tab_prompt_reg:
    st.markdown("### ⚙️ Hệ thống Quản lý Prompts Tập trung (Prompt Registry)")
    st.markdown("Quản lý, chỉnh sửa, và kích hoạt các phiên bản system prompts cho từng Agent trong hệ thống mà không cần cập nhật file n8n workflow.")
    
    # Selected profile
    profile_col1, profile_col2 = st.columns([3, 1])
    with profile_col1:
        selected_profile = st.selectbox(
            "📁 Chọn Profile Prompts",
            options=["default", "math", "science"],
            index=0,
            key="prompt_reg_profile"
        )
    with profile_col2:
        custom_profile = st.text_input("Hoặc nhập Profile mới", value="", key="prompt_reg_custom_profile")
        if custom_profile.strip():
            selected_profile = custom_profile.strip()
            
    # List of Agents
    agent_options = [
        "planner",
        "default_teacher",
        "barem_review",
        "theory_explanation",
        "exercise_generator",
        "suggestive_tutor",
        "direct_solver",
        "verifier"
    ]
    
    selected_agent_name = st.selectbox(
        "🤖 Chọn Agent để quản lý",
        options=agent_options,
        index=1, # Default to default_teacher
        format_func=lambda x: {
            "planner": "1. Bộ Điều Phối (Planner Agent)",
            "default_teacher": "2. Giáo viên Mặc định (Default Teacher)",
            "barem_review": "3. Chấm điểm Barem (Barem Reviewer)",
            "theory_explanation": "4. Giảng Lý thuyết (Theory Explainer)",
            "exercise_generator": "5. Tạo Bài tập (Exercise Generator)",
            "suggestive_tutor": "6. Gia sư Gợi mở (Suggestive Tutor)",
            "direct_solver": "7. Giải nhanh (Direct Solver)",
            "verifier": "8. Bộ Kiểm định QA (Verifier Agent)"
        }.get(x, x),
        key="prompt_reg_agent"
    )
    
    # Load active prompt for this agent and profile from FastAPI
    api_url_active = f"http://localhost:8080/api/prompts/active?profile={selected_profile}"
    active_prompt_text = ""
    try:
        res = requests.get(api_url_active)
        if res.status_code == 200:
            active_prompts = res.json()
            active_prompt_text = active_prompts.get(selected_agent_name, "")
        else:
            st.error(f"Lỗi khi tải prompt hiện tại từ backend (Status: {res.status_code})")
    except Exception as e:
        st.error(f"Không thể kết nối đến backend API: {e}")
        
    st.markdown("#### 📝 Nội dung Prompt hiện tại (Hoạt động)")
    new_prompt_text = st.text_area(
        "Chỉnh sửa nội dung prompt",
        value=active_prompt_text,
        height=300,
        key=f"prompt_reg_text_area_{selected_profile}_{selected_agent_name}"
    )
    
    col_pub1, col_pub2 = st.columns([1, 4])
    with col_pub1:
        if st.button("🚀 Xuất bản Phiên bản Mới", type="primary", use_container_width=True, key="btn_publish_prompt"):
            if not new_prompt_text.strip():
                st.error("Nội dung prompt không được để trống.")
            else:
                try:
                    payload = {
                        "agent_name": selected_agent_name,
                        "profile": selected_profile,
                        "prompt_text": new_prompt_text,
                        "updated_by": "admin",
                        "is_active": True
                    }
                    res_pub = requests.post("http://localhost:8080/api/prompts", json=payload)
                    if res_pub.status_code == 200:
                        st.success(f"✅ Đã xuất bản phiên bản {res_pub.json().get('version')} thành công!")
                        st.rerun()
                    else:
                        st.error(f"Lỗi khi xuất bản: {res_pub.text}")
                except Exception as e:
                    st.error(f"Lỗi kết nối: {e}")
                    
    # History of versions
    st.markdown("---")
    st.markdown("#### ⏳ Lịch sử thay đổi (Versions History)")
    api_url_history = f"http://localhost:8080/api/prompts/versions?agent_name={selected_agent_name}&profile={selected_profile}"
    try:
        res_hist = requests.get(api_url_history)
        if res_hist.status_code == 200:
            history = res_hist.json()
            if not history:
                st.info("Chưa có lịch sử phiên bản nào cho Agent và Profile này.")
            else:
                for item in history:
                    is_act = item["is_active"] == 1
                    status_lbl = "🟢 [ĐANG HOẠT ĐỘNG]" if is_act else "⚪ [LỊCH SỬ]"
                    with st.expander(f"Phiên bản {item['version']} | {status_lbl} | Cập nhật bởi: {item['updated_by']} lúc {item['updated_at']}"):
                        st.code(item["prompt_text"], language="text")
                        if not is_act:
                            if st.button(f"Kích hoạt & Quay lại phiên bản {item['version']}", key=f"btn_rollback_{item['id']}"):
                                try:
                                    payload_act = {
                                        "agent_name": selected_agent_name,
                                        "profile": selected_profile,
                                        "version": item["version"],
                                        "updated_by": "admin"
                                    }
                                    res_act = requests.post("http://localhost:8080/api/prompts/activate", json=payload_act)
                                    if res_act.status_code == 200:
                                        st.success(f"✅ Đã quay lại phiên bản {item['version']} thành công!")
                                        st.rerun()
                                    else:
                                        st.error(f"Lỗi khi kích hoạt phiên bản: {res_act.text}")
                                except Exception as e:
                                    st.error(f"Lỗi kết nối: {e}")
        else:
            st.error(f"Lỗi khi tải lịch sử: {res_hist.status_code}")
    except Exception as e:
        st.error(f"Lỗi kết nối khi tải lịch sử: {e}")


# =====================================================================
# TAB 8: LIVE TESTING SECURE WEBHOOK
# =====================================================================
with tab_live_test:
    st.markdown("### 🧪 Live Testing (n8n Webhook Verification)")
    st.markdown("Gửi các câu hỏi kiểm thử kèm theo tùy chỉnh profile prompt, phiên bản, hoặc các prompt overrides trực tiếp tới n8n Webhook và theo dõi phản hồi thời gian thực.")
    
    use_overrides = st.checkbox("Sử dụng Prompt Overrides", value=False, key="lt_use_overrides")
    
    col_lt_cfg1, col_lt_cfg2 = st.columns(2)
    with col_lt_cfg1:
        n8n_url_lt = st.text_input(
            "🔗 n8n Webhook URL", 
            value="http://localhost:5678/webhook/rag-math-assistant",
            key="lt_n8n_url",
            help="Điền URL Webhook n8n. Nếu kiểm thử thủ công, đổi '/webhook/' thành '/webhook-test/'."
        )
        st.info("💡 **Mẹo sửa lỗi 404 Webhook:**\n"
                "- Nếu workflow n8n **đang tắt** (Inactive): Hãy đổi chữ `/webhook/` trong URL thành `/webhook-test/` và click nút **'Listen for test event'** trong n8n trước khi chạy thử.\n"
                "- Nếu muốn chạy chính thức: Hãy **kích hoạt** workflow bằng cách gạt nút **'Active'** ở góc trên cùng bên phải giao diện n8n.")
    with col_lt_cfg2:
        lt_profile = st.text_input("📁 prompt_profile", value="default", key="lt_profile")
        lt_version_str = st.text_input("🔢 prompt_version (Tùy chọn, để trống = active)", value="", key="lt_version")
        lt_version = int(lt_version_str) if lt_version_str.strip().isdigit() else None
        
    st.markdown("#### 🧠 Prompt Overrides (Tùy chỉnh đè hệ thống)")
    st.markdown("Bạn có thể viết đè prompt tạm thời cho các Agent cụ thể (chỉ áp dụng cho lượt gọi Webhook này).")
    
    prompt_overrides = {}
    
    if use_overrides:
        agent_override_options = [
            "planner",
            "default_teacher",
            "barem_review",
            "theory_explanation",
            "exercise_generator",
            "suggestive_tutor",
            "direct_solver",
            "verifier",
            "verifier_default_teacher",
            "verifier_barem_review",
            "verifier_theory_explanation",
            "verifier_exercise_generator",
            "verifier_suggestive_tutor",
            "verifier_direct_solver"
        ]
        
        for agent_name in agent_override_options:
            override_val = st.text_area(
                f"Đè prompt cho '{agent_name}'",
                value="",
                height=100,
                key=f"lt_override_{agent_name}",
                placeholder="Nhập prompt thay thế để kiểm thử..."
            )
            if override_val.strip():
                prompt_overrides[agent_name] = override_val.strip()
                
    st.markdown("#### 📝 Nội dung câu hỏi thử nghiệm")
    lt_prompt = st.text_area("Câu hỏi (Prompt)", value="Con muốn làm bài 2 trang 15 tập 1 nhưng chưa biết bắt đầu thế nào. Cô gợi ý cho con được không?", height=100, key="lt_prompt")
    
    col_lt_t1, col_lt_t2 = st.columns(2)
    with col_lt_t1:
        st.markdown("**Chọn các tài liệu (Tag Name UUIDs):**")
        lt_selected_tags = []
        for tag in available_tags:
            default_val = tag in selected_tags
            if st.checkbox(f"📁 {tag}", value=default_val, key=f"lt_cb_{tag}"):
                lt_selected_tags.append(tag)
                
    with col_lt_t2:
        st.markdown("**Chọn các Tổ chức (Organization IDs):**")
        available_orgs = get_all_org_ids()
        lt_selected_orgs = []
        for org in available_orgs:
            if st.checkbox(f"🏢 {org}", value=True, key=f"lt_org_cb_{org}"):
                lt_selected_orgs.append(org)
    
    if st.button("🚀 Thực thi Live Test", type="primary", use_container_width=True, key="btn_run_lt"):
        if not lt_prompt.strip():
            st.error("Vui lòng nhập câu hỏi.")
        else:
            with st.spinner("Đang gửi câu hỏi & prompt cấu hình tới n8n Multi-Agent... 💭"):
                start_t = time.time()
                try:
                    payload = {
                        "prompt": lt_prompt,
                        "tag_name_uuid": lt_selected_tags if lt_selected_tags else ["math"],
                        "org_id": lt_selected_orgs if lt_selected_orgs else ["org_default"],
                        "prompt_profile": lt_profile,
                        "prompt_version": lt_version,
                        "prompt_overrides": prompt_overrides
                    }
                    
                    headers = {
                        "Content-Type": "application/json"
                    }
                    res = requests.post(n8n_url_lt, json=payload, headers=headers, timeout=120)
                    elapsed = time.time() - start_t
                    
                    if res.status_code == 200:
                        try:
                            res_data = res.json()
                            output_text = res_data.get("output", "")
                            if not output_text and "response" in res_data:
                                output_text = res_data["response"]
                                
                            st.success(f"✅ Hoàn thành trong {elapsed:.2f} giây!")
                            
                            st.markdown("#### 🎯 Phản hồi đã xác minh (Verified Output):")
                            st.markdown('<div class="custom-card" style="background-color: #f0fdf4; border-left: 5px solid #16a34a;">', unsafe_allow_html=True)
                            st.markdown(output_text)
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            with st.expander("📋 Chi tiết phản hồi raw JSON"):
                                st.json(res_data)
                        except Exception as e:
                            st.warning(f"Trả về 200 OK nhưng không thể giải mã JSON: {e}")
                            st.text_area("Raw Response Content", value=res.text, height=200)
                    else:
                        st.error(f"❌ Lỗi từ n8n Webhook (Status Code: {res.status_code})")
                        st.text_area("Chi tiết lỗi raw", value=res.text, height=200)
                except Exception as e:
                    st.error(f"❌ Lỗi kết nối tới n8n Webhook: {e}")


# =====================================================================
# TAB 9: MENTOR TEST GENERATOR & SUBMISSION GRADER STUDIO
# =====================================================================
with tab_mentor_test:
    st.markdown("### 📝 Mentor Studio: Tạo Đề Thi & Chấm Bài Tự Động")
    st.markdown("Giao diện thử nghiệm thủ công (Manual Testing) dành cho Giáo viên/Mentor: Tạo đề thi + barem JSON và chấm điểm bài làm + phân tích chủ đề yếu.")

    subtab_gen, subtab_grade = st.tabs([
        "🎯 1. Tạo Đề Thi & Barem Mẫu (Test Generator)",
        "📊 2. Chấm Bài & Phân Tích Chủ Đề Yếu (Submission Grader)"
    ])

    # -------------------------------------------------------------
    # SUB-TAB 1: TEST GENERATOR
    # -------------------------------------------------------------
    with subtab_gen:
        st.markdown("#### 🛠️ Cấu hình tiêu chuẩn thiết kế Đề Thi")
        
        col_mt_url, col_mt_mode = st.columns([3, 1])
        with col_mt_url:
            mt_gen_webhook = st.text_input(
                "🔗 Webhook URL (Test Generator)",
                value="http://localhost:5678/webhook/mentor-test-generator",
                key="mt_gen_webhook",
                help="Nếu workflow n8n chưa bật Active, đổi /webhook/ thành /webhook-test/."
            )
        with col_mt_mode:
            mt_gen_env = st.selectbox("Môi trường", ["Production (/webhook/)", "Test (/webhook-test/)"], index=0, key="mt_gen_env")
            if "Test" in mt_gen_env and "/webhook/" in mt_gen_webhook:
                mt_gen_webhook = mt_gen_webhook.replace("/webhook/", "/webhook-test/")

        col_mt_1, col_mt_2 = st.columns(2)
        with col_mt_1:
            mt_subject = st.selectbox("Môn học", ["Toán học", "Khoa học tự nhiên", "Ngữ văn", "Tiếng Anh", "Lịch sử & Địa lý"], index=0, key="mt_subject_v2")
            mt_grade = st.selectbox("Khối lớp", ["Lớp 1", "Lớp 2", "Lớp 3", "Lớp 4", "Lớp 5"], index=3, key="mt_grade_v2")
            mt_topic = st.text_input("Chủ đề thi", value="Ôn tập các số đến 100 000, phép cộng, phép trừ và hình học Lớp 4", key="mt_topic_v2")
            mt_knowledge = st.text_area("Kiến thức trọng tâm", value="Tính giá trị biểu thức, số tròn chục nghìn, đặt tính rồi tính và bài toán đố hình học", height=90, key="mt_knowledge_v2")
        with col_mt_2:
            mt_difficulty = st.selectbox("Mức độ khó", ["Dễ", "Trung bình", "Khó", "Phân hóa"], index=1, key="mt_difficulty_v2")
            mt_time = st.selectbox("Thời gian làm bài", ["15 phút", "35 phút", "40 phút", "45 phút", "60 phút"], index=3, key="mt_time_v2")
            col_sc1, col_sc2 = st.columns(2)
            with col_sc1:
                mt_mcq_count = st.number_input("Số câu Trắc nghiệm", min_value=1, max_value=20, value=6, step=1, key="mt_mcq_count_v2")
                mt_mcq_score = st.number_input("Điểm Trắc nghiệm", min_value=0.0, max_value=10.0, value=6.0, step=0.5, key="mt_mcq_score_v2")
            with col_sc2:
                mt_essay_count = st.number_input("Số câu Tự luận", min_value=0, max_value=10, value=4, step=1, key="mt_essay_count_v2")
                mt_essay_score = st.number_input("Điểm Tự luận", min_value=0.0, max_value=10.0, value=4.0, step=0.5, key="mt_essay_score_v2")

        mt_additional = st.text_area("Yêu cầu bổ sung", value="Đặt câu hỏi thực tế sinh động phù hợp học sinh Lớp 4.", height=70, key="mt_additional_v2")

        if st.button("🚀 Thực thi Sinh Đề Thi & Barem JSON", type="primary", use_container_width=True, key="btn_run_gen_test"):
            with st.spinner("Đang gửi yêu cầu thiết kế đề thi tới Test Generator Agent... 💭"):
                start_t = time.time()
                try:
                    payload = {
                        "action": "generate",
                        "subject": mt_subject,
                        "grade": mt_grade,
                        "topic": mt_topic,
                        "knowledge_tested": mt_knowledge,
                        "difficulty": mt_difficulty,
                        "time_limit": mt_time,
                        "mcq_count": mt_mcq_count,
                        "essay_count": mt_essay_count,
                        "mcq_score_total": mt_mcq_score,
                        "essay_score_total": mt_essay_score,
                        "additional_instructions": mt_additional
                    }
                    res = requests.post(mt_gen_webhook, json=payload, headers={"Content-Type": "application/json"}, timeout=120)
                    elapsed = time.time() - start_t

                    if res.status_code == 200:
                        res_data = res.json()
                        st.session_state["latest_generated_test"] = res_data
                        st.success(f"✅ Hoàn thành sinh đề thi trong {elapsed:.2f} giây!")

                        de_thi = res_data.get("de_thi", {})
                        barem = res_data.get("barem_cham_diem", {})
                        test_id = res_data.get("test_id", "N/A")

                        # Display Summary Metrics
                        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                        col_m1.metric("Mã Đề Thi", test_id)
                        col_m2.metric("Môn / Lớp", f"{de_thi.get('subject', mt_subject)} - {de_thi.get('grade', mt_grade)}")
                        col_m3.metric("Tổng điểm", f"{de_thi.get('total_score', 10.0)} đ")
                        col_m4.metric("Thời gian", de_thi.get('time_limit', mt_time))

                        # Tabs for viewing generated output
                        tab_view_exam, tab_view_barem, tab_view_json = st.tabs(["📄 Nội dung Đề Thi", "🔑 Barem Chấm Điểm Mẫu", "📦 Raw JSON"])

                        with tab_view_exam:
                            st.markdown(f"### {de_thi.get('title', 'ĐỀ KIỂM TRA')}")
                            st.markdown(f"**Hướng dẫn:** {de_thi.get('instructions', 'Đọc kỹ đề và làm bài.')}")
                            for part in de_thi.get("parts", []):
                                st.markdown(f"#### {part.get('part_name', '')}")
                                for q in part.get("questions", []):
                                    st.markdown(f"**Câu {q.get('question_number', '')} ({q.get('score', '')}đ):** {q.get('prompt', '')}")
                                    options = q.get("options")
                                    if options and isinstance(options, dict):
                                        for k, v in options.items():
                                            st.markdown(f"- **{k}.** {v}")
                                    st.markdown("---")

                        with tab_view_barem:
                            st.markdown("#### 1. Đáp án phần Trắc nghiệm")
                            mcq_ans = barem.get("mcq_answers", [])
                            if mcq_ans:
                                st.table([
                                    {
                                        "Mã câu": m.get("question_id"),
                                        "Đáp án đúng": m.get("correct_option"),
                                        "Điểm": m.get("score"),
                                        "Giải thích": m.get("explanation")
                                    } for m in mcq_ans
                                ])

                            st.markdown("#### 2. Thang điểm chi tiết Phần Tự luận")
                            for essay_ans in barem.get("essay_answers", []):
                                with st.expander(f"📌 {essay_ans.get('question_id')} - Điểm tối đa: {essay_ans.get('score')}đ"):
                                    for s in essay_ans.get("solution_steps", []):
                                        st.markdown(f"- **Bước {s.get('step')} ({s.get('score')}đ):** {s.get('description')}")

                        with tab_view_json:
                            st.json(res_data)

                    else:
                        st.error(f"❌ Lỗi HTTP {res.status_code} từ n8n Webhook")
                        st.text_area("Chi tiết phản hồi lỗi", value=res.text, height=150)
                except Exception as e:
                    st.error(f"❌ Lỗi kết nối tới Webhook: {e}")

    # -------------------------------------------------------------
    # SUB-TAB 2: SUBMISSION GRADER & WEAK TOPICS DIAGNOSTICS
    # -------------------------------------------------------------
    with subtab_grade:
        st.markdown("#### 📊 Chấm điểm bài làm & Phân tích chẩn đoán chủ đề yếu")

        col_gr_url, col_gr_quick = st.columns([3, 2])
        with col_gr_url:
            mt_grade_webhook = st.text_input(
                "🔗 Webhook URL (Submission Grader)",
                value="http://localhost:5678/webhook/mentor-test-generator",
                key="mt_grade_webhook"
            )
        with col_gr_quick:
            st.markdown("**Thao tác nhanh:**")
            if st.button("💡 Nạp Đề Thi, Barem & Bài Làm Mẫu (Lớp 4 - 50% Điểm)", key="btn_load_sample_math4"):
                # Pre-fill sample payload in session state
                st.session_state["gr_test_id"] = "TEST_MATH4_SAMPLE_E2E"
                st.session_state["gr_student_id"] = "Trần Văn C - Lớp 4A"
                sample_barem = {
                    "test_id": "TEST_MATH4_SAMPLE_E2E",
                    "total_score": 10.0,
                    "mcq_answers": [
                        {"question_id": "MCQ_1", "correct_option": "B", "score": 1.0, "explanation": "45 000 + 35 000 = 80 000"},
                        {"question_id": "MCQ_2", "correct_option": "A", "score": 1.0, "explanation": "Số 56 789 nhỏ nhất"},
                        {"question_id": "MCQ_3", "correct_option": "C", "score": 1.0, "explanation": "120 x 4 = 480"},
                        {"question_id": "MCQ_4", "correct_option": "D", "score": 1.0, "explanation": "Hình vuông có 4 góc vuông"},
                        {"question_id": "MCQ_5", "correct_option": "A", "score": 1.0, "explanation": "Chu vi = (25 + 15) x 2 = 80m"},
                        {"question_id": "MCQ_6", "correct_option": "B", "score": 1.0, "explanation": "Diện tích = 10 x 10 = 100 cm2"}
                    ],
                    "essay_answers": [
                        {
                            "question_id": "ESSAY_1",
                            "score": 1.0,
                            "solution_steps": [
                                {"step": 1, "description": "Đặt tính đúng và cộng các hàng: 34 567 + 23 412 = 57 979", "score": 1.0}
                            ]
                        },
                        {
                            "question_id": "ESSAY_2",
                            "score": 1.0,
                            "solution_steps": [
                                {"step": 1, "description": "Tính số kg gạo mỗi bao: 45 : 5 = 9 (kg)", "score": 0.5},
                                {"step": 2, "description": "Tính số kg gạo 8 bao: 9 x 8 = 72 (kg)", "score": 0.5}
                            ]
                        },
                        {
                            "question_id": "ESSAY_3",
                            "score": 1.0,
                            "solution_steps": [
                                {"step": 1, "description": "Tính nửa chu vi: 50 : 2 = 25 (m)", "score": 0.5},
                                {"step": 2, "description": "Tính diện tích: 25 x 10 = 250 (m2)", "score": 0.5}
                            ]
                        },
                        {
                            "question_id": "ESSAY_4",
                            "score": 1.0,
                            "solution_steps": [
                                {"step": 1, "description": "Sắp xếp theo thứ tự tăng dần: 12 345, 23 456, 34 567, 45 678", "score": 1.0}
                            ]
                        }
                    ]
                }
                sample_submission_text = """MÃ ĐỀ THI: TEST_MATH4_SAMPLE_E2E
HỌC SINH: Trần Văn C - Lớp 4A

PHẦN I: TRẮC NGHIỆM
Câu 1 (MCQ_1): B
Câu 2 (MCQ_2): A
Câu 3 (MCQ_3): C
Câu 4 (MCQ_4): A
Câu 5 (MCQ_5): B
Câu 6 (MCQ_6): C

PHẦN II: TỰ LUẬN
Câu tự luận 1 (ESSAY_1):
Lời giải:
- Bước 1: 34 567 + 23 412 = 57 979
Đáp số: 57 979

Câu tự luận 2 (ESSAY_2):
Lời giải:
- Bước 1: Số kg gạo mỗi bao là: 45 : 5 = 9 (kg)
- Bước 2: Số kg gạo 8 bao là: 9 x 8 = 72 (kg)
Đáp số: 72 kg

Câu tự luận 3 (ESSAY_3):
Lời giải:
- Bước 1: Thực hiện tính tổng: 150 + 250 = 350 (kg)
Đáp số: 350 kg

Câu tự luận 4 (ESSAY_4):
Lời giải:
- Bước 1: Thực hiện tính tổng: 150 + 250 = 350 (kg)
Đáp số: 350 kg"""
                st.session_state["gr_barem_json"] = json.dumps(sample_barem, ensure_ascii=False, indent=2)
                st.session_state["gr_submission_txt"] = sample_submission_text
                st.toast("✅ Đã nạp Đề thi & Bài làm mẫu (50% điểm) thành công!")

        # Pull values from session_state if set
        default_test_id = st.session_state.get("gr_test_id", "TEST_MATH4_001")
        default_student_id = st.session_state.get("gr_student_id", "Trần Văn C - Lớp 4A")
        default_barem_str = st.session_state.get("gr_barem_json", "{\n  \"test_id\": \"TEST_MATH4_001\"\n}")
        default_submission_txt = st.session_state.get("gr_submission_txt", "")

        col_gr1, col_gr2 = st.columns(2)
        with col_gr1:
            gr_test_id = st.text_input("Mã Đề Thi (test_id)", value=default_test_id, key="gr_test_id_input")
            gr_student_id = st.text_input("Tên / Mã Học Sinh", value=default_student_id, key="gr_student_id_input")
            gr_barem_text = st.text_area("Barem Chấm Điểm (JSON)", value=default_barem_str, height=250, key="gr_barem_text_input")
        with col_gr2:
            st.markdown("**Bài Làm Của Học Sinh (.txt hoặc Nhập Văn Bản)**")
            uploaded_file = st.file_uploader("Tải tệp bài làm (.txt)", type=["txt"], key="gr_file_uploader")
            if uploaded_file is not None:
                submission_from_file = uploaded_file.read().decode("utf-8")
                default_submission_txt = submission_from_file
            
            gr_submission_text = st.text_area("Nội dung bài làm của học sinh", value=default_submission_txt, height=270, key="gr_submission_text_input")

        if st.button("📊 Chấm Bài Thi & Phân Tích Lỗi Sai", type="primary", use_container_width=True, key="btn_run_grading"):
            if not gr_submission_text.strip():
                st.error("Vui lòng nhập hoặc tải tệp bài làm của học sinh.")
            else:
                with st.spinner("Submission Grader Agent đang chấm bài và phân tích chẩn đoán... 💭"):
                    start_t = time.time()
                    try:
                        # Try parsing barem json
                        try:
                            barem_obj = json.loads(gr_barem_text)
                        except Exception:
                            barem_obj = gr_barem_text

                        grade_payload = {
                            "action": "grade",
                            "test_id": gr_test_id,
                            "student_id": gr_student_id,
                            "barem": barem_obj,
                            "student_submission": gr_submission_text
                        }

                        res = requests.post(mt_grade_webhook, json=grade_payload, headers={"Content-Type": "application/json"}, timeout=120)
                        elapsed = time.time() - start_t

                        if res.status_code == 200:
                            res_data = res.json()
                            st.success(f"✅ Đã chấm bài hoàn tất trong {elapsed:.2f} giây!")

                            grading_res = res_data.get("grading_result", {})
                            total_score = grading_res.get("total_score", 0)
                            max_score = grading_res.get("max_score", 10)
                            percentage = grading_res.get("percentage", 0)
                            overall_feedback = grading_res.get("overall_feedback", "")
                            weak_topics = grading_res.get("weak_topics", [])

                            # Top Score Metrics Cards
                            main_topic = grading_res.get("topic", "Tổng hợp kiến thức")
                            col_sm1, col_sm2, col_sm3, col_sm4 = st.columns(4)
                            col_sm1.metric("Chủ Đề Kiểm Tra", main_topic)
                            col_sm2.metric("Tổng Điểm Đạt Được", f"{total_score} / {max_score}")
                            col_sm3.metric("Tỷ Lệ Chính Xác", f"{percentage}%")
                            eval_status = "🟢 Giỏi / Xuất Sắc" if percentage >= 80 else ("🟡 Khá / Trung Bình" if percentage >= 50 else "🔴 Cần Tăng Cường")
                            col_sm4.metric("Đánh Giá Trung", eval_status)

                            # Overall Feedback Card
                            st.markdown("#### 💬 Nhận xét Tổng quan của Giáo viên:")
                            st.markdown(f'<div class="custom-card" style="background-color: #f0f9ff; border-left: 5px solid #0284c7;">'
                                        f'<strong>{overall_feedback}</strong></div>', unsafe_allow_html=True)

                            # WEAK TOPICS DIAGNOSTICS SECTION
                            st.markdown("#### ⚠️ CHẨN ĐOÁN CHỦ ĐỀ HỔNG KIẾN THỨC / SAI NHIỀU (WEAK TOPICS)")
                            if weak_topics:
                                for idx, topic_item in enumerate(weak_topics, 1):
                                    t_title = topic_item.get("topic") or topic_item.get("topic_name", "Chủ đề hổng kiến thức")
                                    sev = topic_item.get("severity", "Trung bình").lower()
                                    badge_color = "#ef4444" if "cao" in sev else ("#f59e0b" if "trung" in sev else "#3b82f6")
                                    bg_color = "#fef2f2" if "cao" in sev else ("#fffbeb" if "trung" in sev else "#eff6ff")
                                    
                                    st.markdown(
                                        f'<div class="custom-card" style="background-color: {bg_color}; border-left: 5px solid {badge_color};">'
                                        f'<h5>{idx}. {t_title} '
                                        f'<span style="background-color:{badge_color}; color:white; padding:2px 8px; border-radius:10px; font-size:0.8rem;">Mức độ: {topic_item.get("severity", "Trung bình")}</span></h5>'
                                        f'<p><strong>🔍 Nguyên nhân & Lỗi sai:</strong> {topic_item.get("description", "")}</p>'
                                        f'<p><strong>💡 Gợi ý khắc phục:</strong> {topic_item.get("recommendation", "")}</p>'
                                        f'</div>',
                                        unsafe_allow_html=True
                                    )
                            else:
                                st.info("🎉 Học sinh không có chủ đề hổng kiến thức nghiêm trọng nào!")

                            # Detailed Per-Question Breakdowns
                            st.markdown("#### 🔍 Chi Tiết Chấm Điểm Từng Câu")
                            tab_mcq_det, tab_essay_det, tab_raw_grade = st.tabs(["📝 Trắc Nghiệm (MCQ)", "✍️ Tự Luận (Essay)", "📦 Raw JSON Output"])

                            with tab_mcq_det:
                                mcq_res = grading_res.get("mcq_results", [])
                                if mcq_res:
                                    mcq_table_data = []
                                    for m in mcq_res:
                                        status_str = "✅ Đúng" if m.get("is_correct") else "❌ Sai"
                                        mcq_table_data.append({
                                            "Câu hỏi": m.get("question_id"),
                                            "Đáp án học sinh": m.get("student_answer"),
                                            "Đáp án đúng": m.get("correct_answer"),
                                            "Kết quả": status_str,
                                            "Điểm đạt": f"{m.get('score_earned')}/{m.get('max_score')}",
                                            "Nhận xét": m.get("feedback")
                                        })
                                    st.table(mcq_table_data)

                            with tab_essay_det:
                                essay_res = grading_res.get("essay_results", [])
                                for e in essay_res:
                                    with st.expander(f"✍️ {e.get('question_id')} - Điểm: {e.get('score_earned')}/{e.get('max_score')}đ"):
                                        st.markdown(f"**Bài làm học sinh:**\n```text\n{e.get('student_answer')}\n```")
                                        st.markdown(f"**Nhận xét chung câu này:** {e.get('feedback')}")
                                        st.markdown("**Đánh giá từng bước:**")
                                        for stp in e.get("step_evaluations", []):
                                            st.markdown(f"- **Bước {stp.get('step')} ({stp.get('earned_score')}/{stp.get('max_score')}đ):** {stp.get('comment')} *(Mô tả: {stp.get('description')})*")

                            with tab_raw_grade:
                                st.json(res_data)

                        else:
                            st.error(f"❌ Lỗi HTTP {res.status_code} từ n8n Webhook")
                            st.text_area("Chi tiết phản hồi lỗi raw", value=res.text, height=150)
                    except Exception as e:
                        st.error(f"❌ Lỗi kết nối tới n8n Webhook: {e}")

