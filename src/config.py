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
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", os.getenv("CLAUDE_API_KEY", ""))
CLAUDE_API_KEY = ANTHROPIC_API_KEY

# Default LLM Provider & Model Tier settings
DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "gemini").lower()
DEFAULT_LLM_MODEL_TIER = os.getenv("DEFAULT_LLM_MODEL_TIER", "med").lower()

# Multi-Provider Model Matrix with 3 tiers (High, Med, Low)
LLM_PROVIDER_MODELS = {
    "gemini": {
        "display_name": "Google Gemini (Studio / Vertex AI)",
        "high": "gemini-2.5-pro",
        "med": "gemini-2.5-flash",
        "low": "gemini-2.5-flash-lite",
        "pricing": {
            "gemini-2.5-pro": (1.25, 5.00),
            "gemini-2.5-flash": (0.075, 0.30),
            "gemini-2.5-flash-lite": (0.0375, 0.15)
        }
    },
    "openai": {
        "display_name": "OpenAI API",
        "high": "gpt-4o",
        "med": "gpt-4o-mini",
        "low": "gpt-3.5-turbo",
        "pricing": {
            "gpt-4o": (2.50, 10.00),
            "gpt-4o-mini": (0.15, 0.60),
            "gpt-3.5-turbo": (0.50, 1.50)
        }
    },
    "claude": {
        "display_name": "Anthropic Claude",
        "high": "claude-3-5-sonnet-20241022",
        "med": "claude-3-5-haiku-20241022",
        "low": "claude-3-haiku-20240307",
        "pricing": {
            "claude-3-5-sonnet-20241022": (3.00, 15.00),
            "claude-3-5-haiku-20241022": (0.80, 4.00),
            "claude-3-haiku-20240307": (0.25, 1.25)
        }
    }
}

PROVIDER_ALIASES = {
    "gemini": "gemini",
    "google": "gemini",
    "studio": "gemini",
    "vertex": "gemini",
    "vertexai": "gemini",
    "openai": "openai",
    "openaiapi": "openai",
    "chatgpt": "openai",
    "gpt": "openai",
    "claude": "claude",
    "anthropic": "claude"
}

TIER_ALIASES = {
    "high": "high",
    "pro": "high",
    "advanced": "high",
    "deep": "high",
    "med": "med",
    "medium": "med",
    "normal": "med",
    "standard": "med",
    "flash": "med",
    "low": "low",
    "lite": "low",
    "fast": "low",
    "basic": "low",
    "cheap": "low"
}

def resolve_provider(provider_str: str | None = None) -> str:
    """Normalize provider name string to canonical 'gemini', 'openai', or 'claude'."""
    if not provider_str:
        return DEFAULT_LLM_PROVIDER
    p = provider_str.strip().lower()
    return PROVIDER_ALIASES.get(p, DEFAULT_LLM_PROVIDER)

def resolve_model(provider_str: str | None = None, tier_or_model: str | None = None) -> str:
    """Resolve concrete model name given provider and tier/model alias."""
    provider = resolve_provider(provider_str)
    prov_config = LLM_PROVIDER_MODELS.get(provider, LLM_PROVIDER_MODELS["gemini"])
    
    if not tier_or_model:
        return prov_config.get(DEFAULT_LLM_MODEL_TIER, prov_config["med"])
    
    target = tier_or_model.strip()
    tier_normalized = TIER_ALIASES.get(target.lower())
    if tier_normalized and tier_normalized in prov_config:
        return prov_config[tier_normalized]
    
    # If a specific model string was provided directly, return it
    return target

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

