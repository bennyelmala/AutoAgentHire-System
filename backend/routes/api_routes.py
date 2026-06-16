"""
Main API routes for AutoAgentHire application.
Handles job automation, user management, and application tracking.
"""
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
import logging
import os
import json
from datetime import datetime

from backend.database.connection import get_db
from backend.database.crud import UserRepository, ResumeRepository
from backend.auth.dependencies import get_current_user
from backend.database.models_complete import User
from backend.auth.validators import validate_email_format, validate_phone_number

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])


# ==========================================
# Request/Response Models
# ==========================================

class UserProfileCreate(BaseModel):
    """User profile creation model."""
    full_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    linkedin_email: EmailStr
    linkedin_password: str = Field(..., min_length=6)
    job_keywords: List[str] = Field(default_factory=list)
    preferred_locations: List[str] = Field(default_factory=list)
    job_type: str = Field(default="Remote", pattern="^(Remote|On-site|Hybrid|Any)$")
    experience_level: str = Field(default="Mid-level")
    skills: List[str] = Field(default_factory=list)
    gemini_api_key: Optional[str] = None


class JobSearchRequest(BaseModel):
    """Job search request model."""
    keywords: str = Field(..., min_length=1)
    location: str = Field(default="Remote")
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    easy_apply_only: bool = True
    max_results: int = Field(default=50, le=100)
    linkedin_email: Optional[str] = None
    linkedin_password: Optional[str] = None
    submit_applications: bool = False  # Safety flag


class ApplicationSubmitRequest(BaseModel):
    """Application submission request."""
    job_id: str
    cover_letter: Optional[str] = None
    additional_answers: Optional[Dict[str, str]] = None


class AgentRunRequest(BaseModel):
    """Full agent automation run request."""
    user_profile: UserProfileCreate
    search_criteria: JobSearchRequest
    auto_submit: bool = False
    min_match_score: float = Field(default=0.7, ge=0, le=1)


# ==========================================
# Global State Management
# ==========================================

class ApplicationState:
    """Tracks the current state of agent execution."""
    
    def __init__(self):
        self.status = "idle"  # idle, running, paused, completed, failed
        self.current_phase = ""  # login, searching, applying, etc.
        self.jobs_found = 0
        self.applications_submitted = 0
        self.applications_previewed = 0
        self.errors = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.logs = []
    
    def reset(self):
        self.__init__()
    
    def add_log(self, level: str, message: str):
        self.logs.append({
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message
        })
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "phase": self.current_phase,
            "jobs_found": self.jobs_found,
            "applications_submitted": self.applications_submitted,
            "applications_previewed": self.applications_previewed,
            "errors": self.errors,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "logs": self.logs[-20:]  # Last 20 logs
        }


# Global state instance
app_state = ApplicationState()


# ==========================================
# Routes
# ==========================================

@router.post("/run-agent")
async def run_agent(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    keyword: str = Form(...),
    location: str = Form(...),
    skills: str = Form(...),
    linkedin_email: str = Form(...),
    linkedin_password: str = Form(...),
    experience_level: str = Form("Any"),
    job_type: str = Form("Any"),
    salary_range: str = Form("Any"),
    max_jobs: int = Form(15),
    max_applications: int = Form(5),
    similarity_threshold: float = Form(0.6),
    auto_apply: str = Form("true"),
    first_name: str = Form(""),
    last_name: str = Form(""),
    phone_number: str = Form(""),
    linkedin_url: str = Form(""),
    portfolio_url: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    country: str = Form(""),
    # NEW: Accept comprehensive user profile as JSON string
    user_profile_json: str = Form("{}")
):
    """
    Start the automated job application agent with resume upload and user profile.
    
    This endpoint triggers the full workflow:
    1. Upload and parse resume
    2. Login to LinkedIn
    3. Search for jobs matching criteria
    4. Evaluate job matches using AI
    5. Auto-fill application forms with user profile data (NEW)
    6. Submit applications automatically
    
    NEW: The user_profile_json parameter accepts a JSON string with complete user info
    for automatic form filling (name, contact, address, work history, education, etc.)
    """
    if app_state.status == "running":
        raise HTTPException(400, "Agent is already running")
    
    try:
        # Save resume file
        upload_dir = "uploads/resumes"
        os.makedirs(upload_dir, exist_ok=True)
        
        resume_path = os.path.join(upload_dir, f"{linkedin_email}_{file.filename}")
        with open(resume_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"Resume saved for agent run: {resume_path}")
        
        # NEW: Parse user profile JSON
        try:
            user_profile = json.loads(user_profile_json) if user_profile_json else {}
        except json.JSONDecodeError:
            logger.warning("Invalid user_profile_json, using empty profile")
            user_profile = {}
        
        # Merge form fields into user profile (for backward compatibility)
        if not user_profile:
            user_profile = {}
        
        if first_name and not user_profile.get('first_name'):
            user_profile['first_name'] = first_name
        if last_name and not user_profile.get('last_name'):
            user_profile['last_name'] = last_name
        if phone_number and not user_profile.get('phone_number'):
            user_profile['phone_number'] = phone_number
        if city and not user_profile.get('city'):
            user_profile['city'] = city
        if state and not user_profile.get('state'):
            user_profile['state'] = state
        if country and not user_profile.get('country'):
            user_profile['country'] = country
        if linkedin_url and not user_profile.get('linkedin_url'):
            user_profile['linkedin_url'] = linkedin_url
        if portfolio_url and not user_profile.get('portfolio_url'):
            user_profile['portfolio_url'] = portfolio_url
        
        # Prepare data for workflow
        data = {
            "resume_path": resume_path,
            "keyword": keyword,
            "location": location,
            "skills": skills,
            "linkedin_email": linkedin_email,
            "linkedin_password": linkedin_password,
            "experience_level": experience_level,
            "job_type": job_type,
            "salary_range": salary_range,
            "max_jobs": max_jobs,
            "max_applications": max_applications,
            "similarity_threshold": similarity_threshold,
            "auto_apply": auto_apply.lower() in ("true", "1", "yes"),
            # Include individual fields for backward compatibility
            "first_name": first_name,
            "last_name": last_name,
            "phone_number": phone_number,
            "linkedin_url": linkedin_url,
            "portfolio_url": portfolio_url,
            "city": city,
            "state": state,
            "country": country,
            # NEW: Pass complete user profile to bot
            "user_profile": user_profile
        }
        
        # Reset state
        app_state.reset()
        app_state.status = "running"
        app_state.start_time = datetime.now()
        app_state.add_log("INFO", f"Agent started for {linkedin_email} with auto-fill profile")
        
        # Run in background
        background_tasks.add_task(execute_agent_workflow, data)
        
        return {
            "status": "started",
            "message": "Agent workflow started with auto-fill enabled",
            "job_id": "agent-run-1"
        }
        
    except Exception as e:
        logger.error(f"Failed to start agent: {e}", exc_info=True)
        app_state.status = "failed"
        app_state.add_log("ERROR", str(e))
        raise HTTPException(500, f"Failed to start agent: {e}")


@router.get("/agent/status")
async def get_agent_status():
    """Get current agent execution status."""
    return {
        "status": app_state.status,
        "detail": app_state.to_dict()
    }


@router.post("/agent/pause")
async def pause_agent():
    """Pause the running agent."""
    if app_state.status != "running":
        raise HTTPException(400, "Agent is not running")
    
    app_state.status = "paused"
    app_state.add_log("INFO", "Agent paused by user")
    
    return {"status": "paused"}


@router.post("/agent/resume")
async def resume_agent():
    """Resume a paused agent."""
    if app_state.status != "paused":
        raise HTTPException(400, "Agent is not paused")
    
    app_state.status = "running"
    app_state.add_log("INFO", "Agent resumed by user")
    
    return {"status": "resumed"}


@router.post("/agent/stop")
async def stop_agent():
    """Stop the running agent."""
    if app_state.status not in ["running", "paused"]:
        raise HTTPException(400, "Agent is not running or paused")
    
    app_state.status = "stopped"
    app_state.end_time = datetime.now()
    app_state.add_log("INFO", "Agent stopped by user")
    
    return {"status": "stopped"}


@router.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload and process resume for the authenticated user.
    Saves the file to uploads/resumes/, persists metadata to the database,
    and returns parsed resume data.
    """
    if not file.filename or not file.filename.lower().endswith(('.pdf', '.docx')):
        raise HTTPException(400, "Only PDF and DOCX files are supported")

    try:
        # Save file to disk
        upload_dir = "uploads/resumes"
        os.makedirs(upload_dir, exist_ok=True)

        safe_name = f"{current_user.id}_{file.filename}"
        file_path = os.path.join(upload_dir, safe_name)

        content = await file.read()
        if not content:
            raise HTTPException(400, "Uploaded file is empty")

        with open(file_path, "wb") as f:
            f.write(content)

        file_size = len(content)
        file_ext = os.path.splitext(file.filename)[1].lower().lstrip(".")

        logger.info(f"Resume uploaded successfully: {file_path} (user_id={current_user.id})")

        # Persist resume metadata to the database
        try:
            resume = ResumeRepository.create(
                db,
                user_id=int(current_user.id),  # type: ignore
                filename=file.filename,
                file_path=file_path,
                file_size_bytes=file_size,
                file_type=file_ext,
            )
            logger.info("Resume uploaded successfully (DB record id=%s)", resume.id)
        except Exception as db_exc:
            logger.error("DB insert failed for resume upload: %s", db_exc)
            raise HTTPException(
                status_code=500,
                detail="Resume file saved but failed to persist metadata to database.",
            )

        # Parse resume
        try:
            from backend.parsers.resume_parser import ResumeParser
            parser = ResumeParser()
            parsed_data = parser.parse(file_path)
        except Exception:
            parsed_data = {}

        resume_text = parsed_data.get("raw_text", "")
        skills = parsed_data.get("skills", [])
        experience = parsed_data.get("experience", [])
        education = parsed_data.get("education", [])
        contact = parsed_data.get("contact", {})

        return {
            "status": "success",
            "resume_id": resume.id,
            "filename": file.filename,
            "file_path": file_path,
            "text_length": len(resume_text),
            "parsed_data": {
                "skills": skills,
                "experience": experience,
                "education": education,
                "contact": contact,
            },
            "metadata": {
                "skills_count": len(skills),
                "experience_count": len(experience),
                "education_count": len(education),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading resume: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to process resume: {str(e)}")




# ── User Profile Update ───────────────────────────────────────────────────────

class UserProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    skills: Optional[List[str]] = None
    experience: Optional[str] = None


@router.post("/user/profile")
def update_user_profile(
    body: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save or update user profile fields (name, phone, location, skills, experience).
    Validates phone number format before persisting.
    """
    # Phone validation
    if body.phone:
        phone_err = validate_phone_number(body.phone)
        if phone_err:
            raise HTTPException(status_code=400, detail=phone_err)

    update_fields: Dict[str, Any] = {}
    if body.full_name is not None:
        update_fields["full_name"] = body.full_name
    if body.phone is not None:
        update_fields["phone"] = body.phone
    if body.location is not None:
        update_fields["location"] = body.location
    if body.skills is not None:
        update_fields["default_skills"] = body.skills
    if body.experience is not None:
        update_fields["default_experience_level"] = body.experience

    try:
        user = UserRepository.update(db, int(current_user.id), **update_fields)  # type: ignore
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("DB update failed for user profile: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save user profile. Please try again.")

    logger.info("User profile saved successfully for user_id=%s", current_user.id)
    return {
        "status": "success",
        "message": "User profile saved successfully",
        "user_id": user.id,
        "updated_fields": list(update_fields.keys()),
    }


@router.get("/user/profile")
def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the authenticated user's profile."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "phone": current_user.phone,
        "location": current_user.location,
        "skills": current_user.default_skills,
        "experience": current_user.default_experience_level,
        "created_at": str(current_user.created_at),
    }


# ── Cover Letter ──────────────────────────────────────────────────────────────

@router.post("/generate-cover-letter")
async def generate_cover_letter(
    job_title: str = Form(...),
    company: str = Form(...),
    job_description: str = Form(...),
    user_name: str = Form(...),
    resume_text: str = Form(...),
    ai_provider: str = Form("gemini"),
    api_key: Optional[str] = Form(None)
):
    """
    Generate AI-powered cover letter for a job application.
    Supports multiple AI providers: gemini, groq, openai
    """
    try:
        from backend.llm.multi_ai_service import MultiAIService, AIProvider
        
        # Validate provider
        valid_providers = ["gemini", "groq", "openai"]
        if ai_provider not in valid_providers:
            raise HTTPException(400, f"Invalid AI provider. Choose from: {', '.join(valid_providers)}")
        
        # Initialize AI service with specified provider and API key
        ai_service = MultiAIService(
            provider=ai_provider,  # type: ignore
            api_key=api_key
        )
        
        if not ai_service.is_available():
            raise HTTPException(
                400, 
                f"AI provider '{ai_provider}' is not available. Please check your API key."
            )
        
        cover_letter = ai_service.generate_cover_letter(
            job_title=job_title,
            company_name=company,
            job_description=job_description,
            resume_text=resume_text,
            user_name=user_name
        )
        
        if not cover_letter:
            raise HTTPException(500, "Failed to generate cover letter")
        
        # Save cover letter
        upload_dir = "uploads/cover_letters"
        os.makedirs(upload_dir, exist_ok=True)
        
        filename = f"{user_name}_{company}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        file_path = os.path.join(upload_dir, filename)
        
        with open(file_path, "w") as f:
            f.write(cover_letter)
        
        return {
            "status": "success",
            "cover_letter": cover_letter,
            "file_path": file_path
        }
        
    except Exception as e:
        logger.error(f"Error generating cover letter: {e}")
        raise HTTPException(500, f"Failed to generate cover letter: {e}")


@router.post("/answer-question")
async def answer_application_question(
    question: str = Form(...),
    job_title: str = Form(...),
    company: str = Form(...),
    resume_text: str = Form(...),
    max_words: Optional[int] = Form(None),
    ai_provider: str = Form("gemini"),
    api_key: Optional[str] = Form(None)
):
    """
    Generate intelligent answer to application question using AI.
    Supports multiple AI providers: gemini, groq, openai
    """
    try:
        from backend.llm.multi_ai_service import MultiAIService
        
        # Validate provider
        valid_providers = ["gemini", "groq", "openai"]
        if ai_provider not in valid_providers:
            raise HTTPException(400, f"Invalid AI provider. Choose from: {', '.join(valid_providers)}")
        
        # Initialize AI service
        ai_service = MultiAIService(
            provider=ai_provider,  # type: ignore
            api_key=api_key
        )
        
        if not ai_service.is_available():
            raise HTTPException(
                400, 
                f"AI provider '{ai_provider}' is not available. Please check your API key."
            )
        
        job_context = f"Job Title: {job_title}\nCompany: {company}"
        
        answer = ai_service.answer_question(
            question=question,
            resume_text=resume_text,
            job_context=job_context
        )
        
        if not answer:
            raise HTTPException(500, "Failed to generate answer")
        
        return {
            "status": "success",
            "question": question,
            "answer": answer
        }
        
    except Exception as e:
        logger.error(f"Error answering question: {e}")
        raise HTTPException(500, f"Failed to generate answer: {e}")


@router.post("/match-profile")
async def match_profile(
    resume_file_path: str = Form(...),
    job_description: str = Form(...),
    job_title: str = Form(""),
    company_name: str = Form(""),
    ai_provider: str = Form("gemini"),
    api_key: Optional[str] = Form(None)
):
    """
    Match a resume against a job description and return compatibility score.
    Returns match score (0-100), reasoning, strengths, concerns, and recommendation.
    
    Supports multiple AI providers: gemini, groq, openai
    """
    try:
        from backend.parsers.resume_parser import ResumeParser
        from backend.matching.profile_matcher import ProfileMatcher
        
        # Validate provider
        valid_providers = ["gemini", "groq", "openai"]
        if ai_provider not in valid_providers:
            raise HTTPException(400, f"Invalid AI provider. Choose from: {', '.join(valid_providers)}")
        
        # Check if resume file exists
        if not os.path.exists(resume_file_path):
            raise HTTPException(404, f"Resume file not found: {resume_file_path}")
        
        # Parse the resume
        parser = ResumeParser()
        resume_data = parser.parse(resume_file_path)
        
        # Match against job
        matcher = ProfileMatcher(ai_provider=ai_provider, api_key=api_key)  # type: ignore
        match_result = matcher.match_profile(
            resume_data=resume_data,
            job_description=job_description,
            job_title=job_title,
            company_name=company_name
        )
        
        return {
            "status": "success",
            "match_score": match_result["match_score"],
            "reasoning": match_result["reasoning"],
            "strengths": match_result["strengths"],
            "concerns": match_result["concerns"],
            "recommendation": match_result["recommendation"],
            "extracted_skills": resume_data.get("skills", []),
            "experience_count": len(resume_data.get("experience", []))
        }
        
    except FileNotFoundError as e:
        logger.error(f"Resume file not found: {e}")
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Error matching profile: {e}")
        raise HTTPException(500, f"Failed to match profile: {e}")


@router.post("/batch-match")
async def batch_match_jobs(
    resume_file_path: str = Form(...),
    jobs: str = Form(...),  # JSON string of job list
    min_score: int = Form(0),
    ai_provider: str = Form("gemini"),
    api_key: Optional[str] = Form(None)
):
    """
    Match a resume against multiple jobs and return sorted results.
    
    Args:
        resume_file_path: Path to the uploaded resume
        jobs: JSON string containing array of job objects with title, company, description
        min_score: Minimum match score to include (0-100)
        ai_provider: AI provider (gemini, groq, openai)
        api_key: Optional API key for the provider
    
    Returns:
        List of jobs with match results, sorted by score (highest first)
    """
    try:
        import json
        from backend.parsers.resume_parser import ResumeParser
        from backend.matching.profile_matcher import ProfileMatcher
        
        # Validate provider
        valid_providers = ["gemini", "groq", "openai"]
        if ai_provider not in valid_providers:
            raise HTTPException(400, f"Invalid AI provider. Choose from: {', '.join(valid_providers)}")
        
        # Check if resume file exists
        if not os.path.exists(resume_file_path):
            raise HTTPException(404, f"Resume file not found: {resume_file_path}")
        
        # Parse jobs JSON
        try:
            jobs_list = json.loads(jobs)
            if not isinstance(jobs_list, list):
                raise ValueError("Jobs must be an array")
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"Invalid JSON format for jobs: {e}")
        
        # Parse the resume
        parser = ResumeParser()
        resume_data = parser.parse(resume_file_path)
        
        # Match against all jobs
        matcher = ProfileMatcher(ai_provider=ai_provider, api_key=api_key)  # type: ignore
        results = matcher.batch_match(
            resume_data=resume_data,
            jobs=jobs_list,
            min_score=min_score
        )
        
        return {
            "status": "success",
            "total_jobs": len(jobs_list),
            "matched_jobs": len(results),
            "min_score": min_score,
            "results": results
        }
        
    except FileNotFoundError as e:
        logger.error(f"Resume file not found: {e}")
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Error in batch matching: {e}")
        raise HTTPException(500, f"Failed to batch match: {e}")


@router.get("/applications")
async def get_applications(
    user_email: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
):
    """
    Get application history with company names and LinkedIn job URLs.
    """
    try:
        from pathlib import Path
        import json
        
        # Load applications from JSON file
        applications_file = Path("data") / "applications.json"
        
        if not applications_file.exists():
            return {
                "applications": [],
                "total": 0,
                "page": 1,
                "limit": limit
            }
        
        with open(applications_file, 'r') as f:
            all_applications = json.load(f)
        
        # Filter by user_email if provided
        if user_email:
            all_applications = [
                app for app in all_applications 
                if app.get("user_id") == user_email
            ]
        
        # Filter by status if provided
        if status:
            all_applications = [
                app for app in all_applications 
                if app.get("result", {}).get("status") == status
            ]
        
        # Format applications for frontend
        formatted_apps = []
        for app in all_applications[:limit]:
            result = app.get("result", {})
            formatted_apps.append({
                "id": hash(result.get("url", "")),  # Generate ID from URL
                "title": result.get("title", "Unknown Position"),
                "company": result.get("company", "Unknown Company"),
                "url": result.get("url", ""),
                "status": result.get("status", "applied"),
                "applied_date": result.get("timestamp", ""),
                "match_score": result.get("match_score", 0)
            })
        
        return {
            "applications": formatted_apps,
            "total": len(formatted_apps),
            "page": 1,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Failed to load applications: {e}")
        return {
            "applications": [],
            "total": 0,
            "page": 1,
            "limit": limit
        }


@router.get("/jobs/search")
async def search_jobs(
    keywords: str,
    location: str = "Remote",
    max_results: int = 20
):
    """
    Search for jobs without automation (preview only).
    """
    try:
        # Try to import linkedin scraper, fallback to mock data if not available
        try:
            from backend.automation.linkedin_scraper import search_linkedin_jobs  # type: ignore
        except ImportError:
            # Return mock data if scraper not implemented yet
            logger.warning("LinkedIn scraper not implemented, returning mock data")
            return {
                "status": "success",
                "jobs": [
                    {
                        "id": "mock1",
                        "title": f"{keywords} - Mock Job 1",
                        "company": "Sample Company",
                        "location": location or "Remote",
                        "description": "This is a mock job listing. Implement linkedin_scraper.py for real jobs."
                    }
                ],
                "count": 1,
                "message": "Mock data - implement linkedin_scraper.py for real results"
            }
        
        jobs = search_linkedin_jobs(
            keywords=keywords,
            location=location,
            max_results=max_results
        )
        
        return {
            "jobs": jobs,
            "count": len(jobs)
        }
        
    except Exception as e:
        logger.error(f"Error searching jobs: {e}")
        raise HTTPException(500, f"Job search failed: {e}")


# ==========================================
# Background Task Functions
# ==========================================

async def execute_agent_workflow(data: Dict[str, Any]):
    """
    Execute the complete agent workflow in the background.
    """
    import asyncio
    
    try:
        app_state.current_phase = "initializing"
        app_state.add_log("INFO", "Initializing automation")
        
        # Initialize orchestrator
        from backend.agents.orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator()
        
        # Prepare search criteria - handle both old and new format
        keywords = data.get("keyword", data.get("keywords", ""))
        
        search_criteria = {
            "keywords": keywords,
            "location": data.get("location", "Remote"),
            "linkedin_email": data.get("linkedin_email", ""),
            "linkedin_password": data.get("linkedin_password", ""),
            "submit": data.get("auto_apply", data.get("submit", False)),
            "resume_path": data.get("resume_path", ""),
            "max_jobs": data.get("max_jobs", 15),
            "max_applications": data.get("max_applications", 5),
            "similarity_threshold": data.get("similarity_threshold", 0.6),
            # IMPORTANT: pass through the full user profile for Easy Apply auto-fill
            "user_profile": data.get("user_profile", {})
        }
        
        app_state.current_phase = "executing"
        app_state.add_log("INFO", f"Starting job search: {search_criteria['keywords']} in {search_criteria['location']}")
        
        # Execute workflow
        result = await orchestrator.execute_job_search_workflow(
            user_id="default_user",
            search_criteria=search_criteria
        )
        
        # Update state
        app_state.jobs_found = result.get("jobs_found", 0)
        if search_criteria["submit"]:
            app_state.applications_submitted = result.get("applications_created", 0)
        else:
            app_state.applications_previewed = result.get("applications_created", 0)
        
        app_state.status = "completed"
        app_state.end_time = datetime.now()
        app_state.current_phase = "completed"
        app_state.add_log("INFO", "Workflow completed successfully")
        
    except Exception as e:
        logger.error(f"Agent workflow error: {e}", exc_info=True)
        app_state.status = "failed"
        app_state.end_time = datetime.now()
        app_state.errors.append(str(e))
        app_state.add_log("ERROR", str(e))
