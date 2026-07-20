import sys
from pathlib import Path

# Add src to python path if needed
sys.path.append(str(Path(__file__).parent.parent))

from src.vector_store.client import get_vector_db_client, get_embedding_function, get_or_create_collection
from src.vector_store.search import book_knowledge_search

def inspect_db():
    print("=" * 60)
    print("         INSPECTING CHROMA VECTOR DATABASE")
    print("=" * 60)
    
    try:
        client = get_vector_db_client()
        embedding_fn = get_embedding_function()
        collection = get_or_create_collection(client, embedding_fn)
        
        # 1. Count
        count = collection.count()
        print(f"Total documents (pages) in Vector DB: {count}")
        
        if count == 0:
            print("❌ The database is empty! Please run ingestion first using: python run_ingest.py")
            return
            
        # 2. Peek at a few IDs
        print("\nPeeking at first 5 documents:")
        peek = collection.peek(limit=5)
        for idx, doc_id in enumerate(peek["ids"]):
            metadata = peek["metadatas"][idx]
            print(f"  - ID: {doc_id}")
            print(f"    Volume: {metadata.get('volume')}, Page: {metadata.get('physical_page')}")
            print(f"    Lesson: {metadata.get('lesson_name')}")
            print(f"    Snippet: {peek['documents'][idx][:120]}...")
            print("-" * 40)
            
        # 3. Test a quick hybrid search query
        test_query = "bài 1 trang 15"
        print(f"\nTesting hybrid search query: '{test_query}'")
        results = book_knowledge_search(test_query, top_k=2)
        
        print(f"Found {len(results)} matches:")
        for res in results:
            print(f"  - ID: {res['id']}")
            print(f"    Volume: {res['metadata'].get('volume')}, Page: {res['metadata'].get('physical_page')}")
            print(f"    Lesson: {res['metadata'].get('lesson_name')}")
            print(f"    Snippet: {res['text'][:150]}...")
            print("-" * 40)
            
    except Exception as e:
        print(f"❌ Error during database inspection: {e}")

if __name__ == "__main__":
    inspect_db()
