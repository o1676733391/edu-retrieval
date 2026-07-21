from src.vector_store.client import get_vector_db_client, get_embedding_function, get_or_create_collection
from rank_bm25 import BM25Okapi
import re

def extract_hints_from_query(query: str) -> tuple[int | None, str | None]:
    """
    Extracts physical page number hints and volume hints from query string.
    E.g., "bài 2 trang 15 tập 1" -> page_hint = 15, volume_hint = "1"
    """
    page_hint = None
    volume_hint = None
    
    # 1. Page extraction (e.g., "trang 15", "tr. 15", "t 15", "p. 15")
    page_match = re.search(r'\b(trang|tr|t|p)\.?\s*(\d+)\b', query, re.IGNORECASE)
    if page_match:
        page_hint = int(page_match.group(2))
        
    # 2. Volume extraction (e.g., "tập 1", "tập I", "tập một", "tập 2", "tập II", "tập hai")
    if re.search(r'\b(?:tập|t)\s*(?:1|i|một)\b', query, re.IGNORECASE):
        volume_hint = "1"
    elif re.search(r'\b(?:tập|t)\s*(?:2|ii|hai)\b', query, re.IGNORECASE):
        volume_hint = "2"
        
    return page_hint, volume_hint

def tokenize_vietnamese(text: str) -> list[str]:
    """
    Simple word tokenization for BM25.
    Lowers case and splits on non-alphanumeric.
    """
    return [w.lower() for w in re.findall(r'\b\w+\b', text) if w]

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
    
    # Initialize DB client and collection
    client = get_vector_db_client()
    embedding_fn = get_embedding_function()
    col_name = f"{config.COLLECTION_NAME}_{field}"
    collection = get_or_create_collection(client, embedding_fn, collection_name=col_name)
    
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
        # We search a window of [page_hint - 1, page_hint, page_hint + 1] to ensure coverage
        page_window = [page_hint - 1, page_hint, page_hint + 1]
        page_window = [p for p in page_window if p > 0]
        
        if len(page_window) == 1:
            filters.append({"physical_page": page_window[0]})
        else:
            filters.append({"$or": [{"physical_page": p} for p in page_window]})
            
    if len(filters) == 1:
        where_filter = filters[0]
    elif len(filters) > 1:
        where_filter = {"$and": filters}
        
    # 1. DENSE VECTOR SEARCH
    # If where_filter is empty, pass None to chroma
    chroma_where = where_filter if where_filter else None
    
    try:
        dense_results = collection.query(
            query_texts=[query],
            n_results=top_k * 2,  # retrieve slightly more to allow hybrid merging
            where=chroma_where
        )
    except Exception as e:
        print(f"Error during collection query: {e}")
        dense_results = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        
    # 2. BM25 KEYWORD SEARCH OVER COLOURED CORPUS
    # Fetch all items matching the filter (or all items if no filter) to run BM25
    try:
        if chroma_where:
            all_docs = collection.get(where=chroma_where, include=["documents", "metadatas"])
        else:
            all_docs = collection.get(include=["documents", "metadatas"])
    except Exception as e:
        print(f"Error fetching docs for BM25: {e}")
        all_docs = {"ids": [], "documents": [], "metadatas": []}
        
    bm25_results = []
    if all_docs and all_docs["ids"]:
        corpus = all_docs["documents"]
        metadatas = all_docs["metadatas"]
        ids = all_docs["ids"]
        
        tokenized_corpus = [tokenize_vietnamese(doc) for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        
        tokenized_query = tokenize_vietnamese(query)
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
    """
    client = get_vector_db_client()
    embedding_fn = get_embedding_function()
    
    all_candidate_results = []
    
    existing_cols = [c.name for c in client.list_collections()]
    
    for tag_uuid in tag_name_uuids:
        tag_clean = tag_uuid.strip().lower()
        if not tag_clean:
            continue
        
        col_name = f"{tag_clean}_{doc_type}"
        from src import config
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
            collection = get_or_create_collection(client, embedding_fn, collection_name=c_name)
            
            # Build metadata filter
            filters = []
            
            # Metadata tag constraint if searching shared collection
            if meta_tag_filter:
                filters.append({"$or": [{"file_id": meta_tag_filter}, {"tag_name_uuid": meta_tag_filter}]})
                
            # Date range filters using numeric timestamps for ChromaDB
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
            # Query collection
            try:
                query_res = collection.query(
                    query_texts=[query],
                    n_results=top_k,
                    where=where_filter if where_filter else None
                )
                if query_res and query_res["ids"] and query_res["ids"][0]:
                    for idx, doc_id in enumerate(query_res["ids"][0]):
                        all_candidate_results.append({
                            "id": doc_id,
                            "collection": c_name,
                            "text": query_res["documents"][0][idx],
                            "metadata": query_res["metadatas"][0][idx],
                            "distance": query_res["distances"][0][idx] if "distances" in query_res and query_res["distances"] else 0.0
                        })
            except Exception as e:
                print(f"Error querying collection {c_name}: {e}")
            
    # Sort candidates by distance (smaller distance = higher similarity)
    all_candidate_results.sort(key=lambda x: x.get("distance", 0.0))
    return all_candidate_results[:top_k]


