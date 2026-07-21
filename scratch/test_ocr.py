import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
import fitz

# 1. Load environment configs
load_dotenv()
sys.stdout.reconfigure(encoding='utf-8')

use_vertex = os.environ.get("USE_VERTEXAI", "false").lower() == "true"
project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
api_key = os.environ.get("GEMINI_API_KEY")

print("=== RUNNING OCR TEST WITH VERTEX AI ===")
print(f"USE_VERTEXAI:          {use_vertex}")
print(f"GOOGLE_CLOUD_PROJECT:   {project}")
print(f"GOOGLE_CLOUD_LOCATION:  {location}")

# Set application credentials path if gcp-key.json exists in data directory
gcp_key = Path("data/gcp-key.json")
if gcp_key.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(gcp_key.resolve())
    print(f"Found GCP credentials file at: {gcp_key.resolve()}")

# 2. Initialize Client
try:
    if use_vertex:
        client = genai.Client(
            vertexai=True,
            project=project,
            location=location
        )
        print("Initialized client using Google Cloud Vertex AI.")
    else:
        client = genai.Client(api_key=api_key)
        print("Initialized client using Google AI Studio developer API key.")
except Exception as e:
    print(f"Failed to initialize client: {e}")
    sys.exit(1)

# 3. Load PDF Page and render to PNG
pdf_path = Path("data-samples/toan-3-tap-1.pdf")
if not pdf_path.exists():
    print(f"Error: PDF not found at {pdf_path}")
    sys.exit(1)

doc = fitz.open(pdf_path)
page = doc.load_page(24)  # Page index 24
pix = page.get_pixmap(dpi=150)
img_bytes = pix.tobytes("png")

prompt = """
Đây là hình ảnh trang sách giáo khoa Toán lớp 3, thuộc bộ sách "Kết nối tri thức với cuộc sống".
Hãy phân tích hình ảnh và thực hiện các nhiệm vụ sau:
1. Đọc số trang vật lý (được in ở góc dưới của trang sách). Nếu không thấy hoặc bị che khuất, hãy để null.
2. Xác định tên bài học lớn hiện tại của trang này.
3. Trích xuất toàn bộ văn bản và các bài tập toán trên trang này.

Trả về kết quả dưới định dạng JSON theo cấu trúc sau:
{
  "physical_page": <int hoặc null>,
  "lesson_name": "string",
  "text": "string"
}
"""

# 4. Call LLM
print("\nCalling gemini-2.5-flash model via genai client...")
start_time = time.time()
try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
            prompt
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    print(f"Success! Response generated in {time.time() - start_time:.2f} seconds:")
    print("-" * 50)
    print(response.text)
    print("-" * 50)
except Exception as e:
    print(f"Error calling model: {e}")
