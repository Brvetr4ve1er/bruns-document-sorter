import os
import json

class VectorSearchEngine:
    def __init__(self, db_dir: str):
        import chromadb
        self.db_dir = db_dir
        os.makedirs(self.db_dir, exist_ok=True)
        # Initialize local ChromaDB client
        self.client = chromadb.PersistentClient(path=self.db_dir)
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )

    def embed_document(self, doc_id: int, module: str, raw_text: str, extracted_data: dict):
        """Index a document's raw text and structured data for semantic search."""
        
        combined_text = f"Module: {module}\n"
        combined_text += f"Structured Data: {json.dumps(extracted_data)}\n"
        combined_text += f"Raw Text: {raw_text[:2000]}"
        
        metadata = {
            "document_id": doc_id,
            "module": module,
            "doc_type": extracted_data.get("document_type", "UNKNOWN")
        }
        
        self.collection.upsert(
            documents=[combined_text],
            metadatas=[metadata],
            ids=[f"doc_{doc_id}"]
        )
        
    def search(self, query: str, module: str = None, n_results: int = 5):
        """Perform semantic search against the indexed documents."""
        where_filter = {"module": module} if module else None
        
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter
        )
        
        parsed_results = []
        if results and results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                parsed_results.append({
                    "document_id": results['metadatas'][0][i].get("document_id"),
                    "module": results['metadatas'][0][i].get("module"),
                    "doc_type": results['metadatas'][0][i].get("doc_type"),
                    "distance": results['distances'][0][i],
                    "id": results['ids'][0][i]
                })
                
        return parsed_results
