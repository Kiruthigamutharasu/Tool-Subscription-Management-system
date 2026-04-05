import os
import faiss
import numpy as np
import json

FAISS_INDEX_FILE = "memory.index"
DOCS_FILE = "memory_docs.json"

class LongTermMemory:
    def __init__(self, dimension=1536):
        self.dimension = dimension
        self.index = self._load_index()
        self.docs = self._load_docs()
        
    def _load_index(self):
        if os.path.exists(FAISS_INDEX_FILE):
            return faiss.read_index(FAISS_INDEX_FILE)
        return faiss.IndexFlatL2(self.dimension)

    def _save_index(self):
        faiss.write_index(self.index, FAISS_INDEX_FILE)
        
    def _load_docs(self):
        if os.path.exists(DOCS_FILE):
            try:
                with open(DOCS_FILE, 'r') as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _save_docs(self):
        with open(DOCS_FILE, 'w') as f:
            json.dump(self.docs, f)

    def add_memory(self, embedding: list[float], text: str, user_id: int):
        vec = np.array([embedding], dtype='float32')
        self.index.add(vec)
        self.docs.append({"user_id": user_id, "text": text})
        self._save_index()
        self._save_docs()

    def search(self, embedding: list[float], user_id: int, top_k: int = 3):
        if self.index.ntotal == 0:
            return []
            
        vec = np.array([embedding], dtype='float32')
        distances, indices = self.index.search(vec, top_k * 2)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx >= 0 and idx < len(self.docs):
                doc = self.docs[idx]
                if doc["user_id"] == user_id:
                    results.append(doc["text"])
            if len(results) >= top_k:
                break
        return results

ltm = LongTermMemory()