import json
import logging
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, List, Union
from src import config

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "logs")
os.makedirs(LOG_DIR, exist_ok=True)


class DailyFileHandler(logging.Handler):
    """Writes to a new file named '{prefix}-YYYY-MM-DD.log' whenever the date changes."""

    def __init__(self, log_dir, prefix="api"):
        super().__init__()
        self.log_dir = log_dir
        self.prefix = prefix
        self._current_date = None
        self._stream = None

    def _open_for_today(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_date:
            if self._stream:
                self._stream.close()
            self._current_date = today
            path = os.path.join(self.log_dir, f"{self.prefix}-{today}.log")
            self._stream = open(path, "a", encoding="utf-8")

    def emit(self, record):
        try:
            self._open_for_today()
            self._stream.write(self.format(record) + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self):
        if self._stream:
            self._stream.close()
        super().close()


# Full request/response detail (method, path, body) -> file only
logger = logging.getLogger("api")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    file_handler = DailyFileHandler(LOG_DIR, prefix="api")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(file_handler)

# Short status only ("OK"/"FAILED") -> console only
console_logger = logging.getLogger("api.console")
console_logger.setLevel(logging.INFO)
console_logger.propagate = False
if not console_logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    console_logger.addHandler(console_handler)
from src.pipeline.ingest import run_ingest
from src.vector_store.search import book_knowledge_search, multi_domain_retrieval
from src.vector_store.client import get_vector_db_client, get_embedding_function, get_or_create_collection, get_vector_store
from src.prompt_registry.registry import (
    initialize_prompt_db,
    get_active_prompts,
    get_prompt_versions,
    create_prompt_version,
    activate_prompt_version,
    CreatePromptRequest,
    ActivatePromptRequest
)

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

@app.on_event("startup")
def on_startup():
    initialize_prompt_db()


@app.middleware("http")
async def log_requests_responses(request: Request, call_next):
    req_body = await request.body()
    logger.info(f"[API] Incoming Request - {request.method} {request.url.path}"
                f"{'?' + str(request.url.query) if request.url.query else ''}"
                f" - body: {req_body.decode('utf-8', errors='replace')}")

    response = await call_next(request)

    resp_body = b""
    async for chunk in response.body_iterator:
        resp_body += chunk
    logger.info(f"[API] Outgoing Response - {request.method} {request.url.path}"
                f" - status: {response.status_code} - body: {resp_body.decode('utf-8', errors='replace')}")

    status_label = "OK" if response.status_code < 400 else "FAILED"
    console_logger.info(f"[API] {request.method} {request.url.path} -> {response.status_code} {status_label}")

    return Response(
        content=resp_body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
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
    
    # Modular execution steps
    step_ocr: Optional[bool] = True
    step_ingest: Optional[bool] = True

    # Backend compatibility fields
    datetime_str: Optional[str] = None
    collection_name_override: Optional[str] = None


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
    org_id: Optional[str] = "org_default"
    
    # Modular execution steps
    step_ocr: Optional[bool] = True
    step_ingest: Optional[bool] = True


class RetrievalPayloadRequest(BaseModel):
    text: str
    tag_name_uuids: Union[List[str], str]
    type: Optional[str] = "doc"  # "doc" | "qa"
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    top_k: Optional[int] = 5
    org_ids: Optional[Union[List[str], str]] = None


class OutlinePayloadRequest(BaseModel):
    tag_name_uuids: Optional[Union[List[str], str]] = None
    doc_type: Optional[str] = "doc"
    org_ids: Optional[Union[List[str], str]] = None


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
        if config.VECTOR_DB_BACKEND == "qdrant":
            from qdrant_client import QdrantClient
            if config.QDRANT_HOST:
                client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
            else:
                client = QdrantClient(path=str(config.DATA_DIR / "qdrant_db"))
            client.get_collections()
            db_connected = True
        else:
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
        normalized_path = req.file_path.replace("\\", "/") if req.file_path else None
        run_ingest(
            force_ocr=req.force,
            field=target_field,
            visibility=req.visibility,
            pdf_path=normalized_path,
            volume=req.volume,
            description=req.description,
            file_id=req.file_id,
            file_name=req.file_name,
            owner_id=req.owner_id,
            allowed_group=req.allowed_group,
            allowed_user=req.allowed_user,
            mode=req.mode,
            step_ocr=req.step_ocr,
            step_ingest=req.step_ingest,
            datetime_str=req.datetime_str,
            collection_name_override=req.collection_name_override
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
        vector_store = get_vector_store(field)
        
        # Build metadata filters for RBAC
        where_filter = {}
        if role != config.ROLE_ADMIN:
            allowed_visibilities = config.ROLE_VISIBILITY_MAPPING.get(role, ["public"])
            if len(allowed_visibilities) == 1:
                where_filter = {"visibility": allowed_visibilities[0]}
            else:
                where_filter = {"$or": [{"visibility": v} for v in allowed_visibilities]}
                
        # Fetch documents
        results = vector_store.get_all(where=where_filter)
        
        formatted_records = []
        if results and "ids" in results:
            for idx, doc_id in enumerate(results["ids"][:limit]):
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
        vector_store = get_vector_store(field)
        results = vector_store.get_all()
        
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
        clean_file_id = file_id.strip().lower()
        clean_doc_type = doc_type.strip().lower()
        clean_field = field.strip().lower()
        
        col_names_to_check = [
            f"{clean_file_id}_{clean_doc_type}",
            f"{config.COLLECTION_NAME}_{clean_field}",
            f"{clean_field}_{clean_doc_type}"
        ]
        
        if config.VECTOR_DB_BACKEND == "qdrant":
            from qdrant_client import QdrantClient
            if config.QDRANT_HOST:
                client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
            else:
                client = QdrantClient(path=str(config.DATA_DIR / "qdrant_db"))
            existing_cols = [c.name for c in client.get_collections().collections]
        else:
            client = get_vector_db_client()
            existing_cols = [c.name for c in client.list_collections()]
            
        target_collection_name = None
        where_clause = None
        
        for c_name in col_names_to_check:
            if c_name in existing_cols:
                target_collection_name = c_name
                if c_name.startswith(f"{clean_file_id}_"):
                    where_clause = None
                else:
                    where_clause = {"$or": [{"file_id": file_id}, {"tag_name_uuid": file_id}]}
                break
                
        if not target_collection_name:
            target_collection_name = f"{config.COLLECTION_NAME}_{clean_field}"
            where_clause = {"$or": [{"file_id": file_id}, {"tag_name_uuid": file_id}]}

        vector_store = get_vector_store(clean_field, collection_name_override=target_collection_name)
        res = vector_store.get_all(where=where_clause)
        
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
        vector_store = get_vector_store(field)
        
        # Deleting all matching records
        vector_store.delete(where={"file_id": str(file_id)})
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
            
        doc_col_name = f"{clean_name}_doc"
        qa_col_name = f"{clean_name}_qa"
        
        created = []
        already_existed = []
        
        if config.VECTOR_DB_BACKEND == "qdrant":
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
            if config.QDRANT_HOST:
                client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
            else:
                client = QdrantClient(path=str(config.DATA_DIR / "qdrant_db"))
                
            existing_cols = [c.name for c in client.get_collections().collections]
            embedding_fn = get_embedding_function()
            dummy_emb = embedding_fn(["dummy"])[0]
            vector_size = len(dummy_emb)
            
            for col_name in [doc_col_name, qa_col_name]:
                if col_name in existing_cols:
                    already_existed.append(col_name)
                else:
                    client.create_collection(
                        collection_name=col_name,
                        vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE)
                    )
                    created.append(col_name)
        else:
            client = get_vector_db_client()
            embedding_fn = get_embedding_function()
            existing_cols = [c.name for c in client.list_collections()]
            
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
            collection_name_override=col_override_name,
            step_ocr=req.step_ocr,
            step_ingest=req.step_ingest,
            org_id=req.org_id
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
        tag_uuids = req.tag_name_uuids
        if isinstance(tag_uuids, str):
            v_stripped = tag_uuids.strip()
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                try:
                    parsed = json.loads(v_stripped)
                    if isinstance(parsed, list):
                        tag_uuids = [str(item).strip("'\" ") for item in parsed]
                    else:
                        tag_uuids = [v_stripped.strip("'\" ")]
                except Exception:
                    tag_uuids = [v_stripped.strip("'\" ")]
            else:
                tag_uuids = [v_stripped.strip("'\" ")]
        elif isinstance(tag_uuids, list):
            cleaned = []
            for item in tag_uuids:
                if isinstance(item, str):
                    item_stripped = item.strip()
                    if item_stripped.startswith("[") and item_stripped.endswith("]"):
                        try:
                            parsed = json.loads(item_stripped)
                            if isinstance(parsed, list):
                                cleaned.extend([str(x).strip("'\" ") for x in parsed])
                                continue
                        except Exception:
                            pass
                    cleaned.append(item_stripped.strip("'\" "))
                else:
                    cleaned.append(str(item))
            tag_uuids = cleaned

        # Parse org_ids
        org_ids = req.org_ids
        if org_ids:
            if isinstance(org_ids, str):
                v_stripped = org_ids.strip()
                if v_stripped.startswith("[") and v_stripped.endswith("]"):
                    try:
                        parsed = json.loads(v_stripped)
                        if isinstance(parsed, list):
                            org_ids = [str(item).strip("'\" ") for item in parsed]
                        else:
                            org_ids = [v_stripped.strip("'\" ")]
                    except Exception:
                        org_ids = [v_stripped.strip("'\" ")]
                else:
                    org_ids = [v_stripped.strip("'\" ")]
            elif isinstance(org_ids, list):
                cleaned_orgs = []
                for item in org_ids:
                    if isinstance(item, str):
                        item_stripped = item.strip()
                        if item_stripped.startswith("[") and item_stripped.endswith("]"):
                            try:
                                parsed = json.loads(item_stripped)
                                if isinstance(parsed, list):
                                    cleaned_orgs.extend([str(x).strip("'\" ") for x in parsed])
                                    continue
                            except Exception:
                                pass
                        cleaned_orgs.append(item_stripped.strip("'\" "))
                    else:
                        cleaned_orgs.append(str(item))
                org_ids = cleaned_orgs
        else:
            org_ids = []

        print(f"[Retrieval API] Incoming Request - text: '{req.text}', tag_name_uuids: {tag_uuids}, org_ids: {org_ids}, type: {req.type}")
        results = multi_domain_retrieval(
            query=req.text,
            tag_name_uuids=tag_uuids,
            doc_type=req.type or "doc",
            from_date=req.from_date,
            to_date=req.to_date,
            top_k=req.top_k or 5,
            org_ids=org_ids
        )
        return {
            "text": req.text,
            "tag_name_uuids": tag_uuids,
            "org_ids": org_ids,
            "type": req.type or "doc",
            "total_results": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class LLMRequest(BaseModel):
    prompt: str
    system_instruction: Optional[str] = None


@app.post("/api/llm")
@app.post("/llm")
def call_llm(req: LLMRequest):
    """
    Utility endpoint to call the Gemini model using the configured provider (Vertex AI or Google AI Studio).
    """
    try:
        from google import genai
        from google.genai import types
        
        if config.USE_VERTEXAI:
            ai_client = genai.Client(
                vertexai=True,
                project=config.GOOGLE_CLOUD_PROJECT,
                location=config.GOOGLE_CLOUD_LOCATION
            )
        else:
            if not config.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY is not configured in the environment.")
            ai_client = genai.Client(api_key=config.GEMINI_API_KEY)
            
        config_params = {}
        if req.system_instruction:
            config_params["system_instruction"] = req.system_instruction
            
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=req.prompt,
            config=types.GenerateContentConfig(**config_params) if config_params else None
        )
        
        return {
            "status": "success",
            "text": response.text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prompts/active")
def get_active_prompts_endpoint(profile: str = "default", version: Optional[int] = None):
    try:
        prompts = get_active_prompts(profile=profile, version=version)
        return prompts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prompts/versions")
def get_prompt_versions_endpoint(agent_name: Optional[str] = None, profile: Optional[str] = None):
    try:
        versions = get_prompt_versions(agent_name=agent_name, profile=profile)
        return versions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/prompts")
def create_prompt_endpoint(req: CreatePromptRequest):
    try:
        new_prompt = create_prompt_version(req)
        return new_prompt
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/prompts/activate")
def activate_prompt_endpoint(req: ActivatePromptRequest):
    try:
        success = activate_prompt_version(req)
        return {
            "status": "success",
            "message": f"Successfully activated version {req.version} for agent '{req.agent_name}' in profile '{req.profile}'"
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/outline")
@app.get("/outline")
def get_outline_endpoint_get(
    tag_name_uuids: Optional[Union[List[str], str]] = None,
    doc_type: Optional[str] = "doc",
    org_ids: Optional[Union[List[str], str]] = None
):
    """
    Returns the table of contents/outline for documents matching the given tag_name_uuids or org_ids.
    """
    try:
        from src.vector_store.search import get_document_outline
        outline = get_document_outline(
            tag_name_uuids=tag_name_uuids,
            doc_type=doc_type or "doc",
            org_ids=org_ids
        )
        return {
            "status": "success",
            "tag_name_uuids": tag_name_uuids,
            "org_ids": org_ids,
            "doc_type": doc_type or "doc",
            "total_files": len(outline),
            "outline": outline
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/outline")
@app.post("/outline")
def get_outline_endpoint_post(req: OutlinePayloadRequest):
    """
    Returns the table of contents/outline for documents matching the given tag_name_uuids or org_ids (POST payload format).
    """
    try:
        from src.vector_store.search import get_document_outline
        outline = get_document_outline(
            tag_name_uuids=req.tag_name_uuids,
            doc_type=req.doc_type or "doc",
            org_ids=req.org_ids
        )
        return {
            "status": "success",
            "tag_name_uuids": req.tag_name_uuids,
            "org_ids": req.org_ids,
            "doc_type": req.doc_type or "doc",
            "total_files": len(outline),
            "outline": outline
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



