"""
Browser Automation Adapter for Multi-Agent Orchestrator
=======================================================
Adapts AutoAgentHireBot to work seamlessly with the orchestrator's expected interface.

This adapter ensures the orchestrator can call browser automation methods consistently,
regardless of the underlying implementation details.
"""

import logging
from typing import Dict, List, Optional
from backend.agents.autoagenthire_bot import AutoAgentHireBot


class BrowserAutomationAdapter:
    """
    Adapter that wraps AutoAgentHireBot and ensures it conforms to the interface
    expected by the Multi-Agent Orchestrator.
    
    Expected methods:
    - initialize_browser()
    - login_linkedin() -> bool
    - search_jobs(keywords: str, location: str)
    - collect_job_listings(max_jobs: int) -> List[Dict]
    - apply_to_single_job(job_match: Dict) -> Dict
    - close()
    """
    
    def __init__(self, config: Dict):
        """
        Initialize adapter with configuration.
        
        Args:
            config: Configuration dict with:
                - linkedin_email
                - linkedin_password
                - auto_apply
                - max_results
                - similarity_threshold
        """
        self.bot = AutoAgentHireBot(config=config)
        self.logger = logging.getLogger("BrowserAdapter")
        self._initialized = False
        self._logged_in = False
    
    async def initialize_browser(self) -> None:
        """Initialize browser with persistent profile"""
        self.logger.info("Initializing browser via adapter...")
        await self.bot.initialize_browser(use_persistent_profile=True)
        self._initialized = True
        self.logger.info("✓ Browser initialized")
    
    async def login_linkedin(self) -> bool:
        """
        Login to LinkedIn.
        
        Returns:
            bool: True if login successful, False otherwise
        """
        if not self._initialized:
            raise RuntimeError("Browser not initialized. Call initialize_browser() first.")
        
        self.logger.info("Logging into LinkedIn via adapter...")
        
        try:
            success = await self.bot.login_linkedin()
            self._logged_in = success
            
            if success:
                self.logger.info("✓ LinkedIn login successful")
            else:
                self.logger.error("✗ LinkedIn login failed")
            
            return success
        except Exception as e:
            self.logger.error(f"Login error: {e}")
            return False
    
    async def search_jobs(self, keywords: str, location: str) -> None:
        """
        Execute LinkedIn job search with Easy Apply filter.
        
        Args:
            keywords: Job search keywords
            location: Job location
        """
        if not self._logged_in:
            raise RuntimeError("Not logged in. Call login_linkedin() first.")
        
        self.logger.info(f"Searching jobs: '{keywords}' in '{location}'")
        await self.bot.search_jobs(keyword=keywords, location=location)
        self.logger.info("✓ Search executed")
    
    async def collect_job_listings(self, max_jobs: int = 30) -> List[Dict]:
        """
        Collect job listings from search results.
        
        Args:
            max_jobs: Maximum number of jobs to collect
            
        Returns:
            List[Dict]: List of job dictionaries with keys:
                - job_id
                - title (or job_title)
                - company
                - description (or job_description)
                - url
                - location
        """
        self.logger.info(f"Collecting up to {max_jobs} job listings...")
        
        jobs = await self.bot.collect_job_listings(max_jobs=max_jobs)
        
        # Normalize job data structure for orchestrator
        normalized_jobs = []
        for job in jobs:
            normalized = {
                'job_id': job.get('job_id', job.get('url', '')),
                'title': job.get('title', job.get('job_title', 'Unknown')),
                'company': job.get('company', 'Unknown'),
                'description': job.get('description', job.get('job_description', '')),
                'url': job.get('url', ''),
                'location': job.get('location', '')
            }
            normalized_jobs.append(normalized)
        
        self.logger.info(f"✓ Collected {len(normalized_jobs)} jobs")
        return normalized_jobs
    
    async def apply_to_single_job(self, job_match: Dict) -> Dict:
        """
        Apply to a single job.
        
        Args:
            job_match: Job match dictionary from MatchingAgent with:
                - job_id
                - job_title
                - company
                - job_description
                - match_score
                - url (optional)
        
        Returns:
            Dict: Application result with keys:
                - success: bool
                - status: str ('success' or 'failed')
                - error: Optional[str]
        """
        job_title = job_match.get('job_title', job_match.get('title', 'Unknown'))
        company = job_match.get('company', 'Unknown')
        job_url = job_match.get('url', job_match.get('job_id', ''))
        
        self.logger.info(f"Applying to: {job_title} at {company}")
        
        try:
            # AutoAgentHireBot's apply_to_single_job expects a URL
            if not job_url:
                return {
                    'success': False,
                    'status': 'failed',
                    'error': 'No job URL provided'
                }
            
            result = await self.bot.apply_to_single_job(job_url)
            
            # Normalize result
            return {
                'success': result.get('success', False),
                'status': 'success' if result.get('success') else 'failed',
                'error': result.get('error', result.get('message'))
            }
            
        except Exception as e:
            self.logger.error(f"Application error: {e}")
            return {
                'success': False,
                'status': 'failed',
                'error': str(e)
            }
    
    async def close(self) -> None:
        """Close browser and clean up resources"""
        self.logger.info("Closing browser...")
        await self.bot.close()
        self._initialized = False
        self._logged_in = False
        self.logger.info("✓ Browser closed")


# Convenience function to create adapter
def create_browser_automation(config: Dict) -> BrowserAutomationAdapter:
    """
    Create a browser automation adapter for the orchestrator.
    
    Args:
        config: Configuration dict with:
            - linkedin_email: str
            - linkedin_password: str
            - auto_apply: bool (optional, default True)
            - max_results: int (optional, default 50)
    
    Returns:
        BrowserAutomationAdapter: Ready-to-use adapter
    
    Example:
        browser = create_browser_automation({
            'linkedin_email': 'user@example.com',
            'linkedin_password': 'password',
            'auto_apply': True,
            'max_results': 30
        })
    """
    return BrowserAutomationAdapter(config)
