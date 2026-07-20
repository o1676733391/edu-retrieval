# Workspace Agent Guidelines & Rules

This document outlines the operational rules, behavior constraints, and project standards for all AI agents working in this repository.

> [!IMPORTANT]
> All AI agents working on this project must strictly read and adhere to this document.

---

## 1. Documentation Integrity (Critical Rule)
- **Architectural Alignment:** Whenever you modify any core workflows, retrieval strategies, database client configurations, or agent orchestrations, you **MUST** update the architectural design document [ai_core_architecture.md](../ai_core_architecture.md) accordingly. The design documentation must always mirror the exact implementation in the codebase.
- **Language Standards:**
  - **Technical Documentation & Code:** All project-scoped technical documentation (e.g., `ai_core_architecture.md`, `SKILL.md`, `AGENTS.md`, and docstrings/comments) must be written in **English**.
  - **End-User Communication:** All chatbot responses, teacher prompts, and user-facing CLI inputs/outputs must be written in **Vietnamese**.

---

## 2. Ingestion & PDF Processing Guidelines
- **Vision OCR:** PDF textbooks under `data-samples/` are scanned image-only PDFs. Use a multimodal vision model (e.g., `gemini-1.5-flash`) for OCR parsing. Do not use plain text PDF extractors (like `PyPDF`).
- **OCR Format:** Ensure the vision OCR outputs strictly structured JSON content containing:
  ```json
  {
    "physical_page": int | null,
    "lesson_name": "string",
    "text": "string"
  }
  ```
- **Caching:** Save extracted OCR data into `data/processed_book_data.json` to prevent duplicate API tokens and control costs. Only re-run OCR if the `--force` flag is supplied.

---

## 3. Retrieval & Hybrid Search Guidelines
- **Always Query DB First:** For any query about exercises, mathematics, or textbook contents, you must invoke `book_knowledge_search` via the `search_textbook` tool. Do not rely on LLM general knowledge for textbook contents.
- **Hint Extraction:** Extract physical page (e.g., `trang 15`, `tr. 24`) and volume (e.g., `tập 1`, `tập 2`) hints from the user query using regular expressions.
- **Metadata Window Filter:** Restrict searches to the target page and its immediate neighbors `[page - 1, page, page + 1]` if a page hint is present.
- **RRF Fusion:** Run hybrid search combining Dense Embeddings (using the configured provider's embedding model) and Keyword BM25 search. Fuse rankings using Reciprocal Rank Fusion (RRF).

---

## 4. Teacher Agent Simulation & Response Format
- **Tone:** Encouraging, step-by-step, pedagogical tone matching a primary school teacher, tailored for grade 3 students and parents.
- **Strict Response Layout:**
  ```markdown
  [Friendly step-by-step mathematical reasoning explanation in Vietnamese]
  
  ---
  
  📖 **Reference Source:**
  - **Lesson:** [Exact lesson name from search metadata]
  - **Location:** Page [Physical page number], Grade 3 Math Textbook (Volume [1 or 2])
  ```
- **No Hallucinations:** Never invent or guess page numbers/lessons. If missing, explicitly print that the source is from the textbook but page metadata is missing.

---

## 5. Verification & Code Quality
- **Unit Tests:** Always run unit tests in `tests/test_agent.py` before finalizing changes. Ensure any newly added code paths have corresponding tests.
- **Dependencies:** Keep `requirements.txt` updated with any newly introduced libraries.
