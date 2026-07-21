import fitz  # PyMuPDF
from google import genai
from google.genai import types
from src import config
from pathlib import Path
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

class PDFBookParser:
    def __init__(self, pdf_path: Path, volume: str, api_key: str):
        self.pdf_path = pdf_path
        self.volume = volume
        self.api_key = api_key
        
        # Configure Gemini Client
        if config.USE_VERTEXAI:
            self.client = genai.Client(
                vertexai=True,
                project=config.GOOGLE_CLOUD_PROJECT,
                location=config.GOOGLE_CLOUD_LOCATION
            )
        else:
            self.client = genai.Client(api_key=api_key)
        
        self.doc = fitz.open(pdf_path)
        
    def parse_page(self, page_index: int) -> dict:
        """
        Renders a specific PDF page to PNG and sends it to Gemini for Multimodal OCR.
        """
        page = self.doc.load_page(page_index)
        
        # Render page to PNG at 150 DPI for good readability without huge file size
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
        
        # Retry logic for network/rate-limit issues
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        types.Part.from_bytes(
                            data=img_bytes,
                            mime_type="image/png"
                        ),
                        prompt
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                
                # Parse JSON response
                data = json.loads(response.text)
                return {
                    "volume": self.volume,
                    "pdf_page_index": page_index,
                    "pdf_page_number": page_index + 1,
                    "physical_page": data.get("physical_page"),
                    "lesson_name": data.get("lesson_name"),
                    "text": data.get("text", "")
                }
            except Exception as e:
                error_msg = str(e)
                print(f"[Warning] Retry {attempt + 1}/{max_attempts} for page {page_index} of {self.pdf_path.name}: {error_msg}")
                if attempt == max_attempts - 1:
                    return {
                        "volume": self.volume,
                        "pdf_page_index": page_index,
                        "physical_page": None,
                        "lesson_name": None,
                        "text": ""
                    }
                
                # If rate limited, sleep longer
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    sleep_time = 15 * (attempt + 1)
                    print(f"Rate limit hit on page {page_index}. Sleeping for {sleep_time} seconds before retrying...")
                else:
                    sleep_time = 2 ** attempt
                time.sleep(sleep_time)

    def parse_all_pages(self, max_workers: int = 2) -> list[dict]:
        """
        Parses all pages in parallel using a ThreadPoolExecutor.
        """
        pages_count = len(self.doc)
        results = [None] * pages_count
        
        print(f"Starting Multimodal OCR on {self.pdf_path.name} ({pages_count} pages) with {max_workers} threads...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(self.parse_page, i): i 
                for i in range(pages_count)
            }
            
            for future in as_completed(future_to_index):
                i = future_to_index[future]
                try:
                    result = future.result()
                    results[i] = result
                    print(f"Processed page {i+1}/{pages_count} of {self.pdf_path.name}")
                except Exception as e:
                    print(f"Error processing page {i} of {self.pdf_path.name}: {e}")
                    results[i] = {
                        "volume": self.volume,
                        "pdf_page_index": i,
                        "physical_page": None,
                        "lesson_name": None,
                        "text": ""
                    }
                    
        # Apply sequential fallback post-processing
        return self.post_process_pages(results)

    def post_process_pages(self, pages: list[dict]) -> list[dict]:
        """
        Interpolates any missing physical page numbers and propagates lesson names forward.
        """
        # Determine the most common offset (physical_page - pdf_page_index)
        offsets = []
        for p in pages:
            if p["physical_page"] is not None:
                offsets.append(p["physical_page"] - p["pdf_page_index"])
                
        if offsets:
            most_common_offset = max(set(offsets), key=offsets.count)
        else:
            most_common_offset = 0
            
        # Interpolate page numbers
        for i, p in enumerate(pages):
            if p["physical_page"] is None:
                inferred = None
                # Backward check
                for j in range(i - 1, -1, -1):
                    if pages[j]["physical_page"] is not None:
                        inferred = pages[j]["physical_page"] + (i - j)
                        break
                # Forward check
                if inferred is None:
                    for j in range(i + 1, len(pages)):
                        if pages[j]["physical_page"] is not None:
                            inferred = pages[j]["physical_page"] - (j - i)
                            break
                # Fallback to general offset
                if inferred is None or inferred <= 0:
                    inferred = i + most_common_offset
                    
                p["physical_page"] = inferred
                
            # Clean up and propagate lesson name
            if not p["lesson_name"] or p["lesson_name"].strip() == "":
                if i > 0 and pages[i-1]["lesson_name"]:
                    p["lesson_name"] = pages[i-1]["lesson_name"]
                else:
                    p["lesson_name"] = "Giới thiệu / Đầu sách"
            else:
                p["lesson_name"] = p["lesson_name"].strip()
                
        return pages
