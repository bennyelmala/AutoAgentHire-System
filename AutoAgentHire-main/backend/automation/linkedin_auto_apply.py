"""
LinkedIn Auto Apply - Autonomous Job Application Agent
Author: AutoAgentHire Team
Date: October 14, 2025

This module implements comprehensive LinkedIn job automation using Playwright.
Features:
- Secure authentication with anti-detection measures
- Smart job search and filtering
- AI-powered resume matching using RAG
- Automated application submission
- Smart cover letter generation using LLMs
- Daily summary reports
- Human-like interaction patterns
"""

import asyncio
import logging
import os
import random
import re
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict

from pypdf import PdfReader as _PdfReader
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from dotenv import load_dotenv

from backend.automation.application_handler import ApplicationHandler
from backend.automation.intelligent_form_filler import IntelligentFormFiller

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class JobListing:
    """Data class for job listing information."""
    job_id: str
    title: str
    company: str
    location: str
    description: str
    apply_link: str
    salary: Optional[str] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    posted_date: Optional[str] = None
    match_score: float = 0.0
    keywords_matched: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.keywords_matched is None:
            self.keywords_matched = []


@dataclass
class ApplicationResult:
    """Data class for application result tracking."""
    job_id: str
    job_title: str
    company: str
    status: str  # 'success', 'failed', 'skipped'
    timestamp: str
    error_message: Optional[str] = None
    cover_letter_generated: bool = False


class LinkedInAutoApply:
    """
    Main automation class for LinkedIn job applications.
    
    This class handles the entire workflow:
    1. Browser initialization with anti-detection
    2. Secure LinkedIn authentication
    3. Job search and filtering
    4. AI-powered job matching
    5. Automated application submission
    6. Report generation
    """
    
    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        resume_path: Optional[str] = None,
        headless: bool = False,
        use_llm: bool = True
    ):
        """
        Initialize the LinkedIn automation agent.
        
        Args:
            email: LinkedIn email (loaded from env if not provided)
            password: LinkedIn password (loaded from env if not provided)
            resume_path: Path to resume file (.txt or .pdf)
            headless: Run browser in headless mode
            use_llm: Enable LLM for cover letter generation
        """
        # Credentials
        self.email = email or os.getenv('LINKEDIN_EMAIL')
        self.password = password or os.getenv('LINKEDIN_PASSWORD')
        
        if not self.email or not self.password:
            raise ValueError("LinkedIn credentials not provided. Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD")
        
        # Resume handling
        self.resume_path = Path(resume_path or os.getenv('RESUME_PATH', './data/resumes/resume.pdf'))
        self.resume_text = self._load_resume()
        
        # Browser settings
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # LLM integration
        self.use_llm = use_llm
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        
        # Session data
        self.jobs_found: List[JobListing] = []
        self.jobs_applied: List[ApplicationResult] = []
        self.resume_keywords = self._extract_resume_keywords()
        
        # Configuration
        self.max_applications_per_session = int(os.getenv('MAX_APPLICATIONS', '5'))
        self.match_threshold = float(os.getenv('MATCH_THRESHOLD', '75.0'))
        self.application_delay_min = 2.0  # seconds
        self.application_delay_max = 5.0  # seconds
        
        logger.info(f"✅ LinkedInAutoApply initialized for {self.email}")
        logger.info(f"📄 Resume loaded from {self.resume_path}")
        logger.info(f"🎯 Match threshold: {self.match_threshold}%")
        logger.info(f"📊 Max applications per session: {self.max_applications_per_session}")
    
    def _load_resume(self) -> str:
        """Load and parse resume from file."""
        try:
            if not self.resume_path.exists():
                raise FileNotFoundError(f"Resume not found at {self.resume_path}")
            
            if self.resume_path.suffix == '.pdf':
                return self._parse_pdf_resume()
            elif self.resume_path.suffix == '.txt':
                return self.resume_path.read_text(encoding='utf-8')
            else:
                raise ValueError(f"Unsupported resume format: {self.resume_path.suffix}")
        
        except Exception as e:
            logger.error(f"❌ Error loading resume: {e}")
            raise
    
    def _parse_pdf_resume(self) -> str:
        """Extract text from PDF resume."""
        try:
            with open(self.resume_path, 'rb') as file:
                pdf_reader = _PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() or ""
                return text
        except Exception as e:
            logger.error(f"❌ Error parsing PDF resume: {e}")
            raise
    
    def _extract_resume_keywords(self) -> List[str]:
        """Extract key skills and keywords from resume."""
        # Common tech and business keywords
        common_keywords = [
            'python', 'java', 'javascript', 'typescript', 'react', 'node.js',
            'machine learning', 'deep learning', 'ai', 'artificial intelligence',
            'data science', 'sql', 'nosql', 'mongodb', 'postgresql',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes',
            'fastapi', 'django', 'flask', 'express',
            'agile', 'scrum', 'devops', 'ci/cd',
            'leadership', 'management', 'team building'
        ]
        
        resume_lower = self.resume_text.lower()
        keywords = [kw for kw in common_keywords if kw in resume_lower]
        
        logger.info(f"📝 Extracted {len(keywords)} keywords from resume")
        return keywords
    
    # ==================== BROWSER AUTOMATION ====================
    
    async def initialize_browser(self):
        """
        Step 1: Initialize browser with anti-detection measures.
        
        Implements:
        - Stealth mode to avoid bot detection
        - Realistic browser fingerprint
        - Human-like viewport and settings
        """
        logger.info("🚀 Initializing browser with anti-detection measures...")
        
        self.playwright = await async_playwright().start()
        
        # Launch browser with stealth settings
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        
        # Create context with realistic fingerprint
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            color_scheme='light',
            device_scale_factor=1.0,
            has_touch=False,
            is_mobile=False,
        )
        
        self.page = await self.context.new_page()
        
        # Inject anti-detection scripts
        await self.page.add_init_script("""
            // Remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Chrome runtime
            window.chrome = {
                runtime: {}
            };
        """)
        
        # Set extra HTTP headers
        await self.page.set_extra_http_headers({
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        })
        
        logger.info("✅ Browser initialized successfully")
    
    async def human_delay(self, min_seconds: Optional[float] = None, max_seconds: Optional[float] = None):
        """Add human-like random delay."""
        min_seconds = min_seconds if min_seconds is not None else self.application_delay_min
        max_seconds = max_seconds if max_seconds is not None else self.application_delay_max
        delay = random.uniform(min_seconds, max_seconds)
        logger.debug(f"⏳ Waiting {delay:.2f}s (human delay)")
        await asyncio.sleep(delay)
    
    async def random_mouse_movement(self):
        """Simulate random mouse movements."""
        if self.page:
            x = random.randint(100, 1500)
            y = random.randint(100, 800)
            await self.page.mouse.move(x, y, steps=random.randint(10, 30))
    
    async def human_type(self, selector: str, text: str):
        """Type text with human-like delays."""
        if not self.page:
            return
        await self.page.click(selector)
        await self.human_delay(0.5, 1.0)
        
        for char in text:
            await self.page.type(selector, char)
            await asyncio.sleep(random.uniform(0.05, 0.15))
    
    # ==================== AUTHENTICATION ====================
    
    async def login_linkedin(self) -> bool:
        """
        Step 2: Authenticate with LinkedIn using stored credentials.
        
        Returns:
            bool: True if login successful, False otherwise
        """
        logger.info("🔐 Logging into LinkedIn...")
        
        if not self.page:
            logger.error("❌ Browser page not initialized")
            return False
        
        try:
            # Navigate to LinkedIn login page
            await self.page.goto('https://www.linkedin.com/login', wait_until='domcontentloaded')
            await self.human_delay(2, 3)
            
            # Wait for login form
            await self.page.wait_for_selector('#username', timeout=10000)
            
            # Enter email with human-like typing
            logger.info("📧 Entering email...")
            if self.email:
                await self.human_type('#username', self.email)
            await self.human_delay(0.5, 1.0)
            
            # Enter password
            logger.info("🔑 Entering password...")
            if self.password:
                await self.human_type('#password', self.password)
            await self.human_delay(0.5, 1.0)
            
            # Random mouse movement
            await self.random_mouse_movement()
            
            # Click login button
            logger.info("👆 Clicking login button...")
            await self.page.click('button[type="submit"]')

            # LinkedIn often keeps network connections open; `networkidle` can hang.
            # Instead: wait for a clear post-login signal (URL or a nav/search UI),
            # or detect the security checkpoint.
            await self.human_delay(1.0, 2.0)

            async def _is_logged_in() -> bool:
                if not self.page:
                    return False
                url = self.page.url
                if any(p in url for p in ('/feed', '/mynetwork', '/jobs', '/in/')):
                    return True
                # Common UI markers for authenticated state
                selectors = [
                    'input[placeholder*="Search"]',
                    'a[href*="/feed/"]',
                    'a[href*="/jobs/"]',
                    'nav[aria-label="Primary"]',
                ]
                for sel in selectors:
                    try:
                        if await self.page.query_selector(sel):
                            return True
                    except Exception:
                        continue
                return False

            # Wait up to 45s for either logged-in state or a challenge to appear.
            deadline = asyncio.get_event_loop().time() + 45.0
            while asyncio.get_event_loop().time() < deadline:
                current_url = self.page.url
                if 'checkpoint/challenge' in current_url:
                    break
                if await _is_logged_in():
                    logger.info("✅ Successfully logged into LinkedIn!")
                    return True
                await asyncio.sleep(1)

            # Check if login successful or challenge detected
            current_url = self.page.url
            if await _is_logged_in():
                logger.info("✅ Successfully logged into LinkedIn!")
                return True
            elif 'checkpoint/challenge' in current_url:
                logger.warning("⚠️ LinkedIn security challenge detected. Manual intervention required.")
                logger.info("🔍 Please complete the security challenge in the browser...")
                
                # Wait for user to complete challenge (max 2 minutes)
                for i in range(24):  # 24 * 5 = 120 seconds
                    await asyncio.sleep(5)
                    current_url = self.page.url
                    if 'feed' in current_url or 'mynetwork' in current_url:
                        logger.info("✅ Security challenge completed!")
                        return True
                
                logger.error("❌ Security challenge timeout")
                return False
            else:
                logger.error(f"❌ Login failed. Current URL: {current_url}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Error during login: {e}")
            return False
    
    # ==================== JOB SEARCH ====================
    
    async def search_jobs(
        self,
        keywords: str,
        location: str = "United States",
        experience_level: Optional[str] = None,
        job_type: Optional[str] = None,
        easy_apply_only: bool = True
    ) -> int:
        """
        Step 3: Search for jobs based on criteria.
        
        Args:
            keywords: Job title or keywords (e.g., "AI Engineer", "Machine Learning")
            location: Job location (e.g., "Remote", "United States", "San Francisco")
            experience_level: Filter by experience (e.g., "Entry level", "Mid-Senior level")
            job_type: Filter by type (e.g., "Full-time", "Contract")
            easy_apply_only: Only show Easy Apply jobs
        
        Returns:
            int: Number of jobs found
        """
        logger.info(f"🔍 Searching jobs: {keywords} in {location}")
        
        if not self.page:
            logger.error("❌ Browser page not initialized")
            return 0
        
        try:
            # Navigate to jobs page
            await self.page.goto('https://www.linkedin.com/jobs/', wait_until='domcontentloaded')
            await self.human_delay(2, 3)
            
            # Enter keywords
            keyword_selector = 'input[aria-label*="Search by title"]'
            await self.page.wait_for_selector(keyword_selector, timeout=10000)
            await self.page.fill(keyword_selector, keywords)
            await self.human_delay(0.5, 1.0)
            
            # Enter location
            location_selector = 'input[aria-label*="City, state, or zip code"]'
            await self.page.fill(location_selector, location)
            await self.human_delay(0.5, 1.0)
            
            # Click search button
            search_button = 'button.jobs-search-box__submit-button'
            await self.page.click(search_button)
            await self.page.wait_for_load_state('networkidle', timeout=15000)
            await self.human_delay(2, 3)
            
            # Apply Easy Apply filter if requested
            if easy_apply_only:
                logger.info("🎯 Applying Easy Apply filter...")
                await self._apply_easy_apply_filter()
            
            # Apply experience level filter
            if experience_level:
                logger.info(f"📊 Applying experience level filter: {experience_level}")
                await self._apply_experience_filter(experience_level)
            
            # Apply job type filter
            if job_type:
                logger.info(f"💼 Applying job type filter: {job_type}")
                await self._apply_job_type_filter(job_type)
            
            # Count jobs found
            await self.human_delay(2, 3)
            jobs_count = await self._count_jobs()
            logger.info(f"✅ Found {jobs_count} jobs matching criteria")
            
            return jobs_count
        
        except Exception as e:
            logger.error(f"❌ Error during job search: {e}")
            return 0
    
    async def _apply_easy_apply_filter(self):
        """Apply Easy Apply filter."""
        if not self.page:
            return
        try:
            # Click "Easy Apply" filter button
            easy_apply_button = 'button[aria-label*="Easy Apply filter"]'
            await self.page.wait_for_selector(easy_apply_button, timeout=5000)
            await self.page.click(easy_apply_button)
            await self.human_delay(1, 2)
            await self.page.wait_for_load_state('networkidle', timeout=10000)
            logger.info("✅ Easy Apply filter applied")
        except Exception as e:
            logger.warning(f"⚠️ Could not apply Easy Apply filter: {e}")
    
    async def _apply_experience_filter(self, experience_level: str):
        """Apply experience level filter."""
        if not self.page:
            return
        try:
            # Click "Experience Level" filter
            await self.page.click('button:has-text("Experience Level")')
            await self.human_delay(0.5, 1.0)
            
            # Select the experience level
            await self.page.click(f'label:has-text("{experience_level}")')
            await self.human_delay(0.5, 1.0)
            
            # Apply filter
            await self.page.click('button:has-text("Show results")')
            await self.page.wait_for_load_state('networkidle', timeout=10000)
            logger.info(f"✅ Experience level filter applied: {experience_level}")
        except Exception as e:
            logger.warning(f"⚠️ Could not apply experience filter: {e}")
    
    async def _apply_job_type_filter(self, job_type: str):
        """Apply job type filter."""
        if not self.page:
            return
        try:
            # Click "Job Type" filter
            await self.page.click('button:has-text("Job Type")')
            await self.human_delay(0.5, 1.0)
            
            # Select the job type
            await self.page.click(f'label:has-text("{job_type}")')
            await self.human_delay(0.5, 1.0)
            
            # Apply filter
            await self.page.click('button:has-text("Show results")')
            await self.page.wait_for_load_state('networkidle', timeout=10000)
            logger.info(f"✅ Job type filter applied: {job_type}")
        except Exception as e:
            logger.warning(f"⚠️ Could not apply job type filter: {e}")
    
    async def _count_jobs(self) -> int:
        """Count total jobs found."""
        if not self.page:
            return 0
        try:
            results_text = await self.page.text_content('.jobs-search-results-list__subtitle')
            if results_text:
                # Extract number from text like "1,234 results"
                match = re.search(r'([\d,]+)', results_text)
                if match:
                    return int(match.group(1).replace(',', ''))
            return 0
        except:
            return 0
    
    # ==================== JOB PARSING ====================
    
    async def parse_job_listings(self, max_jobs: int = 50) -> List[JobListing]:
        """
        Step 4: Parse job details from search results.
        
        Args:
            max_jobs: Maximum number of jobs to parse
        
        Returns:
            List[JobListing]: List of parsed job listings
        """
        logger.info(f"📄 Parsing job listings (max: {max_jobs})...")
        
        jobs = []
        
        if not self.page:
            logger.error("❌ Browser page not initialized")
            return jobs
        
        try:
            # Scroll to load more jobs
            await self._scroll_job_list(max_jobs)
            
            # Get all job cards
            job_cards = await self.page.query_selector_all('.jobs-search-results__list-item')
            logger.info(f"Found {len(job_cards)} job cards")
            
            for i, card in enumerate(job_cards[:max_jobs]):
                try:
                    # Click on job card to load details
                    await card.click()
                    await self.human_delay(1, 2)
                    
                    # Extract job details
                    job = await self._extract_job_details(card)
                    
                    if job:
                        jobs.append(job)
                        logger.info(f"✅ Parsed job {i+1}: {job.title} at {job.company}")
                    
                    # Human-like delay
                    await self.human_delay(0.5, 1.5)
                
                except Exception as e:
                    logger.warning(f"⚠️ Error parsing job card {i+1}: {e}")
                    continue
            
            self.jobs_found = jobs
            logger.info(f"✅ Successfully parsed {len(jobs)} jobs")
            return jobs
        
        except Exception as e:
            logger.error(f"❌ Error parsing job listings: {e}")
            return jobs
    
    async def _scroll_job_list(self, target_count: int):
        """Scroll job list to load more jobs."""
        if not self.page:
            return
        try:
            job_list = await self.page.query_selector('.jobs-search-results-list')
            
            if not job_list:
                return
            
            for _ in range(min(target_count // 10, 10)):  # Scroll up to 10 times
                await job_list.evaluate('el => el.scrollTop = el.scrollHeight')
                await self.human_delay(1, 2)
        
        except Exception as e:
            logger.warning(f"⚠️ Error scrolling job list: {e}")
    
    async def _extract_job_details(self, card) -> Optional[JobListing]:
        """Extract details from a job card."""
        if not self.page:
            return None
        try:
            # Extract job ID
            job_id = await card.get_attribute('data-job-id') or f"job_{random.randint(10000, 99999)}"
            
            # Extract title
            title_elem = await self.page.query_selector('.job-details-jobs-unified-top-card__job-title')
            title_text = await title_elem.text_content() if title_elem else None
            title = title_text.strip() if title_text else "Unknown"
            
            # Extract company
            company_elem = await self.page.query_selector('.job-details-jobs-unified-top-card__company-name')
            company_text = await company_elem.text_content() if company_elem else None
            company = company_text.strip() if company_text else "Unknown"
            
            # Extract location
            location_elem = await self.page.query_selector('.job-details-jobs-unified-top-card__bullet')
            location_text = await location_elem.text_content() if location_elem else None
            location = location_text.strip() if location_text else "Unknown"
            
            # Extract description
            description_elem = await self.page.query_selector('.jobs-description-content__text')
            description_text = await description_elem.text_content() if description_elem else None
            description = description_text.strip() if description_text else ""
            
            # Extract salary if available
            salary = None
            salary_elems = await self.page.query_selector_all('.job-details-jobs-unified-top-card__job-insight')
            for elem in salary_elems:
                text = await elem.text_content()
                if text and '$' in text:
                    salary = text.strip()
                    break
            
            # Get apply link
            apply_link = self.page.url
            
            # Extract employment type and experience level from description
            employment_type = self._extract_employment_type(description)
            experience_level = self._extract_experience_level(description)
            
            return JobListing(
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                description=description,
                apply_link=apply_link,
                salary=salary,
                employment_type=employment_type,
                experience_level=experience_level,
                posted_date=None
            )
        
        except Exception as e:
            logger.warning(f"⚠️ Error extracting job details: {e}")
            return None
    
    def _extract_employment_type(self, text: str) -> Optional[str]:
        """Extract employment type from text."""
        text_lower = text.lower()
        if 'full-time' in text_lower or 'full time' in text_lower:
            return 'Full-time'
        elif 'part-time' in text_lower or 'part time' in text_lower:
            return 'Part-time'
        elif 'contract' in text_lower:
            return 'Contract'
        elif 'internship' in text_lower:
            return 'Internship'
        return None
    
    def _extract_experience_level(self, text: str) -> Optional[str]:
        """Extract experience level from text."""
        text_lower = text.lower()
        if 'entry level' in text_lower or 'entry-level' in text_lower:
            return 'Entry level'
        elif 'mid-senior level' in text_lower or 'mid level' in text_lower:
            return 'Mid-Senior level'
        elif 'director' in text_lower or 'executive' in text_lower:
            return 'Executive'
        return None
    
    # ==================== JOB MATCHING ====================
    
    def analyze_job_fit(self, job: JobListing) -> Tuple[float, List[str]]:
        """
        Step 5: Analyze job fit using keyword matching.
        
        Args:
            job: Job listing to analyze
        
        Returns:
            Tuple[float, List[str]]: (match_score, matched_keywords)
        """
        # Combine job title and description
        job_text = f"{job.title} {job.description}".lower()
        
        # Find matching keywords
        matched_keywords = []
        for keyword in self.resume_keywords:
            if keyword in job_text:
                matched_keywords.append(keyword)
        
        # Calculate match score
        if self.resume_keywords:
            match_score = (len(matched_keywords) / len(self.resume_keywords)) * 100
        else:
            match_score = 0.0
        
        # Boost score for title matches
        title_lower = job.title.lower()
        title_matches = sum(1 for kw in self.resume_keywords if kw in title_lower)
        if title_matches > 0:
            match_score += title_matches * 5  # 5% boost per title match
        
        match_score = min(match_score, 100.0)  # Cap at 100%
        
        job.match_score = match_score
        job.keywords_matched = matched_keywords
        
        logger.info(f"📊 Job fit analysis: {job.title} - {match_score:.1f}% match ({len(matched_keywords)} keywords)")
        
        return match_score, matched_keywords
    
    async def analyze_all_jobs(self) -> List[JobListing]:
        """
        Analyze all found jobs and sort by match score.
        
        Returns:
            List[JobListing]: Sorted list of jobs (highest match first)
        """
        logger.info(f"🔍 Analyzing {len(self.jobs_found)} jobs for fit...")
        
        for job in self.jobs_found:
            self.analyze_job_fit(job)
        
        # Sort by match score
        self.jobs_found.sort(key=lambda j: j.match_score, reverse=True)
        
        # Filter by threshold
        qualified_jobs = [j for j in self.jobs_found if j.match_score >= self.match_threshold]
        
        logger.info(f"✅ Analysis complete: {len(qualified_jobs)} jobs above {self.match_threshold}% threshold")
        
        return qualified_jobs
    
    # ==================== APPLICATION ====================
    
    async def auto_apply_job(self, job: JobListing) -> ApplicationResult:
        """
        Step 6: Automatically apply to a job.
        
        Args:
            job: Job listing to apply to
        
        Returns:
            ApplicationResult: Result of the application attempt
        """
        logger.info(f"📝 Applying to: {job.title} at {job.company}")
        
        result = ApplicationResult(
            job_id=job.job_id,
            job_title=job.title,
            company=job.company,
            status='failed',
            timestamp=datetime.now().isoformat()
        )
        
        if not self.page:
            logger.error("❌ Browser page not initialized")
            result.error_message = "Browser not initialized"
            return result
        
        try:
            # Open application using robust handler (navigation + click + modal wait)
            application_handler = ApplicationHandler(self.page)
            open_result = await application_handler.open_job_application(job.apply_link)
            if open_result.get('status') != 'SUCCESS':
                result.status = 'skipped'
                result.error_message = open_result.get('reason', 'Failed to open application')
                return result

            # Fill the whole form using IntelligentFormFiller
            # Parse skill_experience from env var format: "Python:4,FastAPI:3,SQL:5"
            skill_exp_raw = os.getenv('SKILL_EXPERIENCE', '')
            skill_experience = {}
            if skill_exp_raw:
                for pair in skill_exp_raw.split(','):
                    if ':' in pair:
                        skill, years = pair.split(':', 1)
                        skill_experience[skill.strip()] = years.strip()

            user_profile = {
                'email': self.email,
                'first_name': os.getenv('FIRST_NAME', ''),
                'last_name': os.getenv('LAST_NAME', ''),
                'phone_number': os.getenv('PHONE_NUMBER', ''),
                'city': os.getenv('CITY', ''),
                'linkedin_url': os.getenv('LINKEDIN_URL', ''),
                'github_url': os.getenv('GITHUB_URL', ''),
                'website': os.getenv('PORTFOLIO_URL', ''),
                'requires_sponsorship': os.getenv('REQUIRES_SPONSORSHIP', 'No'),
                'years_experience': os.getenv('YEARS_EXPERIENCE', '3'),
                'notice_period_days': os.getenv('NOTICE_PERIOD_DAYS', '0'),
                'expected_salary': os.getenv('EXPECTED_SALARY', ''),
                'current_ctc': os.getenv('CURRENT_CTC', os.getenv('EXPECTED_SALARY', '0')),
                'cgpa': os.getenv('CGPA', '8.0'),
                'internship_months': os.getenv('INTERNSHIP_MONTHS', '6'),
                'drivers_license': os.getenv('DRIVERS_LICENSE', 'Yes'),
                'gender': os.getenv('GENDER', 'Male'),
                'skill_experience': skill_experience,
            }
            form_filler = IntelligentFormFiller(self.page, user_profile=user_profile, resume_text=self.resume_text,
                                                groq_api_key=os.getenv('GROQ_API_KEY', ''),
                                                gemini_api_key=os.getenv('GEMINI_API_KEY', '') or os.getenv('GOOGLE_API_KEY', ''))
            await form_filler.fill_application_form()

            # Advance through Easy Apply stages (Next/Review/Submit)
            await self._complete_easy_apply_flow(user_profile)
            
            result.status = 'success'
            logger.info(f"[APPLY] Successfully applied to {job.title}")
        
        except Exception as e:
            logger.error(f"[APPLY] Error applying to {job.title}: {e}")
            result.status = 'failed'
            result.error_message = str(e)
        
        return result

    def _build_user_profile(self) -> Dict:
        """Build user_profile dict from env vars (called once per job)."""
        skill_exp_raw = os.getenv('SKILL_EXPERIENCE', '')
        skill_experience = {}
        if skill_exp_raw:
            for pair in skill_exp_raw.split(','):
                if ':' in pair:
                    skill, years = pair.split(':', 1)
                    skill_experience[skill.strip()] = years.strip()
        return {
            'email': self.email,
            'first_name': os.getenv('FIRST_NAME', ''),
            'last_name': os.getenv('LAST_NAME', ''),
            'phone_number': os.getenv('PHONE_NUMBER', ''),
            'city': os.getenv('CITY', ''),
            'linkedin_url': os.getenv('LINKEDIN_URL', ''),
            'github_url': os.getenv('GITHUB_URL', ''),
            'website': os.getenv('PORTFOLIO_URL', ''),
            'requires_sponsorship': os.getenv('REQUIRES_SPONSORSHIP', 'No'),
            'years_experience': os.getenv('YEARS_EXPERIENCE', '3'),
            'notice_period_days': os.getenv('NOTICE_PERIOD_DAYS', '0'),
            'expected_salary': os.getenv('EXPECTED_SALARY', '600000'),
            'current_ctc': os.getenv('CURRENT_CTC', os.getenv('EXPECTED_SALARY', '0')),
            'cgpa': os.getenv('CGPA', '8.0'),
            'internship_months': os.getenv('INTERNSHIP_MONTHS', '6'),
            'drivers_license': os.getenv('DRIVERS_LICENSE', 'Yes'),
            'gender': os.getenv('GENDER', 'Male'),
            'skill_experience': skill_experience,
        }

    async def _complete_easy_apply_flow(self, user_profile: Optional[Dict] = None, max_steps: int = 12):
        """Complete the Easy Apply modal: fill → validate → click Next → detect errors → retry once."""
        if not self.page:
            raise Exception("Browser not initialized")

        if user_profile is None:
            user_profile = self._build_user_profile()

        page = self.page

        next_selectors = [
            'button[aria-label*="Continue" i]',
            'button[aria-label*="Next" i]',
            'button:has-text("Next")',
            'button:has-text("Continue")',
        ]
        review_selectors = [
            'button[aria-label*="Review" i]',
            'button:has-text("Review")',
            'button:has-text("Preview")',
        ]
        submit_selectors = [
            'button[aria-label*="Submit application" i]',
            'button:has-text("Submit application")',
            'button:has-text("Submit")',
        ]

        async def _first_clickable(selectors):
            for sel in selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible() and await el.is_enabled():
                        return el
                except Exception:
                    continue
            return None

        def _make_filler():
            return IntelligentFormFiller(page, user_profile=user_profile,
                                        resume_text=self.resume_text,
                                        groq_api_key=os.getenv('GROQ_API_KEY', ''),
                                        gemini_api_key=os.getenv('GEMINI_API_KEY', '') or os.getenv('GOOGLE_API_KEY', ''))

        for step in range(max_steps):
            # Security challenge guard
            url_lower = (page.url or '').lower()
            if 'checkpoint/challenge' in url_lower or 'captcha' in url_lower:
                raise Exception("Security challenge detected; cannot proceed automatically")

            # ---- FILL CURRENT PAGE ----
            filler = _make_filler()
            await filler.fill_application_form()
            await filler.validate_and_fix()

            # ---- SUBMIT (end condition) ----
            submit_btn = await _first_clickable(submit_selectors)
            if submit_btn:
                # Final validation sweep before submit
                filler_final = _make_filler()
                await filler_final.validate_and_fix()
                logger.info("[APPLY] Submitting application...")
                await submit_btn.click()
                await self.human_delay(2, 4)
                logger.info("[APPLY] Application submitted")
                return

            # ---- REVIEW ----
            review_btn = await _first_clickable(review_selectors)
            if review_btn:
                logger.info("[APPLY] Clicking Review...")
                await review_btn.click()
                await self.human_delay(1.5, 3)
                # Fill any fields on the review page
                filler2 = _make_filler()
                await filler2.fill_application_form()
                await filler2.validate_and_fix()
                continue

            # ---- NEXT / CONTINUE ----
            next_btn = await _first_clickable(next_selectors)
            if next_btn:
                logger.info("[APPLY] Clicking Next...")
                await next_btn.click()
                await self.human_delay(1.5, 3)

                # Detect errors AFTER clicking Next; retry once
                filler_post = _make_filler()
                if await filler_post.has_visible_errors():
                    logger.info("[APPLY] Errors detected after Next — re-filling dropdowns & retrying...")
                    await filler_post.scan_and_fix_validation_errors()
                    await filler_post.fill_application_form()
                    await filler_post.validate_and_fix()
                    await self.human_delay(0.5, 1)

                    # Check if errors persist
                    if await filler_post.has_visible_errors():
                        logger.warning("[APPLY] Errors persist after re-fill — doing aggressive dropdown sweep")
                        # Aggressive: run dropdown handlers one more time
                        filler_retry = _make_filler()
                        await filler_retry._fill_dropdowns_via_locator()
                        await filler_retry._fill_custom_dropdowns()
                        await filler_retry._fix_remaining_select_an_option()
                        await filler_retry.scan_and_fix_validation_errors()
                        await filler_retry.validate_and_fix()
                        await self.human_delay(0.3, 0.5)

                    # Re-click Next
                    next_btn2 = await _first_clickable(next_selectors)
                    if next_btn2:
                        await next_btn2.click()
                        await self.human_delay(1.5, 3)
                continue

            # No progression button found
            raise Exception("Could not find Next/Review/Submit button in Easy Apply modal")
    
    async def _fill_application_form(self, job: JobListing):
        """Fill out the Easy Apply application form."""
        logger.info("📋 Filling application form...")
        
        if not self.page:
            logger.error("❌ Browser page not initialized")
            raise Exception("Browser not initialized")
        
        try:
            # Wait for form modal
            await self.page.wait_for_selector('.jobs-easy-apply-content', timeout=5000)
            
            # Upload resume if required
            resume_input = await self.page.query_selector('input[type="file"]')
            if resume_input:
                logger.info("📎 Uploading resume...")
                await resume_input.set_input_files(str(self.resume_path))
                await self.human_delay(1, 2)
            
            # Fill phone number if asked
            phone_input = await self.page.query_selector('input[id*="phoneNumber"]')
            if phone_input:
                phone = os.getenv('PHONE_NUMBER', '555-123-4567')
                await self.human_type('input[id*="phoneNumber"]', phone)
            
            # Handle multi-page forms
            max_pages = 5
            for page_num in range(max_pages):
                # Check for "Next" button
                next_button = await self.page.query_selector('button[aria-label*="Continue"]')
                
                if not next_button:
                    # No next button, we're on the last page
                    break
                
                # Fill any visible form fields
                await self._fill_visible_fields()
                
                # Click next
                await next_button.click()
                await self.human_delay(2, 3)
            
            logger.info("✅ Form filled successfully")
        
        except Exception as e:
            logger.error(f"❌ Error filling form: {e}")
            raise
    
    async def _fill_visible_fields(self):
        """Fill visible form fields with sensible defaults."""
        if not self.page:
            return
        try:
            # Get all text inputs
            text_inputs = await self.page.query_selector_all('input[type="text"]:visible')
            
            for input_field in text_inputs:
                # Get field label or placeholder
                field_id = await input_field.get_attribute('id')
                field_name = await input_field.get_attribute('name')
                placeholder = await input_field.get_attribute('placeholder')
                
                # Check if already filled
                current_value = await input_field.input_value()
                if current_value:
                    continue
                
                # Fill based on field type
                if field_id and 'year' in field_id.lower():
                    await input_field.fill('5')  # 5 years experience
                elif field_name and 'salary' in field_name.lower():
                    await input_field.fill('negotiable')
                elif placeholder and 'website' in placeholder.lower():
                    website = os.getenv('PORTFOLIO_URL', '')
                    if website:
                        await input_field.fill(website)
            
            # Handle dropdowns
            select_elements = await self.page.query_selector_all('select:visible')
            for select in select_elements:
                # Select first non-empty option
                options = await select.query_selector_all('option')
                if len(options) > 1:
                    await select.select_option(index=1)
            
            # Handle radio buttons (select "Yes" by default)
            radio_yes = await self.page.query_selector('input[type="radio"][value*="yes" i]')
            if radio_yes:
                await radio_yes.click()
        
        except Exception as e:
            logger.warning(f"⚠️ Error filling visible fields: {e}")
    
    async def _add_cover_letter(self, cover_letter: str):
        """Add cover letter to application if field exists."""
        if not self.page:
            return
        try:
            # Look for cover letter textarea
            cover_letter_field = await self.page.query_selector('textarea[id*="coverLetter"]')
            
            if cover_letter_field:
                logger.info("📝 Adding cover letter...")
                await cover_letter_field.fill(cover_letter)
                await self.human_delay(1, 2)
                logger.info("✅ Cover letter added")
        
        except Exception as e:
            logger.warning(f"⚠️ Could not add cover letter: {e}")
    
    async def _submit_application(self):
        """Submit the application."""
        if not self.page:
            raise Exception("Browser not initialized")
        try:
            # Look for submit/review button
            submit_button = await self.page.query_selector('button[aria-label*="Submit application"]')
            
            if not submit_button:
                submit_button = await self.page.query_selector('button:has-text("Submit")')
            
            if submit_button:
                logger.info("✉️ Submitting application...")
                await submit_button.click()
                await self.human_delay(3, 5)
                logger.info("✅ Application submitted")
            else:
                raise Exception("Submit button not found")
        
        except Exception as e:
            logger.error(f"❌ Error submitting application: {e}")
            raise
    
    # ==================== COVER LETTER GENERATION ====================
    
    async def generate_cover_letter(self, job: JobListing) -> Optional[str]:
        """
        Step 7: Generate smart cover letter using LLM.
        
        Args:
            job: Job listing to generate cover letter for
        
        Returns:
            Optional[str]: Generated cover letter or None
        """
        if not self.use_llm:
            return None
        
        logger.info(f"✍️ Generating cover letter for {job.title}...")
        
        try:
            # Try Gemini first (faster and cheaper)
            if self.gemini_api_key and self.gemini_api_key != 'your-gemini-api-key':
                try:
                    return await self._generate_cover_letter_gemini(job)
                except Exception as e:
                    logger.warning(f"⚠️ Gemini API failed: {e}, trying OpenAI...")
            
            # Fallback to OpenAI
            if self.openai_api_key and self.openai_api_key != 'your-openai-api-key':
                return await self._generate_cover_letter_openai(job)
            
            logger.warning("⚠️ No valid LLM API key configured")
            return None
        
        except Exception as e:
            logger.error(f"❌ Error generating cover letter: {e}")
            return None
    
    async def _generate_cover_letter_openai(self, job: JobListing) -> str:
        """Generate cover letter using OpenAI API."""
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(api_key=self.openai_api_key)
        
        prompt = f"""
        Write a professional, concise cover letter for this job application:
        
        Job Title: {job.title}
        Company: {job.company}
        Location: {job.location}
        
        Job Description (excerpt):
        {job.description[:500]}
        
        Candidate Resume (excerpt):
        {self.resume_text[:500]}
        
        Requirements:
        - Maximum 200 words
        - Professional tone
        - Highlight relevant skills
        - Express enthusiasm
        - No placeholders or [Your Name] tags
        """
        
        response = await client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are a professional cover letter writer."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        
        cover_letter = response.choices[0].message.content
        if cover_letter:
            cover_letter = cover_letter.strip()
        logger.info("✅ Cover letter generated with OpenAI")
        return cover_letter or ""
    
    async def _generate_cover_letter_gemini(self, job: JobListing) -> str:
        """Generate cover letter using Gemini API."""
        try:
            import google.generativeai as genai  # type: ignore
            
            genai.configure(api_key=self.gemini_api_key)  # type: ignore
            model = genai.GenerativeModel('gemini-2.5-flash')  # type: ignore # Latest fast model
            
            prompt = f"""
            Write a professional, concise cover letter for this job application:
            
            Job Title: {job.title}
            Company: {job.company}
            Location: {job.location}
            
            Job Description (excerpt):
            {job.description[:500]}
            
            Candidate Resume (excerpt):
            {self.resume_text[:500]}
            
            Requirements:
            - Maximum 200 words
            - Professional tone
            - Highlight relevant skills from the resume that match the job
            - Express enthusiasm for the role
            - No placeholders like [Your Name]
            - Start with "Dear Hiring Manager,"
            - End with "Best regards"
            - Do not include signature name
            """
            
            response = model.generate_content(prompt)  # type: ignore
            cover_letter = response.text.strip() if response.text else ""  # type: ignore
            
            logger.info("✅ Cover letter generated with Gemini")
            return cover_letter
        
        except Exception as e:
            logger.error(f"❌ Error with Gemini API: {e}")
            # Return fallback cover letter
            return f"""Dear Hiring Manager,

I am excited to apply for the {job.title} position at {job.company}. With my background in software development and proven experience in relevant technologies, I am confident I would be a valuable addition to your team.

My skills align well with your requirements, and I am particularly drawn to this opportunity because of {job.company}'s innovative approach and strong industry presence.

I look forward to the opportunity to discuss how my experience and skills can contribute to your team's success.

Best regards"""
    
    # ==================== BATCH APPLICATION ====================
    
    async def apply_to_qualified_jobs(self) -> List[ApplicationResult]:
        """
        Apply to all qualified jobs (above threshold).
        
        Returns:
            List[ApplicationResult]: Results of all application attempts
        """
        # Get qualified jobs
        qualified_jobs = [j for j in self.jobs_found if j.match_score >= self.match_threshold]
        
        # Limit to max applications
        jobs_to_apply = qualified_jobs[:self.max_applications_per_session]
        
        logger.info(f"🚀 Starting batch application to {len(jobs_to_apply)} jobs...")
        
        for i, job in enumerate(jobs_to_apply, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Application {i}/{len(jobs_to_apply)}")
            logger.info(f"{'='*60}")
            
            result = await self.auto_apply_job(job)
            self.jobs_applied.append(result)
            
            # Human-like delay between applications
            if i < len(jobs_to_apply):
                delay = random.uniform(10, 20)  # 10-20 seconds between applications
                logger.info(f"⏳ Waiting {delay:.1f}s before next application...")
                await asyncio.sleep(delay)
        
        logger.info(f"\n✅ Batch application complete!")
        return self.jobs_applied
    
    # ==================== REPORTING ====================
    
    def generate_report(self) -> Dict[str, Any]:
        """
        Step 8: Generate comprehensive session report.
        
        Returns:
            Dict: Report data including statistics and results
        """
        logger.info("📊 Generating session report...")
        
        successful = [r for r in self.jobs_applied if r.status == 'success']
        failed = [r for r in self.jobs_applied if r.status == 'failed']
        skipped = [r for r in self.jobs_applied if r.status == 'skipped']
        
        report = {
            'session_date': datetime.now().isoformat(),
            'statistics': {
                'total_jobs_found': len(self.jobs_found),
                'total_qualified': len([j for j in self.jobs_found if j.match_score >= self.match_threshold]),
                'applications_submitted': len(successful),
                'applications_failed': len(failed),
                'applications_skipped': len(skipped),
                'cover_letters_generated': len([r for r in self.jobs_applied if r.cover_letter_generated])
            },
            'top_matches': [
                {
                    'title': j.title,
                    'company': j.company,
                    'location': j.location,
                    'match_score': f"{j.match_score:.1f}%",
                    'keywords_matched': len(j.keywords_matched) if j.keywords_matched else 0
                }
                for j in self.jobs_found[:10]
            ],
            'applications': [
                {
                    'title': r.job_title,
                    'company': r.company,
                    'status': r.status,
                    'timestamp': r.timestamp,
                    'error': r.error_message
                }
                for r in self.jobs_applied
            ]
        }
        
        # Save report to file
        report_path = Path(f"reports/session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"✅ Report saved to {report_path}")
        
        return report
    
    async def send_email_report(self, report: Dict[str, Any]):
        """
        Send report via email.
        
        Args:
            report: Report data to send
        """
        email_to = os.getenv('REPORT_EMAIL')
        email_from = os.getenv('SMTP_FROM_EMAIL')
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_password = os.getenv('SMTP_PASSWORD')
        
        if not all([email_to, email_from, smtp_server, smtp_password]):
            logger.warning("⚠️ Email configuration incomplete. Skipping email report.")
            return
        
        try:
            # Create email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"LinkedIn Auto Apply Report - {datetime.now().strftime('%Y-%m-%d')}"
            msg['From'] = email_from  # type: ignore
            msg['To'] = email_to  # type: ignore
            
            # Create HTML body
            html = self._create_html_report(report)
            msg.attach(MIMEText(html, 'html'))
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:  # type: ignore
                server.starttls()
                server.login(email_from, smtp_password)  # type: ignore
                server.send_message(msg)
            
            logger.info(f"✅ Report emailed to {email_to}")
        
        except Exception as e:
            logger.error(f"❌ Error sending email report: {e}")
    
    def _create_html_report(self, report: Dict[str, Any]) -> str:
        """Create HTML formatted report."""
        stats = report['statistics']
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                h1 {{ color: #0073b1; }}
                h2 {{ color: #333; border-bottom: 2px solid #0073b1; padding-bottom: 10px; }}
                .stats {{ background: #f3f6f8; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .stat {{ display: inline-block; margin: 10px 20px; }}
                .stat-value {{ font-size: 32px; font-weight: bold; color: #0073b1; }}
                .stat-label {{ font-size: 14px; color: #666; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #0073b1; color: white; }}
                .success {{ color: #057642; font-weight: bold; }}
                .failed {{ color: #cc1016; font-weight: bold; }}
                .skipped {{ color: #f5bb00; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>🤖 LinkedIn Auto Apply Report</h1>
            <p><strong>Date:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
            
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{stats['total_jobs_found']}</div>
                    <div class="stat-label">Jobs Found</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{stats['total_qualified']}</div>
                    <div class="stat-label">Qualified Jobs</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{stats['applications_submitted']}</div>
                    <div class="stat-label">Applications Submitted</div>
                </div>
            </div>
            
            <h2>📊 Top Job Matches</h2>
            <table>
                <tr>
                    <th>Job Title</th>
                    <th>Company</th>
                    <th>Location</th>
                    <th>Match Score</th>
                </tr>
        """
        
        for job in report['top_matches'][:10]:
            html += f"""
                <tr>
                    <td>{job['title']}</td>
                    <td>{job['company']}</td>
                    <td>{job['location']}</td>
                    <td>{job['match_score']}</td>
                </tr>
            """
        
        html += """
            </table>
            
            <h2>📝 Applications Submitted</h2>
            <table>
                <tr>
                    <th>Job Title</th>
                    <th>Company</th>
                    <th>Status</th>
                    <th>Time</th>
                </tr>
        """
        
        for app in report['applications']:
            status_class = app['status']
            status_text = app['status'].capitalize()
            html += f"""
                <tr>
                    <td>{app['title']}</td>
                    <td>{app['company']}</td>
                    <td class="{status_class}">{status_text}</td>
                    <td>{datetime.fromisoformat(app['timestamp']).strftime('%I:%M %p')}</td>
                </tr>
            """
        
        html += """
            </table>
        </body>
        </html>
        """
        
        return html
    
    def print_console_report(self, report: Dict[str, Any]):
        """Print formatted report to console."""
        stats = report['statistics']
        
        print("\n" + "="*70)
        print("🤖 LINKEDIN AUTO APPLY - SESSION REPORT")
        print("="*70)
        print(f"\n📅 Date: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\n")
        
        print("📊 STATISTICS")
        print("-" * 70)
        print(f"  Total Jobs Found:          {stats['total_jobs_found']}")
        print(f"  Qualified Jobs (>={self.match_threshold}%): {stats['total_qualified']}")
        print(f"  Applications Submitted:    {stats['applications_submitted']} ✅")
        print(f"  Applications Failed:       {stats['applications_failed']} ❌")
        print(f"  Applications Skipped:      {stats['applications_skipped']} ⏭️")
        print(f"  Cover Letters Generated:   {stats['cover_letters_generated']} ✍️")
        
        if report['top_matches']:
            print(f"\n🎯 TOP 10 JOB MATCHES")
            print("-" * 70)
            for i, job in enumerate(report['top_matches'][:10], 1):
                print(f"\n{i}. {job['title']} at {job['company']}")
                print(f"   📍 {job['location']}")
                print(f"   📊 Match Score: {job['match_score']}")
                print(f"   🔑 Keywords Matched: {job['keywords_matched']}")
        
        if report['applications']:
            print(f"\n📝 APPLICATIONS SUBMITTED")
            print("-" * 70)
            for i, app in enumerate(report['applications'], 1):
                status_emoji = {'success': '✅', 'failed': '❌', 'skipped': '⏭️'}
                print(f"\n{i}. {app['title']} at {app['company']}")
                print(f"   Status: {status_emoji.get(app['status'], '❓')} {app['status'].upper()}")
                print(f"   Time: {datetime.fromisoformat(app['timestamp']).strftime('%I:%M %p')}")
                if app['error']:
                    print(f"   Error: {app['error']}")
        
        print("\n" + "="*70)
        print("✅ Session complete!")
        print("="*70 + "\n")
    
    # ==================== CLEANUP ====================
    
    async def cleanup(self):
        """Close browser and cleanup resources."""
        logger.info("🧹 Cleaning up resources...")
        
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            
            logger.info("✅ Cleanup complete")
        
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")
    
    # ==================== MAIN WORKFLOW ====================
    
    async def run_automation(
        self,
        keywords: str,
        location: str = "United States",
        experience_level: Optional[str] = None,
        job_type: Optional[str] = None,
        max_jobs: int = 50
    ):
        """
        Run the complete automation workflow.
        
        Args:
            keywords: Job search keywords
            location: Job location
            experience_level: Experience level filter
            job_type: Job type filter
            max_jobs: Maximum jobs to parse
        """
        try:
            logger.info("🚀 Starting LinkedIn Auto Apply automation...")
            logger.info(f"🔍 Search: {keywords} in {location}")
            
            # Phase 1: Initialize browser
            await self.initialize_browser()
            
            # Phase 2: Login
            login_success = await self.login_linkedin()
            if not login_success:
                raise Exception("Login failed")
            
            # Phase 3: Search jobs
            jobs_count = await self.search_jobs(
                keywords=keywords,
                location=location,
                experience_level=experience_level,
                job_type=job_type,
                easy_apply_only=True
            )
            
            if jobs_count == 0:
                logger.warning("⚠️ No jobs found matching criteria")
                return
            
            # Phase 4: Parse job listings
            await self.parse_job_listings(max_jobs=max_jobs)
            
            # Phase 5: Analyze job fit
            await self.analyze_all_jobs()
            
            # Phase 6: Apply to qualified jobs
            await self.apply_to_qualified_jobs()
            
            # Phase 7: Generate report
            report = self.generate_report()
            self.print_console_report(report)
            
            # Phase 8: Send email report (optional)
            if os.getenv('SEND_EMAIL_REPORT', 'false').lower() == 'true':
                await self.send_email_report(report)
            
            logger.info("✅ Automation workflow completed successfully!")
        
        except Exception as e:
            logger.error(f"❌ Automation workflow failed: {e}")
            raise
        
        finally:
            await self.cleanup()


# ==================== MAIN ENTRY POINT ====================

async def main():
    """Main entry point for the automation script."""
    
    # Configuration
    config = {
        'keywords': os.getenv('JOB_KEYWORDS', 'AI Engineer'),
        'location': os.getenv('JOB_LOCATION', 'United States'),
        'experience_level': os.getenv('EXPERIENCE_LEVEL'),  # e.g., "Mid-Senior level"
        'job_type': os.getenv('JOB_TYPE'),  # e.g., "Full-time"
        'max_jobs': int(os.getenv('MAX_JOBS_TO_PARSE', '50')),
        'headless': os.getenv('HEADLESS_MODE', 'false').lower() == 'true',
        'use_llm': os.getenv('USE_LLM', 'true').lower() == 'true'
    }
    
    logger.info("="*70)
    logger.info("🤖 LINKEDIN AUTO APPLY - AUTONOMOUS JOB APPLICATION AGENT")
    logger.info("="*70)
    logger.info(f"\n📋 Configuration:")
    logger.info(f"  Keywords: {config['keywords']}")
    logger.info(f"  Location: {config['location']}")
    logger.info(f"  Experience Level: {config['experience_level'] or 'Any'}")
    logger.info(f"  Job Type: {config['job_type'] or 'Any'}")
    logger.info(f"  Max Jobs: {config['max_jobs']}")
    logger.info(f"  Headless Mode: {config['headless']}")
    logger.info(f"  LLM Enabled: {config['use_llm']}\n")
    
    # Create automation agent
    agent = LinkedInAutoApply(
        headless=config['headless'],
        use_llm=config['use_llm']
    )
    
    # Run automation
    await agent.run_automation(
        keywords=config['keywords'],
        location=config['location'],
        experience_level=config['experience_level'],
        job_type=config['job_type'],
        max_jobs=config['max_jobs']
    )


if __name__ == "__main__":
    # Run the automation
    asyncio.run(main())
