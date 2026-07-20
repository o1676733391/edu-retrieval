import json
from pathlib import Path
from src import config
from src.pipeline.pdf_parser import PDFBookParser
from src.vector_store.client import get_vector_db_client, get_embedding_function, get_or_create_collection

def parse_to_epoch(date_input: str) -> float:
    import datetime
    if not date_input:
        return datetime.datetime.now(datetime.timezone.utc).timestamp()
    try:
        dt = datetime.datetime.fromisoformat(date_input.replace('Z', '+00:00'))
        return dt.timestamp()
    except Exception:
        try:
            dt = datetime.datetime.strptime(date_input, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
            return dt.timestamp()
        except Exception:
            return datetime.datetime.now(datetime.timezone.utc).timestamp()

def run_ingest(
    force_ocr: bool = False,
    field: str = "math",
    visibility: str = "public",
    pdf_path: str = None,
    volume: str = "1",
    description: str = None,
    file_id: str = None,
    file_name: str = None,
    owner_id: str = None,
    allowed_group: str = None,
    allowed_user: str = None,
    mode: str = "keep_cache",
    datetime_str: str = None,
    doc_type: str = "doc",
    collection_name_override: str = None
):
    """
    Main ingestion script. 
    1. Parse PDFs via Gemini OCR (or load cache if exists).
    2. Save cached parsing to processed_book_data.json.
    3. Index documents into Chroma Vector Database.
    """
    cache_file = config.DATA_DIR / f"processed_{field}_data.json"
    processed_pages = []
    
    # If custom pdf_path is provided, run ingestion for that specific file
    if pdf_path:
        target_path = Path(pdf_path)
        if not target_path.exists():
            raise FileNotFoundError(f"PDF file not found at {pdf_path}")
        print(f"Running OCR on custom PDF: {pdf_path} (field={field}, visibility={visibility})")
        
        # Verify API Key
        if not config.GEMINI_API_KEY:
            raise ValueError("Error: GEMINI_API_KEY is not configured in your environment.")
            
        parser = PDFBookParser(target_path, volume=str(volume), api_key=config.GEMINI_API_KEY)
        processed_pages = parser.parse_all_pages()
    else:
        # Check if cache exists for the default textbooks
        if cache_file.exists() and not force_ocr:
            print(f"Loading textbook data from cache: {cache_file}")
            with open(cache_file, "r", encoding="utf-8") as f:
                processed_pages = json.load(f)
        else:
            print(f"No cache found or force_ocr=True for field '{field}'. Running Multimodal OCR pipeline...")
            
            # Verify API Key
            if not config.GEMINI_API_KEY:
                raise ValueError(
                    "Error: GEMINI_API_KEY is not configured in your environment. "
                    "Multimodal OCR requires a Gemini API key. Please set it in your .env file."
                )
                
            # Parse Vol 1
            vol1_path = config.DATA_SAMPLES_DIR / "toan-3-tap-1.pdf"
            if vol1_path.exists():
                parser1 = PDFBookParser(vol1_path, volume="1", api_key=config.GEMINI_API_KEY)
                pages1 = parser1.parse_all_pages()
                processed_pages.extend(pages1)
            else:
                print(f"[Warning] Volume 1 not found at {vol1_path}")
                
            # Parse Vol 2
            vol2_path = config.DATA_SAMPLES_DIR / "toan-3-tap-2.pdf"
            if vol2_path.exists():
                parser2 = PDFBookParser(vol2_path, volume="2", api_key=config.GEMINI_API_KEY)
                pages2 = parser2.parse_all_pages()
                processed_pages.extend(pages2)
            else:
                print(f"[Warning] Volume 2 not found at {vol2_path}")
                
            # Save to cache
            if processed_pages:
                print(f"Saving OCR results to cache: {cache_file}")
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(processed_pages, f, ensure_ascii=False, indent=2)
            else:
                print("Error: No pages parsed.")
                return

    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    created_at_val = datetime_str if datetime_str else now_iso
    created_at_ts = parse_to_epoch(created_at_val)

    # Index into Vector DB
    col_name = collection_name_override if collection_name_override else f"{config.COLLECTION_NAME}_{field}"
    print(f"Indexing {len(processed_pages)} pages into Vector DB collection: {col_name}...")
    
    # Initialize Chroma client
    client = get_vector_db_client()
    embedding_fn = get_embedding_function()
    collection = get_or_create_collection(client, embedding_fn, collection_name=col_name)
    
    # Delete first if requested (override or delete_first mode)
    if mode in ["override", "delete_first"]:
        try:
            print(f"Override/Delete mode: deleting existing chunks in collection '{col_name}'...")
            if file_id:
                collection.delete(where={"file_id": str(file_id)})
            elif file_name:
                collection.delete(where={"file_name": str(file_name)})
        except Exception as e:
            print(f"[Warning] Failed to delete existing chunks: {e}")
    
    # Prepare data arrays for bulk adding
    ids = []
    documents = []
    metadatas = []
    
    for page in processed_pages:
        # Create a unique document ID
        phys_page = page.get("physical_page")
        if file_id:
            # Use file_id as prefix to isolate pages of different files
            if phys_page is None:
                doc_id = f"{file_id}_pdf{page['pdf_page_index']}"
            else:
                doc_id = f"{file_id}_p{phys_page}"
        else:
            if phys_page is None:
                doc_id = f"{field}_v{page['volume']}_pdf{page['pdf_page_index']}"
            else:
                doc_id = f"{field}_v{page['volume']}_p{phys_page}"
            
        # Avoid empty content indexing
        text_content = page["text"].strip() if page["text"] else ""
        if not text_content:
            text_content = f"Sách giáo khoa Toán 3 Tập {page['volume']} - Trang {phys_page or page['pdf_page_index']}: [Trang trắng hoặc không có nội dung văn bản]"
            
        ids.append(doc_id)
        documents.append(text_content)
        
        # Save metadata fields including visibility and field
        meta_entry = {
            "volume": str(page["volume"]),
            "physical_page": int(phys_page) if phys_page is not None else -1,
            "pdf_page_index": int(page["pdf_page_index"]),
            "lesson_name": str(page["lesson_name"]) if page["lesson_name"] else "Unknown",
            "field": str(field),
            "visibility": str(visibility),
            "created_at": str(created_at_val),
            "created_at_timestamp": float(created_at_ts),
            "doc_type": str(doc_type)
        }
        if description:
            meta_entry["description"] = str(description)
        if file_id:
            meta_entry["file_id"] = str(file_id)
        if tag_name_uuid:
            meta_entry["tag_name_uuid"] = str(tag_name_uuid)
        if file_name:
            meta_entry["file_name"] = str(file_name)
        if pdf_path:
            meta_entry["file_path"] = str(pdf_path)
        if owner_id:
            meta_entry["owner_id"] = str(owner_id)
        if allowed_group:
            meta_entry["allowed_group"] = str(allowed_group)
        if allowed_user:
            meta_entry["allowed_user"] = str(allowed_user)
            
        metadatas.append(meta_entry)
        
    # Chroma upsert allows replacing existing documents if we rerun
    # Batch upsert
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        end_idx = min(i + batch_size, len(ids))
        print(f"Upserting batch {i} to {end_idx}...")
        collection.upsert(
            ids=ids[i:end_idx],
            documents=documents[i:end_idx],
            metadatas=metadatas[i:end_idx]
        )
        
    # Delete obsolete chunks in keep_cache mode
    if file_id and mode == "keep_cache":
        try:
            print(f"Keep cache mode: cleaning up obsolete chunks for file_id '{file_id}'...")
            existing = collection.get(where={"file_id": str(file_id)}, include=[])
            if existing and "ids" in existing:
                obsolete_ids = list(set(existing["ids"]) - set(ids))
                if obsolete_ids:
                    print(f"Deleting {len(obsolete_ids)} obsolete chunk IDs...")
                    collection.delete(ids=obsolete_ids)
        except Exception as e:
            print(f"[Warning] Failed to clean up obsolete chunks for file_id '{file_id}': {e}")

    print(f"Vector Database indexing for '{field}' ({visibility}) completed successfully!")

if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    field_arg = "math"
    for arg in sys.argv:
        if arg.startswith("--field="):
            field_arg = arg.split("=")[1]
    
    run_ingest(force_ocr=force, field=field_arg)

