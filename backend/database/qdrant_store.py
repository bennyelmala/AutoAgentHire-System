"""
Qdrant Cloud Vector Store for AutoAgentHire
-------------------------------------------
Used for:
  - Resume semantic search (find resumes matching a job)
  - Job semantic search (find jobs matching a resume)
  - Cover letter similarity and deduplication
  - AI-powered skill gap analysis
  - Job match scoring between user profile and job description

Collections created:
  - resumes      : User resume embeddings (384-dim)
  - jobs         : Job description embeddings (384-dim)
  - cover_letters: Generated cover letter embeddings (384-dim)
"""

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, List, Dict, Optional, Any, Type

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Optional imports — always define names so Pylance never sees them as unbound
# ---------------------------------------------------------------------------
QdrantClient: Any = None
VectorParams: Any = None
Distance: Any = None
PointStruct: Any = None
Filter: Any = None
FieldCondition: Any = None
MatchValue: Any = None
SentenceTransformer: Any = None

QDRANT_AVAILABLE = False
ST_AVAILABLE = False

try:
    from qdrant_client import QdrantClient  # type: ignore[assignment]
    from qdrant_client.models import (  # type: ignore[assignment]
        Distance,
        VectorParams,
        PointStruct,
        Filter,
        FieldCondition,
        MatchValue,
    )
    QDRANT_AVAILABLE = True
except ImportError:
    print("[QD] WARNING - qdrant-client not installed. Run: pip install qdrant-client")

try:
    from sentence_transformers import SentenceTransformer  # type: ignore[assignment]
    ST_AVAILABLE = True
except Exception:
    print("[QD] WARNING - sentence-transformers not available. Embeddings disabled.")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
QDRANT_URL = os.getenv("QDRANT_URL") or os.getenv("qdrantendpoint", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or os.getenv("qdrant_api_key", "")

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
VECTOR_DIM = 384

COLLECTION_RESUMES = "resumes"
COLLECTION_JOBS = "jobs"
COLLECTION_COVER_LETTERS = "cover_letters"
ALL_COLLECTIONS = [COLLECTION_RESUMES, COLLECTION_JOBS, COLLECTION_COVER_LETTERS]


# ---------------------------------------------------------------------------
# QdrantVectorStore
# ---------------------------------------------------------------------------
class QdrantVectorStore:
    """
    Cloud vector store backed by Qdrant.
    Manages three collections: resumes, jobs, cover_letters.
    """

    def __init__(self):
        self.client: Any = None          # QdrantClient once connected
        self._embed_model: Any = None    # SentenceTransformer once loaded
        self._model_loaded: bool = False
        self._connected: bool = False

        if not QDRANT_AVAILABLE:
            print("[QD] qdrant-client not installed — store disabled.")
            return

        if not QDRANT_URL or not QDRANT_API_KEY:
            print("[QD] WARNING - QDRANT_URL / QDRANT_API_KEY not set in .env — store disabled.")
            return

        try:
            self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=15)
            self._connected = True
            print("[QD] Connected to Qdrant Cloud: " + QDRANT_URL.split("//")[-1].split(".")[0] + "...")
            self._ensure_collections()
        except Exception as e:
            print("[QD] ERROR - Could not connect: " + str(e).splitlines()[0])

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_collections(self):
        """Create collections if they don't exist yet."""
        existing = {c.name for c in self.client.get_collections().collections}
        for name in ALL_COLLECTIONS:
            if name not in existing:
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
                )
                print("[QD] Created collection: " + name)
            else:
                info = self.client.get_collection(name)
                print("[QD] Collection '" + name + "' ready — " + str(info.points_count) + " vectors")

    def _load_model(self):
        if self._model_loaded:
            return
        if not ST_AVAILABLE:
            self._model_loaded = True
            return
        try:
            self._embed_model = SentenceTransformer(EMBEDDING_MODEL)
            self._model_loaded = True
            print("[QD] Embedding model loaded: " + EMBEDDING_MODEL)
        except Exception as e:
            print("[QD] WARNING - Could not load model: " + str(e).splitlines()[0])
            self._model_loaded = True

    def _embed(self, text: str) -> Optional[List[float]]:
        """Convert text to a 384-dim float vector.
        Tries local model first, then API-based fallbacks."""
        # Try local model first (fast but memory-heavy)
        self._load_model()
        if self._embed_model is not None:
            try:
                vec = self._embed_model.encode(text, convert_to_numpy=True)
                return vec.tolist()
            except Exception as e:
                print("[QD] LOCAL embedding failed: " + str(e).splitlines()[0])
        
        # Fallback: Use OpenAI API
        import urllib.request
        import json
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
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
                    return data["data"][0]["embedding"]
            except Exception as e:
                print(f"[QD] OpenAI embedding failed: {str(e).splitlines()[0]}")
        
        # Fallback: Use Gemini API
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
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
                    return data["embedding"]["values"]
            except Exception as e:
                print(f"[QD] Gemini embedding failed: {str(e).splitlines()[0]}")
        
        # Fallback 3: Use Groq API (using their embedding model)
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
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
                with urllib.request.urlopen(req, timeout=15) as response:
                    data = json.loads(response.read().decode())
                    return data["data"][0]["embedding"]
            except Exception as e:
                print(f"[QD] Groq embedding failed: {str(e).splitlines()[0]}")
        
        # No model and no API configured
        print("[QD] WARNING - No embedding method available, using hash-based fallback")
        words = text.lower().split()
        embedding = [0.0] * 384
        for i, word in enumerate(words[:384]):
            embedding[hash(word) % 384] += 1.0
        # Normalize
        norm = sum(x**2 for x in embedding) ** 0.5
        return [x / norm if norm > 0 else 0.0 for x in embedding]

    # ------------------------------------------------------------------
    # Resume Operations
    # ------------------------------------------------------------------

    def add_resume(self, user_id: int, resume_text: str, metadata: Dict = {}) -> Optional[str]:
        """
        Embed and store a resume in Qdrant.
        Returns the assigned point ID (UUID string).

        Used when: user uploads/updates their resume.
        """
        if not self._connected:
            return None
        vector = self._embed(resume_text)
        if vector is None:
            return None
        point_id = str(uuid.uuid4())
        payload = {"user_id": user_id, "text_preview": resume_text[:300], **metadata}
        self.client.upsert(
            collection_name=COLLECTION_RESUMES,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        print("[QD] Resume stored for user_id=" + str(user_id) + " id=" + point_id[:8] + "...")
        return point_id

    def find_resumes_matching_job(self, job_description: str, top_k: int = 5) -> List[Dict]:
        """
        Given a job description, return the top-k most relevant resumes.

        Used for: showing recruiters the best-matching candidates.
        """
        if not self._connected:
            return []
        vector = self._embed(job_description)
        if vector is None:
            return []
        results = self.client.query_points(
            collection_name=COLLECTION_RESUMES,
            query=vector,
            limit=top_k,
            with_payload=True,
        ).points
        return [
            {"id": str(r.id), "score": round(r.score, 4), **r.payload}
            for r in results
        ]

    # ------------------------------------------------------------------
    # Job Operations
    # ------------------------------------------------------------------

    def add_job(self, job_id: str, job_description: str, metadata: Dict = {}) -> Optional[str]:
        """
        Embed and store a job posting in Qdrant.

        Used when: a new job is discovered during LinkedIn search.
        """
        if not self._connected:
            return None
        vector = self._embed(job_description)
        if vector is None:
            return None
        point_id = str(uuid.uuid4())
        payload = {"job_id": job_id, "text_preview": job_description[:300], **metadata}
        self.client.upsert(
            collection_name=COLLECTION_JOBS,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        print("[QD] Job stored job_id=" + str(job_id) + " id=" + point_id[:8] + "...")
        return point_id

    def find_jobs_matching_resume(self, resume_text: str, top_k: int = 10) -> List[Dict]:
        """
        Given a resume, return the top-k most relevant job listings.

        Used for: smart job recommendations on the user dashboard.
        """
        if not self._connected:
            return []
        vector = self._embed(resume_text)
        if vector is None:
            return []
        results = self.client.query_points(
            collection_name=COLLECTION_JOBS,
            query=vector,
            limit=top_k,
            with_payload=True,
        ).points
        return [
            {"id": str(r.id), "score": round(r.score, 4), **r.payload}
            for r in results
        ]

    def match_score(self, resume_text: str, job_description: str) -> float:
        """
        Return a 0-1 cosine similarity score between a resume and job description.

        Used for: deciding whether to auto-apply to a specific job.
        A score >= 0.6 is considered a good match.
        """
        if not self._connected or not self._embed_model:
            return 0.0
        self._load_model()
        if self._embed_model is None:
            return 0.0
        try:
            import numpy as np
            r_vec = self._embed_model.encode(resume_text, convert_to_numpy=True)
            j_vec = self._embed_model.encode(job_description, convert_to_numpy=True)
            score = float(np.dot(r_vec, j_vec) / (np.linalg.norm(r_vec) * np.linalg.norm(j_vec)))
            return round(max(0.0, score), 4)
        except Exception as e:
            print("[QD] ERROR - match_score: " + str(e).splitlines()[0])
            return 0.0

    # ------------------------------------------------------------------
    # Cover Letter Operations
    # ------------------------------------------------------------------

    def add_cover_letter(self, user_id: int, job_id: str, cover_letter_text: str) -> Optional[str]:
        """
        Store a generated cover letter embedding.

        Used for: detecting duplicate cover letters and quality scoring.
        """
        if not self._connected:
            return None
        vector = self._embed(cover_letter_text)
        if vector is None:
            return None
        point_id = str(uuid.uuid4())
        self.client.upsert(
            collection_name=COLLECTION_COVER_LETTERS,
            points=[PointStruct(
                id=point_id,
                vector=vector,
                payload={"user_id": user_id, "job_id": job_id, "preview": cover_letter_text[:200]},
            )],
        )
        return point_id

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def collection_stats(self) -> Dict[str, int]:
        """Return vector count per collection."""
        if not self._connected:
            return {}
        stats = {}
        for name in ALL_COLLECTIONS:
            try:
                info = self.client.get_collection(name)
                stats[name] = info.points_count
            except Exception:
                stats[name] = -1
        return stats

    def delete_resume(self, point_id: str):
        if self._connected:
            self.client.delete(collection_name=COLLECTION_RESUMES, points_selector=[point_id])

    def delete_job(self, point_id: str):
        if self._connected:
            self.client.delete(collection_name=COLLECTION_JOBS, points_selector=[point_id])

    @property
    def is_connected(self) -> bool:
        return self._connected


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
qdrant_store = QdrantVectorStore()
