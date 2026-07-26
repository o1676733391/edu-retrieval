from src.vector_store.base import BaseVectorStore

class ChromaVectorStore(BaseVectorStore):
    """
    ChromaDB implementation of the BaseVectorStore.
    """
    
    def __init__(self, collection):
        self.collection = collection
        
    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict]):
        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        
    def query(self, query_text: str, top_k: int, where: dict = None) -> dict:
        # Request top_k * 2 to match the RRF hybrid dense retrieval count
        res = self.collection.query(
            query_texts=[query_text],
            n_results=top_k * 2,
            where=where
        )
        return res
        
    def get_all(self, where: dict = None) -> dict:
        if where:
            return self.collection.get(where=where, include=["documents", "metadatas"])
        else:
            return self.collection.get(include=["documents", "metadatas"])
            
    def get_by_ids(self, ids: list[str]) -> list[str]:
        res = self.collection.get(ids=ids, include=[])
        return res.get("ids", []) if res else []
        
    def delete(self, ids: list[str] = None, where: dict = None):
        if ids is not None and where is not None:
            self.collection.delete(ids=ids, where=where)
        elif ids is not None:
            self.collection.delete(ids=ids)
        elif where is not None:
            self.collection.delete(where=where)
