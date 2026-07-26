from abc import ABC, abstractmethod

class BaseVectorStore(ABC):
    """
    Abstract base class for Vector Database Backends (ChromaDB / Qdrant).
    Defines common operations needed by the ingestion and retrieval processes.
    """
    
    @abstractmethod
    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict]):
        """
        Upserts (adds or updates) documents and metadatas with corresponding IDs.
        """
        pass
        
    @abstractmethod
    def query(self, query_text: str, top_k: int, where: dict = None) -> dict:
        """
        Performs a dense vector search on the collection.
        Returns a dict matching Chroma's structure:
        {"ids": [list_of_ids], "documents": [list_of_texts], "metadatas": [list_of_metadatas], "distances": [list_of_floats]}
        """
        pass
        
    @abstractmethod
    def get_all(self, where: dict = None) -> dict:
        """
        Retrieves all documents matching the optional filter.
        Returns a dict matching Chroma's get structure:
        {"ids": list_of_ids, "documents": list_of_texts, "metadatas": list_of_metadatas}
        """
        pass
        
    @abstractmethod
    def get_by_ids(self, ids: list[str]) -> list[str]:
        """
        Retrieves matching IDs that exist in the collection out of the requested list.
        """
        pass
        
    @abstractmethod
    def delete(self, ids: list[str] = None, where: dict = None):
        """
        Deletes documents matching the specified IDs or metadata filter.
        """
        pass
