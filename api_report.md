# OpenAPI & REST API Specification Report

This document provides a modular, fully separated REST API reference for the Python RAG / Vector Engine backend services. Each endpoint is documented with its HTTP Method, URL Path, Request Parameters/Header/Body Schema, Successful (200 OK) Response, Error Responses (400/500), JSON Examples, and cURL commands.

---

## 📌 Quick Endpoint Index

| # | HTTP Method | Endpoint Path | Functionality | Section |
| :---: | :---: | :--- | :--- | :--- |
| 1 | `POST` | `/create-domain` | Initialize `{domain}_doc` & `{domain}_qa` collections | [Section 1](#1-post-create-domain) |
| 2 | `POST` | `/ingestion` | Ingest document/QA with tags, timestamp & mode | [Section 2](#2-post-ingestion) |
| 3 | `POST` | `/retrieval` | Search multi-domain collections with date & type filters | [Section 3](#3-post-retrieval) |
| 4 | `GET` | `/api/documents` | List unique ingested files & chunk statistics | [Section 4](#4-get-apidocuments) |
| 5 | `DELETE` | `/api/documents/{file_id}` | Delete all vector chunks of a specific document | [Section 5](#5-delete-apidocumentsfile_id) |
| 6 | `POST` | `/api/search` | Single-field RAG vector search | [Section 6](#6-post-apisearch) |
| 7 | `POST` | `/api/ingest` | Legacy single-field document ingestion | [Section 7](#7-post-apiingest) |
| 8 | `GET` | `/api/health` | Health check & ChromaDB connection status | [Section 8](#8-get-apihealth) |
| 9 | `POST` | `/api/preview` | Inspect database records by role & field | [Section 9](#9-post-apipreview) |

---

## 1. `POST /create-domain`

**Aliases:** `POST /create-domain`, `POST /api/create-domain`  
**Description:** Verifies whether the requested domain collections exist in ChromaDB. If they do not exist, it creates two isolated collections: `{domain_name}_doc` (for raw document chunks) and `{domain_name}_qa` (for Q&A pairs).

### Request Headers
- `Content-Type: application/json`

### Request Body Schema (`application/json`)
| Field | Type | Required | Default | Description |
| :--- | :---: | :---: | :---: | :--- |
| `domain_name` | `string` | **Yes** | — | Name of the domain/subject (e.g. `"science"`, `"robotics"`). Lowercased automatically. |

#### Example Request Body
```json
{
  "domain_name": "stem_robotics"
}
```

### Responses

#### `200 OK` — Success Response
```json
{
  "status": "success",
  "domain_name": "stem_robotics",
  "created_collections": [
    "stem_robotics_doc",
    "stem_robotics_qa"
  ],
  "existing_collections": []
}
```

#### `400 Bad Request` — Invalid Input Error
```json
{
  "detail": "domain_name cannot be empty"
}
```

#### `500 Internal Server Error` — Database Connection Failure
```json
{
  "detail": "Failed to connect to ChromaDB instance"
}
```

### cURL Command
```bash
curl -X POST "http://localhost:8080/create-domain" \
     -H "Content-Type: application/json" \
     -d '{"domain_name": "stem_robotics"}'
```

---

## 2. `POST /ingestion`

**Aliases:** `POST /ingestion`, `POST /api/ingestion`  
**Description:** Runs Vision OCR on a PDF document (or loads OCR cache), converts text into 768-dimensional embeddings, attaches creation timestamps, and indexes chunks into collection `{tag_name_uuid}_{doc_type}` using update or override modes.

### Request Headers
- `Content-Type: application/json`

### Request Body Schema (`application/json`)
| Field | Type | Required | Default | Description |
| :--- | :---: | :---: | :---: | :--- |
| `tag_name_uuid` | `string` | **Yes** | — | Unique domain/tag UUID string for this document. Exactly 1 UUID is assigned per document ingested. |
| `file_path` | `string` | No | `null` | Absolute or relative path to PDF file. If omitted, uses default textbook. |
| `file_name` | `string` | No | `null` | File name for display and deletion tracking. Defaults to `tag_name_uuid`. |
| `description` | `string` | No | `null` | Description of the document contents. |
| `datetime` | `string` | No | `null` | ISO 8601 creation timestamp (e.g. `"2026-07-15T10:00:00Z"`). Converted to epoch float `created_at_timestamp` for range queries. |
| `mode` | `string` | No | `"update"` | `"update"` (incremental addition) or `"override"` (wipes old file vectors before ingesting). |
| `doc_type` | `string` | No | `"doc"` | Content type targeting: `"doc"` (documents) or `"qa"` (Question & Answer pairs). |
| `volume` | `string` | No | `"1"` | Book volume number (`"1"` or `"2"`). |
| `force` | `boolean` | No | `false` | If `true`, bypasses OCR cache and re-runs Gemini Vision API. |

#### Example Request Body
```json
{
  "file_path": "data-samples/toan-3-tap-1.pdf",
  "file_name": "robotics_handbook.pdf",
  "tag_name_uuid": "stem_robotics",
  "description": "Robotics hardware handbook 2026",
  "datetime": "2026-07-15T10:00:00Z",
  "mode": "update",
  "doc_type": "doc"
}
```

### Responses

#### `200 OK` — Success Response
```json
{
  "status": "success",
  "message": "Successfully ingested into domain collection 'stem_robotics_doc'",
  "tag_name_uuid": "stem_robotics",
  "doc_type": "doc",
  "mode": "update"
}
```

#### `500 Internal Server Error` — Ingestion Failure
```json
{
  "detail": "PDF file not found at data-samples/invalid.pdf"
}
```

### cURL Command
```bash
curl -X POST "http://localhost:8080/ingestion" \
     -H "Content-Type: application/json" \
     -d '{
       "file_path": "data-samples/toan-3-tap-1.pdf",
       "tag_name_uuid": "stem_robotics",
       "datetime": "2026-07-15T10:00:00Z",
       "mode": "update",
       "doc_type": "doc"
     }'
```

---

## 3. `POST /retrieval`

**Aliases:** `POST /retrieval`, `POST /api/retrieval`  
**Description:** Performs multi-domain hybrid vector retrieval across multiple collections (`[tag_uuid_1, tag_uuid_2]`), filtering by content type (`doc` vs `qa`) and date window (`from_date` -> `to_date`). Aggregates candidate chunks, globally ranks them by vector similarity distance (smallest distance = highest match), and returns the top `top_k` results.

### Request Headers
- `Content-Type: application/json`

### Request Body Schema (`application/json`)
| Field | Type | Required | Default | Description |
| :--- | :---: | :---: | :---: | :--- |
| `text` | `string` | **Yes** | — | Search query text string. |
| `tag_name_uuids` | `array[string]` | **Yes** | — | Array of domain/tag UUIDs to search across (e.g. `["robotics", "ai"]`). |
| `type` | `string` | No | `"doc"` | Target content type (`"doc"` or `"qa"`). Routes search to `{uuid}_{type}` collections. |
| `from_date` | `string` | No | `null` | Minimum ISO/Date string (e.g. `"2026-07-01"`). Filters via `$gte` on `created_at_timestamp`. |
| `to_date` | `string` | No | `null` | Maximum ISO/Date string (e.g. `"2026-07-31"`). Filters via `$lte` on `created_at_timestamp`. |
| `top_k` | `integer` | No | `5` | Maximum number of vector matches to return. Global ranking returns the top `top_k` highest-scoring chunks across all queried collections. |

#### Example Request Body
```json
{
  "text": "microcontrollers and sensors",
  "tag_name_uuids": [
    "uuid_1",
    "uuid_2",
    "uuid_3",
    "uuid_4"
  ],
  "type": "doc",
  "from_date": "2026-07-01",
  "to_date": "2026-07-31",
  "top_k": 3
}
```

### Responses

#### `200 OK` — Success Response
```json
{
  "text": "microcontrollers and sensors",
  "tag_name_uuids": [
    "stem_robotics"
  ],
  "type": "doc",
  "total_results": 1,
  "results": [
    {
      "id": "stem_robotics_p15",
      "collection": "stem_robotics_doc",
      "text": "Robotics fundamentals: sensors, actuators, and microcontrollers.",
      "distance": 0.1674,
      "metadata": {
        "volume": "1",
        "physical_page": 15,
        "pdf_page_index": 14,
        "lesson_name": "Hardware Basics",
        "field": "stem_robotics",
        "visibility": "public",
        "file_id": "stem_robotics",
        "file_name": "robotics_handbook.pdf",
        "created_at": "2026-07-15T10:00:00Z",
        "created_at_timestamp": 1784112000.0,
        "doc_type": "doc"
      }
    }
  ]
}
```

#### `500 Internal Server Error` — Query Processing Error
```json
{
  "detail": "Error during collection query"
}
```

### cURL Command
```bash
curl -X POST "http://localhost:8080/retrieval" \
     -H "Content-Type: application/json" \
     -d '{
       "text": "microcontrollers and sensors",
       "tag_name_uuids": ["stem_robotics"],
       "type": "doc",
       "from_date": "2026-07-01",
       "to_date": "2026-07-31"
     }'
```

---

## 4. `GET /api/documents`

**Description:** Retrieves a grouped inventory of all ingested files in a given subject field collection, providing file names, IDs, visibility permissions, owner IDs, and chunk counts.

### Query Parameters
| Parameter | Type | Required | Default | Description |
| :--- | :---: | :---: | :---: | :--- |
| `field` | `string` | No | `"math"` | Subject field collection name suffix (e.g. `"math"`, `"science"`). |

### Responses

#### `200 OK` — Success Response
```json
{
  "field": "math",
  "total_documents": 2,
  "documents": [
    {
      "file_id": "doc_syllabus_2026",
      "file_name": "course_syllabus.pdf",
      "field": "math",
      "visibility": "public",
      "owner_id": "user_admin",
      "allowed_group": "teachers",
      "allowed_user": null,
      "description": "2026 Grade 3 Syllabus",
      "chunk_count": 12
    },
    {
      "file_id": "default_textbook",
      "file_name": "Sách giáo khoa Toán 3 (Tập 1)",
      "field": "math",
      "visibility": "public",
      "owner_id": null,
      "allowed_group": null,
      "allowed_user": null,
      "description": null,
      "chunk_count": 105
    }
  ]
}
```

#### `500 Internal Server Error` — Server Error
```json
{
  "detail": "Failed to connect to database"
}
```

### cURL Command
```bash
curl -X GET "http://localhost:8080/api/documents?field=math"
```

---

### 4b. `GET /api/documents/{file_id}`

**Description:** Retrieves **all text chunks and metadata** belonging to a specific `file_id` for reading, visual inspection, or document comparison, ordered by `physical_page` or `pdf_page_index` ascending.

#### Path & Query Parameters
| Parameter | Location | Type | Required | Default | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `file_id` | Path | `string` | **Yes** | — | Unique identifier of the document. |
| `field` | Query | `string` | No | `"math"` | Subject field collection suffix. |
| `doc_type` | Query | `string` | No | `"doc"` | Content type (`"doc"` or `"qa"`). |

#### Successful Response (`200 OK`):
```json
{
  "file_id": "robotics_handbook",
  "field": "math",
  "doc_type": "doc",
  "total_chunks": 2,
  "chunks": [
    {
      "id": "robotics_handbook_p1",
      "text": "Chapter 1: Microcontrollers and Sensor Basics...",
      "metadata": {
        "volume": "1",
        "physical_page": 1,
        "pdf_page_index": 0,
        "lesson_name": "Hardware Intro",
        "file_id": "robotics_handbook",
        "file_name": "robotics_handbook.pdf",
        "created_at": "2026-07-15T10:00:00Z"
      },
      "physical_page": 1,
      "pdf_page_index": 0
    },
    {
      "id": "robotics_handbook_p2",
      "text": "Chapter 2: Programming Motors...",
      "metadata": {
        "volume": "1",
        "physical_page": 2,
        "pdf_page_index": 1,
        "lesson_name": "Actuators",
        "file_id": "robotics_handbook",
        "file_name": "robotics_handbook.pdf",
        "created_at": "2026-07-15T10:00:00Z"
      },
      "physical_page": 2,
      "pdf_page_index": 1
    }
  ]
}
```

#### cURL Command
```bash
curl -X GET "http://localhost:8080/api/documents/robotics_handbook?field=math&doc_type=doc"
```

---

## 5. `DELETE /api/documents/{file_id}`

**Description:** Deletes all vector chunks associated with a specific `file_id` in the specified subject field collection.

### Parameters
| Parameter | Location | Type | Required | Default | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `file_id` | Path | `string` | **Yes** | — | Unique identifier of the document to delete. |
| `field` | Query | `string` | No | `"math"` | Target subject field collection suffix. |

### Responses

#### `200 OK` — Success Response
```json
{
  "status": "success",
  "message": "Successfully deleted document 'doc_syllabus_2026' from field 'math'"
}
```

#### `500 Internal Server Error` — Deletion Error
```json
{
  "detail": "Failed to delete records for file_id 'doc_syllabus_2026'"
}
```

### cURL Command
```bash
curl -X DELETE "http://localhost:8080/api/documents/doc_syllabus_2026?field=math"
```

---

## 6. `POST /api/search`

**Description:** Standard single-field RAG vector search endpoint. Combines Dense Vector embeddings with BM25 keyword search using Reciprocal Rank Fusion (RRF).

### Request Headers
- `Content-Type: application/json`

### Request Body Schema (`application/json`)
| Field | Type | Required | Default | Description |
| :--- | :---: | :---: | :---: | :--- |
| `query` | `string` | **Yes** | — | Natural language question or search text. |
| `role` | `string` | No | `"student"` | Role of querying user (`"student"`, `"teacher"`, `"admin"`). |
| `field` | `string` | No | `"math"` | Subject field collection suffix. |
| `top_k` | `integer` | No | `5` | Number of results to return. |
| `page_hint` | `integer` | No | `null` | Optional physical page number constraint. |
| `volume_hint` | `string` | No | `null` | Optional book volume constraint (`"1"` or `"2"`). |
| `user_id` | `string` | No | `null` | User ID for ACL matching. |
| `groups` | `array[string]` | No | `null` | User group IDs for ACL matching. |

#### Example Request Body
```json
{
  "query": "bài 1 trang 10 tập 1",
  "role": "student",
  "field": "math",
  "top_k": 3
}
```

### Responses

#### `200 OK` — Success Response
```json
{
  "query": "bài 1 trang 10 tập 1",
  "field": "math",
  "role": "student",
  "results": [
    {
      "id": "math_v1_p10",
      "text": "Bài 1: Ôn tập các số đến 1000...",
      "metadata": {
        "volume": "1",
        "physical_page": 10,
        "lesson_name": "Bài 1",
        "visibility": "public"
      }
    }
  ]
}
```

### cURL Command
```bash
curl -X POST "http://localhost:8080/api/search" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "bài 1 trang 10",
       "role": "student",
       "field": "math",
       "top_k": 3
     }'
```

---

## 7. `POST /api/ingest`

**Description:** Single-field legacy document ingestion endpoint.

### Request Headers
- `Content-Type: application/json`

### Request Body Schema (`application/json`)
| Field | Type | Required | Default | Description |
| :--- | :---: | :---: | :---: | :--- |
| `file_path` | `string` | No | `null` | Path to PDF file. |
| `volume` | `string` | No | `"1"` | Book volume. |
| `field` | `string` | No | `"math"` | Target subject field. |
| `visibility` | `string` | No | `"public"` | Access scope. |
| `force` | `boolean` | No | `false` | Force re-run OCR. |
| `tag_name` | `string` | No | `null` | Maps to `field` if present. |
| `description` | `string` | No | `null` | Description. |
| `file_id` | `string` | No | `null` | Unique file ID. |
| `file_name` | `string` | No | `null` | Display name. |
| `owner_id` | `string` | No | `null` | Owner User ID. |
| `allowed_group` | `string` | No | `null` | Group ACL. |
| `allowed_user` | `string` | No | `null` | User ACL. |
| `mode` | `string` | No | `"keep_cache"` | Overwrite mode (`"keep_cache"` or `"delete_first"`). |

#### Example Request Body
```json
{
  "file_path": "data-samples/test.pdf",
  "field": "math",
  "visibility": "public",
  "force": true,
  "mode": "keep_cache"
}
```

### Responses

#### `200 OK` — Success Response
```json
{
  "status": "success",
  "message": "Ingestion process completed for field 'math' with visibility 'public'"
}
```

### cURL Command
```bash
curl -X POST "http://localhost:8080/api/ingest" \
     -H "Content-Type: application/json" \
     -d '{"field": "math", "force": true}'
```

---

## 8. `GET /api/health`

**Description:** Checks service health and ChromaDB connectivity status.

### Request Headers
- None required

### Responses

#### `200 OK` — Health Status Response
```json
{
  "status": "ok",
  "db_connected": true
}
```

### cURL Command
```bash
curl -X GET "http://localhost:8080/api/health"
```

---

## 9. `POST /api/preview`

**Description:** Developer database inspection tool. Fetches records from a collection filtered by role visibility.

### Request Headers
- `Content-Type: application/json`

### Query Parameters
- `field` *(string, default: `"math"`)*
- `role` *(string, default: `"student"`)*
- `limit` *(integer, default: `20`)*

### Responses

#### `200 OK` — Success Response
```json
{
  "field": "math",
  "role": "student",
  "total_retrieved": 1,
  "records": [
    {
      "id": "math_v1_p1",
      "text": "Bảng nhân 2...",
      "metadata": {
        "volume": "1",
        "physical_page": 1,
        "visibility": "public"
      }
    }
  ]
}
```

### cURL Command
```bash
curl -X POST "http://localhost:8080/api/preview?field=math&role=student&limit=5"
```
