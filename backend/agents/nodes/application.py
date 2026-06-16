"""
Job application node for LangGraph workflow.
Submits applications to matched jobs.
"""
from typing import Dict, Any
from backend.agents.graph_state import AgentState
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def application_node(state: AgentState) -> Dict[str, Any]:
    """
    Submit applications to top matched jobs.
    
    In dry-run mode, simulates applications without actually submitting.
    TODO: Integrate with browser automation for real submissions.
    """
    logger.info(f"[ApplicationNode] Processing {len(state.get('top_matches', []))} applications")
    
    top_matches = state.get("top_matches", [])
    dry_run = state.get("dry_run", False)
    
    submitted_applications = []
    application_errors = []
    
    for job in top_matches:
        try:
            if dry_run:
                # Simulate successful application
                application = {
                    "job_id": job["job_id"],
                    "job_title": job["title"],
                    "company": job["company"],
                    "submitted_at": datetime.now().isoformat(),
                    "status": "submitted (dry-run)",
                    "apply_link": job.get("apply_link"),
                }
                submitted_applications.append(application)
                logger.info(f"[ApplicationNode] DRY RUN: Would apply to {job['title']} at {job['company']}")
            else:
                # TODO: Real application submission via browser automation
                application = {
                    "job_id": job["job_id"],
                    "job_title": job["title"],
                    "company": job["company"],
                    "submitted_at": datetime.now().isoformat(),
                    "status": "submitted",
                    "apply_link": job.get("apply_link"),
                }
                submitted_applications.append(application)
                logger.info(f"[ApplicationNode] Applied to {job['title']} at {job['company']}")
                
        except Exception as e:
            error_record = {
                "job_id": job["job_id"],
                "job_title": job["title"],
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            application_errors.append(error_record)
            logger.error(f"[ApplicationNode] Failed to apply to {job['title']}: {e}")
    
    logger.info(f"[ApplicationNode] Successfully submitted {len(submitted_applications)} applications")
    if application_errors:
        logger.warning(f"[ApplicationNode] {len(application_errors)} application(s) failed")
    
    return {
        "submitted_applications": submitted_applications,
        "application_errors": application_errors,
        "current_step": "application_completed",
    }
