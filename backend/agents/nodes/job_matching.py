"""
Job matching node for LangGraph workflow.
Ranks and filters jobs based on resume match.
"""
from typing import Dict, Any, List
from backend.agents.graph_state import AgentState
import logging

logger = logging.getLogger(__name__)


def calculate_match_score(job: Dict[str, Any], skills: List[str]) -> float:
    """
    Calculate match score between job and candidate skills.
    Simple keyword overlap for now.
    """
    job_text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    
    matched_skills = [skill for skill in skills if skill.lower() in job_text]
    
    if not skills:
        return 50.0  # Neutral score
    
    score = (len(matched_skills) / len(skills)) * 100
    return min(score, 100.0)


def job_matching_node(state: AgentState) -> Dict[str, Any]:
    """
    Rank jobs by match score and filter based on criteria.
    """
    logger.info(f"[JobMatchingNode] Matching {len(state.get('job_listings', []))} jobs")
    
    job_listings = state.get("job_listings", [])
    skills = state.get("extracted_skills", [])
    min_salary = state.get("min_salary")
    max_applications = state.get("max_applications", 10)
    
    # Calculate match scores
    ranked_jobs = []
    for job in job_listings:
        match_score = calculate_match_score(job, skills)
        job_with_score = {**job, "match_score": match_score}
        ranked_jobs.append(job_with_score)
    
    # Sort by match score (highest first)
    ranked_jobs.sort(key=lambda x: x["match_score"], reverse=True)
    
    # Filter by salary if specified
    if min_salary:
        ranked_jobs = [
            job for job in ranked_jobs
            if job.get("salary_min", 0) >= min_salary
        ]
    
    # Take top N matches
    top_matches = ranked_jobs[:max_applications]
    
    if top_matches:
        logger.info(f"[JobMatchingNode] Top match score: {top_matches[0]['match_score']:.1f}%")
    else:
        logger.warning("[JobMatchingNode] No jobs passed filtering criteria")
    logger.info(f"[JobMatchingNode] Selected {len(top_matches)} jobs for application")
    
    return {
        "ranked_jobs": ranked_jobs,
        "top_matches": top_matches,
        "filtered_count": len(top_matches),
        "current_step": "job_matching_completed",
    }
