# edu-retrieval

FastAPI & ChromaDB Multi-Domain RAG Vector Retrieval Engine for Educational Textbooks.

## 🚀 Features
- **Domain Management (`/create-domain`):** Dynamically provisions `{domain}_doc` and `{domain}_qa` isolated vector collections.
- **Single-UUID Ingestion (`/ingestion`):** Ingests PDF/QA documents with Vision OCR, epoch timestamping, and `update` / `override` modes.
- **Multi-Domain & Date-Filtered Retrieval (`/retrieval`):** Searches across multiple domain UUIDs with content type targeting (`doc` vs `qa`) and numeric date-range filters (`from_date` to `to_date`).
- **Interactive Streamlit Web UI:** Features an AI Chatbot teacher area with Gemini reasoning, source citations, and Visual Chunk Separated Cards.

## 📖 API Documentation
For full OpenAPI specifications and cURL request/response examples, see [api_report.md](api_report.md).
