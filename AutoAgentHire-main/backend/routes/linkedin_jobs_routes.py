"""FastAPI Routes for LinkedIn Recommended Jobs."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import sys
import os
import subprocess
import json
import asyncio

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from matching.job_filter import get_available_roles
from matching.job_filter_production import filter_jobs_batch, ROLE_TAXONOMY

router = APIRouter(prefix="/api/linkedin", tags=["LinkedIn Jobs"])


def _resolve_python_executable() -> str:
    """Use workspace venv Python when available to guarantee Playwright deps."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    venv_python = os.path.join(repo_root, ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        return venv_python
    return sys.executable


def _run_recommended_jobs_subprocess(email: Optional[str], password: Optional[str]) -> list[dict]:
    """Run LinkedIn scraping in a separate process to avoid Windows event-loop issues."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    script_path = os.path.join(repo_root, "backend", "automation", "run_scraper.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = repo_root

    cmd = [
        _resolve_python_executable(),
        script_path,
        email or "None",
        password or "None",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            cwd=repo_root,
            timeout=240,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Scraper timed out after 240 seconds") from exc

    if result.returncode != 0:
        stderr_text = (result.stderr or "").strip()
        stdout_text = (result.stdout or "").strip()
        raise RuntimeError(
            "Scraper process failed. "
            f"stderr={stderr_text[:800]} stdout={stdout_text[:800]}"
        )

    output = result.stdout or ""
    start_marker = "---JSON_OUTPUT_START---"
    end_marker = "---JSON_OUTPUT_END---"
    if start_marker not in output or end_marker not in output:
        raise RuntimeError(
            "Scraper output parsing failed. "
            f"stdout={output[:1000]} stderr={(result.stderr or '')[:500]}"
        )

    json_str = output.split(start_marker, 1)[1].split(end_marker, 1)[0].strip()
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Scraper JSON decode failed: {exc}") from exc

    if not isinstance(parsed, list):
        raise RuntimeError("Scraper returned invalid payload format (expected list)")
    return parsed


class RecommendedJobsRequest(BaseModel):
    """Request body for fetching LinkedIn recommended jobs."""

    linkedin_email: Optional[str] = None
    linkedin_password: Optional[str] = None
    max_jobs: int = 25
    job_role: Optional[str] = "cloud_engineer"
    enable_filtering: bool = True


@router.post("/recommended-jobs")
async def get_recommended_jobs(payload: RecommendedJobsRequest):
    """Fetch recommended jobs from LinkedIn and apply production filters."""
    try:
        print("[JOBS] Received request for recommended jobs")
        print(f"[JOBS]   Role filter: {payload.job_role}")
        print(f"[JOBS]   Filtering enabled: {payload.enable_filtering}")

        raw_jobs = await asyncio.to_thread(
            _run_recommended_jobs_subprocess,
            payload.linkedin_email,
            payload.linkedin_password,
        )
        print(f"[JOBS] Fetched {len(raw_jobs)} raw jobs from LinkedIn")

        jobs_for_filtering = []
        for job in raw_jobs:
            jobs_for_filtering.append(
                {
                    "job_id": job.get("url", ""),
                    "title": job.get("title", ""),
                    # Recommended jobs often lack full descriptions; keep this empty
                    # so skill-based filters don't run on placeholder content.
                    "description": "",
                    "company": job.get("company", "Unknown Company"),
                    "location": job.get("location", "Unknown Location"),
                    "posted_date": datetime.now() - timedelta(days=1),
                    "applicant_count": 0,
                    "apply_button_present": True,
                    "apply_link": job.get("url", ""),
                    "index": job.get("index", 0),
                }
            )

        if payload.enable_filtering and payload.job_role:
            role_key = payload.job_role.lower().replace(" ", "_")
            print(f"[JOBS] Applying production filtering for role: {role_key}")

            if role_key not in ROLE_TAXONOMY:
                filtered_jobs = jobs_for_filtering
                filter_warning = f"Role '{payload.job_role}' not recognized. Showing all jobs."
            else:
                filtered_jobs = filter_jobs_batch(
                    jobs=jobs_for_filtering,
                    role_key=role_key,
                    skip_freshness=True,
                    return_reasons=True,
                )
                print(
                    f"[JOBS] Production filter: {len(filtered_jobs)}/{len(jobs_for_filtering)} jobs passed"
                )
                if len(filtered_jobs) == 0:
                    filter_warning = (
                        f"No jobs matched strict '{payload.job_role}' criteria. "
                        "Try disabling filtering to see all recommendations."
                    )
                else:
                    filter_warning = None
        else:
            filtered_jobs = jobs_for_filtering
            filter_warning = None

        result_jobs = []
        for idx, job in enumerate(filtered_jobs):
            result_jobs.append(
                {
                    "title": job["title"],
                    "company": job["company"],
                    "location": job["location"],
                    "url": job["apply_link"],
                    "role": payload.job_role if payload.job_role else "general",
                    "index": idx + 1,
                }
            )

        if payload.max_jobs and payload.max_jobs > 0:
            result_jobs = result_jobs[: payload.max_jobs]

        response_message = (
            f"Successfully fetched {len(result_jobs)} relevant "
            f"{payload.job_role or 'jobs'} (filtered from {len(raw_jobs)} total)"
        )
        if filter_warning:
            response_message = filter_warning

        return {
            "status": "success",
            "total": len(result_jobs),
            "filtered_from": len(raw_jobs),
            "jobs": result_jobs,
            "message": response_message,
            "filter_applied": payload.enable_filtering,
            "warning": filter_warning,
        }

    except Exception as e:
        msg = str(e) or repr(e)
        import traceback

        print(f"[JOBS] ERROR in recommended jobs endpoint: {msg}")
        traceback.print_exc()

        if isinstance(msg, str) and (
            "Login failed" in msg
            or "Login not confirmed" in msg
            or "checkpoint" in msg.lower()
            or "authwall" in msg.lower()
        ):
            return {
                "status": "error",
                "total": 0,
                "jobs": [],
                "message": msg,
            }

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch recommended jobs: {msg}",
        )


@router.get("/recommended-jobs/health")
async def health_check():
    """Health check endpoint for LinkedIn jobs service."""
    return {
        "status": "healthy",
        "service": "LinkedIn Recommended Jobs",
        "endpoints": [
            "/api/linkedin/recommended-jobs",
            "/api/linkedin/available-roles",
        ],
    }


@router.get("/available-roles")
async def get_available_roles_endpoint():
    """Get list of available job roles for filtering."""
    roles = get_available_roles()
    role_display_names = {
        "machine_learning_engineer": "Machine Learning Engineer",
        "data_scientist": "Data Scientist",
        "ai_engineer": "AI Engineer",
        "software_engineer": "Software Engineer",
        "data_engineer": "Data Engineer",
        "mlops_engineer": "MLOps Engineer",
        "research_scientist": "Research Scientist",
        "backend_engineer": "Backend Engineer",
        "frontend_engineer": "Frontend Engineer",
        "fullstack_engineer": "Fullstack Engineer",
        "cloud_engineer": "Cloud Engineer",
        "devops_engineer": "DevOps Engineer",
    }

    return {
        "status": "success",
        "total": len(roles),
        "roles": [
            {
                "key": role,
                "display_name": role_display_names.get(role, role.replace("_", " ").title()),
            }
            for role in roles
        ],
    }
