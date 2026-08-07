---
name: Math Textbook Assistant
description: Skill for running, maintaining, and extending the Grade 3 Math Textbook Assistant project, including PDF Multimodal OCR parsing, ChromaDB vector search indexing, and teacher-agent orchestration.
---

# Grade 3 Math Textbook Assistant Skill

This document defines the architecture, guidelines, and rules of engagement for AI Agents working on, extending, or maintaining this project.

> [!IMPORTANT]
> **Documentation Rule:** If any changes are made to the workflow or system architecture, the agent MUST update the architectural design document [ai_core_architecture.md](../../../ai_core_architecture.md) accordingly to ensure alignment between design and source code.

---

## 1. Project Structure

The codebase is organized as follows:
- **[data-samples/](../../../data-samples):** Contains the original scanned PDF textbooks (Volume 1 and Volume 2). These PDFs consist of scanned page images.
- **[data/](../../../data):** Contains the persistent local Chroma Vector Database (`chroma_db`) and the OCR cache file `processed_book_data.json`.
- **[src/config.py](../../../src/config.py):** System configuration loader, including paths and API keys from the `.env` file.
- **[src/pipeline/pdf_parser.py](../../../src/pipeline/pdf_parser.py):** Renders PDF pages to PNG images in memory and runs concurrent Multimodal OCR via the Gemini API.
- **[src/pipeline/ingest.py](../../../src/pipeline/ingest.py):** Ingestion orchestrator: reads PDFs -> calls Gemini OCR -> caches results to JSON -> indexes into Chroma Vector DB.
- **[src/vector_store/client.py](../../../src/vector_store/client.py):** Initializes ChromaDB client and configures Gemini/OpenAI embedding functions.
- **[src/vector_store/search.py](../../../src/vector_store/search.py):** Extracts page/volume hints from raw user queries and performs hybrid search (Vector Dense + BM25 Okapi + Metadata Window Filtering).
- **[src/agent/prompts.py](../../../src/agent/prompts.py):** Contains the system prompt representing the elementary math teacher.
- **[src/agent/orchestrator.py](../../../src/agent/orchestrator.py):** Agent controller handling Gemini/OpenAI model API calls and automatic tool calling bindings.
- **[tests/test_agent.py](../../../tests/test_agent.py):** Unit tests verifying query hint parsing, Vietnamese tokenization, and configuration loading.

---

## 2. Ingestion & PDF Processing Guidelines

Because the textbooks in `data-samples` are scanned images with no embedded text, OCR is required.
- **Extraction Rules:**
  1. Use a multimodal vision model (e.g., `gemini-2.5-flash`) to process rendered page images.
  2. The OCR API response must be strictly structured in JSON as:
     ```json
     {
       "physical_page": int | null,
       "text": "string"
     }
     ```
  3. Implement page interpolation in `pdf_parser.py` to fill in physical page numbers that are missing or occluded in the scan.
  4. Automatic topic/lesson extraction is disabled. Users supply a custom topic range list during ingestion (`topics` parameter in `POST /api/ingest` or `POST /api/ingestion`):
     ```json
     [
       { "title": "Bài 1. Ôn tập các số đến 100 000", "from": 6, "to": 8 },
       { "title": "Bài 2. Ôn tập các phép tính trong phạm vi 100 000", "from": 9, "to": 11 }
     ]
     ```
     Page chunks are mapped to `lesson_name` based on physical page numbers falling within `[from, to]` bounds.
- **Caching Rules:** To save token costs during development, the parsed OCR results must be saved to `data/processed_<field>_data.json`. Only re-run the Multimodal OCR from scratch when the `--force` flag is specified.

---

## 3. Retrieval & Search Guidelines

For every textbook query, the Agent must use the `search_textbook` tool (which invokes `book_knowledge_search` from `search.py`).

- **Hint Extraction:**
  - Parse the query using regular expressions to find physical page numbers (e.g., *"trang 15"*, *"tr. 24"*, *"p. 33"*) or book volumes (e.g., *"tập 1"*, *"tập 2"*).
- **Metadata Filtering:**
  - If a `page_hint` is detected, filter ChromaDB queries using a window filter `[page_hint - 1, page_hint, page_hint + 1]` to ensure contiguous math exercises are captured.
- **Hybrid Search:**
  - Combine Vector similarity search (for semantic intent) with BM25 Okapi keyword search (for exact matches like math problem IDs).
  - Merge the search rankings using Reciprocal Rank Fusion (RRF).

---

## 4. Response Formatting Constraints

The Agent must simulate a primary school teacher and strictly format the output:

1. **Teacher Tone:** Warm, friendly, encouraging, and patient. Explanations must be step-by-step (pedagogical explanation), breaking down calculations for elementary school students or parents.
2. **Divider:** Insert a single markdown horizontal rule `---` on its own line between the explanation and the source citation.
3. **Mandatory Source Citation:** Every response must end with the following block structure:
   ```text
   📖 **Reference Source:**
   - **Lesson:** [Exact lesson name from tool metadata]
   - **Location:** Page [Exact physical page number from tool metadata], Grade 3 Math Textbook (Volume [1 or 2])
   ```
4. **No Hallucination:** If the search result has no physical page number or lesson metadata, explicitly state that it is from the textbook but page metadata is missing. Do not invent page numbers.
5. **Language:** The output text to the user must always be in **Vietnamese**.

---

## 5. Setup, Run & Test Commands

- **Install Dependencies:**
  ```powershell
  pip install -r requirements.txt
  ```
- **Run Book Ingestion (Build Vector DB):**
  ```powershell
  python run_ingest.py
  ```
- **Force Re-run Multimodal OCR:**
  ```powershell
  python run_ingest.py --force
  ```
- **Run Interactive Chatbot:**
  ```powershell
  python chat.py
  ```
- **Run Unit Tests:**
  ```powershell
  python -m unittest tests/test_agent.py
  ```

---

## 6. Docker Compose Setup

This project supports running in containers with a standalone ChromaDB instance.

- **Build Services:**
  ```powershell
  docker compose build
  ```
- **Run Ingestion in Container:**
  ```powershell
  docker compose run --rm math-assistant python run_ingest.py
  ```
- **Run Interactive Chat inside Container:**
  ```powershell
  docker compose run math-assistant
  ```
- **Run Tests inside Container:**
  ```powershell
  docker compose run --rm math-assistant python -m unittest tests/test_agent.py
  ```
