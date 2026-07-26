import uuid
from qdrant_client import QdrantClient
from qdrant_client.http import models
from src.vector_store.base import BaseVectorStore

def convert_chroma_filter_to_qdrant(chroma_filter: dict) -> models.Filter | None:
    """
    Recursively converts a ChromaDB metadata filter query to Qdrant's Filter syntax.
    """
    if not chroma_filter:
        return None

    must_conditions = []
    should_conditions = []
    must_not_conditions = []

    if "$and" in chroma_filter:
        for cond in chroma_filter["$and"]:
            q_filter = convert_chroma_filter_to_qdrant(cond)
            if q_filter:
                must_conditions.append(q_filter)
        return models.Filter(must=must_conditions)

    if "$or" in chroma_filter:
        for cond in chroma_filter["$or"]:
            q_filter = convert_chroma_filter_to_qdrant(cond)
            if q_filter:
                should_conditions.append(q_filter)
        return models.Filter(should=should_conditions)

    for key, val in chroma_filter.items():
        if key.startswith("$"):
            continue

        if isinstance(val, dict):
            for op, inner_val in val.items():
                if op == "$eq":
                    must_conditions.append(models.FieldCondition(key=key, match=models.MatchValue(value=inner_val)))
                elif op == "$ne":
                    must_not_conditions.append(models.FieldCondition(key=key, match=models.MatchValue(value=inner_val)))
                elif op == "$in":
                    must_conditions.append(models.FieldCondition(key=key, match=models.MatchAny(any=list(inner_val))))
                elif op == "$nin":
                    must_not_conditions.append(models.FieldCondition(key=key, match=models.MatchAny(any=list(inner_val))))
        else:
            must_conditions.append(models.FieldCondition(key=key, match=models.MatchValue(value=val)))

    if not must_conditions and not should_conditions and not must_not_conditions:
        return None

    return models.Filter(
        must=must_conditions if must_conditions else None,
        should=should_conditions if should_conditions else None,
        must_not=must_not_conditions if must_not_conditions else None
    )


class QdrantVectorStore(BaseVectorStore):
    """
    Qdrant implementation of BaseVectorStore.
    """
    
    def __init__(self, client: QdrantClient, collection_name: str, embedding_function):
        self.client = client
        self.collection_name = collection_name
        self.embedding_function = embedding_function

    def _ensure_collection(self):
        if not self.client.collection_exists(self.collection_name):
            # Fetch embedding dimension dynamically
            dummy_emb = self.embedding_function(["dummy"])[0]
            vector_size = len(dummy_emb)
            
            print(f"Creating Qdrant collection '{self.collection_name}' with vector size {vector_size}...")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE)
            )

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict]):
        self._ensure_collection()
        
        # In Qdrant, we must compute raw embeddings since the client doesn't do it automatically
        vectors = self.embedding_function(documents)
        
        points = []
        for doc_id, text, metadata, vector in zip(ids, documents, metadatas, vectors):
            # Inject page text content and original string ID into the payload
            payload = {**metadata, "page_content": text, "_original_id": doc_id}
            
            # Map string ID to deterministic UUIDv5
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_id))
            
            points.append(models.PointStruct(
                id=point_id,
                vector=vector,
                payload=payload
            ))
            
        self.client.upsert(collection_name=self.collection_name, points=points)

    def query(self, query_text: str, top_k: int, where: dict = None) -> dict:
        self._ensure_collection()
        
        query_vector = self.embedding_function([query_text])[0]
        q_filter = convert_chroma_filter_to_qdrant(where)
        
        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=q_filter,
            limit=top_k * 2,  # Request top_k * 2 to match the RRF hybrid dense retrieval count
            with_payload=True
        )
        
        ids = []
        documents = []
        metadatas = []
        distances = []
        
        for hit in res.points:
            # Map Qdrant cosine similarity (score) back to cosine distance
            # cosine similarity = 1 - cosine distance
            distance = 1.0 - hit.score
            
            payload = hit.payload or {}
            text = payload.pop("page_content", "")
            doc_id = payload.pop("_original_id", hit.id)
            
            ids.append(doc_id)
            documents.append(text)
            metadatas.append(payload)
            distances.append(distance)
            
        return {
            "ids": [ids],
            "documents": [documents],
            "metadatas": [metadatas],
            "distances": [distances]
        }

    def get_all(self, where: dict = None) -> dict:
        self._ensure_collection()
        q_filter = convert_chroma_filter_to_qdrant(where)
        
        offset = None
        ids = []
        documents = []
        metadatas = []
        
        while True:
            res, next_page = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=q_filter,
                limit=100,
                with_payload=True,
                with_vectors=False,
                offset=offset
            )
            
            for pt in res:
                payload = pt.payload or {}
                text = payload.pop("page_content", "")
                doc_id = payload.pop("_original_id", pt.id)
                
                ids.append(doc_id)
                documents.append(text)
                metadatas.append(payload)
                
            if not next_page:
                break
            offset = next_page
            
        return {
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas
        }

    def get_by_ids(self, ids: list[str]) -> list[str]:
        self._ensure_collection()
        
        # Map string IDs to UUIDs to look up in Qdrant
        uuid_to_doc_id = {str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_id)): doc_id for doc_id in ids}
        
        res = self.client.retrieve(
            collection_name=self.collection_name,
            ids=list(uuid_to_doc_id.keys()),
            with_payload=False,
            with_vectors=False
        )
        
        return [uuid_to_doc_id[pt.id] for pt in res if pt.id in uuid_to_doc_id]

    def delete(self, ids: list[str] = None, where: dict = None):
        self._ensure_collection()
        
        if ids is not None and where is not None:
            uuids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_id)) for doc_id in ids]
            q_filter = convert_chroma_filter_to_qdrant(where)
            combined_filter = models.Filter(
                must=[
                    models.HasIdCondition(has_id=uuids),
                    q_filter
                ]
            )
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(filter=combined_filter)
            )
        elif ids is not None:
            uuids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_id)) for doc_id in ids]
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(points=uuids)
            )
        elif where is not None:
            q_filter = convert_chroma_filter_to_qdrant(where)
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(filter=q_filter)
            )
