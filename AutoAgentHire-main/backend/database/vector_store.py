"""
Vector Store Manager for AutoAgentHire
Hybrid FAISS + Database approach for semantic job matching
"""

import os
import json
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime

# Optional imports with proper type handling
faiss: Any = None
SentenceTransformer: Any = None
FAISS_AVAILABLE = False
SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import faiss as _faiss
    faiss = _faiss
    FAISS_AVAILABLE = True
except ImportError:
    print("[VS] WARNING - FAISS not installed. Using fallback similarity search.")

try:
    from sentence_transformers import SentenceTransformer as _SentenceTransformer
    SentenceTransformer = _SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except Exception:
    print("[VS] WARNING - sentence-transformers/torch not available. Using fallback embedding.")


class VectorStoreManager:
    """
    Hybrid vector store using FAISS for fast similarity search
    with PostgreSQL/SQLite backup for persistence.
    """
    
    def __init__(self, index_path: str = "data/vectors"):
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # Index paths
        self.resume_index_path = self.index_path / "resume_index.faiss"
        self.resume_mapping_path = self.index_path / "resume_mapping.pkl"
        self.job_index_path = self.index_path / "job_index.faiss"
        self.job_mapping_path = self.index_path / "job_mapping.pkl"
        
        # Embedding configuration
        self.embedding_model_name = "all-MiniLM-L6-v2"
        self.dimension = 384  # all-MiniLM-L6-v2 dimension
        
        # Initialize embedding model (lazy loading)
        self.embedding_model = None
        self._model_loaded = False
        
        # Initialize FAISS indexes
        self.resume_index = None
        self.job_index = None
        self.resume_mapping: Dict[int, int] = {}  # faiss_idx -> resume_id
        self.job_mapping: Dict[int, str] = {}  # faiss_idx -> job_id
        
        if FAISS_AVAILABLE:
            self._load_or_create_indexes()
    
    def _load_or_create_indexes(self):
        """Load existing indexes or create new ones"""
        # Resume index
        if self.resume_index_path.exists():
            self.resume_index = faiss.read_index(str(self.resume_index_path))
            self.resume_mapping = self._load_mapping(self.resume_mapping_path)
            print("[VS] Loaded resume index with " + str(self.resume_index.ntotal) + " vectors")
        else:
            self.resume_index = faiss.IndexFlatIP(self.dimension)  # Inner product for cosine similarity
            self.resume_mapping = {}
            print("[VS] Created new resume index")
        
        # Job index
        if self.job_index_path.exists():
            self.job_index = faiss.read_index(str(self.job_index_path))
            self.job_mapping = self._load_mapping(self.job_mapping_path)
            print("[VS] Loaded job index with " + str(self.job_index.ntotal) + " vectors")
        else:
            self.job_index = faiss.IndexFlatIP(self.dimension)
            self.job_mapping = {}
            print("[VS] Created new job index")
    
    def _ensure_model_loaded(self):
        """Lazy load the embedding model when first needed"""
        if not self._model_loaded and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer(self.embedding_model_name)
                self._model_loaded = True
                print("[VS] Loaded embedding model: " + self.embedding_model_name)
            except Exception as e:
                print("[VS] WARNING - Could not load embedding model: " + str(e).splitlines()[0])
                self._model_loaded = True  # Mark as attempted to avoid repeated failures
    
    def _load_mapping(self, path: Path) -> Dict:
        """Load index to ID mapping from pickle file"""
        if path.exists():
            with open(path, 'rb') as f:
                return pickle.load(f)
        return {}
    
    def _save_mapping(self, mapping: Dict, path: Path):
        """Save index to ID mapping to pickle file"""
        with open(path, 'wb') as f:
            pickle.dump(mapping, f)
    
    def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for text using sentence transformer"""
        if not text or not text.strip():
            return None
        
        # Lazy load the model
        self._ensure_model_loaded()
        
        if self.embedding_model:
            try:
                embedding = self.embedding_model.encode(text, convert_to_numpy=True)
                return embedding.astype('float32')
            except Exception as e:
                print("[VS] ERROR - Embedding generation: " + str(e).splitlines()[0])
                return None
        else:
            # Fallback: simple TF-IDF style vector (not recommended for production)
            return self._fallback_embedding(text)
    
    def _fallback_embedding(self, text: str) -> np.ndarray:
        """Fallback to OpenAI/Gemini APIs if available, otherwise simple hash-based"""
        import os
        
        # 1. Try OpenAI if API key exists
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                import urllib.request
                import json
                req = urllib.request.Request(
                    "https://api.openai.com/v1/embeddings",
                    data=json.dumps({
                        "model": "text-embedding-3-small",
                        "input": text[:8000]
                    }).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {openai_key}",
                        "Content-Type": "application/json"
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    vec = data["data"][0]["embedding"]
                    # Pad or truncate to self.dimension (usually 384)
                    arr = np.zeros(self.dimension, dtype='float32')
                    arr[:min(len(vec), self.dimension)] = vec[:self.dimension]
                    norm = np.linalg.norm(arr)
                    return arr / norm if norm > 0 else arr
            except Exception as e:
                print(f"[VS] Fallback OpenAI embedding failed: {e}")
                
        # 2. Try Gemini if API key exists  
        gemini_key = os.getenv("GEMINI_API_KEY")      
        if gemini_key:
            try:
                import urllib.request
                import json
                req = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={gemini_key}",
                    method="POST",
                    data=json.dumps({
                        "model": "models/text-embedding-004",
                        "content": {"parts": [{"text": text[:8000]}]}
                    }).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    vec = data["embedding"]["values"]
                    # Pad or truncate to self.dimension
                    arr = np.zeros(self.dimension, dtype='float32')
                    arr[:min(len(vec), self.dimension)] = vec[:self.dimension]
                    norm = np.linalg.norm(arr)
                    return arr / norm if norm > 0 else arr
            except Exception as e:
                print(f"[VS] Fallback Gemini embedding failed: {e}")
        
        # 3. Try Groq if API key exists (using their embedding model)
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
                import urllib.request
                import json
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/embeddings",
                    data=json.dumps({
                        "model": "nomic-embed-text-v1.5",
                        "input": text[:8000]
                    }).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json"
                    }
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())
                    vec = data["data"][0]["embedding"]
                    arr = np.zeros(self.dimension, dtype='float32')
                    arr[:min(len(vec), self.dimension)] = vec[:self.dimension]
                    norm = np.linalg.norm(arr)
                    return arr / norm if norm > 0 else arr
            except Exception as e:
                print(f"[VS] Fallback Groq embedding failed: {e}")

        # 4. Absolute worst-case scenario: simple hash-based embedding (NOT recommended for production)
        words = text.lower().split()
        embedding = np.zeros(self.dimension, dtype='float32')
        for i, word in enumerate(words[:self.dimension]):
            embedding[hash(word) % self.dimension] += 1
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding
    
    def add_resume_embedding(self, resume_id: int, text: str) -> Optional[List[float]]:
        """
        Generate embedding for resume text and add to FAISS index.
        Returns the embedding vector as a list.
        """
        embedding = self.generate_embedding(text)
        if embedding is None:
            return None
        
        # Normalize for cosine similarity
        embedding = embedding.reshape(1, -1)
        faiss.normalize_L2(embedding)
        
        if FAISS_AVAILABLE and self.resume_index is not None:
            # Add to FAISS index
            idx = self.resume_index.ntotal
            self.resume_index.add(embedding)
            self.resume_mapping[idx] = resume_id
            
            # Save to disk
            faiss.write_index(self.resume_index, str(self.resume_index_path))
            self._save_mapping(self.resume_mapping, self.resume_mapping_path)
            
            print("[VS] Added resume " + str(resume_id) + " to vector index (idx=" + str(idx) + ")")
        
        return embedding.flatten().tolist()
    
    def add_job_embedding(self, job_id: str, text: str) -> Optional[List[float]]:
        """
        Generate embedding for job text and add to FAISS index.
        Returns the embedding vector as a list.
        """
        embedding = self.generate_embedding(text)
        if embedding is None:
            return None
        
        # Normalize for cosine similarity
        embedding = embedding.reshape(1, -1)
        faiss.normalize_L2(embedding)
        
        if FAISS_AVAILABLE and self.job_index is not None:
            # Add to FAISS index
            idx = self.job_index.ntotal
            self.job_index.add(embedding)
            self.job_mapping[idx] = job_id
            
            # Save to disk
            faiss.write_index(self.job_index, str(self.job_index_path))
            self._save_mapping(self.job_mapping, self.job_mapping_path)
            
            print("[VS] Added job " + str(job_id) + " to vector index (idx=" + str(idx) + ")")
        
        return embedding.flatten().tolist()
    
    def search_similar_jobs(
        self, 
        resume_embedding: np.ndarray, 
        k: int = 20
    ) -> List[Dict]:
        """
        Find k most similar jobs to a resume embedding.
        
        Args:
            resume_embedding: Resume embedding vector
            k: Number of similar jobs to return
            
        Returns:
            List of dicts with job_id and similarity_score
        """
        if not FAISS_AVAILABLE or self.job_index is None:
            return []
        
        if self.job_index.ntotal == 0:
            return []
        
        # Prepare embedding
        embedding = np.array(resume_embedding, dtype='float32').reshape(1, -1)
        faiss.normalize_L2(embedding)
        
        # Search
        k = min(k, self.job_index.ntotal)
        distances, indices = self.job_index.search(embedding, k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx >= 0 and idx in self.job_mapping:
                results.append({
                    'job_id': self.job_mapping[idx],
                    'similarity_score': float(dist)  # Inner product (cosine after normalization)
                })
        
        return results
    
    def search_similar_resumes(
        self, 
        job_embedding: np.ndarray, 
        k: int = 10
    ) -> List[Dict]:
        """
        Find k most similar resumes to a job embedding.
        
        Args:
            job_embedding: Job embedding vector
            k: Number of similar resumes to return
            
        Returns:
            List of dicts with resume_id and similarity_score
        """
        if not FAISS_AVAILABLE or self.resume_index is None:
            return []
        
        if self.resume_index.ntotal == 0:
            return []
        
        # Prepare embedding
        embedding = np.array(job_embedding, dtype='float32').reshape(1, -1)
        faiss.normalize_L2(embedding)
        
        # Search
        k = min(k, self.resume_index.ntotal)
        distances, indices = self.resume_index.search(embedding, k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx >= 0 and idx in self.resume_mapping:
                results.append({
                    'resume_id': self.resume_mapping[idx],
                    'similarity_score': float(dist)
                })
        
        return results
    
    def calculate_similarity(
        self, 
        text1: str, 
        text2: str
    ) -> float:
        """
        Calculate cosine similarity between two texts.
        
        Args:
            text1: First text (e.g., resume)
            text2: Second text (e.g., job description)
            
        Returns:
            Similarity score between 0 and 1
        """
        emb1 = self.generate_embedding(text1)
        emb2 = self.generate_embedding(text2)
        
        if emb1 is None or emb2 is None:
            return 0.0
        
        # Normalize and compute cosine similarity
        emb1 = emb1 / np.linalg.norm(emb1)
        emb2 = emb2 / np.linalg.norm(emb2)
        
        similarity = float(np.dot(emb1, emb2))
        return max(0.0, min(1.0, similarity))  # Clamp to [0, 1]
    
    def batch_calculate_similarities(
        self, 
        resume_text: str, 
        job_texts: List[str]
    ) -> List[float]:
        """
        Calculate similarities between a resume and multiple jobs efficiently.
        
        Args:
            resume_text: Resume text
            job_texts: List of job description texts
            
        Returns:
            List of similarity scores
        """
        resume_emb = self.generate_embedding(resume_text)
        if resume_emb is None:
            return [0.0] * len(job_texts)
        
        resume_emb = resume_emb / np.linalg.norm(resume_emb)
        
        similarities = []
        for job_text in job_texts:
            job_emb = self.generate_embedding(job_text)
            if job_emb is None:
                similarities.append(0.0)
            else:
                job_emb = job_emb / np.linalg.norm(job_emb)
                sim = float(np.dot(resume_emb, job_emb))
                similarities.append(max(0.0, min(1.0, sim)))
        
        return similarities
    
    def remove_resume(self, resume_id: int) -> bool:
        """Remove a resume from the index (requires rebuilding)"""
        # FAISS doesn't support direct deletion, need to rebuild index
        # For production, consider using IVF index with IDSelector
        print("[VS] Resume " + str(resume_id) + " marked for removal (rebuild required)")
        return True
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the index (requires rebuilding)"""
        print("[VS] Job " + str(job_id) + " marked for removal (rebuild required)")
        return True
    
    def rebuild_indexes(self):
        """Rebuild FAISS indexes from database (call periodically)"""
        # This would typically:
        # 1. Load all embeddings from database
        # 2. Create new FAISS indexes
        # 3. Replace old indexes
        print("🔄 Index rebuild requested (implement with database)")
    
    def get_stats(self) -> Dict:
        """Get vector store statistics"""
        stats = {
            "faiss_available": FAISS_AVAILABLE,
            "sentence_transformers_available": SENTENCE_TRANSFORMERS_AVAILABLE,
            "embedding_model": self.embedding_model_name,
            "dimension": self.dimension,
            "resume_vectors": self.resume_index.ntotal if FAISS_AVAILABLE and self.resume_index else 0,
            "job_vectors": self.job_index.ntotal if FAISS_AVAILABLE and self.job_index else 0,
        }
        return stats


# Global vector store instance
vector_store = VectorStoreManager()


# Convenience functions
def get_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding for text"""
    emb = vector_store.generate_embedding(text)
    return emb.tolist() if emb is not None else None


def calculate_job_match_score(resume_text: str, job_description: str) -> float:
    """Calculate match score between resume and job"""
    return vector_store.calculate_similarity(resume_text, job_description)


def find_matching_jobs(resume_embedding: List[float], k: int = 20) -> List[Dict]:
    """Find jobs matching a resume"""
    return vector_store.search_similar_jobs(np.array(resume_embedding), k)
