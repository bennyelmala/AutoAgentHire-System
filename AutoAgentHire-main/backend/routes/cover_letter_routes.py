"""
Cover Letter Generation Routes
Separate endpoint for AI-powered cover letter generation
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.llm.gemini_service import GeminiService

router = APIRouter(prefix="/api/cover-letter", tags=["Cover Letter"])

# Instantiated on first request, not at import time
_gemini_service = None

def _get_gemini():
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service


class CoverLetterRequest(BaseModel):
    """Request model for cover letter generation"""
    job_description: str
    resume_text: str


@router.post("/generate")
async def generate_cover_letter_endpoint(request: CoverLetterRequest):
    """
    Generate tailored cover letter using Gemini AI
    """
    
    try:
        # Use Gemini's generate_cover_letter method with proper parameters
        cover_letter = _get_gemini().generate_cover_letter(
            job_title="Position from Job Description",  # Extract from JD if needed
            company="Company Name",  # Extract from JD if needed
            job_description=request.job_description,
            resume_text=request.resume_text[:3000],  # Limit to 3000 chars
            user_name="Applicant"  # Can be extracted from resume if needed
        )
        
        if not cover_letter:
            raise HTTPException(status_code=500, detail="Failed to generate cover letter")
        
        return {
            "status": "success",
            "cover_letter": cover_letter.strip()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cover letter generation failed: {str(e)}")
