import os
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
import fitz

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")
pdf_path = Path("data-samples/toan-3-tap-1.pdf")

# Configure
genai.configure(api_key=api_key)
# We test gemini-2.0-flash
model = genai.GenerativeModel("gemini-2.0-flash")

doc = fitz.open(pdf_path)
page = doc.load_page(24)
pix = page.get_pixmap(dpi=150)
img_bytes = pix.tobytes("png")

prompt = """
Đây là hình ảnh trang sách giáo khoa Toán lớp 3, thuộc bộ sách "Kết nối tri thức với cuộc sống".
Hãy phân tích hình ảnh và thực hiện các nhiệm vụ sau:
1. Đọc số trang vật lý (được in ở góc dưới của trang sách). Nếu không thấy hoặc bị che khuất, hãy để null.
2. Xác định tên bài học lớn hiện tại của trang này (ví dụ: "Bài 4: Phép cộng, phép trừ trong phạm vi 1000").
3. Trích xuất toàn bộ văn bản và các bài tập toán trên trang này. Chuyển đổi các biểu thức toán học, phép nhân, phép chia thành định dạng văn bản rõ ràng hoặc LaTeX nếu cần thiết. Đảm bảo giữ đúng thứ tự bài tập.

Trả về kết quả dưới định dạng JSON theo cấu trúc sau:
{
  "physical_page": <int hoặc null>,
  "lesson_name": "string",
  "text": "string"
}
"""

try:
    print("Calling Gemini 2.0 Flash...")
    response = model.generate_content(
        contents=[
            {"mime_type": "image/png", "data": img_bytes},
            prompt
        ],
        generation_config={"response_mime_type": "application/json"}
    )
    print("Response text:")
    print(response.text)
except Exception as e:
    print(f"Error: {e}")
