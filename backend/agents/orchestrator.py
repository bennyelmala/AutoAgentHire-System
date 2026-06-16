"""
Agent Orchestrator - Coordinates multiple agents.
Uses CrewAI Crew to manage agent workflow.
"""
from typing import Dict, Any
# from crewai import Crew, Process
# from backend.agents.job_search_agent import JobSearchAgent
# from backend.agents.analysis_agent import AnalysisAgent
# from backend.agents.application_agent import ApplicationAgent


class AgentOrchestrator:
    """
    Orchestrates multiple agents in a coordinated workflow.
    """
    
    def __init__(self):
        """Initialize the orchestrator with all agents."""
        # TODO: Initialize all agents
        # self.job_search_agent = JobSearchAgent()
        # self.analysis_agent = AnalysisAgent()
        # self.application_agent = ApplicationAgent()
        pass
    
    async def execute_job_search_workflow(
        self,
        user_id: str,
        search_criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the complete job search and application workflow.
        
        Workflow:
        1. Job Search Agent discovers opportunities
        2. Analysis Agent evaluates and ranks jobs
        3. Application Agent handles top matches
        
        Args:
            user_id: User identifier
            search_criteria: Job search parameters
            
        Returns:
            Workflow execution results
        """
        # Use the comprehensive AutoAgentHireBot for full automation
        from backend.agents.autoagenthire_bot import AutoAgentHireBot
        from backend.agents.state import set_status
        from backend.config import settings
        import os

        set_status("running", {"phase": "starting"})

        # Use credentials from search_criteria
        linkedin_email = search_criteria.get("linkedin_email") or settings.LINKEDIN_EMAIL or os.getenv("LINKEDIN_EMAIL", "")
        linkedin_password = search_criteria.get("linkedin_password") or settings.LINKEDIN_PASSWORD or os.getenv("LINKEDIN_PASSWORD", "")
        
        if not linkedin_email or not linkedin_password:
            set_status("failed", {"reason": "missing_credentials", "message": "LinkedIn credentials not provided"})
            return {"status": "failed", "reason": "missing_credentials", "message": "Please provide LinkedIn credentials"}

        # Prepare configuration for AutoAgentHireBot
        keywords = search_criteria.get("keywords", "") or search_criteria.get("keyword", "") or os.getenv("JOB_KEYWORDS", "Python Developer")
        location = search_criteria.get("location", "") or os.getenv("JOB_LOCATION", "Remote")
        resume_path = search_criteria.get("resume_path", "")
        auto_apply = search_criteria.get("auto_apply", False) or search_criteria.get("submit", False)
        max_jobs = search_criteria.get("max_jobs", 5)
        max_applications = search_criteria.get("max_applications", 5)
        similarity_threshold = search_criteria.get("similarity_threshold", 0.6)
        
        bot_config = {
            "linkedin_email": linkedin_email,
            "linkedin_password": linkedin_password,
            "keyword": keywords,
            "location": location,
            "resume_path": resume_path,
            "auto_apply": auto_apply,
            "max_jobs": max_applications,  # How many to apply to
            "max_results": max_jobs,  # How many to search
            "similarity_threshold": similarity_threshold,
            # Pass full user profile through for form auto-fill
            "user_profile": search_criteria.get("user_profile", {})
        }
        
        # Set credentials in environment for bot to use
        os.environ["LINKEDIN_EMAIL"] = linkedin_email
        os.environ["LINKEDIN_PASSWORD"] = linkedin_password
        
        # Set user profile information from search_criteria or fallback to .env
        os.environ["FIRST_NAME"] = search_criteria.get("first_name") or os.getenv("FIRST_NAME", "")
        os.environ["LAST_NAME"] = search_criteria.get("last_name") or os.getenv("LAST_NAME", "")
        os.environ["PHONE_NUMBER"] = search_criteria.get("phone_number") or os.getenv("PHONE_NUMBER", "")
        os.environ["LINKEDIN_URL"] = search_criteria.get("linkedin_url") or os.getenv("LINKEDIN_URL", "")
        os.environ["PORTFOLIO_URL"] = search_criteria.get("portfolio_url") or os.getenv("PORTFOLIO_URL", "")
        os.environ["CITY"] = search_criteria.get("city") or os.getenv("CITY", "")
        os.environ["STATE"] = search_criteria.get("state") or os.getenv("STATE", "")
        os.environ["COUNTRY"] = search_criteria.get("country") or os.getenv("COUNTRY", "")

        bot = AutoAgentHireBot(config=bot_config)

        try:
            set_status("running", {"phase": "initializing", "message": f"Starting automation for {linkedin_email}"})
            
            # Run the full automation workflow
            result = await bot.run_automation()
            
            # Update status with results
            jobs_found = result.get("jobs_found", 0)
            applications_successful = result.get("applications_successful", 0)
            applications_attempted = result.get("applications_attempted", 0)
            
            set_status("running", {"phase": "completed", "jobs_found": jobs_found, "applications": applications_successful})

            # Persist results
            try:
                from backend.agents.storage import save_application_result
                from datetime import datetime
                
                for job in result.get("jobs", []):
                    if job.get("application_status") == "SUCCESS":
                        save_application_result({
                            "user_id": user_id,
                            "result": {
                                "url": job.get("url", ""),
                                "title": job.get("title", "Unknown Position"),
                                "company": job.get("company", "Unknown Company"),
                                "status": "applied",
                                "timestamp": job.get("application_timestamp") or datetime.now().isoformat(),
                                "match_score": job.get("similarity_score", 0)
                            }
                        })
            except Exception as e:
                print(f"Warning: Could not save results: {e}")

            set_status("completed", {
                "jobs_found": jobs_found,
                "applications_attempted": applications_attempted,
                "applications_successful": applications_successful,
                "summary": result.get("summary", ""),
                "duration": result.get("duration_seconds", 0)
            })
            
            return {
                "jobs_found": jobs_found,
                "applications_created": applications_successful,
                "applications_attempted": applications_attempted,
                "status": "completed",
                "summary": result.get("summary", "")
            }
            
        except Exception as e:
            print(f"❌ Automation error: {e}")
            import traceback
            traceback.print_exc()
            set_status("failed", {"reason": str(e)})
            return {
                "status": "failed",
                "reason": str(e),
                "jobs_found": 0,
                "applications_created": 0
            }
        finally:
            try:
                if bot.browser:
                    await bot.browser.close()
            except Exception:
                pass
    
    async def execute_daily_automation(self) -> Dict[str, Any]:
        """
        Execute daily automation tasks for all users.
        
        Returns:
            Daily automation results
        """
        # TODO: Implement daily automation
        # 1. Get all users with automation enabled
        # 2. Run job search for each user
        # 3. Analyze new opportunities
        # 4. Send notifications
        
        return {
            "users_processed": 0,
            "jobs_found": 0,
            "notifications_sent": 0
        }
