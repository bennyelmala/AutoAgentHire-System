"""
Job Search Agent - Discovers relevant job opportunities.
Uses CrewAI framework to search and extract job listings.
Enhanced with AI-powered profile matching to prioritize best-fit positions.
"""
from typing import List, Dict, Any, Optional
import logging
# from crewai import Agent, Task
# from backend.agents.tools import WebSearchTool, DatabaseQueryTool

logger = logging.getLogger(__name__)


class JobSearchAgent:
    """
    Agent responsible for discovering job opportunities.
    
    Role: Job Discovery Specialist
    Goal: Find relevant jobs matching user preferences
    Enhanced: AI-powered profile matching and intelligent filtering
    """
    
    def __init__(
        self, 
        ai_provider: str = "gemini",
        api_key: Optional[str] = None,
        enable_matching: bool = True
    ):
        """
        Initialize the job search agent.
        
        Args:
            ai_provider: AI provider for profile matching (gemini, groq, openai)
            api_key: Optional API key for the AI provider
            enable_matching: Whether to enable profile matching (default: True)
        """
        self.ai_provider = ai_provider
        self.api_key = api_key
        self.enable_matching = enable_matching
        
        # Initialize profile matcher if enabled
        if self.enable_matching:
            try:
                from backend.matching.profile_matcher import ProfileMatcher
                self.matcher = ProfileMatcher(
                    ai_provider=ai_provider,  # type: ignore
                    api_key=api_key
                )
            except Exception as e:
                logger.warning(f"Failed to initialize profile matcher: {e}")
                self.matcher = None
        else:
            self.matcher = None
    
    async def search_jobs(
        self,
        keywords: str,
        location: str = "",
        experience_level: str = "",
        job_type: str = "",
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search for jobs based on criteria.
        
        Args:
            keywords: Job title or keywords
            location: Desired location
            experience_level: Experience level (entry, mid, senior)
            job_type: Type of job (full-time, contract, etc.)
            max_results: Maximum number of results
            
        Returns:
            List of job listings with metadata
        """
        # TODO: Implement job search logic
        # 1. Search multiple job boards
        # 2. Extract job details
        # 3. Store in database
        # 4. Return results
        
        return []
    
    async def search_and_match(
        self,
        keywords: str,
        resume_file_path: str,
        location: str = "",
        experience_level: str = "",
        job_type: str = "",
        max_results: int = 100,
        min_match_score: int = 70
    ) -> List[Dict[str, Any]]:
        """
        Search for jobs and match them against user's resume.
        Returns jobs sorted by match score.
        
        Args:
            keywords: Job title or keywords
            resume_file_path: Path to user's resume file
            location: Desired location
            experience_level: Experience level
            job_type: Type of job
            max_results: Maximum number of results
            min_match_score: Minimum match score to include (0-100)
            
        Returns:
            List of matched jobs sorted by score (highest first)
        """
        try:
            # First, search for jobs
            jobs = await self.search_jobs(
                keywords=keywords,
                location=location,
                experience_level=experience_level,
                job_type=job_type,
                max_results=max_results
            )
            
            if not jobs or not self.matcher:
                return jobs
            
            # Parse the resume
            from backend.parsers.resume_parser import ResumeParser
            parser = ResumeParser()
            resume_data = parser.parse(resume_file_path)
            
            # Match jobs against resume
            logger.info(f"Matching {len(jobs)} jobs against resume...")
            matched_jobs = self.matcher.batch_match(
                resume_data=resume_data,
                jobs=jobs,
                min_score=min_match_score
            )
            
            logger.info(f"Found {len(matched_jobs)} jobs with score >= {min_match_score}")
            
            return matched_jobs
            
        except Exception as e:
            logger.error(f"Error in search_and_match: {e}")
            # Return unmatched jobs if matching fails
            return await self.search_jobs(
                keywords=keywords,
                location=location,
                experience_level=experience_level,
                job_type=job_type,
                max_results=max_results
            )
    
    async def extract_job_details(self, job_url: str) -> Dict[str, Any]:
        """
        Extract detailed information from a job posting.
        
        Args:
            job_url: URL of the job posting
            
        Returns:
            Dictionary with job details
        """
        # TODO: Implement job detail extraction
        return {}
    
    def should_apply(self, job: Dict[str, Any], min_score: int = 70) -> bool:
        """
        Determine if should auto-apply to a job based on match score.
        
        Args:
            job: Job dictionary with optional 'match' field
            min_score: Minimum match score required
            
        Returns:
            True if should apply, False otherwise
        """
        if "match" not in job:
            # No match data - don't auto-apply
            return False
        
        match_score = job["match"].get("match_score", 0)
        recommendation = job["match"].get("recommendation", "Skip")
        
        # Apply if score meets threshold AND recommendation is "Apply"
        return match_score >= min_score and recommendation == "Apply"

