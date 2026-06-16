"""
AutoAgentHire FastAPI Endpoints
Handles frontend requests and automation orchestration
"""

import asyncio
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

# Lazy-load to avoid slow startup (autoagenthire_bot imports torch/playwright at module level)
_AutoAgentHireBot = None

def _get_bot():
    global _AutoAgentHireBot
    if _AutoAgentHireBot is None:
        from backend.agents.autoagenthire_bot import AutoAgentHireBot
        _AutoAgentHireBot = AutoAgentHireBot
    return _AutoAgentHireBot

router = APIRouter(prefix="/api", tags=["AutoAgentHire"])

# Store active automation tasks (used by /autoagenthire/start and status endpoints)
active_tasks = {}


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


@router.get("/agent/status")
async def agent_status():
    """Deprecated shim: agent status lives under `/api/agent/status` (api_routes)."""
    raise HTTPException(
        status_code=410,
        detail="This endpoint moved to /api/agent/status"
    )


from pydantic import BaseModel

class JobSearchRequest(BaseModel):
    linkedin_email: Optional[str] = None
    linkedin_password: Optional[str] = None
    job_role: Optional[str] = "Software Engineer"
    location: Optional[str] = "United States"
    remote_only: Optional[bool] = False
    easy_apply_only: Optional[bool] = True
    max_results: Optional[int] = 25

class StartAutomationRequest(BaseModel):
    linkedin_email: Optional[str] = None
    linkedin_password: Optional[str] = None
    job_role: Optional[str] = "Software Engineer"
    location: Optional[str] = "United States"
    max_applications: Optional[int] = 10
    easy_apply_only: Optional[bool] = True
    resume_path: Optional[str] = None
    user_profile: Optional[dict] = None

class ApplySingleRequest(BaseModel):
    linkedin_email: Optional[str] = None
    linkedin_password: Optional[str] = None
    job_url: str
    job_title: Optional[str] = None
    company: Optional[str] = None
    resume_path: Optional[str] = None
    user_profile: Optional[dict] = None
    # Safety first: by default do NOT click the final Submit button.
    dry_run: Optional[bool] = True


@router.get("/api/applications")
async def get_applications():
    """
    Get all submitted job applications
    """
    try:
        from pathlib import Path
        import json
        
        applications_file = Path("data/applications.json")
        
        if not applications_file.exists():
            return {
                "status": "success",
                "applications": [],
                "count": 0
            }
        
        with open(applications_file, 'r') as f:
            applications = json.load(f)
        
        return {
            "status": "success",
            "applications": applications,
            "count": len(applications)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/autoagenthire/search-jobs")
async def search_linkedin_jobs(request: JobSearchRequest):
    """
    Search for LinkedIn jobs without applying
    Returns job listings with URLs that users can click
    """
    import json
    
    try:
        # Get credentials from request (frontend-only)
        linkedin_email = (request.linkedin_email or "").strip()
        linkedin_password = request.linkedin_password or ""
        
        # Check if credentials are placeholder values or not configured
        is_placeholder = (
            not linkedin_email or 
            not linkedin_password or
            'example.com' in linkedin_email or
            'your-' in linkedin_email.lower() or
            'your-' in linkedin_password.lower() or
            linkedin_password == 'your-encrypted-password'
        )
        
        if is_placeholder:
            # Return sample jobs if credentials not configured
            return {
                "status": "demo",
                "message": "LinkedIn credentials not configured. Showing sample jobs.",
                "jobs": generate_sample_jobs(request.job_role or "Software Engineer", request.location or "United States", request.max_results or 25)
            }
        
        # Initialize bot for job search only
        config = {
            'keyword': request.job_role or "Software Engineer",
            'location': request.location or "United States",
            'max_jobs': min(request.max_results or 25, 50),
            'easy_apply_only': request.easy_apply_only,
            'search_only': True,  # Don't apply, just search
            'linkedin_email': linkedin_email,
            'linkedin_password': linkedin_password,
        }
        
        print(f"\n Searching LinkedIn for: {config['keyword']} in {config['location']}")
        
        bot = _get_bot()(config)
        
        # Only search, don't apply
        jobs = await bot.search_jobs_only()
        
        return {
            "status": "success",
            "message": f"Found {len(jobs)} jobs",
            "jobs": jobs
        }
        
    except Exception as e:
        print(f"❌ Job search error: {str(e)}")
        # Return sample jobs on error
        return {
            "status": "fallback",
            "message": f"Using sample data: {str(e)}",
            "jobs": generate_sample_jobs(request.job_role or "Software Engineer", request.location or "United States", request.max_results or 25)
        }


@router.post("/autoagenthire/start")
async def start_automation(request: StartAutomationRequest):
    """Start the full automation process"""
    import uuid
    
    run_id = str(uuid.uuid4())[:8]
    
    try:
        linkedin_email = (request.linkedin_email or "").strip()
        linkedin_password = request.linkedin_password or ""

        if not linkedin_email or not linkedin_password:
            return {
                "status": "error",
                "message": "LinkedIn credentials are required (frontend must send linkedin_email/linkedin_password)"
            }
        
        config = {
            'keyword': request.job_role or "Software Engineer",
            'location': request.location or "United States",
            'max_applications': min(request.max_applications or 10, 20),
            'easy_apply_only': request.easy_apply_only,
            'auto_apply': True,
            # Frontend-supplied credentials (do not rely on backend .env)
            'linkedin_email': linkedin_email,
            'linkedin_password': linkedin_password,
            # Add resume and user profile if provided
            'resume_path': request.resume_path,
            'user_profile': request.user_profile or {},
        }
        
        # Store task
        active_tasks[run_id] = {
            "status": "started",
            "config": config
        }
        
        # Run in background
        asyncio.create_task(run_automation_task(run_id, config))
        
        return {
            "status": "started",
            "run_id": run_id,
            "message": f"Automation started. Applying to up to {config['max_applications']} jobs."
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/autoagenthire/run/{run_id}")
async def get_automation_run(run_id: str):
    """Get status/result for a previously started background automation run."""
    if run_id not in active_tasks:
        raise HTTPException(status_code=404, detail="run_id not found")
    return {
        "run_id": run_id,
        **active_tasks[run_id],
    }


@router.post("/autoagenthire/apply-single")
async def apply_single_job(request: ApplySingleRequest):
    """Apply to a single job"""
    try:
        linkedin_email = (request.linkedin_email or "").strip()
        linkedin_password = request.linkedin_password or ""
        
        if not linkedin_email or not linkedin_password:
            return {
                "success": False,
                "message": "LinkedIn credentials are required (frontend must send linkedin_email/linkedin_password)"
            }
        
        config = {
            'single_job_url': request.job_url,
            'job_title': request.job_title,
            'company': request.company,
            'auto_apply': True,
            # Default to safe mode unless explicitly enabled in request payload
            'dry_run': getattr(request, 'dry_run', True),
            'linkedin_email': linkedin_email,
            'linkedin_password': linkedin_password,
            # Add resume and user profile if provided
            'resume_path': request.resume_path,
            'user_profile': request.user_profile or {},
        }

        bot = _get_bot()(config)
        try:
            result = await bot.apply_to_single_job(request.job_url)
        finally:
            try:
                await bot.close()
            except Exception:
                pass

        return {
            "success": result.get('success', False),
            "status": result.get('status', None),
            "message": result.get('message', 'Application processed'),
            "job": result.get('job', None)
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


async def run_automation_task(run_id: str, config: dict):
    """Background task to run automation"""
    try:
        bot = _get_bot()(config)
        result = await bot.run_automation()
        
        active_tasks[run_id] = {
            "status": "completed",
            "result": result
        }
        
        # Save to applications
        if result.get('applications_successful', 0) > 0:
            save_applications_to_file(result.get('jobs', []))
            
    except Exception as e:
        active_tasks[run_id] = {
            "status": "error",
            "error": str(e)
        }


def save_applications_to_file(jobs: list):
    """Save successful applications to applications.json"""
    import json
    from datetime import datetime
    
    applications_file = Path("data/applications.json")
    applications_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing
    existing = []
    if applications_file.exists():
        try:
            with open(applications_file, 'r') as f:
                existing = json.load(f)
        except:
            existing = []
    
    # Add new applications
    for job in jobs:
        if job.get('applied', False):
            app = {
                "id": len(existing) + 1,
                "title": job.get('title', 'Unknown'),
                "company": job.get('company', 'Unknown'),
                "url": job.get('url', ''),
                "status": "applied",
                "applied_date": datetime.now().isoformat(),
                "match_score": int(job.get('match_score', 0) * 100) if job.get('match_score', 0) <= 1 else job.get('match_score', 80)
            }
            existing.append(app)
    
    # Save
    with open(applications_file, 'w') as f:
        json.dump(existing, f, indent=2)


def generate_sample_jobs(job_role: str, location: str, count: int = 10) -> list:
    """Generate sample LinkedIn jobs for demo/testing"""
    import random
    
    companies = [
        "Google", "Microsoft", "Amazon", "Apple", "Meta", "Netflix", "Tesla",
        "Salesforce", "Adobe", "Oracle", "IBM", "Intel", "Cisco", "VMware",
        "Uber", "Airbnb", "Spotify", "Stripe", "Shopify", "Slack"
    ]
    
    locations = [
        f"{location}", "Remote", f"Remote - {location}", 
        "San Francisco, CA", "New York, NY", "Seattle, WA", "Austin, TX"
    ]
    
    jobs = []
    for i in range(min(count, 25)):
        company = random.choice(companies)
        job_id = random.randint(3000000000, 4000000000)
        
        jobs.append({
            "id": str(job_id),
            "title": f"{job_role}" if i % 3 == 0 else f"Senior {job_role}" if i % 3 == 1 else f"Staff {job_role}",
            "company": company,
            "location": random.choice(locations),
            "salary": f"${random.randint(100, 250)}k - ${random.randint(250, 400)}k",
            "posted": f"{random.randint(1, 7)} days ago",
            "match_score": random.randint(75, 98),
            "url": f"https://www.linkedin.com/jobs/view/{job_id}",
            "is_easy_apply": True,
            "description": f"Join {company} as a {job_role}. We're looking for talented individuals to help build the future."
        })
    
    return jobs


def register_autoagenthire_routes(app):
    """Register AutoAgentHire routes with the main app"""
    app.include_router(router)
    print("✅ AutoAgentHire routes registered")
