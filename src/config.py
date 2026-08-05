import os
from pathlib import Path
# Load environment variables from .env file
if Path(".env").exists():
    from dotenv import load_dotenv
    load_dotenv(override=True)

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_SAMPLES_DIR = BASE_DIR / "data-samples"
DATA_DIR = BASE_DIR / "data"
DB_DIR = DATA_DIR / "chroma_db"

# Ensure data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

# Vector Database Selection
VECTOR_DB_BACKEND = os.getenv("VECTOR_DB_BACKEND", "chromadb").lower()

# ChromaDB Remote server configs
CHROMA_HOST = os.getenv("CHROMA_HOST", "")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))

# Qdrant Remote server configs
QDRANT_HOST = os.getenv("QDRANT_HOST", "")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# Model configs
EMBEDDING_MODEL_NAME = "text-embedding-004"  # Default Gemini/Vertex AI embedding model

# Local Embedding configs
USE_LOCAL_EMBEDDING = os.getenv("USE_LOCAL_EMBEDDING", "false").lower() == "true"
LOCAL_EMBEDDING_MODEL_NAME = os.getenv("LOCAL_EMBEDDING_MODEL_NAME", "keepitreal/vietnamese-sbert")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Vertex AI configs
USE_VERTEXAI = os.getenv("USE_VERTEXAI", "false").lower() == "true"
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# Dynamically set GOOGLE_APPLICATION_CREDENTIALS if not already specified in environment
if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ or not os.environ["GOOGLE_APPLICATION_CREDENTIALS"]:
    GCP_KEY_FILE = DATA_DIR / "gcp-key.json"
    if GCP_KEY_FILE.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(GCP_KEY_FILE)

# Default collection name for Vector Database
COLLECTION_NAME = "toan_3_curriculum"

# Backend webhook settings (report ingestion status back to rag-assistant-be)
BE_API_BASE_URL = os.getenv("BE_API_BASE_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Host used to retry downloading a file_path when it points at localhost/127.0.0.1
# and the connection is refused (container "localhost" != host machine's localhost).
CDN_FALLBACK_HOST = os.getenv("CDN_FALLBACK_HOST", "host.docker.internal")

# RBAC Settings
ROLE_STUDENT = "student"
ROLE_TEACHER = "teacher"
ROLE_ADMIN = "admin"

ROLE_VISIBILITY_MAPPING = {
    ROLE_STUDENT: ["public"],
    ROLE_TEACHER: ["public", "teacher_only"],
    ROLE_ADMIN: ["public", "teacher_only", "admin_only"]
}

