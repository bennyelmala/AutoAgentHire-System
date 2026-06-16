"""LinkedIn Recommended Jobs Scraper.

Playwright automation for fetching LinkedIn's recommended jobs list.
"""

import os
import sys
import asyncio
from typing import List, Dict, Set, Optional, Any
from playwright.async_api import async_playwright, Page, Browser
from dotenv import load_dotenv

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv()

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")


class LinkedInRecommendedJobsScraper:
    """
    Scraper for LinkedIn recommended jobs with human-like behavior
    """
    
    def __init__(self, email: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize scraper with LinkedIn credentials
        
        Args:
            email: LinkedIn email (defaults to env var)
            password: LinkedIn password (defaults to env var)
        """
        self.email = email or LINKEDIN_EMAIL
        self.password = password or LINKEDIN_PASSWORD
        self.browser: Browser = None
        self.page: Page = None
        self.playwright = None
        self.context = None
        
        # Validate credentials
        if not self.email or not self.password:
            raise ValueError(
                "LinkedIn credentials are required. Please provide email/password from the frontend."
            )

    def _is_logged_in_url(self, url: str) -> bool:
        """Heuristic: URLs that indicate the session is authenticated."""
        u = (url or "").lower()
        return any(token in u for token in ["/feed", "/mynetwork", "/jobs", "/in/"]) and "/login" not in u

    def _is_checkpoint_url(self, url: str) -> bool:
        u = (url or "").lower()
        return any(token in u for token in ["checkpoint", "challenge", "captcha", "authwall"]) 
        
    async def human_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Random human-like delay"""
        import random
        await asyncio.sleep(random.uniform(min_seconds, max_seconds))

    def _page_alive(self) -> bool:
        """Return True if page exists and is not closed."""
        try:
            return self.page is not None and not self.page.is_closed()
        except Exception:
            return False

    async def _safe_evaluate(self, script: str):
        """Evaluate JS only if the page is still alive."""
        if not self._page_alive():
            raise RuntimeError("Playwright page is closed")
        return await self.page.evaluate(script)
        
    async def initialize_browser(self):
        """Launch browser with human-like configuration"""
        from backend.config import settings
        is_headless = settings.PLAYWRIGHT_HEADLESS
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=is_headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        # Create context with realistic viewport and user agent
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        self.page = await self.context.new_page()
        
        # Inject script to mask automation
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
    async def login_to_linkedin(self) -> bool:
        """
        Login to LinkedIn with credentials
        
        Returns:
            bool: True if login successful, False otherwise
        """
        try:
            print("🔐 Logging into LinkedIn...")
            if not self._page_alive():
                raise RuntimeError("Page is not available (closed)")

            await self.page.goto("https://www.linkedin.com/login", timeout=60000, wait_until="domcontentloaded")
            await self.human_delay(2, 3)
            
            # Wait for form to be ready
            await self.page.wait_for_selector("input#username", timeout=10000)
            
            # Fill credentials
            await self.page.fill("input#username", self.email)
            await self.human_delay(0.5, 1)
            await self.page.fill("input#password", self.password)
            await self.human_delay(0.5, 1)
            
            # Submit login
            await self.page.click("button[type='submit']")
            
            # Wait for navigation with longer timeout
            try:
                await self.page.wait_for_load_state("networkidle", timeout=60000)
            except:
                # If networkidle times out, wait for domcontentloaded
                await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                
            await self.human_delay(3, 5)
            
            # Check if login successful
            current_url = self.page.url
            if self._is_logged_in_url(current_url):
                print("✅ Login successful!")
                return True
            elif self._is_checkpoint_url(current_url):
                print("⚠️  Security checkpoint detected!")
                return False
            else:
                # If we are still on the login page, credentials are wrong or a captcha blocked submission.
                if "/login" in current_url:
                    print(f"❌ Still on LinkedIn login page after submit: {current_url}")
                    return False

                print(f"⚠️  Unexpected URL after login: {current_url}")
                # Still try to continue - user might be logged in
                return True
                
        except Exception as e:
            print(f"❌ Login error: {str(e)}")
            return False
            
    async def navigate_to_recommended_jobs(self) -> bool:
        """
        Navigate to LinkedIn recommended jobs page
        
        Returns:
            bool: True if navigation successful
        """
        try:
            print("🧭 Navigating to Recommended Jobs...")
            if not self._page_alive():
                raise RuntimeError("Page is not available (closed)")
            await self.page.goto(
                "https://www.linkedin.com/jobs/collections/recommended/",
                timeout=60000,
                wait_until="domcontentloaded"
            )
            await self.human_delay(2, 3)
            
            # Wait for job listings to load
            try:
                await self.page.wait_for_selector(
                    "li.jobs-search-results__list-item, div.job-card-container",
                    timeout=10000
                )
                print("✅ Recommended jobs page loaded")
                return True
            except:
                print("⚠️  No job cards found, but continuing...")
                return True
                
        except Exception as e:
            print(f"❌ Navigation error: {str(e)}")
            return False
            
    async def scroll_and_load_jobs(self, scroll_iterations: int = 8):
        """
        Scroll page to load lazy-loaded job cards
        
        Args:
            scroll_iterations: Number of times to scroll
        """
        print(f"📜 Scrolling to load jobs ({scroll_iterations} iterations)...")

        if not self._page_alive():
            raise RuntimeError("Page is not available (closed)")
        
        for i in range(scroll_iterations):
            # Scroll down
            await self._safe_evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
            await self.human_delay(1.5, 2.5)
            
            # Occasionally scroll up a bit (human behavior)
            if i % 3 == 0 and i > 0:
                await self._safe_evaluate("window.scrollBy(0, -200)")
                await self.human_delay(0.5, 1)
                
        # Scroll to bottom
        await self._safe_evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await self.human_delay(2, 3)
        print("✅ Scrolling complete")
        
    async def extract_job_data(self) -> List[Dict[str, Any]]:
        """
        Extract job data from loaded job cards
        
        Returns:
            List of job dictionaries with title, company, location, url
        """
        jobs: List[Dict[str, Any]] = []
        seen_links: Set[str] = set()
        
        print("🔍 Extracting job data...")
        
        # Try multiple selectors for job cards
        job_card_selectors = [
            "li.jobs-search-results__list-item",
            "div.scaffold-layout__list-item",
            "div.job-card-container",
            "li[class*='job']"
        ]
        
        job_cards = []
        for selector in job_card_selectors:
            try:
                cards = await self.page.query_selector_all(selector)
                if cards:
                    job_cards = cards
                    print(f"✅ Found {len(job_cards)} job cards using selector: {selector}")
                    break
            except:
                continue
                
        if not job_cards:
            print("⚠️  No job cards found")
            return jobs
            
        for idx, card in enumerate(job_cards):
            try:
                # Extract job title and link
                title = None
                job_url = None
                
                # Try multiple selectors for title/link
                title_selectors = [
                    "a.job-card-list__title",
                    "a.job-card-container__link",
                    "a[class*='job-card']",
                    "h3.job-card-list__title a",
                    "a[data-control-name*='job']"
                ]
                
                for sel in title_selectors:
                    try:
                        link_el = await card.query_selector(sel)
                        if link_el:
                            title = await link_el.inner_text()
                            job_url = await link_el.get_attribute("href")
                            if title and job_url:
                                break
                    except:
                        continue
                        
                if not title or not job_url:
                    continue
                    
                # Make URL absolute
                if not job_url.startswith("http"):
                    job_url = f"https://www.linkedin.com{job_url}"
                    
                # Deduplicate by URL
                if job_url in seen_links:
                    continue
                    
                # Extract company name
                company = "Unknown Company"
                company_selectors = [
                    "h4.job-card-container__company-name",
                    "span.job-card-container__company-name",
                    "a.job-card-container__company-name",
                    "div[class*='company-name']",
                    "h4[class*='company']"
                ]
                
                for sel in company_selectors:
                    try:
                        company_el = await card.query_selector(sel)
                        if company_el:
                            company = await company_el.inner_text()
                            if company:
                                break
                    except:
                        continue
                        
                # Extract location
                location = "Unknown Location"
                location_selectors = [
                    "span.job-card-container__metadata-item",
                    "li.job-card-container__metadata-item",
                    "div[class*='location']",
                    "span[class*='location']"
                ]
                
                for sel in location_selectors:
                    try:
                        location_el = await card.query_selector(sel)
                        if location_el:
                            loc_text = await location_el.inner_text()
                            if loc_text and loc_text.strip():
                                location = loc_text
                                break
                    except:
                        continue
                        
                # Add to results
                seen_links.add(job_url)
                jobs.append({
                    "title": title.strip(),
                    "company": company.strip(),
                    "location": location.strip(),
                    "url": job_url,
                    "index": idx + 1
                })
                
            except Exception as e:
                print(f"⚠️  Error extracting job {idx + 1}: {str(e)}")
                continue
                
        print(f"✅ Extracted {len(jobs)} unique jobs")
        return jobs
        
    async def fetch_recommended_jobs(self) -> List[Dict[str, str]]:
        """
        Main method to fetch all recommended jobs
        
        Returns:
            List of job dictionaries
        """
        try:
            # Initialize
            await self.initialize_browser()
            
            # Login
            if not await self.login_to_linkedin():
                raise RuntimeError("Login failed (invalid credentials or LinkedIn checkpoint)")

            # Defensive: if LinkedIn redirected back to login/authwall, stop early.
            current_url = self.page.url if self._page_alive() else ""
            if (not self._is_logged_in_url(current_url)) or self._is_checkpoint_url(current_url) or ("/login" in (current_url or "")):
                raise RuntimeError(f"Login not confirmed (current URL: {current_url})")
                
            # Navigate to recommended jobs
            if not await self.navigate_to_recommended_jobs():
                raise RuntimeError("Navigation to recommended jobs failed")
                
            # Scroll and load all jobs
            await self.scroll_and_load_jobs(scroll_iterations=8)
            
            # Extract job data
            jobs = await self.extract_job_data()
            
            return jobs
            
        except Exception as e:
            print(f"❌ Error fetching recommended jobs: {str(e)}")
            raise
            
        finally:
            # Cleanup
            if self.browser:
                print("\n🧹 Cleaning up...")
                try:
                    await self.browser.close()
                except Exception as e:
                    print(f"⚠️  Browser cleanup warning: {str(e)}")
                    
            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception as e:
                    print(f"⚠️  Playwright cleanup warning: {str(e)}")
                    
            print("✅ Cleanup complete")


async def fetch_recommended_jobs(email: Optional[str] = None, password: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Convenience function to fetch recommended jobs
    
    Args:
        email: LinkedIn email
        password: LinkedIn password
        
    Returns:
        List of job dictionaries
    """
    scraper = LinkedInRecommendedJobsScraper(email=email, password=password)
    return await scraper.fetch_recommended_jobs()


# Test function
async def main():
    """Test the scraper"""
    jobs = await fetch_recommended_jobs()
    print(f"\n{'='*60}")
    print(f"TOTAL JOBS FOUND: {len(jobs)}")
    print(f"{'='*60}\n")
    
    for job in jobs[:5]:  # Show first 5
        print(f"Title: {job['title']}")
        print(f"Company: {job['company']}")
        print(f"Location: {job['location']}")
        print(f"URL: {job['url']}")
        print("-" * 60)


if __name__ == "__main__":
    asyncio.run(main())
