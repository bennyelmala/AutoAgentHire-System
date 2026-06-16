"""
ATS Resume Checker Routes
Provides endpoints for ATS matching and cover letter generation
"""

import os
import re
import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import docx
from pypdf import PdfReader

# Lazy imports — do NOT load sklearn/numpy at module level (causes OOM on low-memory servers)
# They are imported inside the endpoint function that actually needs them.

router = APIRouter(prefix="/api/ats", tags=["ATS"])


def _safe_suffix(filename: str | None) -> str:
    """Return a safe suffix (including leading dot) for temp files."""
    if not filename:
        return ""
    name = filename.lower()
    if name.endswith(".pdf"):
        return ".pdf"
    if name.endswith(".docx"):
        return ".docx"
    return ""


def _temp_upload_path(upload_dir: str, filename: str | None) -> str:
    """Create a safe, unique file path for uploaded files (no user-controlled path parts)."""
    suffix = _safe_suffix(filename)
    tmp_name = f"{uuid.uuid4().hex}{suffix or '.bin'}"
    return os.path.join(upload_dir, tmp_name)


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF file"""
    # 1) Try PyPDF2 first (fastest, already a dependency)
    try:
        text_parts: list[str] = []
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                if page_text:
                    text_parts.append(page_text)
        text = "\n".join(text_parts).strip()
        if text:
            return text
    except Exception:
        # Fall back to pdfminer.six below
        pass

    # 2) Fallback to pdfminer.six for tricky/malformed PDFs
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text
    except Exception as e:  # pragma: no cover
        raise HTTPException(
            status_code=400,
            detail=(
                "Failed to parse PDF with PyPDF2 and pdfminer.six is unavailable. "
                f"Original import error: {str(e)}"
            ),
        )

    try:
        text = (pdfminer_extract_text(file_path) or "").strip()
        if not text:
            raise ValueError("No extractable text found in PDF")
        return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from DOCX file"""
    text = ""
    try:
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse DOCX: {str(e)}")
    return text


def extract_keywords(text: str) -> List[str]:
    """Extract keywords from text using simple NLP"""
    # Remove common words and extract meaningful keywords
    text = text.lower()
    # Remove special characters but keep spaces
    text = re.sub(r'[^a-z0-9\s+#]', ' ', text)
    
    # Common stop words to exclude
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
        'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'should', 'could', 'may', 'might', 'must', 'can', 'this', 'that',
        'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
    }
    
    words = text.split()
    keywords = []
    
    for word in words:
        word = word.strip()
        # Keep words with length > 2 and not in stop words
        if len(word) > 2 and word not in stop_words:
            # Include technical terms like c++, c#
            if '+' in word or '#' in word or word.isalnum():
                keywords.append(word)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for keyword in keywords:
        if keyword not in seen:
            seen.add(keyword)
            unique_keywords.append(keyword)
    
    return unique_keywords


def extract_skills(text: str) -> List[str]:
    """Extract technical skills from text"""
    text = text.lower()
    
    # Common technical skills dictionary
    common_skills = [
        # Programming Languages
        'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'ruby', 'php',
        'swift', 'kotlin', 'go', 'rust', 'scala', 'perl', 'r', 'matlab',
        
        # Web Technologies
        'html', 'css', 'react', 'angular', 'vue', 'nodejs', 'express', 'django',
        'flask', 'fastapi', 'spring', 'nextjs', 'gatsby', 'svelte',
        
        # Databases
        'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'cassandra', 'oracle',
        'sqlite', 'dynamodb', 'elasticsearch',
        
        # Cloud & DevOps
        'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'gitlab',
        'terraform', 'ansible', 'ci/cd', 'devops',
        
        # AI/ML
        'machine learning', 'deep learning', 'tensorflow', 'pytorch', 'keras',
        'scikit-learn', 'nlp', 'computer vision', 'llm', 'transformers',
        
        # Data Science
        'pandas', 'numpy', 'matplotlib', 'seaborn', 'tableau', 'power bi',
        'data analysis', 'data visualization', 'statistics',
        
        # Others
        'git', 'agile', 'scrum', 'jira', 'api', 'rest', 'graphql', 'microservices',
        'testing', 'unit testing', 'selenium', 'pytest', 'jest'
    ]
    
    found_skills = []
    for skill in common_skills:
        if skill in text:
            found_skills.append(skill)
    
    return found_skills


def calculate_ats_score(resume_text: str, job_description: str) -> Dict[str, Any]:
    """
    Calculate ATS score using:
    1. Keyword matching (exact)
    2. Semantic similarity (TF-IDF + cosine)
    3. Skill overlap
    """
    
    # Extract keywords from both
    resume_keywords = set(extract_keywords(resume_text))
    jd_keywords = set(extract_keywords(job_description))
    
    # Extract skills
    resume_skills = set(extract_skills(resume_text))
    jd_skills = set(extract_skills(job_description))
    
    # Keyword overlap
    matched_keywords = resume_keywords.intersection(jd_keywords)
    missing_keywords = jd_keywords - resume_keywords
    
    # Skill overlap
    matched_skills = resume_skills.intersection(jd_skills)
    
    # Calculate keyword match percentage
    keyword_score = (len(matched_keywords) / len(jd_keywords) * 100) if jd_keywords else 0
    
    # Calculate semantic similarity using TF-IDF
    try:
        # Lazy import — only loads sklearn when this endpoint is actually called
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform([resume_text, job_description])
        # Calculate cosine similarity and convert result to float
        similarity_result = cosine_similarity(tfidf_matrix, tfidf_matrix)
        # Get similarity between first and second document
        similarity = float(similarity_result[0, 1]) if similarity_result.shape[0] > 1 else 0.0
        semantic_score = similarity * 100
    except Exception:
        semantic_score = keyword_score
    
    # Calculate skill match score
    skill_score = (len(matched_skills) / len(jd_skills) * 100) if jd_skills else 0
    
    # Final weighted score
    final_score = int(
        keyword_score * 0.4 +
        semantic_score * 0.4 +
        skill_score * 0.2
    )
    
    # Generate suggestions
    suggestions = []
    if final_score < 60:
        suggestions.append("Your resume has low keyword match. Add more relevant keywords from the job description.")
    if len(missing_keywords) > 10:
        suggestions.append(f"Add {len(missing_keywords)} missing keywords to improve ATS score.")
    if len(matched_skills) < len(jd_skills) * 0.5:
        suggestions.append("Include more technical skills mentioned in the job description.")
    if semantic_score < 50:
        suggestions.append("Restructure your resume to better align with the job requirements.")
    
    # Limit keywords for display (most important ones)
    matched_keywords_list = sorted(list(matched_keywords))[:30]
    missing_keywords_list = sorted(list(missing_keywords))[:20]
    
    return {
        "score": min(final_score, 100),
        # Backwards/forwards compatibility: some clients expect `match_score`
        "match_score": min(final_score, 100),
        "matched_keywords": matched_keywords_list,
        "missing_keywords": missing_keywords_list,
        "matched_skills": sorted(list(matched_skills)),
        "suggestions": suggestions,
        "resume_text": resume_text
    }


@router.post("/parse-resume")
async def parse_resume(file: UploadFile = File(...)):
    """Parse resume and extract text"""
    
    # Save uploaded file temporarily
    upload_dir = "uploads/resumes"
    os.makedirs(upload_dir, exist_ok=True)

    file_path = _temp_upload_path(upload_dir, file.filename)
    
    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Extract text based on file type
        if file.filename and file.filename.lower().endswith('.pdf'):
            resume_text = extract_text_from_pdf(file_path)
        elif file.filename and file.filename.lower().endswith('.docx'):
            resume_text = extract_text_from_docx(file_path)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        # Clean up
        if os.path.exists(file_path):
            os.remove(file_path)
        
        return {
            "status": "success",
            "text": resume_text,
            "length": len(resume_text)
        }
    
    except Exception as e:
        # Clean up on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/match")
async def match_resume(
    resume: UploadFile = File(...),
    job_description: str = Form(...)
):
    """
    Main ATS matching endpoint
    Returns ATS score, matched/missing keywords, skills, and suggestions
    """
    
    # Save uploaded file temporarily
    upload_dir = "uploads/resumes"
    os.makedirs(upload_dir, exist_ok=True)

    file_path = _temp_upload_path(upload_dir, resume.filename)
    
    try:
        # Save file
        with open(file_path, "wb") as buffer:
            content = await resume.read()
            buffer.write(content)
        
        # Extract text
        filename = (resume.filename or "").lower()
        if filename.endswith(".pdf"):
            resume_text = extract_text_from_pdf(file_path)
        elif filename.endswith(".docx"):
            resume_text = extract_text_from_docx(file_path)
        elif filename.endswith(".txt") or (resume.content_type or "").startswith("text/"):
            try:
                resume_text = content.decode("utf-8", errors="ignore")
            except Exception:
                resume_text = ""
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Use PDF, DOCX, or TXT",
            )
        
        # Validate content
        if len(resume_text.strip()) < 100:
            raise HTTPException(status_code=400, detail="Resume content is too short or couldn't be extracted")
        
        if len(job_description.strip()) < 50:
            raise HTTPException(status_code=400, detail="Job description is too short")
        
        # Calculate ATS score
        result = calculate_ats_score(resume_text, job_description)
        
        # Clean up
        if os.path.exists(file_path):
            os.remove(file_path)
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        # Clean up on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"ATS matching failed: {str(e)}")
