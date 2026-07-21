from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from src import config
from src.pipeline.ingest import run_ingest
from src.vector_store.search import book_knowledge_search, multi_domain_retrieval
from src.vector_store.client import get_vector_db_client, get_embedding_function, get_or_create_collection

app = FastAPI(
    title="Grade 3 Math Assistant API",
    description="Backend services for Grade 3 Math AI Assistant, with Role-Based Access Control and Field Isolation.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class IngestRequest(BaseModel):
    file_path: Optional[str] = None
    volume: Optional[str] = "1"
    field: Optional[str] = "math"
    visibility: Optional[str] = "public"
    force: Optional[bool] = False
    
    # Future metadata fields
    tag_name: Optional[str] = None
    description: Optional[str] = None
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    
    # Fine-grained RBAC/ACL fields
    owner_id: Optional[str] = None
    allowed_group: Optional[str] = None
    allowed_user: Optional[str] = None
    
    # Overwrite mode: "keep_cache" or "delete_first"
    mode: Optional[str] = "keep_cache"


class CreateDomainRequest(BaseModel):
    domain_name: str


class IngestionPayloadRequest(BaseModel):
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    tag_name_uuid: str
    description: Optional[str] = None
    datetime: Optional[str] = None
    mode: Optional[str] = "update"  # "update" | "override"
    doc_type: Optional[str] = "doc"  # "doc" | "qa"
    volume: Optional[str] = "1"
    force: Optional[bool] = False


class RetrievalPayloadRequest(BaseModel):
    text: str
    tag_name_uuids: List[str]
    type: Optional[str] = "doc"  # "doc" | "qa"
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    top_k: Optional[int] = 5


class SearchRequest(BaseModel):
    query: str
    role: Optional[str] = "student"
    field: Optional[str] = "math"
    top_k: Optional[int] = 5
    page_hint: Optional[int] = None
    volume_hint: Optional[str] = None
    
    # Fine-grained RBAC/ACL fields
    user_id: Optional[str] = None
    groups: Optional[list[str]] = None

@app.get("/api/health")
def health_check():
    """
    Verifies server health and database connectivity.
    """
    try:
        client = get_vector_db_client()
        client.heartbeat()
        db_connected = True
    except Exception:
        db_connected = False
    return {
        "status": "ok",
        "db_connected": db_connected
    }

@app.post("/api/ingest")
def ingest_document(req: IngestRequest):
    """
    Ingests a document (OCR parsing -> Embedding generation -> ChromaDB indexing)
    into an isolated subject field with specified visibility permissions.
    """
    try:
        target_field = req.tag_name if req.tag_name else req.field
        run_ingest(
            force_ocr=req.force,
            field=target_field,
            visibility=req.visibility,
            pdf_path=req.file_path,
            volume=req.volume,
            description=req.description,
            file_id=req.file_id,
            file_name=req.file_name,
            owner_id=req.owner_id,
            allowed_group=req.allowed_group,
            allowed_user=req.allowed_user,
            mode=req.mode
        )
        return {
            "status": "success",
            "message": f"Successfully ingested {req.file_path} into field '{target_field}' with visibility '{req.visibility}'"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search")
def search_textbook_api(req: SearchRequest):
    """
    Queries the vector database using hybrid search (Dense + BM25) and applies RBAC visibility rules.
    """
    try:
        results = book_knowledge_search(
            query=req.query,
            page_hint=req.page_hint,
            volume_hint=req.volume_hint,
            top_k=req.top_k,
            field=req.field,
            user_role=req.role,
            user_id=req.user_id,
            user_groups=req.groups
        )
        return {
            "query": req.query,
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/preview")
def preview_db(field: str = "math", role: str = "student", limit: int = 10):
    """
    Peeks inside the vector database collection to preview the raw text and metadata 
    associated with a specific role's permission level.
    """
    try:
        client = get_vector_db_client()
        embedding_fn = get_embedding_function()
        col_name = f"{config.COLLECTION_NAME}_{field}"
        collection = get_or_create_collection(client, embedding_fn, collection_name=col_name)
        
        # Build metadata filters for RBAC
        where_filter = {}
        if role != config.ROLE_ADMIN:
            allowed_visibilities = config.ROLE_VISIBILITY_MAPPING.get(role, ["public"])
            if len(allowed_visibilities) == 1:
                where_filter = {"visibility": allowed_visibilities[0]}
            else:
                where_filter = {"$or": [{"visibility": v} for v in allowed_visibilities]}
                
        chroma_where = where_filter if where_filter else None
        
        # Fetch documents
        results = collection.get(
            limit=limit,
            where=chroma_where,
            include=["documents", "metadatas"]
        )
        
        formatted_records = []
        if results and "ids" in results:
            for idx, doc_id in enumerate(results["ids"]):
                formatted_records.append({
                    "id": doc_id,
                    "text": results["documents"][idx],
                    "metadata": results["metadatas"][idx]
                })
                
        return {
            "field": field,
            "role": role,
            "total_retrieved": len(formatted_records),
            "records": formatted_records
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents")
def list_documents(field: str = "math"):
    """
    Lists unique ingested documents in the specified subject field.
    """
    try:
        client = get_vector_db_client()
        embedding_fn = get_embedding_function()
        col_name = f"{config.COLLECTION_NAME}_{field}"
        collection = get_or_create_collection(client, embedding_fn, collection_name=col_name)
        
        # Get all chunk metadata
        results = collection.get(include=["metadatas"])
        
        docs_dict = {}
        if results and "metadatas" in results:
            for idx, meta in enumerate(results["metadatas"]):
                file_id = meta.get("file_id")
                if not file_id:
                    file_id = "default_textbook"
                    file_name = f"Sách giáo khoa Toán 3 (Tập {meta.get('volume', '1')})"
                else:
                    file_name = meta.get("file_name", "Unknown File")
                    
                if file_id not in docs_dict:
                    docs_dict[file_id] = {
                        "file_id": file_id,
                        "file_name": file_name,
                        "field": meta.get("field", field),
                        "visibility": meta.get("visibility", "public"),
                        "owner_id": meta.get("owner_id"),
                        "allowed_group": meta.get("allowed_group"),
                        "allowed_user": meta.get("allowed_user"),
                        "description": meta.get("description"),
                        "chunk_count": 0
                    }
                docs_dict[file_id]["chunk_count"] += 1
                
        return {
            "field": field,
            "total_documents": len(docs_dict),
            "documents": list(docs_dict.values())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents/{file_id}")
def get_document_chunks_endpoint(file_id: str, field: str = "math", doc_type: str = "doc"):
    """
    Retrieves all text chunks and metadata belonging to a specific file_id for reading or visual comparison,
    ordered by physical_page / pdf_page_index.
    """
    try:
        client = get_vector_db_client()
        embedding_fn = get_embedding_function()
        
        clean_file_id = file_id.strip().lower()
        clean_doc_type = doc_type.strip().lower()
        clean_field = field.strip().lower()
        
        col_names_to_check = [
            f"{clean_file_id}_{clean_doc_type}",
            f"{config.COLLECTION_NAME}_{clean_field}",
            f"{clean_field}_{clean_doc_type}"
        ]
        
        existing_cols = [c.name for c in client.list_collections()]
        target_collection = None
        where_clause = None
        
        for c_name in col_names_to_check:
            if c_name in existing_cols:
                target_collection = get_or_create_collection(client, embedding_fn, collection_name=c_name)
                if c_name.startswith(f"{clean_file_id}_"):
                    where_clause = None
                else:
                    where_clause = {"$or": [{"file_id": file_id}, {"tag_name_uuid": file_id}]}
                break
                
        if not target_collection:
            col_name = f"{config.COLLECTION_NAME}_{clean_field}"
            target_collection = get_or_create_collection(client, embedding_fn, collection_name=col_name)
            where_clause = {"$or": [{"file_id": file_id}, {"tag_name_uuid": file_id}]}

        res = target_collection.get(where=where_clause, include=["documents", "metadatas"])
        
        chunks = []
        if res and res.get("ids"):
            for idx, chunk_id in enumerate(res["ids"]):
                text = res["documents"][idx] if "documents" in res and res["documents"] else ""
                meta = res["metadatas"][idx] if "metadatas" in res and res["metadatas"] else {}
                chunks.append({
                    "id": chunk_id,
                    "text": text,
                    "metadata": meta,
                    "physical_page": meta.get("physical_page", -1),
                    "pdf_page_index": meta.get("pdf_page_index", 0)
                })
                
        # Sort chunks in reading order by physical_page or pdf_page_index
        chunks.sort(key=lambda c: (c["physical_page"] if c["physical_page"] > 0 else 99999, c["pdf_page_index"]))
        
        return {
            "file_id": file_id,
            "field": field,
            "doc_type": doc_type,
            "total_chunks": len(chunks),
            "chunks": chunks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/documents/{file_id}")
def delete_document(file_id: str, field: str = "math"):
    """
    Deletes all chunks associated with a file_id.
    """
    try:
        client = get_vector_db_client()
        embedding_fn = get_embedding_function()
        col_name = f"{config.COLLECTION_NAME}_{field}"
        collection = get_or_create_collection(client, embedding_fn, collection_name=col_name)
        
        # Deleting all matching records
        collection.delete(where={"file_id": str(file_id)})
        return {
            "status": "success",
            "message": f"Successfully deleted document '{file_id}' from field '{field}'"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/create-domain")
@app.post("/create-domain")
def create_domain_endpoint(req: CreateDomainRequest):
    """
    Creates two database collections ({domain_name}_doc and {domain_name}_qa)
    after verifying they do not already exist.
    """
    try:
        clean_name = req.domain_name.strip().lower()
        if not clean_name:
            raise HTTPException(status_code=400, detail="domain_name cannot be empty")
            
        client = get_vector_db_client()
        embedding_fn = get_embedding_function()
        
        existing_cols = [c.name for c in client.list_collections()]
        doc_col_name = f"{clean_name}_doc"
        qa_col_name = f"{clean_name}_qa"
        
        created = []
        already_existed = []
        
        for col_name in [doc_col_name, qa_col_name]:
            if col_name in existing_cols:
                already_existed.append(col_name)
            else:
                get_or_create_collection(client, embedding_fn, collection_name=col_name)
                created.append(col_name)
                
        return {
            "status": "success",
            "domain_name": clean_name,
            "created_collections": created,
            "existing_collections": already_existed
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingestion")
@app.post("/ingestion")
def ingestion_endpoint(req: IngestionPayloadRequest):
    """
    Ingests a document or QA set with tag_name_uuid, timestamp, description,
    and supports mode ("update" | "override").
    """
    try:
        clean_tag = req.tag_name_uuid.strip().lower()
        doc_type_clean = req.doc_type.strip().lower() if req.doc_type else "doc"
        col_override_name = f"{clean_tag}_{doc_type_clean}"
        
        run_ingest(
            force_ocr=req.force,
            field=clean_tag,
            pdf_path=req.file_path,
            volume=req.volume,
            description=req.description,
            file_id=req.tag_name_uuid,
            file_name=req.file_name or req.tag_name_uuid,
            mode=req.mode,
            datetime_str=req.datetime,
            doc_type=doc_type_clean,
            collection_name_override=col_override_name
        )
        return {
            "status": "success",
            "message": f"Successfully ingested into domain collection '{col_override_name}'",
            "tag_name_uuid": clean_tag,
            "doc_type": doc_type_clean,
            "mode": req.mode
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/retrieval")
@app.post("/retrieval")
def retrieval_endpoint(req: RetrievalPayloadRequest):
    """
    Retrieves vector search results across multiple tag/domain collections
    with type targeting (doc | qa) and date-range filtering (from_date -> to_date).
    """
    try:
        results = multi_domain_retrieval(
            query=req.text,
            tag_name_uuids=req.tag_name_uuids,
            doc_type=req.type or "doc",
            from_date=req.from_date,
            to_date=req.to_date,
            top_k=req.top_k or 5
        )
        return {
            "text": req.text,
            "tag_name_uuids": req.tag_name_uuids,
            "type": req.type or "doc",
            "total_results": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
