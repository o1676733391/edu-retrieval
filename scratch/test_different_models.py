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

doc = fitz.open(pdf_path)
page = doc.load_page(24)
pix = page.get_pixmap(dpi=150)
img_bytes = pix.tobytes("png")

prompt = """
Đây là hình ảnh trang sách giáo khoa Toán lớp 3, thuộc bộ sách "Kết nối tri thức với cuộc sống".
Hãy phân tích hình ảnh và thực hiện các nhiệm vụ sau:
1. Đọc số trang vật lý (được in ở góc dưới của trang sách).
2. Xác định tên bài học lớn hiện tại của trang này.
3. Trích xuất toàn bộ văn bản.
Trả về định dạng JSON:
{
  "physical_page": 24,
  "lesson_name": "test",
  "text": "test"
}
"""

models_to_test = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-3.5-flash",
    "gemini-flash-latest",
]

for model_name in models_to_test:
    print(f"\n--- Testing {model_name} ---")
    model = genai.GenerativeModel(model_name)
    try:
        response = model.generate_content(
            contents=[
                {"mime_type": "image/png", "data": img_bytes},
                prompt
            ],
            generation_config={"response_mime_type": "application/json"}
        )
        print(f"Success! Response text: {response.text[:200]}")
        break
    except Exception as e:
        print(f"Failed: {e}")
