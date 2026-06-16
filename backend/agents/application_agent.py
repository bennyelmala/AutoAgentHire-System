"""
Application Agent - Automates job applications.
Handles cover letter generation and form filling.
Enhanced with AI-powered profile matching to auto-apply only to high-match jobs.
"""
from typing import Dict, Any, Optional
import logging
# from crewai import Agent
# from backend.agents.tools import CoverLetterTool, FormFillerTool

logger = logging.getLogger(__name__)


class ApplicationAgent:
    """
    Agent responsible for automating job applications.
    
    Role: Application Automation Specialist
    Goal: Submit high-quality job applications
    Enhanced: Smart auto-apply based on profile match scores
    """
    
    def __init__(
        self,
        ai_provider: str = "gemini",
        api_key: Optional[str] = None,
        min_auto_apply_score: int = 70
    ):
        """
        Initialize the application agent.
        
        Args:
            ai_provider: AI provider for cover letter generation (gemini, groq, openai)
            api_key: Optional API key for the AI provider
            min_auto_apply_score: Minimum match score required for auto-apply (default: 70)
        """
        self.ai_provider = ai_provider
        self.api_key = api_key
        self.min_auto_apply_score = min_auto_apply_score
        
        # Initialize AI service for cover letter generation
        try:
            from backend.llm.multi_ai_service import MultiAIService
            self.ai_service = MultiAIService(
                provider=ai_provider,  # type: ignore
                api_key=api_key
            )
        except Exception as e:
            logger.warning(f"Failed to initialize AI service: {e}")
            self.ai_service = None
    
    async def apply_to_job(
        self,
        job: Dict[str, Any],
        user_id: str,
        resume_data: Optional[Dict[str, Any]] = None,
        auto_submit: bool = False,
        force_apply: bool = False
    ) -> Dict[str, Any]:
        """
        Apply to a job posting with intelligent auto-apply based on match score.
        
        Args:
            job: Job dictionary with optional 'match' field
            user_id: User identifier
            resume_data: Optional parsed resume data
            auto_submit: Whether to enable auto-submit mode
            force_apply: Force apply regardless of match score
            
        Returns:
            Application submission result with status and reasoning
        """
        try:
            # Check if should auto-apply
            should_apply = self._should_auto_apply(job, force_apply)
            
            if not should_apply and auto_submit:
                return {
                    "status": "skipped",
                    "job_id": job.get("id", "unknown"),
                    "job_title": job.get("title", "Unknown"),
                    "company": job.get("company", "Unknown"),
                    "match_score": job.get("match", {}).get("match_score", 0),
                    "reason": "Match score below threshold or recommendation is not 'Apply'",
                    "message": "Job skipped - does not meet auto-apply criteria"
                }
            
            # Generate cover letter if AI service is available
            cover_letter = None
            if self.ai_service and resume_data:
                cover_letter = await self.generate_cover_letter(
                    resume_data=resume_data,
                    job_description=job.get("description", ""),
                    job_title=job.get("title", ""),
                    company_name=job.get("company", "")
                )
            
            # Perform actual Easy Apply via AutoAgentHireBot.
            # By default, we run in dry-run mode unless auto_submit=True.
            from backend.agents.autoagenthire_bot import AutoAgentHireBot

            bot_config = {
                "linkedin_email": None,
                "linkedin_password": None,
                "resume_path": None,
                "dry_run": not bool(auto_submit),
                # metadata for reporting
                "job_title": job.get("title"),
                "company": job.get("company"),
            }

            bot = AutoAgentHireBot(bot_config)
            try:
                result = await bot.apply_to_single_job(job.get("url", ""))
            finally:
                try:
                    await bot.close()
                except Exception:
                    pass

            # Normalize
            status = "submitted" if result.get("success") and auto_submit else "pending_review"
            if result.get("success") and bot_config["dry_run"]:
                status = "dry_run"

            return {
                "status": status,
                "job_id": job.get("id", "unknown"),
                "job_title": job.get("title", "Unknown"),
                "company": job.get("company", "Unknown"),
                "match_score": job.get("match", {}).get("match_score", 0),
                "cover_letter": cover_letter[:200] + "..." if cover_letter else None,
                "message": result.get("message", "Application processed"),
                "details": result,
            }
            
        except Exception as e:
            logger.error(f"Error applying to job: {e}")
            return {
                "status": "error",
                "job_id": job.get("id", "unknown"),
                "message": f"Failed to apply: {str(e)}"
            }
    
    def _should_auto_apply(self, job: Dict[str, Any], force: bool = False) -> bool:
        """
        Determine if should auto-apply to a job based on match score.
        
        Args:
            job: Job dictionary with optional 'match' field
            force: Force apply regardless of score
            
        Returns:
            True if should auto-apply, False otherwise
        """
        if force:
            return True
        
        if "match" not in job:
            # No match data - don't auto-apply
            logger.info(f"Job {job.get('title', 'Unknown')} has no match data - skipping")
            return False
        
        match_score = job["match"].get("match_score", 0)
        recommendation = job["match"].get("recommendation", "Skip")
        
        # Apply if score meets threshold AND recommendation is "Apply"
        should_apply = match_score >= self.min_auto_apply_score and recommendation == "Apply"
        
        if not should_apply:
            logger.info(
                f"Job {job.get('title', 'Unknown')} - Score: {match_score}, "
                f"Recommendation: {recommendation} - skipping"
            )
        else:
            logger.info(
                f"Job {job.get('title', 'Unknown')} - Score: {match_score}, "
                f"Recommendation: {recommendation} - will apply"
            )
        
        return should_apply
    
    async def generate_cover_letter(
        self,
        resume_data: Dict[str, Any],
        job_description: str,
        job_title: str = "",
        company_name: str = ""
    ) -> str:
        """
        Generate a personalized cover letter using AI.
        
        Args:
            resume_data: Parsed resume information
            job_description: Job posting description
            job_title: Job title
            company_name: Company name
            
        Returns:
            Generated cover letter text
        """
        try:
            if not self.ai_service:
                logger.warning("AI service not available for cover letter generation")
                return ""
            
            # Extract user info from resume
            contact = resume_data.get("contact", {})
            user_name = contact.get("name", "")
            summary = resume_data.get("summary", "")
            experience = resume_data.get("experience", [])
            skills = resume_data.get("skills", [])
            
            # Build resume text
            resume_text = f"{summary}\n\nSkills: {', '.join(skills)}\n\n"
            for exp in experience[:3]:  # Include top 3 experiences
                resume_text += f"{exp.get('title', '')} at {exp.get('company', '')} - {exp.get('description', '')}\n"
            
            cover_letter = self.ai_service.generate_cover_letter(
                job_title=job_title,
                company_name=company_name,
                job_description=job_description,
                resume_text=resume_text,
                user_name=user_name
            )
            
            return cover_letter or ""
            
        except Exception as e:
            logger.error(f"Error generating cover letter: {e}")
            return ""
    
    async def batch_apply(
        self,
        jobs: list[Dict[str, Any]],
        user_id: str,
        resume_data: Optional[Dict[str, Any]] = None,
        auto_submit: bool = False
    ) -> Dict[str, Any]:
        """
        Apply to multiple jobs in batch.
        
        Args:
            jobs: List of job dictionaries with match data
            user_id: User identifier
            resume_data: Optional parsed resume data
            auto_submit: Whether to enable auto-submit mode
            
        Returns:
            Summary of batch application results
        """
        results = {
            "submitted": [],
            "pending_review": [],
            "skipped": [],
            "errors": []
        }
        
        for job in jobs:
            result = await self.apply_to_job(
                job=job,
                user_id=user_id,
                resume_data=resume_data,
                auto_submit=auto_submit
            )
            
            status = result.get("status", "error")
            results[status].append(result)
        
        return {
            "total_jobs": len(jobs),
            "submitted": len(results["submitted"]),
            "pending_review": len(results["pending_review"]),
            "skipped": len(results["skipped"]),
            "errors": len(results["errors"]),
            "details": results
        }

