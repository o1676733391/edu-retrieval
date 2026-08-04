import json
import os
import hashlib
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from google import genai
from google.genai import types
from src import config
from src.vector_store.client import get_vector_store, get_embedding_function

# Lock for thread-safe cache updates and saving
_cache_lock = threading.Lock()

IMAGE_OCR_PROMPT = """
Đây là hình ảnh liên quan đến một ngôi nhà/bất động sản đang được rao bán.
Hãy phân tích hình ảnh này và thực hiện các nhiệm vụ sau:
1. Xác định đây là bộ phận/phòng nào của bất động sản (ví dụ: Mặt tiền, phòng khách, phòng ngủ, nhà bếp, nhà vệ sinh, ban công, sân thượng, ngõ đi, bản vẽ thiết kế, v.v.). Gán giá trị này vào trường "room_type".
2. Đọc và trích xuất mọi văn bản/chữ viết xuất hiện trên hình ảnh (OCR), bao gồm cả chữ số, sơ đồ thiết kế hoặc văn bản tiếng Việt nếu có. Gán kết quả vào trường "ocr_text".
3. Mô tả chi tiết trực quan phong phú (khoảng 100 từ) về những gì xuất hiện trong hình ảnh (không gian rộng hay hẹp, chất liệu gỗ hay đá, màu sắc chủ đạo, thiết bị nội thất mới hay cũ, tình trạng ánh sáng tự nhiên, góc chụp, cách sắp xếp đồ đạc). Gán kết quả vào trường "visual_description".

Hãy trả về kết quả dưới định dạng JSON theo đúng cấu trúc sau:
{
  "room_type": "Tên phòng/bộ phận",
  "ocr_text": "Văn bản trích xuất được hoặc chuỗi rỗng",
  "visual_description": "Mô tả trực quan chi tiết phong phú bằng tiếng Việt khoảng 100 từ"
}
"""

UNIFIED_HOUSE_PROMPT = """
Bạn là một chuyên gia bất động sản cao cấp có kinh nghiệm viết bài quảng cáo hấp dẫn và trung thực.
Dưới đây là thông số kỹ thuật của căn nhà:
- ID nhà: {house_id}
- Tên địa điểm/Dự án: {place_name}
- Tên đường/Phố: {street_name}
- Diện tích sổ đỏ: {area} m²
- Diện tích thực tế: {actual_area} m²
- Số tầng: {floors}
- Chiều rộng mặt tiền: {wide} m
- Chiều sâu: {depth} m
- Giá bán rao: {offering_price} tỷ VNĐ
- Số phòng ngủ: {bedrooms}
- Số phòng tắm: {bathrooms}
- Có bãi đỗ xe ô tô: {has_car_parking}

Dưới đây là mô tả chi tiết thu được từ việc phân tích hình ảnh thực tế của ngôi nhà:
{images_summary}

Hãy tổng hợp tất cả thông tin trên để viết một bài giới thiệu bất động sản toàn diện, thu hút và có cấu trúc mạch lạc bằng tiếng Việt.
Bài viết cần mô tả trực quan sinh động căn nhà, phân tích các điểm mạnh nổi bật (ví dụ: phòng khách rộng rãi, bếp hiện đại, phòng ngủ ấm cúng, thiết bị cao cấp, ô tô đỗ cửa, vị trí đẹp, v.v.) dựa trên mô tả thực tế từ các phòng và thông số kỹ thuật đã cho. Tránh bịa đặt thông tin không có trong mô tả ảnh hoặc thông số kỹ thuật.

Hãy trả về kết quả dưới định dạng JSON theo đúng cấu trúc sau:
{{
  "unified_description": "Nội dung bài giới thiệu chi tiết bất động sản bằng tiếng Việt"
}}
"""


def load_houses_cache():
    cache_path = config.DATA_DIR / "houses_cache.json"
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Warning] Failed to load houses cache: {e}")
            return {"images": {}, "houses": {}}
    else:
        return {"images": {}, "houses": {}}


def save_houses_cache(cache_data):
    cache_path = config.DATA_DIR / "houses_cache.json"
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Warning] Failed to save houses cache: {e}")


def get_gemini_client(api_key: str = None):
    key = api_key or config.GEMINI_API_KEY
    if config.USE_VERTEXAI:
        return genai.Client(
            vertexai=True,
            project=config.GOOGLE_CLOUD_PROJECT,
            location=config.GOOGLE_CLOUD_LOCATION
        )
    else:
        if not key:
            raise ValueError("GEMINI_API_KEY is not configured in your environment.")
        return genai.Client(api_key=key)


def process_single_image(client, img_path: Path, force_ocr: bool = False) -> dict:
    """
    Worker function to process a single house image using Gemini.
    """
    img_name = img_path.name
    
    # Check cache first
    if not force_ocr:
        with _cache_lock:
            cache = load_houses_cache()
            if img_name in cache.get("images", {}):
                print(f"[Cache Hit] Image description loaded from cache for '{img_name}'.")
                return cache["images"][img_name]

    print(f"[OCR] Sending image '{img_name}' to Gemini...")
    if not img_path.exists():
        print(f"[Warning] Image path not found: {img_path}")
        return {"room_type": "Unknown", "ocr_text": "", "visual_description": "Image not found."}

    # Determine MIME type based on extension
    suffix = img_path.suffix.lower()
    mime_type = "image/jpeg"
    if suffix == ".png":
        mime_type = "image/png"
    elif suffix == ".webp":
        mime_type = "image/webp"

    with open(img_path, "rb") as f:
        img_bytes = f.read()

    # Retry logic
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(
                        data=img_bytes,
                        mime_type=mime_type
                    ),
                    IMAGE_OCR_PROMPT
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            # Parse JSON
            data = json.loads(response.text)
            parsed_result = {
                "room_type": data.get("room_type", "Unknown"),
                "ocr_text": data.get("ocr_text", ""),
                "visual_description": data.get("visual_description", "")
            }

            # Write back to cache thread-safely
            with _cache_lock:
                cache = load_houses_cache()
                cache.setdefault("images", {})[img_name] = parsed_result
                save_houses_cache(cache)

            return parsed_result
        except Exception as e:
            error_msg = str(e)
            print(f"[Warning] Retry {attempt + 1}/{max_attempts} for image {img_name}: {error_msg}")
            if attempt == max_attempts - 1:
                return {"room_type": "Unknown", "ocr_text": "", "visual_description": f"Failed to parse image. Error: {error_msg}"}

            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                sleep_time = 15 * (attempt + 1)
                print(f"Rate limit hit on image {img_name}. Sleeping for {sleep_time} seconds before retrying...")
            else:
                sleep_time = 2 ** attempt
            time.sleep(sleep_time)

    return {"room_type": "Unknown", "ocr_text": "", "visual_description": "Failed to parse image."}


def run_houses_ingest(
    houses_json_path: str = None,
    images_dir: str = None,
    collection_name: str = "houses",
    force_ocr: bool = False,
    api_key: str = None,
    batch_size: int = 5
) -> dict:
    """
    Full workflow to ingest house listings, perform OCR/description on all house images,
    synthesize a comprehensive house description, embed it, and store it in Vector DB.
    """
    print("Starting House Ingest Workflow...")
    
    # 1. Paths resolution
    if not houses_json_path:
        houses_json_path = config.DATA_SAMPLES_DIR / "houses" / "houses.json"
    else:
        houses_json_path = Path(houses_json_path)

    if not images_dir:
        images_dir = config.DATA_SAMPLES_DIR / "houses"
    else:
        images_dir = Path(images_dir)

    if not houses_json_path.exists():
        raise FileNotFoundError(f"houses.json not found at {houses_json_path}")

    # Load houses listing
    with open(houses_json_path, "r", encoding="utf-8") as f:
        houses_data = json.load(f)

    print(f"Loaded {len(houses_data)} houses from {houses_json_path.name}.")

    client = get_gemini_client(api_key)

    # Output stats
    results = {
        "status": "success",
        "total_houses": len(houses_data),
        "processed_houses": [],
        "errors": []
    }

    # 2. Iterate through houses
    for house_idx, house in enumerate(houses_data):
        house_id = str(house["id"])
        print(f"\n--- [House {house_idx + 1}/{len(houses_data)}] ID: {house_id} ---")
        
        # Check cache for unified description
        cache = load_houses_cache()
        unified_description = None
        if not force_ocr:
            unified_description = cache.get("houses", {}).get(house_id, {}).get("unified_description")
            if unified_description:
                print(f"[Cache Hit] Unified description for house {house_id} loaded from cache.")

        # If not cached, analyze images and then generate description
        if not unified_description:
            media_list = house.get("media", [])
            images_to_process = []
            for media in media_list:
                if media.get("mediaType") == "image":
                    img_name = media.get("fileName")
                    img_path = images_dir / img_name
                    if img_path.exists():
                        images_to_process.append(img_path)
                    else:
                        print(f"[Warning] Image file not found locally: {img_path}")

            print(f"House {house_id} has {len(images_to_process)} local images to process.")
            
            image_results = []
            if images_to_process:
                # Concurrently process house images in batches to prevent API rate limit while staying fast
                batches = [images_to_process[i:i + batch_size] for i in range(0, len(images_to_process), batch_size)]
                for b_idx, batch in enumerate(batches):
                    print(f"Processing image batch {b_idx + 1}/{len(batches)} for house {house_id}...")
                    with ThreadPoolExecutor(max_workers=min(len(batch), 3)) as executor:
                        future_to_img = {executor.submit(process_single_image, client, img, force_ocr): img for img in batch}
                        for future in as_completed(future_to_img):
                            img_path = future_to_img[future]
                            try:
                                img_res = future.result()
                                image_results.append((img_path.name, img_res))
                            except Exception as exc:
                                print(f"[Error] Image {img_path.name} generated an exception: {exc}")
                                image_results.append((img_path.name, {"room_type": "Unknown", "ocr_text": "", "visual_description": f"Exception: {exc}"}))

            # Build summaries string
            images_summary_list = []
            for img_name, res in image_results:
                images_summary_list.append(
                    f"- Ảnh '{img_name}' ({res.get('room_type', 'Không rõ')}):\n"
                    f"  + Chữ viết trong ảnh (OCR): {res.get('ocr_text', 'Không có')}\n"
                    f"  + Mô tả trực quan: {res.get('visual_description', '')}"
                )
            images_summary_str = "\n".join(images_summary_list) if images_summary_list else "Không có hình ảnh thực tế."

            # Generate Unified Description
            print(f"Synthesizing unified description for house {house_id}...")
            place_name = house.get("placeName", "").replace("\n", " ").strip()
            street_name = house.get("streetName") or "Chưa rõ"
            area = house.get("area") or 0.0
            actual_area = house.get("actualArea") or area
            floors = house.get("floors") or "Chưa rõ"
            wide = house.get("wide") or 0.0
            depth = house.get("depth") or 0.0
            offering_price = house.get("offeringPrice") or 0.0
            bedrooms = house.get("bedrooms") or "Chưa rõ"
            bathrooms = house.get("bathrooms") or "Chưa rõ"
            has_car_parking = "Có" if house.get("hasCarParking") else ("Không" if house.get("hasCarParking") is False else "Chưa rõ")

            prompt = UNIFIED_HOUSE_PROMPT.format(
                house_id=house_id,
                place_name=place_name,
                street_name=street_name,
                area=area,
                actual_area=actual_area,
                floors=floors,
                wide=wide,
                depth=depth,
                offering_price=offering_price,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                has_car_parking=has_car_parking,
                images_summary=images_summary_str
            )

            # Generate call with retry
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json"
                        )
                    )
                    desc_data = json.loads(response.text)
                    unified_description = desc_data.get("unified_description", "")
                    
                    # Update cache
                    with _cache_lock:
                        cache = load_houses_cache()
                        cache.setdefault("houses", {})[house_id] = {
                            "unified_description": unified_description,
                            "images_summary": images_summary_str,
                            "metadata": {
                                "id": int(house_id),
                                "placeName": place_name,
                                "streetName": street_name,
                                "area": area,
                                "actualArea": actual_area,
                                "floors": floors,
                                "wide": wide,
                                "depth": depth,
                                "offeringPrice": offering_price,
                                "bedrooms": bedrooms,
                                "bathrooms": bathrooms,
                                "hasCarParking": house.get("hasCarParking")
                            }
                        }
                        save_houses_cache(cache)
                    break
                except Exception as e:
                    error_msg = str(e)
                    print(f"[Warning] Retry {attempt + 1}/{max_attempts} unified description for house {house_id}: {error_msg}")
                    if attempt == max_attempts - 1:
                        unified_description = f"Mô tả cơ bản: {place_name}. Giá rao {offering_price} tỷ. Diện tích {area} m²."
                    time.sleep(2 ** attempt)

        # Retrieve images_summary from cache if it wasn't generated in this run
        if 'images_summary_str' not in locals() or not images_summary_str:
            cache = load_houses_cache()
            images_summary_str = cache.get("houses", {}).get(house_id, {}).get("images_summary", "Không có chi tiết ảnh.")

        # Build full text to embed: includes BOTH general description AND all individual image descriptions (~100 words each)
        full_embed_text = (
            f"THÔNG TIN CHUNG VÀ MÔ TẢ TỔNG QUÁT CĂN NHÀ (ID {house_id}):\n"
            f"{unified_description}\n\n"
            f"MÔ TẢ CHI TIẾT TỪNG HÌNH ẢNH THỰC TẾ (KHOẢNG 100 TỪ MỖI ẢNH):\n"
            f"{images_summary_str}"
        )

        # 3. Embedding and Indexing into Vector DB
        print(f"Indexing house {house_id} into collection '{collection_name}'...")
        
        # Prepare Metadata (ensure strict basic types for Chroma/Qdrant)
        place_name_clean = house.get("placeName", "").replace("\n", " ").strip() if house.get("placeName") else ""
        metadata_entry = {
            "house_id": int(house["id"]),
            "latitude": float(house["latitude"]) if house.get("latitude") is not None else 0.0,
            "longitude": float(house["longitude"]) if house.get("longitude") is not None else 0.0,
            "placeName": place_name_clean,
            "streetName": str(house["streetName"]) if house.get("streetName") else "Unknown",
            "area": float(house["area"]) if house.get("area") is not None else 0.0,
            "actualArea": float(house["actualArea"]) if house.get("actualArea") is not None else 0.0,
            "floors": int(house["floors"]) if house.get("floors") is not None else -1,
            "wide": float(house["wide"]) if house.get("wide") is not None else 0.0,
            "depth": float(house["depth"]) if house.get("depth") is not None else 0.0,
            "offeringPrice": float(house["offeringPrice"]) if house.get("offeringPrice") is not None else 0.0,
            "bedrooms": int(house["bedrooms"]) if house.get("bedrooms") is not None else -1,
            "bathrooms": int(house["bathrooms"]) if house.get("bathrooms") is not None else -1,
            "hasCarParking": bool(house["hasCarParking"]) if house.get("hasCarParking") is not None else False,
            "doc_type": "house",
            "page_content": full_embed_text,
            "unified_description": unified_description,
            "images_summary": images_summary_str
        }

        try:
            # Let's use field="houses" so that default structure works smoothly
            vector_store = get_vector_store("houses", collection_name_override=collection_name)
            
            doc_id = f"house_{house_id}"
            vector_store.upsert(
                ids=[doc_id],
                documents=[full_embed_text],
                metadatas=[metadata_entry]
            )
            print(f"[DB] Successfully indexed house ID: {house_id}")
            results["processed_houses"].append(house_id)
        except Exception as e:
            err_msg = f"Failed to index house {house_id}: {str(e)}"
            print(f"[Error] {err_msg}")
            results["errors"].append(err_msg)

    print("\nHouse Ingest Workflow Completed Successfully!")
    return results
