import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from src import config
import os
import time

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
        batch_size = 100
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
    task_type: "RETRIEVAL_DOCUMENT" for indexing, "RETRIEVAL_QUERY" for search queries.
    """
    if config.GEMINI_API_KEY or config.USE_VERTEXAI:
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

def get_vector_db_client():
    """
    Initializes and returns the ChromaDB client.
    Connects via HTTP HttpClient if host is configured, otherwise falls back to local PersistentClient.
    """
    if config.CHROMA_HOST:
        print(f"Connecting to remote ChromaDB server at http://{config.CHROMA_HOST}:{config.CHROMA_PORT}")
        return chromadb.HttpClient(host=config.CHROMA_HOST, port=config.CHROMA_PORT)
    else:
        print(f"Connecting to local persistent ChromaDB at {config.DB_DIR}")
        return chromadb.PersistentClient(path=str(config.DB_DIR))

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

