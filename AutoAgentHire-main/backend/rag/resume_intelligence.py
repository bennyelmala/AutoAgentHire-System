"""
Resume Intelligence Module with RAG & Embeddings
================================================
Impl        logger.info(f"📄 Parsing resume: {file_path_obj.name}")
        
        # Extract text based on file type
        if file_path_obj.suffix.lower() == '.pdf':
            raw_text = self._extract_text_from_pdf(file_path_obj)
        elif file_path_obj.suffix.lower() in ['.docx', '.doc']:
            raw_text = self._extract_text_from_docx(file_path_obj)
        elif file_path_obj.suffix.lower() == '.txt':
            raw_text = file_path_obj.read_text(encoding='utf-8')
        else:
            raise ValueError(f"Unsupported file type: {file_path_obj.suffix}")ntic resume parsing, embeddings generation, and job matching using FAISS.

Features:
- PDF/DOCX resume parsing
- LLM-powered skill extraction
- OpenAI embeddings generation
- FAISS vector store for semantic search
- Job description matching with similarity scores
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import pickle

from pypdf import PdfReader
import docx
import numpy as np
import faiss
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class ResumeData:
    """Structured resume data"""
    raw_text: str
    name: str
    email: str
    phone: str
    skills: List[str]
    experience_years: int
    experience: List[Dict[str, str]]
    education: List[Dict[str, str]]
    tools: List[str]
    keywords: List[str]
    summary: str
    embedding: Optional[np.ndarray] = None


@dataclass
class JobMatch:
    """Job matching result"""
    job_id: str
    job_title: str
    company: str
    job_description: str
    match_score: float  # 0-100%
    matched_keywords: List[str]
    recommendation: str  # 'APPLY', 'MAYBE', 'SKIP'


class ResumeIntelligence:
    """
    Resume parsing and matching using RAG + embeddings.
    """
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize Resume Intelligence system.
        
        Args:
            openai_api_key: OpenAI API key (defaults to env var)
        """
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY in .env")
        
        self.client = OpenAI(api_key=self.openai_api_key)
        self.embedding_model = "text-embedding-3-small"  # 1536 dimensions
        self.llm_model = "gpt-4o-mini"  # For resume parsing
        
        # FAISS vector store
        self.dimension = 1536  # OpenAI embedding dimension
        self.index: Optional[faiss.IndexFlatIP] = None  # Inner product (cosine similarity)
        self.resume_data: Optional[ResumeData] = None
        
        logger.info("✅ Resume Intelligence initialized")
    
    # ===========================
    # RESUME PARSING
    # ===========================
    
    def parse_resume_file(self, file_path: str) -> ResumeData:
        """
        Parse resume from PDF or DOCX file.
        
        Args:
            file_path: Path to resume file
            
        Returns:
            ResumeData: Structured resume data
        """
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"Resume file not found: {file_path_obj}")
        
        logger.info(f"📄 Parsing resume: {file_path_obj.name}")
        
        # Extract text based on file type
        if file_path_obj.suffix.lower() == '.pdf':
            raw_text = self._extract_text_from_pdf(file_path_obj)
        elif file_path_obj.suffix.lower() in ['.docx', '.doc']:
            raw_text = self._extract_text_from_docx(file_path_obj)
        elif file_path_obj.suffix.lower() == '.txt':
            raw_text = file_path_obj.read_text(encoding='utf-8')
        else:
            raise ValueError(f"Unsupported file type: {file_path_obj.suffix}")
        
        logger.info(f"✅ Extracted {len(raw_text)} characters from resume")
        
        # Parse with LLM
        resume_data = self._parse_with_llm(raw_text)
        
        # Generate embedding
        resume_data.embedding = self._generate_embedding(raw_text)
        
        # Store for later use
        self.resume_data = resume_data
        
        # Initialize FAISS index
        self._initialize_faiss()
        
        logger.info("✅ Resume parsing complete")
        return resume_data
    
    def _extract_text_from_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file"""
        try:
            with open(file_path, "rb") as file:
                reader = PdfReader(file)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text.strip()
        except Exception as e:
            logger.error(f"❌ PDF extraction failed: {e}")
            raise

    
    def _extract_text_from_docx(self, file_path: Path) -> str:
        """Extract text from DOCX file"""
        try:
            doc = docx.Document(str(file_path))
            text = "\n".join([para.text for para in doc.paragraphs])
            return text.strip()
        except Exception as e:
            logger.error(f"❌ DOCX extraction failed: {e}")
            raise
    
    def _parse_with_llm(self, raw_text: str) -> ResumeData:
        """
        Use LLM to extract structured data from resume text.
        
        Args:
            raw_text: Raw resume text
            
        Returns:
            ResumeData: Structured resume data
        """
        logger.info("🤖 Parsing resume with LLM...")
        
        prompt = f"""
You are a resume parsing expert. Extract the following information from this resume:

1. Name
2. Email
3. Phone
4. Skills (list of technical skills)
5. Years of experience (estimate total)
6. Experience (list of: {{company, title, duration, description}})
7. Education (list of: {{degree, institution, year}})
8. Tools/Technologies used
9. Keywords for job matching
10. Professional summary (2-3 sentences)

Resume:
{raw_text}

Return ONLY a valid JSON object with these exact keys:
{{
    "name": "...",
    "email": "...",
    "phone": "...",
    "skills": ["skill1", "skill2", ...],
    "experience_years": 5,
    "experience": [
        {{"company": "...", "title": "...", "duration": "...", "description": "..."}},
        ...
    ],
    "education": [
        {{"degree": "...", "institution": "...", "year": "..."}},
        ...
    ],
    "tools": ["tool1", "tool2", ...],
    "keywords": ["keyword1", "keyword2", ...],
    "summary": "..."
}}
"""
        
        response_text = ""  # Initialize to avoid "possibly unbound" error
        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "You are a precise resume parser. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            # Parse JSON response
            response_text = (response.choices[0].message.content or "{}").strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            parsed_data = json.loads(response_text)
            
            # Create ResumeData object
            resume_data = ResumeData(
                raw_text=raw_text,
                name=parsed_data.get('name', 'Unknown'),
                email=parsed_data.get('email', ''),
                phone=parsed_data.get('phone', ''),
                skills=parsed_data.get('skills', []),
                experience_years=parsed_data.get('experience_years', 0),
                experience=parsed_data.get('experience', []),
                education=parsed_data.get('education', []),
                tools=parsed_data.get('tools', []),
                keywords=parsed_data.get('keywords', []),
                summary=parsed_data.get('summary', '')
            )
            
            logger.info(f"✅ Extracted: {resume_data.name}")
            logger.info(f"   Skills: {len(resume_data.skills)}")
            logger.info(f"   Experience: {resume_data.experience_years} years")
            logger.info(f"   Keywords: {len(resume_data.keywords)}")
            
            return resume_data
            
        except json.JSONDecodeError as e:
            response_preview = response_text[:200] if 'response_text' in locals() else "N/A"
            logger.error(f"❌ JSON parsing failed: {e}")
            logger.error(f"Response: {response_preview}")
            raise
        except Exception as e:
            logger.error(f"❌ LLM parsing failed: {e}")
            raise
    
    # ===========================
    # EMBEDDINGS & VECTOR STORE
    # ===========================
    
    def _generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding vector for text using OpenAI.
        
        Args:
            text: Input text
            
        Returns:
            np.ndarray: Embedding vector (1536 dimensions)
        """
        try:
            # Truncate text if too long (max 8191 tokens for text-embedding-3-small)
            if len(text) > 30000:
                text = text[:30000]
            
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            
            embedding = np.array(response.data[0].embedding, dtype=np.float32)
            
            # Normalize for cosine similarity
            embedding = embedding / np.linalg.norm(embedding)
            
            return embedding
            
        except Exception as e:
            logger.error(f"❌ Embedding generation failed: {e}")
            raise
    
    def _initialize_faiss(self):
        """Initialize FAISS index with resume embedding"""
        if self.resume_data is None or self.resume_data.embedding is None:
            raise ValueError("Resume data and embedding required")
        
        # Create FAISS index (Inner Product for cosine similarity with normalized vectors)
        self.index = faiss.IndexFlatIP(self.dimension)
        
        # Add resume embedding
        resume_embedding_array = np.array([self.resume_data.embedding], dtype=np.float32)
        self.index.add(resume_embedding_array)  # type: ignore[call-arg]
        
        logger.info("✅ FAISS index initialized")
    
    # ===========================
    # JOB MATCHING
    # ===========================
    
    def match_job(
        self,
        job_id: str,
        job_title: str,
        company: str,
        job_description: str
    ) -> JobMatch:
        """
        Match a job description against resume using semantic similarity.
        
        Args:
            job_id: Unique job identifier
            job_title: Job title
            company: Company name
            job_description: Full job description
            
        Returns:
            JobMatch: Matching result with score and recommendation
        """
        if self.resume_data is None:
            raise ValueError("Resume data not loaded. Call parse_resume_file() first.")
        
        logger.info(f"🔍 Matching: {job_title} at {company}")
        
        # Generate embedding for job description
        job_embedding = self._generate_embedding(job_description)
        
        # Compute similarity using FAISS
        job_embedding_2d = np.array([job_embedding], dtype=np.float32)
        if self.index is not None:
            distances, indices = self.index.search(job_embedding_2d, k=1)  # type: ignore[call-arg]
        else:
            raise ValueError("FAISS index not initialized")
        
        # Convert distance to similarity score (0-100%)
        similarity = float(distances[0][0])  # Inner product gives cosine similarity
        match_score = max(0, min(100, similarity * 100))  # Clamp to 0-100
        
        # Find matched keywords
        matched_keywords = self._find_matched_keywords(job_description)
        
        # Determine recommendation
        if match_score >= 75:
            recommendation = 'APPLY'
        elif match_score >= 60:
            recommendation = 'MAYBE'
        else:
            recommendation = 'SKIP'
        
        logger.info(f"   Match Score: {match_score:.1f}% → {recommendation}")
        
        return JobMatch(
            job_id=job_id,
            job_title=job_title,
            company=company,
            job_description=job_description,
            match_score=match_score,
            matched_keywords=matched_keywords,
            recommendation=recommendation
        )
    
    def match_multiple_jobs(self, jobs: List[Dict]) -> List[JobMatch]:
        """
        Match multiple jobs and return sorted by match score.
        
        Args:
            jobs: List of job dictionaries with keys: job_id, title, company, description
            
        Returns:
            List[JobMatch]: Sorted list of job matches (highest score first)
        """
        logger.info(f"🎯 Matching {len(jobs)} jobs against resume...")
        
        matches = []
        for job in jobs:
            try:
                match = self.match_job(
                    job_id=job.get('job_id', job.get('url', '')),
                    job_title=job.get('title', ''),
                    company=job.get('company', ''),
                    job_description=job.get('description', '')
                )
                matches.append(match)
            except Exception as e:
                logger.warning(f"⚠️ Failed to match job: {e}")
                continue
        
        # Sort by match score (descending)
        matches.sort(key=lambda x: x.match_score, reverse=True)
        
        logger.info(f"✅ Matched {len(matches)} jobs")
        logger.info(f"   Top score: {matches[0].match_score:.1f}%")
        logger.info(f"   APPLY recommendations: {sum(1 for m in matches if m.recommendation == 'APPLY')}")
        
        return matches
    
    def _find_matched_keywords(self, job_description: str) -> List[str]:
        """Find which resume keywords appear in job description"""
        if not self.resume_data:
            return []
        
        job_text_lower = job_description.lower()
        matched = []
        
        # Check skills
        for skill in self.resume_data.skills:
            if skill.lower() in job_text_lower:
                matched.append(skill)
        
        # Check tools
        for tool in self.resume_data.tools:
            if tool.lower() in job_text_lower:
                matched.append(tool)
        
        # Check keywords
        for keyword in self.resume_data.keywords:
            if keyword.lower() in job_text_lower:
                if keyword not in matched:  # Avoid duplicates
                    matched.append(keyword)
        
        return matched
    
    # ===========================
    # PERSISTENCE
    # ===========================
    
    def save_resume_data(self, output_path: str):
        """Save parsed resume data to file"""
        if not self.resume_data:
            raise ValueError("No resume data to save")
        
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict for JSON serialization
        data_dict = asdict(self.resume_data)
        
        # Convert numpy array to list
        if self.resume_data.embedding is not None:
            data_dict['embedding'] = self.resume_data.embedding.tolist()
        
        with open(str(output_path_obj), 'w') as f:
            json.dump(data_dict, f, indent=2)
        
        logger.info(f"💾 Saved resume data to {output_path_obj}")
    
    def load_resume_data(self, input_path: str) -> ResumeData:
        """Load parsed resume data from file"""
        file_path = Path(input_path)
        
        with open(file_path, 'r') as f:
            data_dict = json.load(f)
        
        # Convert embedding list back to numpy array
        if 'embedding' in data_dict and data_dict['embedding']:
            data_dict['embedding'] = np.array(data_dict['embedding'], dtype=np.float32)
        
        self.resume_data = ResumeData(**data_dict)
        self._initialize_faiss()
        
        logger.info(f"📂 Loaded resume data from {file_path}")
        return self.resume_data


# ===========================
# USAGE EXAMPLE
# ===========================

if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    resume_intel = ResumeIntelligence()
    
    # Parse resume
    resume_data = resume_intel.parse_resume_file("data/resumes/sample_resume.pdf")
    
    print("\n" + "="*60)
    print("RESUME SUMMARY")
    print("="*60)
    print(f"Name: {resume_data.name}")
    print(f"Email: {resume_data.email}")
    print(f"Experience: {resume_data.experience_years} years")
    print(f"Skills: {', '.join(resume_data.skills[:5])}...")
    print(f"Summary: {resume_data.summary[:100]}...")
    
    # Example job matching
    example_job = {
        'job_id': 'job123',
        'title': 'Senior ML Engineer',
        'company': 'TechCorp',
        'description': 'Looking for ML engineer with Python, TensorFlow, and 5+ years experience...'
    }
    
    match = resume_intel.match_job(**example_job)
    
    print("\n" + "="*60)
    print("JOB MATCH RESULT")
    print("="*60)
    print(f"Job: {match.job_title} at {match.company}")
    print(f"Match Score: {match.match_score:.1f}%")
    print(f"Recommendation: {match.recommendation}")
    print(f"Matched Keywords: {', '.join(match.matched_keywords[:10])}")
