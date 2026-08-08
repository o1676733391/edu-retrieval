import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from src import config
import os
import time
import threading

# Cached singletons: clients and embedding models are expensive to build and are
# safe to share across requests, so they are created once per process.
_clients_lock = threading.Lock()
_qdrant_clients = {}
_chroma_client = None
_embedding_functions = {}

class GeminiEmbeddingFunction(EmbeddingFunction):
    def __init__(self, api_key: str, model_name: str = "models/text-embedding-004", task_type: str = "RETRIEVAL_DOCUMENT"):
        from google import genai
        from google.genai import types
        from src import config
        
        self.model_name = model_name
        self.types = types
        self.task_type = task_type
        
        if config.USE_VERTEXAI:
            self.client = genai.Client(
                vertexai=True,
                project=config.GOOGLE_CLOUD_PROJECT,
                location=config.GOOGLE_CLOUD_LOCATION
            )
        else:
            self.client = genai.Client(api_key=api_key)

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        batch_size = 30
        for i in range(0, len(input), batch_size):
            batch = input[i:i+batch_size]
            
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    response = self.client.models.embed_content(
                        model=self.model_name,
                        contents=batch,
                        config=self.types.EmbedContentConfig(
                            task_type=self.task_type
                        )
                    )
                    embeddings.extend([emb.values for emb in response.embeddings])
                    break  # Success
                except Exception as e:
                    error_msg = str(e)
                    print(f"[Warning] Embedding retry {attempt + 1}/{max_attempts}: {error_msg}")
                    if attempt == max_attempts - 1:
                        raise e
                    
                    if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                        sleep_time = 10 * (attempt + 1)
                        print(f"Embedding rate limit hit. Sleeping for {sleep_time} seconds before retrying...")
                    else:
                        sleep_time = 2 ** attempt
                    time.sleep(sleep_time)
            
            # Rate limiting safety sleep
            time.sleep(1.0)

            
        return embeddings



class LocalEmbeddingFunction(EmbeddingFunction):
    def __init__(self, model_name: str = "keepitreal/vietnamese-sbert"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError("Please install sentence-transformers: pip install sentence-transformers")
        
        from src import config
        cache_dir = config.DATA_DIR / "models"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[LocalEmbedding] Loading local model '{model_name}' (cache: {cache_dir})...")
        self.model = SentenceTransformer(model_name, cache_folder=str(cache_dir))
        self.model_name = model_name

    def __call__(self, input: Documents) -> Embeddings:
        # SentenceTransformers encode returns a numpy array, convert to list of floats
        embeddings_numpy = self.model.encode(input, show_progress_bar=False)
        return embeddings_numpy.tolist()

class OpenAIEmbeddingFunction(EmbeddingFunction):
    def __init__(self, api_key: str, model_name: str = "text-embedding-3-small"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        batch_size = 50
        for i in range(0, len(input), batch_size):
            batch = input[i:i+batch_size]
            response = self.client.embeddings.create(
                input=batch,
                model=self.model_name
            )
            embeddings.extend([data.embedding for data in response.data])
        return embeddings

def get_embedding_function(task_type: str = "RETRIEVAL_DOCUMENT") -> EmbeddingFunction:
    """
    Returns the appropriate embedding function based on available API keys.
    Instances are cached per task_type so models/clients are only built once.
    task_type: "RETRIEVAL_DOCUMENT" for indexing, "RETRIEVAL_QUERY" for search queries.
    """
    cached = _embedding_functions.get(task_type)
    if cached is not None:
        return cached
    with _clients_lock:
        cached = _embedding_functions.get(task_type)
        if cached is None:
            cached = _build_embedding_function(task_type)
            _embedding_functions[task_type] = cached
        return cached

def _build_embedding_function(task_type: str) -> EmbeddingFunction:
    if config.USE_LOCAL_EMBEDDING:
        print(f"Using Local Embedding Model: {config.LOCAL_EMBEDDING_MODEL_NAME} ({task_type}).")
        return LocalEmbeddingFunction(model_name=config.LOCAL_EMBEDDING_MODEL_NAME)
    elif config.GEMINI_API_KEY or config.USE_VERTEXAI:
        print(f"Using Gemini API for embeddings ({task_type}).")
        model = config.EMBEDDING_MODEL_NAME
        # Ensure the model name starts with models/ ONLY if NOT using Vertex AI
        if not config.USE_VERTEXAI:
            if not model.startswith("models/"):
                model = f"models/{model}"
        else:
            # For Vertex AI, ensure there is NO "models/" prefix
            if model.startswith("models/"):
                model = model.replace("models/", "", 1)
        return GeminiEmbeddingFunction(api_key=config.GEMINI_API_KEY, model_name=model, task_type=task_type)
    elif config.OPENAI_API_KEY:
        print("Using OpenAI API for embeddings.")
        return OpenAIEmbeddingFunction(api_key=config.OPENAI_API_KEY)
    else:
        # Fallback/Error: We require an API key for vector search embeddings
        raise ValueError("Error: Neither GEMINI_API_KEY nor OPENAI_API_KEY nor Vertex AI is configured in your environment.")

def get_qdrant_client():
    """
    Returns a process-wide cached QdrantClient.
    The underlying client keeps its own HTTP connection pool, so it is meant to be
    created once and reused instead of per API call.
    """
    if config.QDRANT_HOST:
        key = ("remote", config.QDRANT_HOST, config.QDRANT_PORT)
    else:
        key = ("local", str(config.DATA_DIR / "qdrant_db"))

    cached = _qdrant_clients.get(key)
    if cached is not None:
        return cached

    with _clients_lock:
        cached = _qdrant_clients.get(key)
        if cached is None:
            from qdrant_client import QdrantClient
            if key[0] == "remote":
                print(f"Connecting to remote Qdrant server at http://{config.QDRANT_HOST}:{config.QDRANT_PORT}")
                cached = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
            else:
                print(f"Connecting to local persistent Qdrant at {key[1]}")
                cached = QdrantClient(path=key[1])
            _qdrant_clients[key] = cached
        return cached

def get_vector_db_client():
    """
    Initializes and returns the ChromaDB client (cached per process).
    Connects via HTTP HttpClient if host is configured, otherwise falls back to local PersistentClient.
    """
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client

    with _clients_lock:
        if _chroma_client is not None:
            return _chroma_client
        print(f"[VectorDB] VECTOR_DB_BACKEND={config.VECTOR_DB_BACKEND}")
        if config.VECTOR_DB_BACKEND != "chromadb":
            print(f"[VectorDB] Warning: backend '{config.VECTOR_DB_BACKEND}' is not implemented, falling back to chromadb.")
        if config.CHROMA_HOST:
            print(f"Connecting to remote ChromaDB server at http://{config.CHROMA_HOST}:{config.CHROMA_PORT}")
            _chroma_client = chromadb.HttpClient(host=config.CHROMA_HOST, port=config.CHROMA_PORT)
        else:
            print(f"Connecting to local persistent ChromaDB at {config.DB_DIR}")
            _chroma_client = chromadb.PersistentClient(path=str(config.DB_DIR))
        return _chroma_client

def get_or_create_collection(client, embedding_function, collection_name: str = None):
    """
    Retrieves or creates the target vector collection.
    """
    name = collection_name or config.COLLECTION_NAME
    return client.get_or_create_collection(
        name=name,
        embedding_function=embedding_function,
        metadata={"hnsw:space": "cosine"}  # use cosine similarity
    )

def get_vector_store(field: str, collection_name_override: str = None):
    """
    Dynamically returns the configured BaseVectorStore backend (ChromaDB or Qdrant).
    """
    from src.vector_store.base import BaseVectorStore
    from src.vector_store.chroma import ChromaVectorStore
    from src.vector_store.qdrant import QdrantVectorStore

    col_name = collection_name_override if collection_name_override else f"{config.COLLECTION_NAME}_{field}"
    embedding_fn = get_embedding_function()

    if config.VECTOR_DB_BACKEND == "qdrant":
        return QdrantVectorStore(get_qdrant_client(), col_name, embedding_fn)
    else:
        # Default backend: ChromaDB
        client = get_vector_db_client()
        collection = get_or_create_collection(client, embedding_fn, collection_name=col_name)
        return ChromaVectorStore(collection)

