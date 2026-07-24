import fitz  # PyMuPDF
from google import genai
from google.genai import types
from src import config
from pathlib import Path
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import threading
import os

# Thread-safe lock and global in-memory cache for page-level OCR caching
_cache_lock = threading.Lock()
_global_cache = None

def load_global_cache():
    global _global_cache
    if _global_cache is not None:
        return _global_cache
    
    global_cache_path = config.DATA_DIR / "ocr_page_cache.json"
    if global_cache_path.exists():
        try:
            with open(global_cache_path, "r", encoding="utf-8") as f:
                _global_cache = json.load(f)
        except Exception as e:
            print(f"[Warning] Failed to load global OCR page cache: {e}")
            _global_cache = {}
    else:
        _global_cache = {}
    return _global_cache

def save_global_cache():
    global_cache_path = config.DATA_DIR / "ocr_page_cache.json"
    try:
        os.makedirs(os.path.dirname(global_cache_path), exist_ok=True)
        with open(global_cache_path, "w", encoding="utf-8") as f:
            json.dump(_global_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Warning] Failed to save global OCR page cache: {e}")

class PDFBookParser:
    def __init__(self, pdf_path: Path, volume: str, api_key: str, checkpoint_id: str = None):
        self.pdf_path = pdf_path
        self.volume = volume
        self.api_key = api_key
        
        # Unique checkpoint ID
        if checkpoint_id:
            self.checkpoint_id = checkpoint_id
        else:
            self.checkpoint_id = hashlib.md5(str(pdf_path.resolve()).encode()).hexdigest()
        
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
        Uses global page-level cache based on the MD5 hash of the rendered PNG bytes.
        """
        page = self.doc.load_page(page_index)
        
        # Render page to PNG at 150 DPI for good readability without huge file size
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        img_hash = hashlib.md5(img_bytes).hexdigest()
        
        # Check global cache thread-safely
        with _cache_lock:
            cache = load_global_cache()
            if img_hash in cache:
                cached_data = cache[img_hash]
                print(f"[Cache Hit] Page {page_index + 1} of {self.pdf_path.name} loaded from global page cache.")
                return {
                    "volume": self.volume,
                    "pdf_page_index": page_index,
                    "pdf_page_number": page_index + 1,
                    "physical_page": cached_data.get("physical_page"),
                    "lesson_name": cached_data.get("lesson_name"),
                    "text": cached_data.get("text", "")
                }
        
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
                parsed_result = {
                    "volume": self.volume,
                    "pdf_page_index": page_index,
                    "pdf_page_number": page_index + 1,
                    "physical_page": data.get("physical_page"),
                    "lesson_name": data.get("lesson_name"),
                    "text": data.get("text", "")
                }
                
                # Write to global cache thread-safely
                with _cache_lock:
                    cache = load_global_cache()
                    cache[img_hash] = {
                        "physical_page": parsed_result["physical_page"],
                        "lesson_name": parsed_result["lesson_name"],
                        "text": parsed_result["text"]
                    }
                    save_global_cache()
                    
                return parsed_result
            except Exception as e:
                error_msg = str(e)
                print(f"[Warning] Retry {attempt + 1}/{max_attempts} for page {page_index} of {self.pdf_path.name}: {error_msg}")
                if attempt == max_attempts - 1:
                    return {
                        "volume": self.volume,
                        "pdf_page_index": page_index,
                        "pdf_page_number": page_index + 1,
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

    def parse_batch(self, batch: list[int]) -> list[dict]:
        """
        Extracts the specified page indexes into a temp PDF, sends it to Gemini,
        and returns a list of parsed page dictionaries.
        """
        # Render PNG bytes of each page in the batch to calculate their MD5 hashes
        img_hashes = []
        for idx in batch:
            page = self.doc.load_page(idx)
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            img_hashes.append(hashlib.md5(img_bytes).hexdigest())

        # Extract pages into a temporary PDF
        batch_doc = fitz.open()
        for idx in batch:
            batch_doc.insert_pdf(self.doc, from_page=idx, to_page=idx)
        pdf_bytes = batch_doc.write()
        batch_doc.close()

        # Build page list string for prompt
        pdf_page_numbers = [idx + 1 for idx in batch]

        prompt = f"""
        Đây là tài liệu PDF chứa {len(batch)} trang sách giáo khoa Toán lớp 3.
        Các trang này tương ứng với các số trang PDF (bắt đầu từ 1) trong sách gốc lần lượt là: {pdf_page_numbers}.

        Hãy thực hiện OCR và phân tích nội dung cho từng trang theo đúng thứ tự.
        Trả về kết quả dưới dạng một danh sách JSON (array) chứa đúng {len(batch)} phần tử tương ứng theo thứ tự gửi.
        Mỗi phần tử phải tuân thủ cấu trúc sau:
        {{
          "pdf_page_number": <số trang PDF gốc tương ứng trong danh sách {pdf_page_numbers}>,
          "physical_page": <số trang vật lý được in trên trang sách, hoặc null nếu không có>,
          "lesson_name": "tên bài học tương ứng của trang này",
          "text": "toàn bộ văn bản và câu hỏi toán học của trang này"
        }}
        """

        # Retry logic for network/rate-limit issues
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        types.Part.from_bytes(
                            data=pdf_bytes,
                            mime_type="application/pdf"
                        ),
                        prompt
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )

                # Parse JSON response
                results = json.loads(response.text)
                if not isinstance(results, list) or len(results) != len(batch):
                    raise ValueError(f"Gemini returned {len(results) if isinstance(results, list) else 'non-list'} items, expected {len(batch)}.")

                parsed_results = []
                for k, item in enumerate(results):
                    idx = batch[k]
                    parsed_results.append({
                        "volume": self.volume,
                        "pdf_page_index": idx,
                        "pdf_page_number": idx + 1,
                        "physical_page": item.get("physical_page"),
                        "lesson_name": item.get("lesson_name"),
                        "text": item.get("text", "")
                    })

                # Write to global cache thread-safely
                with _cache_lock:
                    cache = load_global_cache()
                    for k, res in enumerate(parsed_results):
                        h = img_hashes[k]
                        cache[h] = {
                            "physical_page": res["physical_page"],
                            "lesson_name": res["lesson_name"],
                            "text": res["text"]
                        }
                    save_global_cache()

                return parsed_results

            except Exception as e:
                error_msg = str(e)
                print(f"[Warning] Retry {attempt + 1}/{max_attempts} for batch {pdf_page_numbers} of {self.pdf_path.name}: {error_msg}")
                if attempt == max_attempts - 1:
                    # Fallback to page-by-page OCR if the batch fails consistently
                    print(f"Batch {pdf_page_numbers} failed consistently. Falling back to page-by-page OCR...")
                    fallback_results = []
                    for idx in batch:
                        fallback_results.append(self.parse_page(idx))
                    return fallback_results

                # If rate limited, sleep longer
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    sleep_time = 20 * (attempt + 1)
                    print(f"Rate limit hit on batch {pdf_page_numbers}. Sleeping for {sleep_time} seconds before retrying...")
                else:
                    sleep_time = 2 ** attempt
                time.sleep(sleep_time)

    def parse_all_pages(self, max_workers: int = 2) -> list[dict]:
        """
        Parses all pages. Groups missing pages into batches to minimize API requests and avoid rate limits.
        """
        pages_count = len(self.doc)
        results = [None] * pages_count
        
        # 1. Setup Checkpoint path
        checkpoint_dir = config.DATA_DIR / "ocr_checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = checkpoint_dir / f"{self.checkpoint_id}.json"
        
        # 2. Try loading existing checkpoint
        checkpoint_data = {}
        if checkpoint_path.exists():
            try:
                with open(checkpoint_path, "r", encoding="utf-8") as f:
                    checkpoint_data = json.load(f)
                print(f"Resuming OCR on {self.pdf_path.name} from checkpoint. Found {len(checkpoint_data)} completed pages.")
            except Exception as e:
                print(f"[Warning] Failed to load checkpoint: {e}")
                
        # Populate results with already completed pages from checkpoint
        completed_pages = 0
        for i in range(pages_count):
            str_i = str(i)
            if str_i in checkpoint_data:
                results[i] = checkpoint_data[str_i]
                completed_pages += 1
                
        # Check global page cache for remaining pages before calling API
        # (This avoids loading/rendering images if they are already in the global cache)
        with _cache_lock:
            cache = load_global_cache()
            
        pages_to_check = [i for i in range(pages_count) if results[i] is None]
        if pages_to_check:
            print(f"Checking global page cache for {len(pages_to_check)} pages of {self.pdf_path.name}...")
            for idx in pages_to_check:
                # We need the image hash to check cache, so we must load the page and render it
                page = self.doc.load_page(idx)
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                img_hash = hashlib.md5(img_bytes).hexdigest()
                
                with _cache_lock:
                    if img_hash in cache:
                        cached_data = cache[img_hash]
                        results[idx] = {
                            "volume": self.volume,
                            "pdf_page_index": idx,
                            "pdf_page_number": idx + 1,
                            "physical_page": cached_data.get("physical_page"),
                            "lesson_name": cached_data.get("lesson_name"),
                            "text": cached_data.get("text", "")
                        }
                        completed_pages += 1
                        checkpoint_data[str(idx)] = results[idx]
                        
        # Write updated checkpoint
        if completed_pages > 0:
            try:
                with open(checkpoint_path, "w", encoding="utf-8") as f:
                    json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[Warning] Failed to write checkpoint: {e}")

        # If all pages are already completed, skip the executor
        if completed_pages < pages_count:
            pages_to_process = [i for i in range(pages_count) if results[i] is None]
            print(f"OCR progress: {completed_pages}/{pages_count} pages completed. Processing remaining {len(pages_to_process)} pages in batches...")
            
            # Group pages_to_process into batches of size N (e.g. 5)
            batch_size = 5
            batches = [pages_to_process[i:i + batch_size] for i in range(0, len(pages_to_process), batch_size)]
            
            # Process batches sequentially to be gentle on RPM rate limits, or with max_workers=2
            for batch_idx, batch in enumerate(batches):
                print(f"Processing batch {batch_idx + 1}/{len(batches)}: pages {[idx + 1 for idx in batch]}")
                batch_results = self.parse_batch(batch)
                
                # Merge batch results
                for res in batch_results:
                    idx = res["pdf_page_index"]
                    results[idx] = res
                    checkpoint_data[str(idx)] = res
                    
                # Save checkpoint after each batch
                try:
                    with open(checkpoint_path, "w", encoding="utf-8") as f:
                        json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"[Warning] Failed to write checkpoint: {e}")
        else:
            print(f"All {pages_count} pages loaded successfully from cache/checkpoint.")

        # Apply sequential fallback post-processing
        processed_results = self.post_process_pages(results)
        
        # Cleanup checkpoint file since the whole document is fully parsed and post-processed
        if checkpoint_path.exists():
            try:
                checkpoint_path.unlink()
                print(f"Successfully completed OCR. Cleaned up checkpoint: {checkpoint_path.name}")
            except Exception as e:
                print(f"[Warning] Failed to delete checkpoint file {checkpoint_path.name}: {e}")
                
        return processed_results

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
