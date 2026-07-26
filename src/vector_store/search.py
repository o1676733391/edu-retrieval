from src.vector_store.client import get_embedding_function, get_vector_db_client
from rank_bm25 import BM25Okapi
import re

def extract_hints_from_query(query: str) -> tuple[int | None, str | None]:
    """
    Extracts physical page number hints and volume hints from query string.
    E.g., "bài 2 trang 15 tập 1" -> page_hint = 15, volume_hint = "1"
    """
    page_hint = None
    volume_hint = None

    # 1. Volume extraction FIRST (before page) to prevent page regex from stealing
    #    the digit from patterns like "tập 2" / "tap 2".
    # Strategy: match "t[aậ]p <digit>" only when it appears in a BOOK context:
    #   (a) preceded by "sgk" (e.g. "sgk tập 2", "sgk tap 2")
    #   (b) at the end of the sentence (e.g. query ends with "tập 2")
    #   (c) followed by a page cue (e.g. "tập 2 trang 16")
    #   (d) "sgk1" / "sgk2" shorthand
    # This prevents "luyện tập 1" from being interpreted as "volume 1".
    _vol_context = r'(?:sgk\s+|\bsách\s+)'
    _vol_pattern_1 = r't[aậ]p\s*(?:1\b|i\b|m[oộ]t\b)'
    _vol_pattern_2 = r't[aậ]p\s*(?:2\b|ii\b|hai\b)'
    # (a) preceded by sgk/sach keyword
    if re.search(_vol_context + _vol_pattern_1, query, re.IGNORECASE):
        volume_hint = "1"
    elif re.search(_vol_context + _vol_pattern_2, query, re.IGNORECASE):
        volume_hint = "2"
    # (a2) followed by sgk/sach/vở keyword
    elif re.search(_vol_pattern_1 + r'\s+(?:sgk|sách|vở)', query, re.IGNORECASE):
        volume_hint = "1"
    elif re.search(_vol_pattern_2 + r'\s+(?:sgk|sách|vở)', query, re.IGNORECASE):
        volume_hint = "2"
    # (b) at end of query (optionally with trailing punctuation/spaces)
    elif re.search(_vol_pattern_1 + r'\s*$', query.rstrip(), re.IGNORECASE):
        volume_hint = "1"
    elif re.search(_vol_pattern_2 + r'\s*$', query.rstrip(), re.IGNORECASE):
        volume_hint = "2"
    # (c) followed by a page cue
    elif re.search(_vol_pattern_1 + r'\s+(?:trang|tr)\.?\s*\d+', query, re.IGNORECASE):
        volume_hint = "1"
    elif re.search(_vol_pattern_2 + r'\s+(?:trang|tr)\.?\s*\d+', query, re.IGNORECASE):
        volume_hint = "2"
    # (d) "sgk1"/"sgk2" shorthand (no space)
    elif re.search(r'\bsgk\s*1\b', query, re.IGNORECASE):
        volume_hint = "1"
    elif re.search(r'\bsgk\s*2\b', query, re.IGNORECASE):
        volume_hint = "2"

    # 2. Page extraction: only accept unambiguous keywords "trang" or "tr."
    #    Avoid single-letter "t" and "p" which falsely match "tập" digit.
    page_match = re.search(r'\b(trang|tr)\.?\s*(\d+)\b', query, re.IGNORECASE)
    if page_match:
        page_hint = int(page_match.group(2))

    return page_hint, volume_hint

def tokenize_vietnamese(text: str, include_bigrams: bool = False) -> list[str]:
    """
    Vietnamese word tokenization for BM25 search.
    Lowers case and extracts unigrams.
    If include_bigrams is True, also includes PyVi morphological compound words and bigrams.
    """
    if not text:
        return []
        
    raw_words = [w.lower() for w in re.findall(r'\b\w+\b', text) if w]
    if not include_bigrams:
        return raw_words

    tokens = list(raw_words)
    
    # 1. Morphological Vietnamese Segmentation via PyVi
    try:
        from pyvi import ViTokenizer
        segmented_text = ViTokenizer.tokenize(text)
        pyvi_words = [w.lower() for w in re.findall(r'\b\w+\b', segmented_text) if w]
        # Add PyVi compound words (containing '_')
        compound_pyvi = [w for w in pyvi_words if '_' in w]
        tokens.extend(compound_pyvi)
    except ImportError:
        pass

    # 2. Generate bigrams
    if len(raw_words) > 1:
        bigrams = [f"{raw_words[i]}_{raw_words[i+1]}" for i in range(len(raw_words)-1)]
        tokens.extend(bigrams)
        
    return tokens

def book_knowledge_search(
    query: str,
    page_hint: int = None,
    volume_hint: str = None,
    top_k: int = 5,
    field: str = "math",
    user_role: str = "student",
    user_id: str = None,
    user_groups: list[str] = None
) -> list[dict]:
    """
    Queries Vector DB using Hybrid Search (Dense Embeddings + BM25) and Metadata Filters.
    
    Parameters:
      - query: The raw search string.
      - page_hint: Optional explicit physical page number.
      - volume_hint: Optional volume number ("1" or "2").
      - top_k: Number of documents to return.
      - field: The subject field to query (isolation).
      - user_role: The role of the querying user (RBAC).
      - user_id: The ID of the querying user (ACL).
      - user_groups: The list of groups the user belongs to (ACL).
    """
    from src import config
    
    # Initialize Vector Store
    from src.vector_store.client import get_vector_store
    vector_store = get_vector_store(field)
    
    # Extract hints from query text if not provided explicitly
    extracted_page, extracted_vol = extract_hints_from_query(query)
    if page_hint is None:
        page_hint = extracted_page
    if volume_hint is None:
        volume_hint = extracted_vol
        
    # Build metadata filters
    where_filter = {}
    filters = []
    
    # Build ACL filter (for non-admin roles)
    acl_filter = None
    if user_role != config.ROLE_ADMIN:
        acl_clauses = [{"visibility": "public"}]
        
        # Add matches for role-based visibilities
        allowed_visibilities = config.ROLE_VISIBILITY_MAPPING.get(user_role, ["public"])
        for vis in allowed_visibilities:
            if vis != "public":  # public is already in clauses
                acl_clauses.append({"visibility": vis})
                
        # Add owner and allowed user checks
        if user_id:
            acl_clauses.append({"owner_id": str(user_id)})
            acl_clauses.append({"allowed_user": str(user_id)})
            
        # Add group checks
        if user_groups:
            for group in user_groups:
                acl_clauses.append({"allowed_group": str(group)})
                
        if len(acl_clauses) == 1:
            acl_filter = acl_clauses[0]
        else:
            acl_filter = {"$or": acl_clauses}
            
    # Combine all filters
    if acl_filter:
        filters.append(acl_filter)
        
    if volume_hint:
        filters.append({"volume": str(volume_hint)})
        
    if page_hint:
        # Search a window of [page_hint - 1, page_hint, page_hint + 1] matching physical_page or PDF page number
        page_window = [page_hint - 1, page_hint, page_hint + 1]
        page_window = [p for p in page_window if p >= 0]
        
        page_clauses = []
        for p in page_window:
            page_clauses.append({"physical_page": p})
            page_clauses.append({"pdf_page_number": p})
            page_clauses.append({"pdf_page_index": p - 1 if p > 0 else 0})
            
        filters.append({"$or": page_clauses})
            
    if len(filters) == 1:
        where_filter = filters[0]
    elif len(filters) > 1:
        where_filter = {"$and": filters}
        
    # 1. DENSE VECTOR SEARCH
    try:
        dense_results = vector_store.query(
            query_text=query,
            top_k=top_k,
            where=where_filter if where_filter else None
        )
    except Exception as e:
        print(f"Error during collection query: {e}")
        dense_results = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        
    # 2. BM25 KEYWORD SEARCH OVER COLOURED CORPUS
    # Fetch all items matching the filter (or all items if no filter) to run BM25
    try:
        all_docs = vector_store.get_all(where=where_filter if where_filter else None)
    except Exception as e:
        print(f"Error fetching docs for BM25: {e}")
        all_docs = {"ids": [], "documents": [], "metadatas": []}
        
    bm25_results = []
    if all_docs and all_docs["ids"]:
        corpus = all_docs["documents"]
        metadatas = all_docs["metadatas"]
        ids = all_docs["ids"]
        
        tokenized_corpus = [tokenize_vietnamese(doc, include_bigrams=True) for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        
        tokenized_query = tokenize_vietnamese(query, include_bigrams=True)
        scores = bm25.get_scores(tokenized_query)
        
        # Sort documents by score
        scored_docs = list(zip(ids, corpus, metadatas, scores))
        scored_docs.sort(key=lambda x: x[3], reverse=True)
        
        # Take top_k * 2
        bm25_results = scored_docs[:top_k * 2]

    # 3. HYBRID MERGING (Reciprocal Rank Fusion - RRF)
    # RRF score = 1 / (60 + rank)
    rrf_scores = {}
    doc_details = {}  # maps doc_id -> (text, metadata)
    
    # Process Dense Results
    if dense_results["ids"] and dense_results["ids"][0]:
        for rank, doc_id in enumerate(dense_results["ids"][0]):
            text = dense_results["documents"][0][rank]
            meta = dense_results["metadatas"][0][rank]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (60.0 + rank + 1)
            doc_details[doc_id] = (text, meta)
            
    # Process BM25 Results
    for rank, (doc_id, text, meta, score) in enumerate(bm25_results):
        # Only count documents with non-zero BM25 score
        if score > 0:
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (60.0 + rank + 1)
            doc_details[doc_id] = (text, meta)
            
    # Sort IDs based on RRF scores descending
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    
    # Return formatted final results
    final_results = []
    for doc_id in sorted_ids[:top_k]:
        text, meta = doc_details[doc_id]
        final_results.append({
            "id": doc_id,
            "text": text,
            "metadata": meta
        })
        
    return final_results


def parse_to_epoch(date_input: str) -> float:
    import datetime
    if not date_input:
        return 0.0
    try:
        dt = datetime.datetime.fromisoformat(date_input.replace('Z', '+00:00'))
        return dt.timestamp()
    except Exception:
        try:
            dt = datetime.datetime.strptime(date_input, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
            return dt.timestamp()
        except Exception:
            return 0.0


def multi_domain_retrieval(
    query: str,
    tag_name_uuids: list[str],
    doc_type: str = "doc",
    from_date: str = None,
    to_date: str = None,
    top_k: int = 5
) -> list[dict]:
    """
    Performs retrieval across multiple tag/domain collections with type filtering ("doc" vs "qa")
    and date range filtering ("from_date" to "to_date").
    Uses Hybrid Search (Dense Vector with RETRIEVAL_QUERY + Bigram BM25) and Reciprocal Rank Fusion.
    """
    from src import config
    
    # Extract page and volume hints from query
    page_hint, volume_hint = extract_hints_from_query(query)
    
    all_candidate_results = []
    
    # List existing collections depending on the active backend
    if config.VECTOR_DB_BACKEND == "qdrant":
        from qdrant_client import QdrantClient
        if config.QDRANT_HOST:
            q_client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
        else:
            q_client = QdrantClient(path=str(config.DATA_DIR / "qdrant_db"))
        existing_cols = [c.name for c in q_client.get_collections().collections]
    else:
        client = get_vector_db_client()
        existing_cols = [c.name for c in client.list_collections()]
        
    for tag_uuid in tag_name_uuids:
        tag_clean = tag_uuid.strip().lower()
        if not tag_clean:
            continue
        
        col_name = f"{tag_clean}_{doc_type}"
        curriculum_col = f"{config.COLLECTION_NAME}_{tag_clean}"
        target_cols_to_search = []
        
        if col_name in existing_cols:
            target_cols_to_search.append((col_name, None))
        if curriculum_col in existing_cols and (curriculum_col, None) not in target_cols_to_search:
            target_cols_to_search.append((curriculum_col, None))
            
        if not target_cols_to_search:
            # Fallback: search all collections matching doc_type, tag_clean, or default curriculum
            for ext_c in existing_cols:
                if (
                    ext_c.endswith(f"_{doc_type}")
                    or ext_c.endswith(f"_{tag_clean}")
                    or ext_c == tag_clean
                    or ext_c == config.COLLECTION_NAME
                ):
                    target_cols_to_search.append((ext_c, tag_clean))
                    
        if not target_cols_to_search:
            print(f"[Warning] No target collections found for tag '{tag_clean}'. Skipping.")
            continue
            
        for c_name, meta_tag_filter in target_cols_to_search:
            from src.vector_store.client import get_vector_store
            vector_store = get_vector_store(field=tag_clean, collection_name_override=c_name)
            
            # Build metadata filter
            filters = []
            if meta_tag_filter:
                filters.append({"$or": [{"file_id": meta_tag_filter}, {"tag_name_uuid": meta_tag_filter}]})
                
            if volume_hint:
                filters.append({"volume": str(volume_hint)})
                
            if page_hint:
                page_window = [page_hint - 1, page_hint, page_hint + 1]
                page_window = [p for p in page_window if p >= 0]
                page_clauses = []
                for p in page_window:
                    page_clauses.append({"physical_page": p})
                    page_clauses.append({"pdf_page_number": p})
                    page_clauses.append({"pdf_page_index": p - 1 if p > 0 else 0})
                filters.append({"$or": page_clauses})
                
            if from_date:
                from_ts = parse_to_epoch(from_date)
                if from_ts > 0:
                    filters.append({"created_at_timestamp": {"$gte": float(from_ts)}})
            if to_date:
                to_ts = parse_to_epoch(to_date)
                if to_ts > 0:
                    if len(to_date) == 10:
                        to_ts += 86399  # end of day
                    filters.append({"created_at_timestamp": {"$lte": float(to_ts)}})
                
            where_filter = None
            if len(filters) == 1:
                where_filter = filters[0]
            elif len(filters) > 1:
                where_filter = {"$and": filters}
            
            # 1. Dense Search
            dense_ids = []
            dense_docs = {}
            dense_metas = {}
            dense_dists = {}
            
            try:
                query_res = vector_store.query(
                    query_text=query,
                    top_k=top_k,
                    where=where_filter if where_filter else None
                )
                    
                if query_res and query_res["ids"] and query_res["ids"][0]:
                    for idx, doc_id in enumerate(query_res["ids"][0]):
                        dense_ids.append(doc_id)
                        dense_docs[doc_id] = query_res["documents"][0][idx]
                        dense_metas[doc_id] = query_res["metadatas"][0][idx]
                        dense_dists[doc_id] = query_res["distances"][0][idx] if "distances" in query_res and query_res["distances"] else 0.0
            except Exception as e:
                print(f"Error querying dense vectors for collection {c_name}: {e}")
                
            # 2. BM25 Search with Bigrams
            bm25_results = []
            try:
                all_docs = vector_store.get_all(where=where_filter if where_filter else None)
                    
                if all_docs and all_docs["ids"]:
                    corpus = all_docs["documents"]
                    metadatas = all_docs["metadatas"]
                    ids = all_docs["ids"]
                    
                    tokenized_corpus = [tokenize_vietnamese(doc, include_bigrams=True) for doc in corpus]
                    bm25 = BM25Okapi(tokenized_corpus)
                    
                    query_tokens = tokenize_vietnamese(query, include_bigrams=True)
                    # Exclude common stopwords and ultra-generic single terms from BM25 query to avoid noise
                    stop_words = {"là", "gì", "thế", "nào", "cho", "hỏi", "em", "với", "các", "những", "số", "của", "và", "có", "trong", "được"}
                    filtered_query_tokens = [t for t in query_tokens if t not in stop_words and not (t.isalpha() and len(t) <= 1)]
                    
                    if filtered_query_tokens:
                        scores = bm25.get_scores(filtered_query_tokens)
                        scored_docs = list(zip(ids, corpus, metadatas, scores))
                        scored_docs.sort(key=lambda x: x[3], reverse=True)
                        bm25_results = scored_docs[:top_k * 2]
            except Exception as e:
                print(f"Error executing BM25 for collection {c_name}: {e}")
                
            # 3. Hybrid RRF Fusion
            rrf_scores = {}
            doc_details = {}
            
            # Process Dense RRF
            for rank, doc_id in enumerate(dense_ids):
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (60.0 + rank + 1)
                doc_details[doc_id] = (dense_docs[doc_id], dense_metas[doc_id], dense_dists.get(doc_id, 0.0))
                
            # Process BM25 RRF
            for rank, (doc_id, text, meta, score) in enumerate(bm25_results):
                if score > 0:
                    rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (60.0 + rank + 1)
                    if doc_id not in doc_details:
                        doc_details[doc_id] = (text, meta, 0.5)
                        
            sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
            
            for doc_id in sorted_ids[:top_k]:
                text, meta, dist = doc_details[doc_id]
                all_candidate_results.append({
                    "id": doc_id,
                    "collection": c_name,
                    "text": text,
                    "metadata": meta,
                    "distance": dist,
                    "rrf_score": rrf_scores[doc_id]
                })
            
    # Sort candidate results by RRF score descending
    all_candidate_results.sort(key=lambda x: x.get("rrf_score", 0.0), reverse=True)
    return all_candidate_results[:top_k]


def get_document_outline(field: str) -> dict[str, list[dict]]:
    """
    Retrieves the syllabus/outline structure for all documents in the specified field.
    Groups by file_name and extracts unique lesson names sorted by page index.
    """
    from src.vector_store.client import get_vector_store
    vector_store = get_vector_store(field)
    
    results = vector_store.get_all()
    if not results or "metadatas" not in results:
        return {}
        
    # Group by file identification
    # key: (file_id, file_name) -> list of chunks metadata
    files_data = {}
    for meta in results["metadatas"]:
        # Skip if metadata is empty
        if not meta:
            continue
        file_id = meta.get("file_id", "default_textbook")
        file_name = meta.get("file_name")
        if not file_name:
            vol = meta.get("volume", "1")
            file_name = f"Tài liệu {field.upper()} (Tập {vol})"
            
        file_key = (file_id, file_name)
        if file_key not in files_data:
            files_data[file_key] = []
        files_data[file_key].append(meta)
        
    outline_by_file = {}
    for (file_id, file_name), metas in files_data.items():
        # Extract unique lessons
        # We want to keep track of first appearance page to sort them properly
        lessons_seen = {}
        for m in metas:
            lesson = m.get("lesson_name") or "Unknown"
            # Normalize lesson name for uniqueness check, but keep original casing
            lesson_norm = lesson.strip().lower()
            
            phys_page = m.get("physical_page", -1)
            pdf_idx = m.get("pdf_page_index", 0)
            vol = m.get("volume", "1")
            
            page_sort_key = (
                int(vol) if str(vol).isdigit() else 1,
                int(phys_page) if phys_page > 0 else 9999,
                int(pdf_idx)
            )
            
            if lesson_norm not in lessons_seen or page_sort_key < lessons_seen[lesson_norm]["sort_key"]:
                lessons_seen[lesson_norm] = {
                    "lesson_name": lesson,
                    "physical_page": phys_page,
                    "pdf_page_index": pdf_idx,
                    "volume": vol,
                    "sort_key": page_sort_key
                }
                
        # Sort lessons by page order
        sorted_lessons = sorted(lessons_seen.values(), key=lambda x: x["sort_key"])
        
        # Remove sort_key from output
        cleaned_lessons = []
        for l in sorted_lessons:
            cleaned_lessons.append({
                "lesson_name": l["lesson_name"],
                "physical_page": l["physical_page"],
                "pdf_page_index": l["pdf_page_index"],
                "volume": l["volume"]
            })
            
        outline_by_file[file_name] = cleaned_lessons
        
    return outline_by_file



