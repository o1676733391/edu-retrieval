from src.vector_store.client import get_embedding_function, get_vector_db_client, get_qdrant_client
from rank_bm25 import BM25Okapi
from typing import Optional, Union, List
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

    # 2. Page extraction: accept keywords "trang", "tr", "page", "p", "trang số", "trang so", "trang thứ", "trang số:"
    page_match = re.search(r'\b(?:trang|tr|page|p)\.?(?:\s+s[ốôo]|\s+th[ứu]|s[ốôo]|\s*:|\s*#)?\s*(\d+)\b', query, re.IGNORECASE)
    if page_match:
        page_hint = int(page_match.group(1))

    return page_hint, volume_hint


def extract_exercise_hint(query: str) -> str | None:
    """
    Extracts exercise number/identifier hint from query string.
    E.g., "giải bài tập 2 trang 10" -> "2"
    "bài 3a trang 15" -> "3a"
    """
    match = re.search(r'\bbài\s*(?:tập\s*)?(\d+[a-z]?|[a-z]|iv|v|vi|vii|viii|ix|x|[i]{1,3})\b', query, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return None


def rerank_page_chunks(query: str, candidate_results: list[dict], page_hint: int | None, exercise_hint: str | None) -> list[dict]:
    """
    Reranks candidate chunks by prioritizing target physical_page and exercise title matching.
    """
    for res in candidate_results:
        meta = res.get("metadata") or {}
        text = res.get("text") or ""
        score = res.get("rrf_score", 0.0)

        # 1. Page exact match boost (Dominant boost for exact physical page)
        phys_page = meta.get("physical_page")
        pdf_num = meta.get("pdf_page_number")
        if page_hint is not None:
            if phys_page == page_hint:
                score += 100.0  # Highest priority for exact physical page
            elif pdf_num == page_hint:
                score += 25.0
            elif phys_page in [page_hint - 1, page_hint + 1]:
                score += 10.0

        # 2. Exercise exact match boost
        if exercise_hint:
            patterns = [
                rf'\bbài\s*(?:tập\s*)?{re.escape(exercise_hint)}\b',
                rf'\b{re.escape(exercise_hint)}[\.\:\)]',
                rf'\b{re.escape(exercise_hint)}\b'
            ]
            for idx, pat in enumerate(patterns):
                if re.search(pat, text, re.IGNORECASE):
                    score += 10.0 / (idx + 1)
                    break

        res["rerank_score"] = score

    candidate_results.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return candidate_results


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

    # Process Page-Hint Matched Documents
    if page_hint and all_docs and all_docs.get("ids"):
        for idx, doc_id in enumerate(all_docs["ids"]):
            if doc_id not in doc_details:
                text = all_docs["documents"][idx]
                meta = all_docs["metadatas"][idx]
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (120.0 + idx + 1)
                doc_details[doc_id] = (text, meta)

    # Sort IDs based on RRF scores descending
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    
    # Return formatted final results
    final_results = []
    effective_top_k = max(top_k, len(doc_details)) if page_hint else top_k
    for doc_id in sorted_ids[:effective_top_k]:
        text, meta = doc_details[doc_id]
        final_results.append({
            "id": doc_id,
            "text": text,
            "metadata": meta
        })
        
    exercise_hint = extract_exercise_hint(query)
    if page_hint or exercise_hint:
        final_results = rerank_page_chunks(query, final_results, page_hint, exercise_hint)

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


def standardize_string_list(input_val: Optional[Union[list[str], str]]) -> list[str]:
    import json
    if not input_val:
        return []
    if isinstance(input_val, str):
        s = input_val.strip()
        if not s:
            return []
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    res = []
                    for item in parsed:
                        res.extend(standardize_string_list(item))
                    return res
            except Exception:
                pass
        if "," in s:
            return [x.strip("'\" ") for x in s.split(",") if x.strip("'\" ")]
        return [s.strip("'\" ")]
    elif isinstance(input_val, list):
        res = []
        for item in input_val:
            if isinstance(item, str):
                res.extend(standardize_string_list(item))
            elif item is not None:
                res.append(str(item))
        return res
    return []


def multi_domain_retrieval(
    query: str,
    tag_name_uuids: Optional[Union[list[str], str]] = None,
    doc_type: str = "doc",
    from_date: str = None,
    to_date: str = None,
    top_k: int = 5,
    org_ids: Optional[Union[list[str], str]] = None
) -> list[dict]:
    """
    Performs retrieval across multiple tag/domain collections with type filtering ("doc" vs "qa")
    and date range filtering ("from_date" to "to_date").
    Uses Hybrid Search (Dense Vector with RETRIEVAL_QUERY + Bigram BM25) and Reciprocal Rank Fusion.
    """
    from src import config
    
    clean_tag_uuids = standardize_string_list(tag_name_uuids)
    clean_org_ids = standardize_string_list(org_ids)

    # Extract page and volume hints from query
    page_hint, volume_hint = extract_hints_from_query(query)
    
    all_candidate_results = []
    
    # List existing collections depending on the active backend
    if config.VECTOR_DB_BACKEND == "qdrant":
        q_client = get_qdrant_client()
        existing_cols = [c.name for c in q_client.get_collections().collections]
    else:
        client = get_vector_db_client()
        existing_cols = [c.name for c in client.list_collections()]
        
    target_cols_to_search = []
    if clean_tag_uuids:
        for tag in clean_tag_uuids:
            tag_clean = tag.strip().lower()
            if not tag_clean:
                continue
            col_name = f"{tag_clean}_{doc_type}"
            curriculum_col = f"{config.COLLECTION_NAME}_{tag_clean}"
            
            if col_name in existing_cols:
                target_cols_to_search.append((col_name, tag_clean))
            if curriculum_col in existing_cols and (curriculum_col, tag_clean) not in target_cols_to_search:
                target_cols_to_search.append((curriculum_col, tag_clean))
                
            for ext_c in existing_cols:
                if (ext_c == tag_clean or ext_c.endswith(f"_{tag_clean}")) and (ext_c, tag_clean) not in target_cols_to_search:
                    target_cols_to_search.append((ext_c, tag_clean))

    if not target_cols_to_search:
        return []

    # Deduplicate target collections
    unique_target_cols = []
    seen_cols = set()
    for c_name, meta_filter in target_cols_to_search:
        if c_name not in seen_cols:
            seen_cols.add(c_name)
            unique_target_cols.append((c_name, meta_filter))

    for c_name, meta_tag_filter in unique_target_cols:
        from src.vector_store.client import get_vector_store
        vector_store = get_vector_store(field=meta_tag_filter, collection_name_override=c_name)
        
        # Build metadata filter
        filters = []
        if clean_tag_uuids and meta_tag_filter in clean_tag_uuids:
            filters.append({"$or": [{"file_id": meta_tag_filter}, {"tag_name_uuid": meta_tag_filter}]})
        if clean_org_ids:
            if len(clean_org_ids) == 1:
                filters.append({"org_id": clean_org_ids[0]})
            else:
                filters.append({"org_id": {"$in": clean_org_ids}})
                
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

            # Fallback: if strict page/volume filter yielded 0 dense results, retry without page/volume filters
            if not dense_ids and where_filter and (page_hint or volume_hint):
                fallback_filters = []
                if meta_tag_filter:
                    fallback_filters.append({"$or": [{"file_id": meta_tag_filter}, {"tag_name_uuid": meta_tag_filter}]})
                if clean_org_ids:
                    if len(clean_org_ids) == 1:
                        fallback_filters.append({"org_id": clean_org_ids[0]})
                    else:
                        fallback_filters.append({"org_id": {"$in": clean_org_ids}})
                fallback_where = fallback_filters[0] if len(fallback_filters) == 1 else ({"$and": fallback_filters} if len(fallback_filters) > 1 else None)
                
                fb_res = vector_store.query(query_text=query, top_k=top_k, where=fallback_where)
                if fb_res and fb_res["ids"] and fb_res["ids"][0]:
                    for idx, doc_id in enumerate(fb_res["ids"][0]):
                        dense_ids.append(doc_id)
                        dense_docs[doc_id] = fb_res["documents"][0][idx]
                        dense_metas[doc_id] = fb_res["metadatas"][0][idx]
                        dense_dists[doc_id] = fb_res["distances"][0][idx] if "distances" in fb_res and fb_res["distances"] else 0.0
        except Exception as e:
            print(f"Error querying dense vectors for collection {c_name}: {e}")
            
        # 2. BM25 Search with Bigrams
        bm25_results = []
        try:
            all_docs = vector_store.get_all(where=where_filter if where_filter else None)
            if (not all_docs or not all_docs.get("ids")) and where_filter and (page_hint or volume_hint):
                fallback_filters = []
                if meta_tag_filter:
                    fallback_filters.append({"$or": [{"file_id": meta_tag_filter}, {"tag_name_uuid": meta_tag_filter}]})
                if clean_org_ids:
                    if len(clean_org_ids) == 1:
                        fallback_filters.append({"org_id": clean_org_ids[0]})
                    else:
                        fallback_filters.append({"org_id": {"$in": clean_org_ids}})
                fallback_where = fallback_filters[0] if len(fallback_filters) == 1 else ({"$and": fallback_filters} if len(fallback_filters) > 1 else None)
                all_docs = vector_store.get_all(where=fallback_where)
                
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

        # Process Page-Hint Matched Documents (Ensure 100% of target page chunks are included)
        if page_hint and all_docs and all_docs.get("ids"):
            for idx, doc_id in enumerate(all_docs["ids"]):
                if doc_id not in doc_details:
                    text = all_docs["documents"][idx]
                    meta = all_docs["metadatas"][idx]
                    rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (120.0 + idx + 1)
                    doc_details[doc_id] = (text, meta, 0.1)

        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        effective_top_k = max(top_k, len(doc_details)) if page_hint else top_k
        for doc_id in sorted_ids[:effective_top_k]:
            text, meta, dist = doc_details[doc_id]
            all_candidate_results.append({
                "id": doc_id,
                "collection": c_name,
                "text": text,
                "metadata": meta,
                "distance": dist,
                "rrf_score": rrf_scores[doc_id]
            })
            
    # Page and Exercise Reranking
    exercise_hint = extract_exercise_hint(query)
    if page_hint or exercise_hint:
        all_candidate_results = rerank_page_chunks(query, all_candidate_results, page_hint, exercise_hint)
    else:
        all_candidate_results.sort(key=lambda x: x.get("rrf_score", 0.0), reverse=True)

    return all_candidate_results[:top_k]


from typing import Optional, Union, List

def get_document_outline(
    tag_name_uuids: Optional[Union[list[str], str]] = None,
    doc_type: str = "doc",
    org_ids: Optional[Union[list[str], str]] = None
) -> dict[str, list[dict]]:
    """
    Retrieves the syllabus/outline structure for all documents in the specified tags.
    Supports multi-domain tag_name_uuids, org_ids, and metadata structure (tag_name_uuid, file_id,
    file_name, file_path, pdf_page_number, physical_page, volume, org_id, doc_type, etc.).
    Groups by file_name and extracts unique lesson names sorted by page index.
    """
    import json
    from src import config
    from src.vector_store.client import get_vector_store, get_vector_db_client, get_qdrant_client

    # Standardize tag_name_uuids to list[str]
    clean_tag_uuids = []
    if tag_name_uuids:
        if isinstance(tag_name_uuids, str):
            val_str = tag_name_uuids.strip()
            if val_str.startswith("[") and val_str.endswith("]"):
                try:
                    parsed = json.loads(val_str)
                    if isinstance(parsed, list):
                        clean_tag_uuids = [str(x).strip("'\" ") for x in parsed if str(x).strip("'\" ")]
                    else:
                        clean_tag_uuids = [val_str.strip("'\" ")]
                except Exception:
                    clean_tag_uuids = [val_str.strip("'\" ")]
            elif "," in val_str:
                clean_tag_uuids = [x.strip("'\" ") for x in val_str.split(",") if x.strip("'\" ")]
            else:
                clean_tag_uuids = [val_str.strip("'\" ")]
        elif isinstance(tag_name_uuids, list):
            for item in tag_name_uuids:
                if isinstance(item, str):
                    s = item.strip()
                    if s.startswith("[") and s.endswith("]"):
                        try:
                            parsed = json.loads(s)
                            if isinstance(parsed, list):
                                clean_tag_uuids.extend([str(x).strip("'\" ") for x in parsed if str(x).strip("'\" ")])
                                continue
                        except Exception:
                            pass
                    clean_tag_uuids.append(s.strip("'\" "))
                elif item:
                    clean_tag_uuids.append(str(item))

    # Standardize org_ids to list[str]
    clean_org_ids = []
    if org_ids:
        if isinstance(org_ids, str):
            val_str = org_ids.strip()
            if val_str.startswith("[") and val_str.endswith("]"):
                try:
                    parsed = json.loads(val_str)
                    if isinstance(parsed, list):
                        clean_org_ids = [str(x).strip("'\" ") for x in parsed if str(x).strip("'\" ")]
                    else:
                        clean_org_ids = [val_str.strip("'\" ")]
                except Exception:
                    clean_org_ids = [val_str.strip("'\" ")]
            elif "," in val_str:
                clean_org_ids = [x.strip("'\" ") for x in val_str.split(",") if x.strip("'\" ")]
            else:
                clean_org_ids = [val_str.strip("'\" ")]
        elif isinstance(org_ids, list):
            for item in org_ids:
                if isinstance(item, str):
                    s = item.strip()
                    clean_org_ids.append(s.strip("'\" "))
                elif item:
                    clean_org_ids.append(str(item))

    # Discover target collections
    if config.VECTOR_DB_BACKEND == "qdrant":
        q_client = get_qdrant_client()
        existing_cols = [c.name for c in q_client.get_collections().collections]
    else:
        client = get_vector_db_client()
        existing_cols = [c.name for c in client.list_collections()]

    target_collections = []
    if clean_tag_uuids:
        for tag in clean_tag_uuids:
            tag_clean = tag.strip().lower()
            if not tag_clean:
                continue
            col_name = f"{tag_clean}_{doc_type}"
            curriculum_col = f"{config.COLLECTION_NAME}_{tag_clean}"
            
            matched = False
            if col_name in existing_cols:
                target_collections.append((col_name, tag_clean))
                matched = True
            if curriculum_col in existing_cols and (curriculum_col, tag_clean) not in target_collections:
                target_collections.append((curriculum_col, tag_clean))
                matched = True
            if not matched:
                for c in existing_cols:
                    if c == tag_clean or c.endswith(f"_{tag_clean}"):
                        target_collections.append((c, tag_clean))

    if not target_collections:
        return {}

    # Deduplicate target collections
    unique_target_cols = []
    seen_col_names = set()
    for c_name, tag_ref in target_collections:
        if c_name not in seen_col_names:
            seen_col_names.add(c_name)
            unique_target_cols.append((c_name, tag_ref))

    all_metadatas = []
    for c_name, tag_ref in unique_target_cols:
        try:
            vector_store = get_vector_store(field=tag_ref, collection_name_override=c_name)
            res = vector_store.get_all()
            if res and "metadatas" in res and res["metadatas"]:
                for m in res["metadatas"]:
                    if m:
                        all_metadatas.append(m)
        except Exception as err:
            print(f"[Warning] Outline retrieval collection error on '{c_name}': {err}")

    if not all_metadatas:
        return {}

    # Group chunks by file identification
    files_data = {}
    for meta in all_metadatas:
        # Check org_id filter if provided
        if clean_org_ids:
            chunk_org = meta.get("org_id", "org_default")
            if chunk_org not in clean_org_ids:
                continue

        file_id = meta.get("file_id") or meta.get("tag_name_uuid") or meta.get("_original_id") or "default_textbook"
        file_name = meta.get("file_name") or meta.get("file_path")
        if not file_name:
            vol = meta.get("volume", "1")
            tag_label = meta.get("tag_name_uuid") or "Document"
            file_name = f"Tài liệu {tag_label} (Tập {vol})"

        file_key = (file_id, file_name)
        if file_key not in files_data:
            files_data[file_key] = []
        files_data[file_key].append(meta)

    outline_by_file = {}
    for (file_id, file_name), metas in files_data.items():
        lessons_seen = {}
        for m in metas:
            lesson = m.get("lesson_name") or m.get("lesson") or "Unknown"
            lesson_norm = lesson.strip().lower()

            phys_page = m.get("physical_page")
            if phys_page is None:
                phys_page = m.get("pdf_page_number")
            if phys_page is None:
                phys_page = m.get("pdf_page_index", -1)

            pdf_idx = m.get("pdf_page_index", 0)
            pdf_num = m.get("pdf_page_number")
            if pdf_num is None:
                pdf_num = int(pdf_idx) + 1 if int(pdf_idx) >= 0 else 1

            vol = m.get("volume", "1")
            tag_uuid = m.get("tag_name_uuid") or m.get("file_id") or ""
            file_path = m.get("file_path", "")
            org_id_val = m.get("org_id", "org_default")
            doc_type_val = m.get("doc_type", doc_type)

            page_sort_key = (
                int(vol) if str(vol).isdigit() else 1,
                int(phys_page) if int(phys_page) > 0 else 9999,
                int(pdf_idx)
            )

            if lesson_norm not in lessons_seen or page_sort_key < lessons_seen[lesson_norm]["sort_key"]:
                lessons_seen[lesson_norm] = {
                    "lesson_name": lesson,
                    "physical_page": phys_page,
                    "pdf_page_index": pdf_idx,
                    "pdf_page_number": pdf_num,
                    "volume": vol,
                    "tag_name_uuid": tag_uuid,
                    "file_id": file_id,
                    "file_path": file_path,
                    "org_id": org_id_val,
                    "doc_type": doc_type_val,
                    "sort_key": page_sort_key
                }

        sorted_lessons = sorted(lessons_seen.values(), key=lambda x: x["sort_key"])

        cleaned_lessons = []
        for l in sorted_lessons:
            item = dict(l)
            item.pop("sort_key", None)
            cleaned_lessons.append(item)

        outline_by_file[file_name] = cleaned_lessons

    return outline_by_file





