"""
Job search node for LangGraph workflow.
Searches for relevant job openings based on user criteria.
"""
from typing import Dict, Any
from backend.agents.graph_state import AgentState
import logging

logger = logging.getLogger(__name__)


def job_search_node(state: AgentState) -> Dict[str, Any]:
    """
    Search for jobs matching user preferences and skills.
    
    For now, returns mock job data.
    TODO: Integrate with LinkedIn scraper / job search agents.
    """
    logger.info(f"[JobSearchNode] Searching jobs for roles: {state.get('target_roles')}")
    
    target_roles = state.get("target_roles", [])
    locations = state.get("desired_locations", [])
    
    # Generate search queries
    search_queries = []
    for role in target_roles:
        role_readable = role.replace("_", " ").title()
        for location in (locations or ["Remote"]):
            search_queries.append(f"{role_readable} in {location}")
    
    # Mock job listings (simulate search results)
    job_listings = [
        {
            "job_id": "job_ml_001",
            "title": "Machine Learning Engineer",
            "company": "TechCorp AI",
            "location": "San Francisco, CA",
            "description": "We're looking for an ML engineer with experience in PyTorch and NLP...",
            "apply_link": "https://linkedin.com/jobs/ml-001",
            "posted_date": "2025-01-05",
            "salary_min": 150000,
            "salary_max": 200000,
            "is_open": True,
        },
        {
            "job_id": "job_ds_002",
            "title": "Senior Data Scientist",
            "company": "DataDriven Inc",
            "location": "Remote",
            "description": "Looking for a data scientist with Python, SQL, and ML model deployment experience...",
            "apply_link": "https://linkedin.com/jobs/ds-002",
            "posted_date": "2025-01-04",
            "salary_min": 130000,
            "salary_max": 180000,
            "is_open": True,
        },
        {
            "job_id": "job_ml_003",
            "title": "ML Engineer - Computer Vision",
            "company": "VisionTech",
            "location": "New York, NY",
            "description": "Computer vision ML engineer needed for autonomous systems...",
            "apply_link": "https://linkedin.com/jobs/ml-003",
            "posted_date": "2025-01-03",
            "salary_min": 160000,
            "salary_max": 210000,
            "is_open": True,
        },
    ]
    
    logger.info(f"[JobSearchNode] Found {len(job_listings)} jobs")
    
    return {
        "job_listings": job_listings,
        "search_queries": search_queries,
        "total_jobs_found": len(job_listings),
        "current_step": "job_search_completed",
    }
