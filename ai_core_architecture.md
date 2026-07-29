# AI Core Architecture & Implementation Specification

This document outlines the detailed system architecture design, data models, features, and input-to-output data processing workflows for the educational AI assistant.

---

## 1. System Architecture Diagram

The diagram below illustrates the offline data processing pipeline, the online REST API web endpoints, and the role-based retrieval loop:

```mermaid
graph TD
    %% Styling
    classDef process fill:#f9f,stroke:#333,stroke-width:2px;
    classDef storage fill:#bbf,stroke:#333,stroke-width:2px;
    classDef api fill:#bfb,stroke:#333,stroke-width:2px;

    %% Pipelines
    subgraph Ingestion_Pipeline ["1. Data Ingestion & Field Isolation"]
        PDF["Input PDF (e.g. Math, Science)"] -->|Specify Subject Field| OCR["Page Rendering & Concurrent Gemini OCR"]
        OCR -->|JSON Output| Validate["Parse Page Index, Lesson Name & Text"]
        Validate -->|Cache| JSON_Cache[("processed_book_data.json")]
        JSON_Cache -->|Embeddings text-embedding-004| Embed["Embeddings Engine"]
        Embed -->|Index into Isolated Collection| DB[("Vector Store Backend<br>(ChromaDB / Qdrant)")]
    end

    subgraph API_Endpoints ["2. REST API Web Services (Port 8080)"]
        Ingest_API["POST /api/ingest<br>(field, visibility, file, metadata)"] -.->|Trigger Ingest| Ingestion_Pipeline
        Search_API["POST /api/search<br>(query, role, field, top_k)"]
        Preview_API["GET /api/preview<br>(field, role, limit)"]
        Health_API["GET /api/health"]
        LLM_Proxy["POST /api/llm<br>(GCP Vertex AI / Gemini API wrapper)"]
    end

    subgraph n8n_Orchestration ["3. n8n Multi-Agent Orchestration & LLM Proxy"]
        Webhook_In["Webhook POST /webhook/rag-math-assistant"] -->|1. Validate Credentials| Security_Gate["Security & Sanitization Gate"]
        Security_Gate -->|2. Fetch Prompts| Fetch_Prompts["Fetch Active Prompts<br>(GET /api/prompts/active)"]
        Fetch_Prompts -->|3. User Prompt & System Prompt| Planner_Agent["Planner Agent"]
        Planner_Agent -->|4. Call Proxy /api/llm| LLM_Proxy
        LLM_Proxy -->|5. Route intent + need RAG?| Parse_Planner["Parse Planner Decision"]
        Parse_Planner -->|6. If RAG = true| Call_Retriever["Call Python Retrieval API<br>(POST /api/retrieval)"]
        Call_Retriever -->|7. Merge Context & Route| Router{"Orchestrator Router"}
        Router -->|Expert Agent| Expert_Agent["Expert LLM Agent<br>(Tutor/Solver/Reviewer...)"]
        Expert_Agent -->|8. Call Proxy /api/llm| LLM_Proxy
        Expert_Agent -->|9. Draft Response| Aggregate["Aggregate Expert Draft"]
        Aggregate -->|10. Verify Grounding| Verifier["Verifier QA Agent"]
        Verifier -->|11. Call Proxy /api/llm| LLM_Proxy
        Verifier -->|12. Final Answer| Respond_Webhook["Respond to Webhook (200 OK JSON)"]
    end

    subgraph Retrieval_Loop ["4. RBAC Retrieval Loop (FastAPI Side)"]
        Search_API -->|Extract hints: Page / Vol| HintExtract["Regex Hint Extractor"]
        HintExtract -->|Build Metadata Filters & Role Visibility| RBAC_Filter["RBAC Visibility Filter"]
        RBAC_Filter -->|Target Collection by Subject Field| DB_Query["Query Isolated Subject Collection"]
        DB -.-> DB_Query
        DB_Query -->|Semantic + BM25 scores| RRF["Reciprocal Rank Fusion (RRF)"]
        RRF -->|Top K matched snippets| Search_API
    end

    subgraph Visualization_UI ["5. Database View & Comparison"]
        Preview_API -->|Query by Field & Role| DB_View["Query Vector Store Collection"]
        DB_View -->|Raw Text & Metadata| UI_Compare["VS Code DB Viewer / Streamlit UI"]
        UI_Compare -->|Manual Validation| Compare["Visual Comparison (Original vs Ingested)"]
    end
```

---

## 2. Core Components & Isolation Design

The system implements strict separation of concerns to handle visually-intensive textbook layouts and fulfill access control policies:

### A. Field-Based Collection Isolation & Switchable Backend
*   To prevent cross-subject interference (e.g., math queries retrieving science formulas), documents are isolated at the **Collection level** in the Vector Database.
*   The subject name (passed as `field`) serves as a suffix for the collection name (e.g., `toan_3_curriculum_math`, `toan_3_curriculum_science`).
*   During ingestion and retrieval, the system connects only to the collection associated with the requested `field`.
*   **Switchable Backend Support (ChromaDB / Qdrant):** 
    - Controlled via the `VECTOR_DB_BACKEND` environment variable.
    - In **Qdrant** mode, string IDs are dynamically mapped to deterministic UUIDv5 point IDs, and dictionary filters are recursively converted to Qdrant's nested filter conditions.
    - Under `VECTOR_DB_BACKEND=qdrant`, ChromaDB is completely bypassed, and vice versa when set to `chromadb`.

### B. Role-Based Access Control (RBAC)
*   **Roles:** The system supports three standard roles: `student`, `teacher`, and `admin`.
*   **Visibility Levels:** Each page chunk in the Vector Database is tagged with a `visibility` metadata attribute:
    *   `public`: Accessible by all roles (`student`, `teacher`, `admin`).
    *   `teacher_only`: Accessible by `teacher` and `admin`.
    *   `admin_only`: Accessible only by `admin`.
*   **Retrieval Enforcement:** When querying the database, the user's role is mapped to allowed visibility levels:
    *   `student` -> `{"visibility": "public"}`
    *   `teacher` -> `{"$or": [{"visibility": "public"}, {"visibility": "teacher_only"}]}`
    *   `admin` -> No visibility filter (accesses all data).
*   This filtering is enforced at the database query level (`where` clause in the active Vector Store) to guarantee that users cannot access vectors outside their authorized scope.

### C. Multimodal OCR & Caching
*   **DPI Rendering:** Uses `PyMuPDF` to convert PDF pages into PNG images at 150 DPI to ensure clear legibility for Gemini vision models.
*   **Gemini Vision OCR:** Sends rendered pages to `gemini-2.5-flash` with a prompt demanding physical page numbers, lesson names, and page markdown text in structured JSON format.
*   **Robust Rate-Limit Handling:** Utilizes a ThreadPoolExecutor with `max_workers=2` and an exponential backoff retry handler (sleeping 15s/30s/45s on `429 RESOURCE_EXHAUSTED` errors) to guarantee complete OCR extraction without empty pages.
*   **Caching:** Results are cached in `data/processed_book_data.json` to prevent duplicate API costs.

### E. Multi-Domain & Tag UUID Data Model (1:1 Ingestion to 1:N Retrieval)
*   **Single-UUID Document Ingestion:** Each ingested document (`POST /ingestion`) is tagged with **exactly 1 unique `tag_name_uuid`**. Every chunk generated from the document explicitly attaches `"tag_name_uuid": "uuid_x"` in its metadata.
*   **Multi-UUID Retrieval Routing:** When querying via `POST /retrieval`, a list of target UUIDs (`tag_name_uuids: ["uuid_1", "uuid_2", ...]`) is passed. The retrieval engine targets collections or chunks associated with ANY of the specified UUIDs in the array. Chunks belonging to UUIDs not present in the list are 100% excluded from the query scope.

### F. LLM Completion Proxying & n8n Orchestration
*   **n8n Workflow Execution:** The workflow begins with a POST Webhook receiving the user query. The `Security & Sanitization Gate` validates credentials and sanitizes prompt overrides, then the `Fetch Active Prompts` node retrieves the active system instructions from the Prompt Registry DB. The Planner Agent evaluates user intent using these fetched system prompts, and decides which expert to call and whether RAG is necessary.
*   **FastAPI LLM Proxy (`/api/llm`):** All LLM calls (Planner Agent, Expert Agents, and Verifier Agent) are routed through the FastAPI backend's `/api/llm` endpoint. The proxy dynamically determines the backend provider based on configuration (`USE_VERTEXAI` or `GEMINI_API_KEY`) and calls Gemini (`gemini-2.5-flash`) securely using the container's GCP environment, removing credential management overhead from n8n.
*   **RAG Routing & Guardrails:** If context retrieval is required, n8n invokes `/api/retrieval`. If retrieval returns no results, a strict fallback guardrail triggers only for lookup-dependent modules (`default` and `theory_explanation`) to prevent LLM hallucinations. For all other modules (`barem_review`, `exercise_generator`, `suggestive_tutor`, `direct_solver`), the workflow bypasses this guardrail, allowing them to solve, tutor, grade, or generate questions without failure.
*   **Multi-Agent Expert Routing:** The Orchestrator Router dynamically splits flows based on the Planner Agent's decision:
    - `barem_review` -> `Barem Reviewer`
    - `theory_explanation` -> `Theory Explainer`
    - `exercise_generator` -> `Exercise Generator`
    - `suggestive_tutor` -> `Suggestive Tutor`
    - `direct_solver` -> `Direct Solver`
    - `default` -> `Default Teacher`
*   **Verifier & Socratic Tone Quality Control:** Once an expert generates a draft response, the `Verifier QA Agent` validates it using a module-specific verifier prompt template fetched dynamically from the database (`verifier_default_teacher`, `verifier_barem_review`, `verifier_theory_explanation`, `verifier_exercise_generator`, `verifier_suggestive_tutor`, `verifier_direct_solver`). The verifier validates grounding (where applicable), mathematical accuracy, compliance with pedagogical style constraints (e.g., ensuring no direct answers are in Socratic tutor drafts), and formatting before outputting the final result.

---

## 3. System Features List

1.  **Tag-based Ingestion & Ingestion API:** Support modular pipelines with custom fields and visibility scopes.
2.  **Subject Field Isolation:** Creates independent database collections per subject area to prevent data cross-contamination.
3.  **Role-Based Access Control:** Filters search results based on visibility tags (`public`, `teacher_only`, `admin_only`) mapped to user roles (`student`, `teacher`, `admin`).
4.  **Hybrid Dense-Sparse Search:** Combines vector embeddings (`text-embedding-004`) with keyword BM25 search.
5.  **Metadata Window Filter:** Extracts page and volume hints from query strings and restricts retrieval to neighboring pages.
6.  **FastAPI REST Web Service:** Exposes ingestion, search/RAG, preview, and health check endpoints.
7.  **Interactive CLI Search Tool:** Provides a terminal-based interface to verify database contents and query RAG retrieval directly.
8.  **Streamlit Web User Interface:** Exposes the RAG Search Explorer, document ingestion, vector DB preview, and health monitoring in a single web UI.
9.  **Vector DB Preview Utility:** Allows listing collection contents, enabling direct text and metadata comparison with original source PDFs.
10. **Google Cloud Vertex AI Authentication:** Supports authenticating natively via Service Account JSON credentials (`data/gcp-key.json`) mounted in Docker.
11. **Domain Management & Dual Collection Creation (`/create-domain`):** Dynamically provisions `{domain}_doc` (documents) and `{domain}_qa` (Q&A pairs) isolated collections.
12. **Multi-Domain & Date-Filtered Retrieval (`/retrieval`):** Routes queries across multiple domain UUIDs with content-type targeting (`doc` vs `qa`) and epoch numeric date-range filtering (`from_date` to `to_date`).
13. **Single-UUID Ingestion & Override/Update Modes (`/ingestion`):** Ingests PDF/QA documents with exact 1:1 `tag_name_uuid` metadata tagging, supporting `update` vs `override` deletion modes.
14. **Interactive Streamlit AI Chatbot & Chunk Visualizer:** Provides interactive pedagogical chat with Gemini AI reasoning, automatic textbook footnotes (`📖 Nguồn tham khảo`), and visual Chunk Separated Cards.
15. **n8n Multi-Agent System:** Automates orchestration, intent analysis, expert routing, and output verification via n8n.
16. **FastAPI LLM proxy wrapper (`/api/llm`):** Eliminates API key rate limits and OAuth overhead inside n8n by funneling LLM prompts through the container's GCP authenticated environment.
17. **Centralized Prompt Registry System:** Manages system prompts dynamically in a SQLite database via Streamlit UI with version history and rollback capabilities.
18. **Secure Webhook Layer:** Enforces Bearer Token/API Key verification and allowlist sanitization on incoming webhook overrides in n8n.
19. **Mentor/Instructor Test Generator & Automated Grading Workflow (`mentor_test_generator_workflow.json`):** Dual-mode n8n workflow supporting structured JSON exam generation with answer key & rubric (`action: "generate"`), and step-by-step automated student submission evaluation against rubrics with structured JSON grading output (`action: "grade"`).

---

## 4. Input-to-Output Data Processing Workflows

### Workflow A: Document Ingestion (POST /api/ingest)
```
[User Request: File Path, Subject Field, Visibility Tag]
   │
   ├──> 1. Ingestion service loads PDF file from path.
   │
   ├──> 2. PDFBookParser renders pages to PNG images.
   │
   ├──> 3. Concurrent Gemini Multimodal OCR parses images to JSON (Lesson Name, Physical Page, Text).
   │      └──> [Rate limit 429 occurs? Sleep for 15s * attempt and retry up to 5 times].
   │
   ├──> 4. OCR results are saved into `data/processed_book_data.json` cache.
   │
   ├──> 5. Text content is embedded via Vertex AI `text-embedding-004` (embeddings extraction).
   │
   └──> 6. Records are upserted into ChromaDB collection `toan_3_curriculum_{field}`.
          └──> Metadata includes: `volume`, `physical_page`, `pdf_page_index`, `lesson_name`, `visibility`.
```

### Workflow B: RAG Search & Retrieval (POST /api/search)
```
[User Input: Query String, User Role, Subject Field, parameters]
   │
   ├──> 1. NodeJS Backend (or direct client) invokes FastAPI `/api/search` POST endpoint.
   │
   ├──> 2. Search Engine receives parameters and extracts page and volume hints via regex.
   │
   ├──> 3. Restricted to the isolated ChromaDB collection corresponding to the `field`.
   │
   ├──> 4. Builds search filters combining page window matching and RBAC user role permissions.
   │
   ├──> 5. Query results from Vector Search and BM25 Okapi are fused via Reciprocal Rank Fusion (RRF).
   │
   └──> 6. Returns a structured JSON list of matching records (ID, raw text, and metadata).
          └──> Used by the NodeJS backend to construct context for final LLM teacher generation.
```

### Workflow C: DB Preview & Validation (GET /api/preview)
```
[User Request: Subject Field, User Role, limit]
   │
   ├──> 1. API identifies ChromaDB collection associated with the `field`.
   │
   ├──> 2. Builds query filter to restrict results to the user's `role` permissions.
   │
   ├──> 3. Calls `collection.get()` with limits to retrieve raw text and metadata.
   │
   └──> 4. Returns JSON list of records (id, physical_page, lesson_name, text snippet).
          └──> Used by developers in VS Code ChromaDB Viewer to verify OCR accuracy.
```

### Workflow D: Multi-Domain & Date-Filtered Retrieval (POST /retrieval)
```
[User Input: text, tag_name_uuids[], type ("doc"|"qa"), from_date, to_date, user_role, user_id, user_groups]
   │
   ├──> 1. FastAPI `/retrieval` parses dates into numeric epoch timestamps (`created_at_timestamp`).
   │
   ├──> 2. Iterates over each UUID in `tag_name_uuids`.
   │      ├──> Dedicated Collection `{uuid}_{type}` exists? Query it directly.
   │      └──> Otherwise: Query shared `_{type}` collections with metadata filter `{"$or": [{"file_id": uuid}, {"tag_name_uuid": uuid}]}`.
   │
   ├──> 3. Applies $gte and $lte date filters on `created_at_timestamp` + ACL RBAC ($or clause).
   │
   ├──> 4. Merges candidate chunks across collections and sorts by similarity distance score.
   │
   └──> 5. Returns structured JSON containing array of matching chunks (id, collection, text, distance, metadata).
```

```

### Workflow F: Document Outline Retrieval (POST /api/outline & GET /api/outline)
```
[User / n8n Workflow Request: tag_name_uuids, org_ids, doc_type]
   │
   ├──> 1. API endpoint `/api/outline` parses `tag_name_uuids` and `org_ids` filters.
   │
   ├──> 2. Discovers matching collections (`{tag}_{doc_type}`, `{COLLECTION_NAME}_{tag}`, etc.) or searches across all collections.
   │
   ├──> 3. Invokes `get_document_outline()` to fetch all chunk metadatas.
   │
   ├──> 4. Groups metadata by file (`file_name`, `file_id`) and extracts unique `lesson_name` entries.
   │
   ├──> 5. Sorts lessons chronologically by `(volume, physical_page, pdf_page_index)`.
   │
   └──> 6. Returns structured JSON containing `{ file_name: [ { lesson_name, physical_page, pdf_page_number, volume, tag_name_uuid, file_id, file_path, org_id, doc_type } ] }`.
```

---

## 5. PostgreSQL & pgvector Integration (Production Target)

To scale the system beyond development collections, the database schema supports deploying on a relational **PostgreSQL** instance equipped with the **`pgvector`** extension.

### A. Core Relational Schema
The database schema defined in [stem.db](file:///d:/Project%20Local/OCR-STEM/data/postgresql/stem.db) manages:
- **Multitenant Organizations (`organizations`, `users`)**: Guarantees complete data separation between different educational or business entities.
- **RBAC Roles & Groups (`roles`, `user_roles`, `groups`, `group_members`)**: Manages structural user scopes.
- **Document Chunk Registry (`documents`, `document_chunks`)**: Couples document ownership to vector chunks containing 768-dimensional embeddings (`vector(768)`).
- **Fine-Grained Permissions (`document_permissions`)**: Maps explicit access control list (ACL) exceptions for documents to specific users, groups, or roles.

### B. High-Performance HNSW Vector Query
To search vector embeddings while strictly filtering by multitenant constraints and role visibility, the search engine joins chunks with parent documents and filters dynamically.
The vector index is built using the HNSW algorithm with Cosine similarity:
```sql
CREATE INDEX idx_document_chunks_embedding ON document_chunks USING hnsw (embedding vector_cosine_ops);
```
During retrieval, a unified SQL query extracts the top relevant pages, ensuring that unauthorized users cannot retrieve vectors outside their access scope. Detailed schema documentation is maintained in [README.md](file:///d:/Project%20Local/OCR-STEM/data/postgresql/README.md).
