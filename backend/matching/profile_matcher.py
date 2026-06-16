"""
Profile Matcher - Intelligent matching between resume and job descriptions.
Uses AI to evaluate compatibility and generate match scores.
Integrates with job_filter module for comprehensive job filtering.
"""
from typing import Dict, Any, List, Optional, Literal
import logging
from backend.llm.multi_ai_service import MultiAIService, AIProvider
from backend.matching.job_filter import filter_jobs, normalize, matches_role

logger = logging.getLogger(__name__)


class ProfileMatcher:
    """
    Matches candidate profiles against job descriptions using AI.
    """
    
    def __init__(self, ai_provider: AIProvider = "gemini", api_key: Optional[str] = None):
        """
        Initialize the profile matcher.
        
        Args:
            ai_provider: AI provider to use (gemini, groq, or openai)
            api_key: API key for the provider (optional if in env)
        """
        self.ai_service = MultiAIService(provider=ai_provider, api_key=api_key)  # type: ignore
    
    def match_profile(
        self, 
        resume_data: Dict[str, Any], 
        job_description: str,
        job_title: str = "",
        company_name: str = ""
    ) -> Dict[str, Any]:
        """
        Match a resume against a job description.
        
        Args:
            resume_data: Parsed resume data with skills, experience, education
            job_description: Full job description text
            job_title: Job title (optional)
            company_name: Company name (optional)
            
        Returns:
            Dictionary with:
                - match_score: Integer 0-100
                - reasoning: Explanation of the match
                - strengths: List of candidate strengths for this role
                - concerns: List of potential concerns or gaps
                - recommendation: Apply, Review, or Skip
        """
        try:
            # Extract key info from resume
            skills = resume_data.get("skills", [])
            experience = resume_data.get("experience", [])
            education = resume_data.get("education", [])
            summary = resume_data.get("summary", "")
            
            # Build candidate profile summary
            profile_text = f"""
Candidate Profile:
- Summary: {summary}
- Skills: {', '.join(skills) if skills else 'Not specified'}
- Experience: {len(experience)} positions listed
- Education: {len(education)} degrees listed

Detailed Experience:
{self._format_experience(experience)}

Education:
{self._format_education(education)}
"""
            
            # Create matching prompt
            prompt = f"""
You are an expert recruiter evaluating a candidate for a job position.

JOB DETAILS:
Title: {job_title}
Company: {company_name}
Description: {job_description[:2000]}

{profile_text}

Evaluate this candidate for the position. Provide:
1. Match Score (0-100): How well does the candidate fit this role?
2. Reasoning: Brief explanation of the score
3. Strengths: 3-5 specific strengths for this role
4. Concerns: 2-3 potential gaps or concerns
5. Recommendation: "Apply" (70+), "Review" (50-69), or "Skip" (<50)

Return ONLY a valid JSON object with these fields:
{{
    "match_score": 85,
    "reasoning": "Strong technical background...",
    "strengths": ["strength1", "strength2", "strength3"],
    "concerns": ["concern1", "concern2"],
    "recommendation": "Apply"
}}
"""
            
            response = self.ai_service.generate_text(prompt)
            
            # Parse the response
            import json
            import re
            
            if not response:
                return self._default_match_result()
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # Ensure all required fields
                result.setdefault("match_score", 0)
                result.setdefault("reasoning", "Unable to evaluate")
                result.setdefault("strengths", [])
                result.setdefault("concerns", [])
                result.setdefault("recommendation", "Skip")
                
                # Validate match score is in range
                if not isinstance(result["match_score"], (int, float)):
                    result["match_score"] = 0
                else:
                    result["match_score"] = max(0, min(100, int(result["match_score"])))
                
                return result
            else:
                return self._default_match_result()
                
        except Exception as e:
            logger.error(f"Error matching profile: {e}")
            return self._default_match_result()
    
    def batch_match(
        self,
        resume_data: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        min_score: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Match a resume against multiple jobs and sort by score.
        
        Args:
            resume_data: Parsed resume data
            jobs: List of job dictionaries with 'title', 'company', 'description'
            min_score: Minimum match score to include (default: 0)
            
        Returns:
            List of jobs with match results, sorted by score (highest first)
        """
        results = []
        
        for job in jobs:
            match_result = self.match_profile(
                resume_data=resume_data,
                job_description=job.get("description", ""),
                job_title=job.get("title", ""),
                company_name=job.get("company", "")
            )
            
            # Only include if meets minimum score
            if match_result["match_score"] >= min_score:
                results.append({
                    **job,
                    "match": match_result
                })
        
        # Sort by match score (highest first)
        results.sort(key=lambda x: x["match"]["match_score"], reverse=True)
        
        return results
    
    def _format_experience(self, experience: List[Dict[str, Any]]) -> str:
        """Format experience list for prompt."""
        if not experience:
            return "No experience listed"
        
        formatted = []
        for exp in experience[:5]:  # Limit to 5 most recent
            title = exp.get("title", "Unknown")
            company = exp.get("company", "Unknown")
            duration = exp.get("duration", "Unknown")
            description = exp.get("description", "")[:200]  # Limit length
            
            formatted.append(f"- {title} at {company} ({duration})\n  {description}")
        
        return "\n".join(formatted)
    
    def _format_education(self, education: List[Dict[str, Any]]) -> str:
        """Format education list for prompt."""
        if not education:
            return "No education listed"
        
        formatted = []
        for edu in education:
            degree = edu.get("degree", "Unknown")
            institution = edu.get("institution", "Unknown")
            year = edu.get("year", "Unknown")
            
            formatted.append(f"- {degree} from {institution} ({year})")
        
        return "\n".join(formatted)
    
    def _default_match_result(self) -> Dict[str, Any]:
        """Return default match result when evaluation fails."""
        return {
            "match_score": 0,
            "reasoning": "Unable to evaluate match",
            "strengths": [],
            "concerns": ["Could not complete evaluation"],
            "recommendation": "Skip"
        }
    
    def batch_match_jobs(
        self,
        resume_data: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        target_role: Optional[str] = None,
        apply_filters: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Match resume against multiple jobs and optionally filter results.
        
        Args:
            resume_data: Parsed resume data
            jobs: List of job dictionaries
            target_role: Target role for filtering (from ROLE_TAXONOMY)
            apply_filters: Whether to apply strict filtering (recommended: True)
            
        Returns:
            List of jobs with match scores, sorted by relevance
        """
        logger.info(f"Batch matching {len(jobs)} jobs")
        
        matched_jobs = []
        
        for job in jobs:
            try:
                # Get match score from AI
                match_result = self.match_profile(
                    resume_data=resume_data,
                    job_description=job.get("description", ""),
                    job_title=job.get("title", ""),
                    company_name=job.get("company", "")
                )
                
                # Add match result to job
                job["match_score"] = match_result["match_score"]
                job["match_reasoning"] = match_result["reasoning"]
                job["match_strengths"] = match_result["strengths"]
                job["match_concerns"] = match_result["concerns"]
                job["recommendation"] = match_result["recommendation"]
                
                matched_jobs.append(job)
                
            except Exception as e:
                logger.error(f"Error matching job {job.get('title')}: {e}")
                # Include job with low score rather than excluding
                job["match_score"] = 0
                job["match_reasoning"] = f"Error during matching: {str(e)}"
                matched_jobs.append(job)
        
        # Apply strict filtering if enabled (RECOMMENDED)
        if apply_filters:
            logger.info("Applying strict job filters")
            matched_jobs = filter_jobs(
                matched_jobs,
                target_role=target_role,
                min_match_score=50,  # Only jobs with 50+ match score
                enable_deduplication=True
            )
        
        # Sort by match score (highest first)
        matched_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        
        logger.info(f"Batch matching complete: {len(matched_jobs)} jobs returned")
        
        return matched_jobs


# Convenience function
def match_resume_to_job(
    resume_data: Dict[str, Any],
    job_description: str,
    job_title: str = "",
    company_name: str = "",
    ai_provider: str = "gemini",
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Quick function to match a resume against a single job.
    
    Args:
        resume_data: Parsed resume data
        job_description: Job description text
        job_title: Job title
        company_name: Company name
        ai_provider: AI provider to use
        api_key: API key for the provider
        
    Returns:
        Match result dictionary
    """
    matcher = ProfileMatcher(ai_provider=ai_provider, api_key=api_key)  # type: ignore
    return matcher.match_profile(
        resume_data=resume_data,
        job_description=job_description,
        job_title=job_title,
        company_name=company_name
    )
