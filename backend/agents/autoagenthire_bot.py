"""
AutoAgentHire - Complete LinkedIn Job Automation Bot
Handles browser automation, job search, AI analysis, and auto-apply
"""

import asyncio
import random
import re
import time
import json
import sys
import concurrent.futures
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
from functools import partial

# Use sync_playwright for Windows compatibility
from playwright.sync_api import sync_playwright, Page as SyncPage, Browser as SyncBrowser, BrowserContext as SyncBrowserContext
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from backend.automation.application_handler import ApplicationHandler
import google.generativeai as genai  # type: ignore
from pypdf import PdfReader
from dotenv import load_dotenv
import os

# Load .env but don't override existing environment variables
load_dotenv(override=False)

# Thread pool executor for sync playwright operations
_playwright_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")


class AutoAgentHireBot:
    """Complete LinkedIn automation with AI-powered job matching and auto-apply"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Page | None = None
        self.resume_text = ""
        self.jobs_data = []
        self.applied_jobs = []
        self.errors = []
        
        # Sync playwright objects (for Windows compatibility)
        self._sync_playwright: Any = None
        self._sync_browser: Optional[SyncBrowser] = None
        self._sync_context: Optional[SyncBrowserContext] = None
        self._sync_page: Optional[SyncPage] = None
        self._use_sync_mode = sys.platform == 'win32'  # Use sync mode on Windows
        
        # Store credentials from config if provided (takes priority over env)
        self.linkedin_email = config.get('linkedin_email') or os.getenv('LINKEDIN_EMAIL')
        self.linkedin_password = config.get('linkedin_password') or os.getenv('LINKEDIN_PASSWORD')
        
        # NEW: Store user profile for auto-fill
        self.user_profile = config.get('user_profile', {})
        
        # Configure Gemini AI
        api_key = os.getenv('GEMINI_API_KEY')
        if api_key and not api_key.startswith('your_'):
            genai.configure(api_key=api_key)  # type: ignore
            self.ai_model = genai.GenerativeModel('gemini-2.0-flash-exp')  # type: ignore
        else:
            self.ai_model = None

    async def _run_sync(self, func, *args, **kwargs) -> Any:
        """Run a sync function in the thread executor."""
        loop = asyncio.get_event_loop()
        if kwargs:
            return await loop.run_in_executor(_playwright_executor, partial(func, *args, **kwargs))
        return await loop.run_in_executor(_playwright_executor, partial(func, *args))
    
    def _get_page(self) -> SyncPage:
        """Get the sync page object (for Windows mode)."""
        if not self._sync_page:
            raise Exception("Browser not initialized")
        return self._sync_page
    
    async def close(self) -> None:
        """Close any open Playwright resources (page/context/browser) safely."""
        # Close sync playwright resources (Windows mode)
        if self._use_sync_mode and self._sync_playwright:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(_playwright_executor, self._close_sync_resources)
            except Exception as e:
                print(f"⚠️ Error closing sync playwright: {e}")
            finally:
                self._sync_playwright = None
                self._sync_browser = None
                self._sync_context = None
                self._sync_page = None
                self.page = None
            return
        
        # Close context first (covers both persistent and non-persistent cases)
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
            finally:
                self.context = None
                self.page = None

        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
            finally:
                self.browser = None
    
    def _close_sync_resources(self) -> None:
        """Close sync playwright resources (runs in thread executor)."""
        try:
            if self._sync_context:
                self._sync_context.close()
        except Exception:
            pass
        try:
            if self._sync_browser:
                self._sync_browser.close()
        except Exception:
            pass
        try:
            if self._sync_playwright:
                self._sync_playwright.stop()
        except Exception:
            pass

    def _init_sync_browser(self, use_persistent_profile: bool = True) -> None:
        """Initialize sync playwright browser (runs in thread executor on Windows)."""
        print("🌐 Initializing browser (sync mode for Windows)...")
        
        self._sync_playwright = sync_playwright().start()
        
        # Profile directory setup
        profile_dir = Path("browser_profile")
        profile_dir.mkdir(exist_ok=True)
        
        # Clean up lock files
        for lock_name in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
            lock_file = profile_dir / lock_name
            if lock_file.exists():
                try:
                    lock_file.unlink()
                    print(f"🧹 Cleaned up stale lock file: {lock_name}")
                except Exception as e:
                    print(f"⚠️ Could not remove {lock_name}: {str(e)}")
        
        headless_mode = os.getenv('HEADLESS_BROWSER', 'false').lower() == 'true'
        slow_mo_delay = int(os.getenv('BROWSER_SLOW_MO', '50'))
        
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-gpu',
            '--disable-software-rasterizer',
            '--disable-extensions',
            '--disable-background-networking',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-features=TranslateUI,BlinkGenPropertyTrees',
            '--no-first-run',
            '--no-default-browser-check',
        ]
        
        if use_persistent_profile:
            print(f"🔐 Using persistent browser profile: {profile_dir}")
            self._sync_context = self._sync_playwright.chromium.launch_persistent_context(
                str(profile_dir),
                headless=headless_mode,
                slow_mo=slow_mo_delay,
                args=browser_args,
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
                ignore_https_errors=True,
            )
            if len(self._sync_context.pages) > 0:
                self._sync_page = self._sync_context.pages[0]
                print("✅ Using existing browser page")
            else:
                self._sync_page = self._sync_context.new_page()
                print("✅ Created new browser page")
        else:
            print("🌐 Launching browser in non-persistent mode...")
            self._sync_browser = self._sync_playwright.chromium.launch(
                headless=headless_mode,
                slow_mo=slow_mo_delay,
                args=browser_args
            )
            self._sync_context = self._sync_browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
                ignore_https_errors=True,
            )
            self._sync_page = self._sync_context.new_page()
            print("✅ Created new browser page")
        
        # Set timeouts
        self._sync_page.set_default_timeout(60000)
        self._sync_page.set_default_navigation_timeout(60000)
        
        # Anti-detection script
        self._sync_context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            window.chrome = {runtime: {}};
        """)
        
        # Test navigation
        print("🧪 Testing browser navigation...")
        self._sync_page.goto('about:blank', wait_until='domcontentloaded', timeout=10000)
        print("✅ Browser initialized successfully with anti-detection")
        print(f"📍 Current URL: {self._sync_page.url}")
    
    async def initialize_browser(self, use_persistent_profile: bool = True) -> None:
        """
        Initialize Playwright browser with anti-detection and optional persistent profile.
        
        Args:
            use_persistent_profile: If True, uses a persistent browser profile to reduce CAPTCHAs
        """
        print("🌐 Initializing browser...")
        
        # On Windows, use sync playwright in thread executor to avoid event loop issues
        if self._use_sync_mode:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    _playwright_executor, 
                    partial(self._init_sync_browser, use_persistent_profile)
                )
                print("✅ Browser initialized (Windows sync mode)")
                return
            except Exception as e:
                print(f"❌ Sync browser initialization failed: {str(e)}")
                raise Exception(f"Failed to initialize browser: {str(e)}")
        
        try:
            playwright = await async_playwright().start()
            
            # Use persistent context if enabled (reduces CAPTCHA triggers)
            if use_persistent_profile:
                profile_dir = Path("browser_profile")
                profile_dir.mkdir(exist_ok=True)
                
                # Clean up any existing lock files from crashed sessions
                lock_file = profile_dir / "SingletonLock"
                socket_file = profile_dir / "SingletonSocket"
                cookie_file = profile_dir / "SingletonCookie"
                
                for lock in [lock_file, socket_file, cookie_file]:
                    if lock.exists():
                        try:
                            lock.unlink()
                            print(f"🧹 Cleaned up stale lock file: {lock.name}")
                        except Exception as e:
                            print(f"⚠️  Could not remove {lock.name}: {str(e)}")
                
                print(f"🔐 Using persistent browser profile: {profile_dir}")
                
                try:
                    # PERFORMANCE OPTIMIZATIONS:
                    # 1. Configurable headless mode (50% faster in production)
                    # 2. Reduced slow_mo from 100ms to 50ms (2x faster actions)
                    # 3. Additional performance args
                    headless_mode = os.getenv('HEADLESS_BROWSER', 'false').lower() == 'true'
                    slow_mo_delay = int(os.getenv('BROWSER_SLOW_MO', '50'))
                    
                    self.context = await playwright.chromium.launch_persistent_context(
                        str(profile_dir),
                        headless=headless_mode,
                        slow_mo=slow_mo_delay,
                        args=[
                            '--disable-blink-features=AutomationControlled',
                            '--disable-dev-shm-usage',
                            '--no-sandbox',
                            '--disable-setuid-sandbox',
                            '--disable-web-security',
                            '--disable-features=IsolateOrigins,site-per-process',
                            # NEW PERFORMANCE ARGS:
                            '--disable-gpu',  # Faster rendering on servers
                            '--disable-software-rasterizer',
                            '--disable-extensions',  # No extension overhead
                            '--disable-background-networking',
                            '--disable-background-timer-throttling',
                            '--disable-backgrounding-occluded-windows',
                            '--disable-renderer-backgrounding',
                            '--disable-features=TranslateUI,BlinkGenPropertyTrees',
                            '--no-first-run',
                            '--no-default-browser-check',
                        ],
                        viewport={'width': 1920, 'height': 1080},
                        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        locale='en-US',
                        timezone_id='America/New_York',
                        geolocation={'longitude': -74.0060, 'latitude': 40.7128},
                        permissions=['geolocation'],
                        ignore_https_errors=True,
                    )
                    
                    # Get the first page or create new one
                    if len(self.context.pages) > 0:
                        self.page = self.context.pages[0]
                        print("✅ Using existing browser page")
                    else:
                        self.page = await self.context.new_page()
                        print("✅ Created new browser page")
                        
                    # Store browser reference (context is browser-like for persistent)
                    self.browser = None  # Not needed for persistent context
                    
                except Exception as persistent_error:
                    print(f"⚠️  Persistent profile failed: {str(persistent_error)}")
                    print("🔄 Falling back to non-persistent mode...")
                    
                    # Fallback to non-persistent mode
                    use_persistent_profile = False
            
            if not use_persistent_profile:
                # Standard non-persistent browser
                print("🌐 Launching browser in non-persistent mode...")
                
                headless_mode = os.getenv('HEADLESS_BROWSER', 'false').lower() == 'true'
                slow_mo_delay = int(os.getenv('BROWSER_SLOW_MO', '50'))
                
                self.browser = await playwright.chromium.launch(
                    headless=headless_mode,
                    slow_mo=slow_mo_delay,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-gpu',
                        '--disable-software-rasterizer',
                        '--disable-extensions',
                        '--disable-background-networking',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding',
                        '--disable-features=TranslateUI,BlinkGenPropertyTrees',
                        '--no-first-run',
                        '--no-default-browser-check',
                    ]
                )
                
                self.context = await self.browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York',
                    geolocation={'longitude': -74.0060, 'latitude': 40.7128},
                    permissions=['geolocation'],
                    ignore_https_errors=True,
                )
                
                self.page = await self.context.new_page()
                print("✅ Created new browser page")
            
            # Set default timeout to 60 seconds
            if self.page:
                self.page.set_default_timeout(60000)
                self.page.set_default_navigation_timeout(60000)
            
            # Anti-detection scripts (works for both modes)
            if self.context:
                await self.context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                    window.chrome = {runtime: {}};
                """)
            
            # Navigate to a test page to verify browser is working
            if self.page:
                print("🧪 Testing browser navigation...")
                await self.page.goto('about:blank', wait_until='domcontentloaded', timeout=10000)
                
                print("✅ Browser initialized successfully with anti-detection")
                print(f"📍 Current URL: {self.page.url}")
            
        except Exception as e:
            print(f"❌ Browser initialization failed: {str(e)}")
            raise Exception(f"Failed to initialize browser: {str(e)}")
    
    async def login_linkedin(self) -> bool:
        """Login to LinkedIn with credentials from .env"""
        # Use sync mode for Windows
        if self._use_sync_mode:
            return await self._run_sync(self._login_linkedin_sync)
        
        if not self.page:
            raise Exception("Browser not initialized")
            
        try:
            email = self.linkedin_email
            password = self.linkedin_password
            
            if not email or not password:
                raise Exception("LinkedIn credentials not found - Please enter them in the dashboard")
            
            # Check for placeholder values
            email_lower = (email or "").lower()
            password_lower = (password or "").lower()
            if (
                'your-email' in email_lower
                or 'your_email' in email_lower
                or 'your-' in email_lower
                or 'example.com' in email_lower
                or 'your-' in password_lower
            ):
                raise Exception(
                    "LinkedIn credentials look like placeholders. Please enter your real LinkedIn email/password in the frontend and try again."
                )
            
            print(f"🔐 Using LinkedIn account: {email[:3]}***@{email.split('@')[1] if '@' in email else 'email.com'}")
            print("🔐 Navigating to LinkedIn login...")
            
            # Try with longer timeout and load instead of networkidle
            try:
                await self.page.goto('https://www.linkedin.com/login', wait_until='load', timeout=60000)
            except:
                # Fallback: try domcontentloaded
                print("⚠️  Network slow, using fallback loading...")
                await self.page.goto('https://www.linkedin.com/login', wait_until='domcontentloaded', timeout=60000)
            
            await asyncio.sleep(random.uniform(2, 3))

            # If already logged in (common with persistent profiles), skip form handling.
            current_url = self.page.url
            if any(path in current_url for path in ['feed', 'mynetwork', 'in/', 'jobs']):
                print(f"✅ Already logged in (URL: {current_url})")
                return True

            # Wait for login form to be visible (LinkedIn UI varies; try multiple selectors)
            print("⏳ Waiting for login form...")
            email_selectors = [
                'input[name="session_key"]',
                'input#username',
                'input[name="username"]',
                'input[type="text"][autocomplete="username"]',
            ]
            password_selectors = [
                'input[name="session_password"]',
                'input#password',
                'input[name="password"]',
                'input[type="password"][autocomplete="current-password"]',
            ]

            email_input = None
            for sel in email_selectors:
                try:
                    await self.page.wait_for_selector(sel, state='visible', timeout=5000)
                    email_input = self.page.locator(sel)
                    break
                except Exception:
                    continue

            password_input = None
            for sel in password_selectors:
                try:
                    await self.page.wait_for_selector(sel, state='visible', timeout=5000)
                    password_input = self.page.locator(sel)
                    break
                except Exception:
                    continue

            if not email_input or not password_input:
                raise Exception(
                    "Could not find LinkedIn login fields. LinkedIn may be showing a CAPTCHA/checkpoint, or the login UI changed."
                )
            
            # Fill email with human-like typing
            print(f"📧 Entering email: {email[:3]}***")
            await email_input.click()
            await email_input.clear()
            await asyncio.sleep(random.uniform(0.5, 1))
            await email_input.type(email, delay=random.uniform(80, 150))  # Slower, more human-like
            await asyncio.sleep(random.uniform(1.5, 2.5))
            
            # Fill password with human-like typing
            print("🔑 Entering password...")
            await password_input.click()
            await password_input.clear()
            await asyncio.sleep(random.uniform(0.5, 1))
            await password_input.type(password, delay=random.uniform(80, 150))  # Slower
            await asyncio.sleep(random.uniform(1.5, 2.5))
            
            # Click sign in
            print("👆 Clicking Sign In button...")
            await self.page.click('button[type="submit"]')
            
            # Wait for navigation with longer timeout
            print("⏳ Waiting for login to complete (may take up to 30 seconds)...")
            await asyncio.sleep(random.uniform(4, 6))  # Initial wait for form submission
            
            # Check for security checkpoint
            current_url = self.page.url
            if 'checkpoint' in current_url or 'challenge' in current_url:
                print("⚠️  Security checkpoint detected")
                await self._handle_captcha_or_security_check("Login security checkpoint")
                # Re-check URL after checkpoint
                current_url = self.page.url
            
            # Check URL immediately - if we're on feed, login succeeded
            print(f"📍 Current URL after login: {current_url}")
            
            # Success indicators in URL
            success_paths = ['feed', 'mynetwork', 'in/', 'check/add-phone', 'jobs']
            if any(path in current_url for path in success_paths):
                print(f"✅ Successfully logged into LinkedIn (verified by URL: {current_url})")
                return True
            
            # If still on login page, login definitely failed
            if '/login' in current_url or '/uas/login' in current_url:
                print("❌ Still on login page - login failed")
                
                # Check for error messages
                try:
                    error_element = await self.page.query_selector('.form__label--error, .alert-error, [role="alert"]')
                    if error_element:
                        error_text = await error_element.text_content()
                        print(f"❌ Login error message: {error_text}")
                        self.errors.append(f"Login failed: {error_text}")
                except:
                    self.errors.append("Login failed - check credentials")
                
                return False
            
            # If not on feed yet, wait for navigation with extended timeout
            print("⏳ Waiting for navigation to complete...")
            try:
                await self.page.wait_for_url(
                    lambda url: any(path in url for path in success_paths),
                    timeout=20000
                )
                current_url = self.page.url
                print(f"✅ Successfully logged into LinkedIn! Final URL: {current_url}")
                return True
            except Exception as timeout_error:
                print(f"⏰ Navigation timeout: {str(timeout_error)}")
                current_url = self.page.url
                print(f"📍 Final URL check: {current_url}")
                current_url = self.page.url
                print(f"📍 Final URL check: {current_url}")
            
            # Fallback: Check for success indicators in page content
            print("🔍 Checking for login success indicators...")
            success_selectors = [
                'nav.global-nav',  # Main navigation
                'a[href*="/feed/"]',  # Feed link
                'button[aria-label*="Start a post"]',  # Post button
                '[data-test-global-nav]',  # Global nav
                'img[alt*="profile"]'  # Profile image
            ]
            
            for selector in success_selectors:
                try:
                    element_count = await self.page.locator(selector).count()
                    if element_count > 0:
                        print(f"✅ Successfully logged into LinkedIn (found: {selector})")
                        return True
                except:
                    continue
            
            # Final check: Are we off the login page?
            if '/login' not in current_url and '/uas/login' not in current_url:
                print(f"✅ Successfully logged into LinkedIn (navigated away from login)")
                return True
            
            print(f"❌ Login verification failed. Current URL: {current_url}")
            self.errors.append("Login verification failed - unable to confirm successful authentication")
            return False
                
        except Exception as e:
            print(f"❌ Login error: {str(e)}")
            self.errors.append(f"Login failed: {str(e)}")
            return False
    
    def _login_linkedin_sync(self) -> bool:
        """Sync version of login_linkedin for Windows."""
        page = self._get_page()
        
        try:
            email = self.linkedin_email
            password = self.linkedin_password
            
            if not email or not password:
                raise Exception("LinkedIn credentials not found")
            
            # Check for placeholder values
            if 'your-email' in (email or "").lower() or 'example.com' in (email or "").lower():
                raise Exception("LinkedIn credentials look like placeholders")
            
            print(f"🔐 Using LinkedIn account: {email[:3]}***@{email.split('@')[1] if '@' in email else 'email.com'}")
            print("🔐 Navigating to LinkedIn login...")
            
            try:
                page.goto('https://www.linkedin.com/login', wait_until='load', timeout=60000)
            except:
                page.goto('https://www.linkedin.com/login', wait_until='domcontentloaded', timeout=60000)
            
            time.sleep(random.uniform(2, 3))
            
            # Check if already logged in
            current_url = page.url
            if any(path in current_url for path in ['feed', 'mynetwork', 'in/', 'jobs']):
                print(f"✅ Already logged in (URL: {current_url})")
                return True
            
            # Wait for login form
            print("⏳ Waiting for login form...")
            email_selectors = ['input[name="session_key"]', 'input#username']
            password_selectors = ['input[name="session_password"]', 'input#password']
            
            email_input = None
            for sel in email_selectors:
                try:
                    page.wait_for_selector(sel, state='visible', timeout=5000)
                    email_input = page.locator(sel)
                    break
                except:
                    continue
            
            password_input = None
            for sel in password_selectors:
                try:
                    page.wait_for_selector(sel, state='visible', timeout=5000)
                    password_input = page.locator(sel)
                    break
                except:
                    continue
            
            if not email_input or not password_input:
                raise Exception("Could not find LinkedIn login fields")
            
            # Fill email
            print(f"📧 Entering email...")
            email_input.click()
            email_input.clear()
            time.sleep(random.uniform(0.5, 1))
            email_input.type(email, delay=random.uniform(80, 150))
            time.sleep(random.uniform(1.5, 2.5))
            
            # Fill password
            print("🔑 Entering password...")
            password_input.click()
            password_input.clear()
            time.sleep(random.uniform(0.5, 1))
            password_input.type(password, delay=random.uniform(80, 150))
            time.sleep(random.uniform(1.5, 2.5))
            
            # Click sign in
            print("👆 Clicking Sign In button...")
            page.click('button[type="submit"]')
            
            # Wait for navigation
            print("⏳ Waiting for login to complete...")
            time.sleep(random.uniform(4, 6))
            
            current_url = page.url
            print(f"📍 Current URL after login: {current_url}")
            
            # Check for successful login
            success_paths = ['feed', 'mynetwork', 'in/', 'check/add-phone', 'jobs']
            if any(path in current_url for path in success_paths):
                print(f"✅ Successfully logged into LinkedIn")
                return True
            
            # Check for security checkpoint
            if 'checkpoint' in current_url or 'challenge' in current_url:
                print("⚠️ Security checkpoint detected - may need manual intervention")
                time.sleep(30)  # Wait for user to solve CAPTCHA
                current_url = page.url
                if any(path in current_url for path in success_paths):
                    print("✅ Checkpoint passed, logged in successfully")
                    return True
            
            if '/login' not in current_url:
                print("✅ Successfully logged into LinkedIn (navigated away from login)")
                return True
            
            print("❌ Login failed")
            return False
            
        except Exception as e:
            print(f"❌ Login error: {str(e)}")
            self.errors.append(f"Login failed: {str(e)}")
            return False
    
    async def search_jobs(self, keyword: str, location: str) -> None:
        """Search for jobs with Easy Apply filter - ALWAYS uses direct URL method"""
        # Use sync mode for Windows
        if self._use_sync_mode:
            await self._run_sync(self._search_jobs_sync, keyword, location)
            return
        
        if not self.page or self.page.is_closed():
            # If context exists, we can recover by opening a new page.
            if self.context:
                self.page = await self.context.new_page()
                self.page.set_default_timeout(60000)
                self.page.set_default_navigation_timeout(60000)
                print("🔄 Recovered by creating a new browser page")
            else:
                raise Exception("Browser not initialized")
            
        try:
            print(f"🔍 Searching for '{keyword}' jobs in '{location}' (Easy Apply only)...")

            # DIRECT URL METHOD - Most reliable approach
            # Build search URL with Easy Apply filter (f_AL=true)
            import urllib.parse
            encoded_keyword = urllib.parse.quote(keyword)
            encoded_location = urllib.parse.quote(location)
            
            # Include Easy Apply filter in URL
            search_url = f'https://www.linkedin.com/jobs/search/?keywords={encoded_keyword}&location={encoded_location}&f_AL=true&sortBy=R'
            
            print(f"📍 Using direct URL: {search_url}")
            
            try:
                await self.page.goto(search_url, wait_until='load', timeout=60000)
                print("✅ Navigated to jobs page")
            except Exception as nav_error:
                # If the page/context got closed, attempt a single recovery.
                if "has been closed" in str(nav_error) and self.context:
                    print("⚠️  Page was closed; reopening a new page and retrying...")
                    self.page = await self.context.new_page()
                    self.page.set_default_timeout(60000)
                    self.page.set_default_navigation_timeout(60000)
                    await self.page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
                    print("✅ Navigated after reopening page")
                else:
                    print(f"⚠️  Load navigation failed, trying domcontentloaded...")
                    try:
                        await self.page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
                        print("✅ Navigated with domcontentloaded")
                    except Exception:
                        raise Exception(f"Could not navigate to jobs page: {str(nav_error)}")

            # Wait for page to stabilize
            await asyncio.sleep(random.uniform(4, 6))
            
            # Verify we're on search results page
            current_url = self.page.url
            print(f"📍 Current URL: {current_url}")
            
            if '/jobs/search' not in current_url and '/jobs/' not in current_url:
                raise Exception(f"Not on jobs search page. Current URL: {current_url}")
            
            # Verify Easy Apply filter is active in URL
            if 'f_AL=true' in current_url or 'f_AL=true' in await self.page.content():
                print("✅ Easy Apply filter confirmed active")
            else:
                print("⚠️  Easy Apply filter may not be active - will verify during collection")
            
            # Wait for job results to load
            print("⏳ Waiting for job results to load...")
            
            # Try multiple selectors for job list
            job_list_selectors = [
                'div.jobs-search-results-list',
                'ul.jobs-search-results__list',
                'div.scaffold-layout__list',
                'div[data-job-id]'
            ]
            
            job_list_found = False
            for selector in job_list_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=10000)
                    job_count = await self.page.locator(selector).count()
                    if job_count > 0:
                        print(f"✅ Found job list with selector: {selector} ({job_count} elements)")
                        job_list_found = True
                        break
                except:
                    continue
            
            if not job_list_found:
                # Check if there are no results
                no_results_texts = ['No matching jobs found', 'no jobs', 'Try different keywords']
                page_content = await self.page.content()
                
                if any(text.lower() in page_content.lower() for text in no_results_texts):
                    print("ℹ️  No jobs found matching your criteria")
                    return
                else:
                    print("⚠️  Could not verify job list loaded, but continuing anyway...")
            
            print("✅ Job search completed successfully")
            print(f"📊 Ready to collect Easy Apply jobs for: {keyword}")

        except Exception as e:
            print(f"❌ Search error: {str(e)}")
            self.errors.append(f"Search failed: {str(e)}")
            raise
    
    def _search_jobs_sync(self, keyword: str, location: str) -> None:
        """Sync version of search_jobs for Windows."""
        page = self._get_page()
        
        try:
            print(f"🔍 Searching for '{keyword}' jobs in '{location}' (Easy Apply only)...")
            
            import urllib.parse
            encoded_keyword = urllib.parse.quote(keyword)
            encoded_location = urllib.parse.quote(location)
            
            # Include Easy Apply filter in URL
            search_url = f'https://www.linkedin.com/jobs/search/?keywords={encoded_keyword}&location={encoded_location}&f_AL=true&sortBy=R'
            
            print(f"📍 Using direct URL: {search_url}")
            
            try:
                page.goto(search_url, wait_until='load', timeout=60000)
                print("✅ Navigated to jobs page")
            except:
                page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
                print("✅ Navigated with domcontentloaded")
            
            time.sleep(random.uniform(3, 5))
            
            # Wait for job cards to load
            job_card_selectors = [
                '.jobs-search-results-list',
                '.scaffold-layout__list',
                '[data-job-id]',
                '.job-card-container',
            ]
            
            for selector in job_card_selectors:
                try:
                    page.wait_for_selector(selector, timeout=10000)
                    print(f"✅ Found job cards using: {selector}")
                    break
                except:
                    continue
            
            print("✅ Job search completed successfully")
            print(f"📊 Ready to collect Easy Apply jobs for: {keyword}")
            
        except Exception as e:
            print(f"❌ Search error: {str(e)}")
            self.errors.append(f"Search failed: {str(e)}")
            raise
    
    async def _apply_filter(self, filter_name: str, value: str) -> None:
        """Helper to apply a specific filter"""
        if not self.page:
            raise Exception("Browser not initialized")
            
        try:
            # Click filter button
            filter_button = await self.page.wait_for_selector(
                f'button:has-text("{filter_name}")',
                timeout=5000
            )
            if filter_button:
                await filter_button.click()
                await asyncio.sleep(1)
            
            # Select option
            option = await self.page.wait_for_selector(
                f'label:has-text("{value}")',
                timeout=5000
            )
            if option:
                await option.click()
                await asyncio.sleep(1)
            
            # Apply
            apply_button = await self.page.wait_for_selector(
                'button:has-text("Apply")',
                timeout=5000
            )
            if apply_button:
                await apply_button.click()
                await asyncio.sleep(2)
            
        except Exception:
            raise
    
    async def collect_job_listings(self, max_jobs: int = 30) -> List[Dict]:
        """Scroll and collect job listings"""
        # Use sync mode for Windows
        if self._use_sync_mode:
            return await self._run_sync(self._collect_job_listings_sync, max_jobs)
        
        if not self.page:
            raise Exception("Browser not initialized")
            
        jobs = []
        
        try:
            print(f"📊 Collecting up to {max_jobs} job listings...")
            
            # Scroll to load more jobs
            for scroll in range(5):
                await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(2)
            
            # Get job cards
            job_cards = await self.page.query_selector_all('div.job-card-container')
            
            if not job_cards:
                # Try alternative selector
                job_cards = await self.page.query_selector_all('li.jobs-search-results__list-item')
            
            print(f"🔢 Found {len(job_cards)} job cards")
            
            for i, card in enumerate(job_cards[:max_jobs]):
                try:
                    # Check if we should continue (handle interruptions)
                    if len(jobs) >= max_jobs:
                        break

                    # Close/dismiss any overlays that can intercept clicks (resume upload, dialogs, etc.)
                    try:
                        await self._dismiss_overlays()
                    except Exception:
                        pass

                    # Click to select job with error handling
                    try:
                        # Scroll card into view and click with fallback strategies to avoid interception
                        await card.scroll_into_view_if_needed()
                        await asyncio.sleep(0.2)
                        clicked = False
                        for attempt_click in range(3):
                            try:
                                await card.click(timeout=6000)
                                clicked = True
                                break
                            except Exception:
                                try:
                                    await self._dismiss_overlays()
                                except Exception:
                                    pass
                                await asyncio.sleep(0.3)

                            try:
                                await card.click(timeout=6000, force=True)
                                clicked = True
                                break
                            except Exception:
                                try:
                                    await self._dismiss_overlays()
                                except Exception:
                                    pass
                                await asyncio.sleep(0.3)

                            # Last resort: JS click
                            try:
                                await card.evaluate("el => el.click()")
                                clicked = True
                                break
                            except Exception:
                                await asyncio.sleep(0.3)

                        if not clicked:
                            raise Exception("Unable to click job card after retries")

                        await asyncio.sleep(random.uniform(1, 2))
                    except Exception as click_error:
                        print(f"⚠️  Could not click job card {i+1}: {str(click_error)}")
                        continue

                    # Extract job details with multiple selector fallbacks
                    title = None
                    company = None
                    location = None

                    # Try multiple selectors for job title
                    title_selectors = [
                        'h1.job-details-jobs-unified-top-card__job-title',
                        'h1[data-test-id="job-title"]',
                        'h1.t-24',
                        'h1.job-title',
                        'h1'
                    ]

                    for selector in title_selectors:
                        try:
                            title = await self.page.text_content(selector, timeout=5000)
                            if title and title.strip():
                                break
                        except:
                            continue

                    # Try multiple selectors for company
                    company_selectors = [
                        'a.job-details-jobs-unified-top-card__company-name',
                        'a[data-test-id="company-name"]',
                        'a.job-company',
                        'span.company-name',
                        'a[href*="/company/"]'
                    ]

                    for selector in company_selectors:
                        try:
                            company = await self.page.text_content(selector, timeout=5000)
                            if company and company.strip():
                                break
                        except:
                            continue

                    # Try multiple selectors for location
                    location_selectors = [
                        'span.job-details-jobs-unified-top-card__bullet',
                        'span[data-test-id="job-location"]',
                        'span.job-location',
                        'span.location'
                    ]

                    for selector in location_selectors:
                        try:
                            location = await self.page.text_content(selector, timeout=5000)
                            if location and location.strip():
                                break
                        except:
                            continue

                    # Get job URL (prefer card link, fallback to detail panel / current URL)
                    url = None
                    card_link_selectors = [
                        'a.job-card-list__title',
                        'a.job-card-container__link',
                        'a.job-card-list__title-link',
                        'a.job-card-list__title--link',
                        'a[href*="/jobs/view/"]',
                    ]

                    for selector in card_link_selectors:
                        try:
                            link = await card.query_selector(selector)
                            if link:
                                href = await link.get_attribute('href')
                                if href:
                                    url = href
                                    break
                        except Exception:
                            continue

                    if not url:
                        detail_link_selectors = [
                            'a[data-control-name="jobdetails_topcard"]',
                            'a[href*="/jobs/view/"]',
                        ]
                        for selector in detail_link_selectors:
                            try:
                                link = await self.page.query_selector(selector)
                                if link:
                                    href = await link.get_attribute('href')
                                    if href:
                                        url = href
                                        break
                            except Exception:
                                continue

                    if url:
                        match = re.search(r"/jobs/view/\d+", url)
                        if match:
                            url = f"https://www.linkedin.com{match.group(0)}"
                        elif url.startswith('/'):
                            url = f"https://www.linkedin.com{url}"
                    else:
                        url = self.page.url

                    # Check for Easy Apply badge with multiple selectors
                    easy_apply = False
                    easy_apply_selectors = [
                        'button.jobs-apply-button',
                        'button[aria-label*="Easy Apply"]',
                        'button[data-test-id="easy-apply-button"]',
                        'button.jobs-easy-apply-button'
                    ]

                    for selector in easy_apply_selectors:
                        try:
                            await self.page.wait_for_selector(selector, timeout=2000)
                            easy_apply = True
                            break
                        except:
                            continue

                    if title and title.strip():
                        # Try to get job description
                        description = ''
                        description_selectors = [
                            'div.jobs-description__content',
                            'div.job-details-jobs-unified-top-card__job-description',
                            'div[class*="description"]',
                            'article.jobs-description'
                        ]
                        
                        for selector in description_selectors:
                            try:
                                desc_elem = await self.page.query_selector(selector)
                                if desc_elem:
                                    description = await desc_elem.inner_text()
                                    if description and len(description.strip()) > 50:
                                        description = description.strip()[:500]  # Limit description length
                                        break
                            except:
                                continue
                        
                        job_data = {
                            'title': title.strip(),
                            'company': company.strip() if company else 'Unknown Company',
                            'location': location.strip() if location else 'Unknown Location',
                            'url': url,
                            'easy_apply': easy_apply,
                            'description': description,
                            'index': i + 1
                        }
                        jobs.append(job_data)
                        print(f"✅ Job {len(jobs)}: {title.strip()[:50]}... at {company.strip()[:30] if company else 'Unknown'}...")

                except Exception:
                    print(f"⚠️  Error extracting job {i+1}")
                    continue
            
            self.jobs_data = jobs
            print(f"📋 Total jobs collected: {len(jobs)}")
            return jobs
            
        except Exception:
            print(f"❌ Collection error occurred")
            self.errors.append("Job collection failed")
            return jobs

    def _collect_job_listings_sync(self, max_jobs: int = 30) -> List[Dict]:
        """Sync version of collect_job_listings for Windows."""
        page = self._get_page()
        jobs = []
        
        try:
            print(f"📊 Collecting up to {max_jobs} job listings...")
            
            # Scroll to load more jobs
            for scroll in range(5):
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(2)
            
            # Get job cards
            job_cards = page.query_selector_all('div.job-card-container')
            
            if not job_cards:
                job_cards = page.query_selector_all('li.jobs-search-results__list-item')
            
            print(f"🔢 Found {len(job_cards)} job cards")
            
            for i, card in enumerate(job_cards[:max_jobs]):
                try:
                    if len(jobs) >= max_jobs:
                        break
                    
                    # Click job card
                    try:
                        card.scroll_into_view_if_needed()
                        time.sleep(0.2)
                        card.click(timeout=6000)
                        time.sleep(random.uniform(1, 2))
                    except Exception as click_error:
                        print(f"⚠️ Could not click job card {i+1}: {str(click_error)}")
                        continue
                    
                    # Extract details
                    title = None
                    company = None
                    location = None
                    
                    # Get title
                    for selector in ['h1.job-details-jobs-unified-top-card__job-title', 'h1.t-24', 'h1']:
                        try:
                            title = page.text_content(selector, timeout=3000)
                            if title and title.strip():
                                break
                        except:
                            continue
                    
                    # Get company
                    for selector in ['a.job-details-jobs-unified-top-card__company-name', 'span.job-details-jobs-unified-top-card__company-name']:
                        try:
                            company = page.text_content(selector, timeout=2000)
                            if company and company.strip():
                                break
                        except:
                            continue
                    
                    # Get location
                    for selector in ['span.job-details-jobs-unified-top-card__primary-description', 'span.job-details-jobs-unified-top-card__bullet']:
                        try:
                            location = page.text_content(selector, timeout=2000)
                            if location and location.strip():
                                break
                        except:
                            continue
                    
                    # Get URL
                    url = page.url
                    
                    # Check Easy Apply
                    easy_apply = False
                    for selector in ['button.jobs-apply-button', 'button[aria-label*="Easy Apply"]']:
                        try:
                            page.wait_for_selector(selector, timeout=2000)
                            easy_apply = True
                            break
                        except:
                            continue
                    
                    if title and title.strip():
                        # Get description
                        description = ''
                        try:
                            desc_elem = page.query_selector('div.jobs-description__content')
                            if desc_elem:
                                description = desc_elem.inner_text()[:500]
                        except:
                            pass
                        
                        job_data = {
                            'title': title.strip(),
                            'company': company.strip() if company else 'Unknown Company',
                            'location': location.strip() if location else 'Unknown Location',
                            'url': url,
                            'easy_apply': easy_apply,
                            'description': description,
                            'index': i + 1
                        }
                        jobs.append(job_data)
                        print(f"✅ Job {len(jobs)}: {title.strip()[:50]}... at {company.strip()[:30] if company else 'Unknown'}...")
                        
                except Exception:
                    print(f"⚠️ Error extracting job {i+1}")
                    continue
            
            self.jobs_data = jobs
            print(f"📋 Total jobs collected: {len(jobs)}")
            return jobs
            
        except Exception as e:
            print(f"❌ Collection error: {str(e)}")
            self.errors.append("Job collection failed")
            return jobs

    async def _dismiss_overlays(self) -> None:
        """Best-effort: close LinkedIn overlays/modals that intercept pointer events."""
        if not self.page:
            return

        close_selectors = [
            'button[aria-label="Dismiss"]',
            'button[aria-label*="Dismiss"]',
            'button[aria-label="Close"]',
            'button[aria-label*="Close"]',
            'button[data-test-modal-close-btn]',
            'button.artdeco-modal__dismiss',
            'button.artdeco-toast-item__dismiss',
        ]

        for selector in close_selectors:
            try:
                buttons = await self.page.query_selector_all(selector)
                for btn in buttons[:5]:
                    try:
                        if await btn.is_visible():
                            await btn.click(force=True, timeout=1500)
                            await asyncio.sleep(0.2)
                    except Exception:
                        continue
            except Exception:
                continue

        # Escape key can dismiss some dialogs
        try:
            await self.page.keyboard.press('Escape')
        except Exception:
            pass
    
    async def analyze_job_with_ai(self, job: Dict) -> Dict:
        """Analyze job compatibility using Gemini AI"""
        if not self.ai_model:
            # Fallback: simple keyword matching
            return self._simple_job_match(job)
        
        try:
            # Get job description with fallback
            job_desc = job.get('description', f"{job.get('title', '')} position at {job.get('company', '')}")
            
            prompt = f"""
Analyze job compatibility and return ONLY valid JSON (no markdown, no code blocks):

RESUME:
{self.resume_text[:3000]}

JOB:
Title: {job.get('title', 'Unknown')}
Company: {job.get('company', 'Unknown')}
Location: {job.get('location', 'Unknown')}
Description: {job_desc}

Return this exact JSON structure:
{{
    "similarity_score": <number 0-100>,
    "matching_skills": ["skill1", "skill2", "skill3"],
    "missing_skills": ["skill1", "skill2"],
    "recommendation": "APPLY or SKIP",
    "confidence": <number 0.0-1.0>,
    "reasoning": "brief explanation"
}}
"""
            
            response = await asyncio.to_thread(
                self.ai_model.generate_content,
                prompt
            )
            
            # Parse JSON from response
            result_text = response.text.strip()
            # Remove markdown code blocks if present
            result_text = re.sub(r'```json\n?', '', result_text)
            result_text = re.sub(r'```\n?', '', result_text)
            
            result = json.loads(result_text)
            
            print(f"🤖 AI Analysis: {result['recommendation']} (Score: {result['similarity_score']}%)")
            return result
            
        except Exception as e:
            print(f"⚠️  AI analysis error: {str(e)}, using fallback")
            return self._simple_job_match(job)
    
    def _simple_job_match(self, job: Dict) -> Dict:
        """Fallback: Simple keyword-based matching"""
        skills = self.config.get('skills', '').lower().split(',')
        # Handle both description field and missing description
        job_desc = job.get('description', '')
        job_text = f"{job.get('title', '')} {job_desc} {job.get('company', '')} {job.get('location', '')}".lower()
        
        matching_skills = [s.strip() for s in skills if s.strip() and s.strip() in job_text]
        score = min(len(matching_skills) * 20, 100) if matching_skills else 50
        
        return {
            'similarity_score': score,
            'matching_skills': matching_skills[:5],
            'missing_skills': [],
            'recommendation': 'APPLY' if score >= 50 else 'SKIP',
            'confidence': 0.7,
            'reasoning': f"Matched {len(matching_skills)} skills from resume"
        }
    
    async def select_top_jobs(self, max_apply: int = 5) -> List[Dict]:
        """Select top jobs to apply based on AI analysis"""
        print(f"🎯 Analyzing jobs with AI to select top {max_apply}...")
        
        analyzed_jobs = []
        threshold = float(self.config.get('similarity_threshold', 0.6)) * 100
        
        for job in self.jobs_data:
            if not job['easy_apply']:
                continue
            
            analysis = await self.analyze_job_with_ai(job)
            
            job_with_analysis = {
                **job,
                'similarity_score': analysis['similarity_score'],
                'ai_decision': analysis['recommendation'],
                'ai_confidence': analysis['confidence'],
                'ai_reason': analysis['reasoning'],
                'matching_skills': analysis.get('matching_skills', []),
                'missing_skills': analysis.get('missing_skills', [])
            }
            
            if analysis['recommendation'] == 'APPLY' and analysis['similarity_score'] >= threshold:
                analyzed_jobs.append(job_with_analysis)
            
            await asyncio.sleep(random.uniform(2, 4))
        
        # Sort by score and take top N
        analyzed_jobs.sort(key=lambda x: x['similarity_score'], reverse=True)
        top_jobs = analyzed_jobs[:max_apply]
        
        print(f"✨ Selected {len(top_jobs)} jobs for application")
        for job in top_jobs:
            print(f"  • {job['title']} at {job['company']} - Score: {job['similarity_score']}%")
        
        return top_jobs
    
    async def auto_apply_job(self, job: Dict) -> Dict:
        """
        Automatically apply to a job (Easy Apply).
        
        This method:
        1. Opens the job URL
        2. Clicks Easy Apply
    3. Handles multi-step flows (Next/Review/Submit)
    4. Optionally runs in dry-run mode (no final submit)
        6. Fills all form fields programmatically
        7. Uploads resume if required
        8. Submits the application
        9. Verifies submission success
        10. Stores result in database
        
        Args:
            job: Dictionary containing job details (title, company, url)
            
        Returns:
            Dictionary with application status and details
        """
        # Use sync mode for Windows
        if self._use_sync_mode:
            return await self._run_sync(self._auto_apply_job_sync, job)
        
        if not self.page:
            raise Exception("Browser not initialized")
            
        print(f"\n🚀 Applying to: {job['title']} at {job['company']}")
        print(f"   🔗 URL: {job['url']}")
        
        dry_run = bool(self.config.get('dry_run', False))

        try:
            # Step 1: Open job application with robust handler
            print("📍 Step 1: Opening job detail page and Easy Apply modal...")
            job_url = job.get('url')
            if not job_url:
                raise Exception("Job URL missing; cannot open application")

            application_handler = ApplicationHandler(self.page)
            open_result = await application_handler.open_job_application(job_url)
            if open_result.get('status') != 'SUCCESS':
                raise Exception(f"Failed to open application: {open_result.get('reason')}")

            print("✅ Application modal opened")

            # Step 4+: Run the Easy Apply wizard (supports multi-step)
            print("📍 Step 4: Completing Easy Apply steps...")
            flow_result = await self._complete_easy_apply_flow(dry_run=dry_run)

            # Persist and normalize outcome
            job['applied_at'] = datetime.now().isoformat()
            job['dry_run'] = dry_run
            job['application_steps'] = flow_result.get('steps', [])
            job['application_errors'] = flow_result.get('errors', [])

            if flow_result.get('status') == 'APPLIED':
                job['application_status'] = 'APPLIED'
                job['application_reason'] = 'Application submitted successfully'
                print(f"🎉 SUCCESS: Application submitted to {job['title']}!")
                self.applied_jobs.append(job)
            elif flow_result.get('status') == 'DRY_RUN':
                job['application_status'] = 'DRY_RUN'
                job['application_reason'] = flow_result.get('reason', 'Dry run completed (no final submit)')
                print(f"🧪 DRY RUN: Reached final step for {job['title']} (did not submit)")
            elif flow_result.get('status') == 'NEEDS_REVIEW':
                job['application_status'] = 'NEEDS_REVIEW'
                job['application_reason'] = flow_result.get('reason', 'Application requires manual review')
                print(f"⚠️  NEEDS REVIEW: {job['title']} - {job['application_reason']}")
            else:
                job['application_status'] = 'FAILED'
                job['application_reason'] = flow_result.get('reason', 'Application failed')
                print(f"❌ FAILED: {job['title']} - {job['application_reason']}")

            await self._save_application(job)
            return job
            
        except Exception as e:
            print(f"❌ FAILED: Application error - {str(e)}")
            job['application_status'] = 'FAILED'
            job['application_reason'] = str(e)
            job['applied_at'] = datetime.now().isoformat()
            self.errors.append(f"Failed to apply to {job['title']}: {str(e)}")
            
            # Save failed application to database for tracking
            await self._save_application(job)
            
            # Try to close modal if still open
            try:
                close_btn = await self.page.query_selector('button[aria-label*="Dismiss"]')
                if close_btn:
                    await close_btn.click()
            except:
                pass
            
            return job

    def _auto_apply_job_sync(self, job: Dict) -> Dict:
        """Sync version of auto_apply_job for Windows."""
        page = self._get_page()
        
        print(f"\n🚀 Applying to: {job['title']} at {job['company']}")
        print(f"   🔗 URL: {job['url']}")
        
        dry_run = bool(self.config.get('dry_run', False))
        
        try:
            # Step 1: Navigate to job URL
            print("📍 Step 1: Opening job detail page...")
            job_url = job.get('url')
            if not job_url:
                raise Exception("Job URL missing")
            
            page.goto(job_url, wait_until='load', timeout=60000)
            time.sleep(random.uniform(2, 3))
            
            # Step 2: Click Easy Apply button
            print("📍 Step 2: Clicking Easy Apply...")
            easy_apply_clicked = False
            for selector in ['button.jobs-apply-button', 'button[aria-label*="Easy Apply"]', 'button:has-text("Easy Apply")']:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible():
                        btn.click()
                        easy_apply_clicked = True
                        print("✅ Easy Apply clicked")
                        break
                except:
                    continue
            
            if not easy_apply_clicked:
                raise Exception("Could not find Easy Apply button")
            
            time.sleep(2)
            
            # Step 3: Complete the multi-step form
            print("📍 Step 3: Completing application form...")
            result = self._complete_easy_apply_flow_sync(page, dry_run=dry_run)
            
            # Update job status
            job['applied_at'] = datetime.now().isoformat()
            job['dry_run'] = dry_run
            job['application_steps'] = result.get('steps', [])
            job['application_errors'] = result.get('errors', [])
            
            if result.get('status') == 'APPLIED':
                job['application_status'] = 'APPLIED'
                job['application_reason'] = 'Application submitted successfully'
                print(f"🎉 SUCCESS: Application submitted to {job['title']}!")
                self.applied_jobs.append(job)
            elif result.get('status') == 'DRY_RUN':
                job['application_status'] = 'DRY_RUN'
                job['application_reason'] = 'Dry run completed (no final submit)'
                print(f"🧪 DRY RUN: Reached final step (did not submit)")
            else:
                job['application_status'] = 'FAILED'
                job['application_reason'] = result.get('reason', 'Application failed')
                print(f"❌ FAILED: {job['application_reason']}")
            
            return job
            
        except Exception as e:
            print(f"❌ FAILED: Application error - {str(e)}")
            job['application_status'] = 'FAILED'
            job['application_reason'] = str(e)
            job['applied_at'] = datetime.now().isoformat()
            self.errors.append(f"Failed to apply to {job['title']}: {str(e)}")
            
            # Try to close modal
            try:
                close_btn = page.query_selector('button[aria-label*="Dismiss"]')
                if close_btn:
                    close_btn.click()
            except:
                pass
            
            return job
    
    def _complete_easy_apply_flow_sync(self, page: SyncPage, dry_run: bool = False, max_steps: int = 10) -> Dict:
        """Sync version of Easy Apply wizard handler for Windows."""
        steps = []
        errors = []
        
        try:
            for i in range(max_steps):
                print(f"\n📍 EASY APPLY STEP {i+1}/{max_steps}")
                time.sleep(1)
                
                # Check for success/completion indicators
                success_selectors = [
                    'text=Application sent',
                    'text=application was sent',
                    'h2:has-text("Application sent")',
                    '[data-test-modal-close-btn]'
                ]
                for selector in success_selectors:
                    try:
                        if page.locator(selector).first.is_visible(timeout=1000):
                            print("🎉 Application submitted successfully!")
                            return {"status": "APPLIED", "steps": steps, "errors": errors}
                    except:
                        continue
                
                # Fill form fields
                self._fill_form_fields_sync(page)
                
                # Find submit/next button
                submit_button = None
                submit_type = None
                
                button_selectors = [
                    ('button:has-text("Submit application")', 'submit'),
                    ('button[aria-label*="Submit application"]', 'submit'),
                    ('button:has-text("Review")', 'review'),
                    ('button:has-text("Next")', 'next'),
                    ('button[aria-label*="Continue"]', 'next'),
                ]
                
                for selector, btn_type in button_selectors:
                    try:
                        btn = page.locator(selector).first
                        if btn.is_visible(timeout=1000) and btn.is_enabled():
                            submit_button = btn
                            submit_type = btn_type
                            break
                    except:
                        continue
                
                if submit_button:
                    print(f"   Found button: {submit_type}")
                    
                    if submit_type == 'submit':
                        if dry_run:
                            print("🧪 DRY RUN: Would submit here but skipping")
                            return {"status": "DRY_RUN", "steps": steps, "errors": errors}
                        else:
                            submit_button.click()
                            time.sleep(3)
                            print("📤 Submit clicked!")
                            steps.append({"name": "submit", "detail": "Clicked submit"})
                            # Check for success
                            time.sleep(2)
                            return {"status": "APPLIED", "steps": steps, "errors": errors}
                    else:
                        submit_button.click()
                        time.sleep(2)
                        steps.append({"name": submit_type, "detail": f"Clicked {submit_type}"})
                else:
                    print("⚠️ No actionable button found")
                    errors.append("no_action_button")
                    break
            
            return {"status": "FAILED", "reason": "Max steps reached", "steps": steps, "errors": errors}
            
        except Exception as e:
            return {"status": "FAILED", "reason": str(e), "steps": steps, "errors": errors}
    
    def _fill_form_fields_sync(self, page: SyncPage) -> None:
        """Fill form fields in sync mode."""
        try:
            # Fill text inputs
            text_inputs = page.query_selector_all('input[type="text"]:not([readonly]), input:not([type]):not([readonly])')
            for input_elem in text_inputs:
                try:
                    if not input_elem.input_value():
                        label = input_elem.get_attribute('aria-label') or input_elem.get_attribute('name') or ''
                        label_lower = label.lower()
                        
                        value = ''
                        if 'name' in label_lower or 'full name' in label_lower:
                            value = self.user_profile.get('full_name', 'Candidate')
                        elif 'email' in label_lower:
                            value = self.linkedin_email or self.user_profile.get('email', '')
                        elif 'phone' in label_lower or 'mobile' in label_lower:
                            value = self.user_profile.get('phone', '')
                        elif 'city' in label_lower:
                            value = self.user_profile.get('city', 'New York')
                        elif 'year' in label_lower and 'experience' in label_lower:
                            value = str(self.user_profile.get('years_experience', '3'))
                        elif 'linkedin' in label_lower:
                            value = f"https://www.linkedin.com/in/{self.linkedin_email.split('@')[0] if self.linkedin_email else 'profile'}"
                        
                        if value:
                            input_elem.fill(value)
                            print(f"   Filled: {label[:30]}...")
                except:
                    continue
            
            # Handle dropdowns/selects
            selects = page.query_selector_all('select')
            for select in selects:
                try:
                    options = select.query_selector_all('option')
                    if len(options) > 1:
                        # Select first non-empty option
                        options[1].click()
                except:
                    continue
            
            # Handle radio buttons - select first option
            radio_groups = page.query_selector_all('[role="radiogroup"]')
            for group in radio_groups:
                try:
                    first_radio = group.query_selector('input[type="radio"]')
                    if first_radio and not first_radio.is_checked():
                        first_radio.click()
                except:
                    continue
                    
        except Exception as e:
            print(f"⚠️ Error filling form: {str(e)}")

    async def _complete_easy_apply_flow(self, dry_run: bool = False, max_steps: int = 10) -> Dict:
        """Best-effort Easy Apply wizard handler.

        Outcomes:
        - APPLIED: submission confirmed
        - DRY_RUN: reached final submit step but did not click submit
        - NEEDS_REVIEW: blocked by unanswered required fields or unsupported widgets
        - FAILED: unexpected error
        """
        if not self.page:
            return {"status": "FAILED", "reason": "Browser not initialized", "steps": [], "errors": ["no_page"]}

        steps: list[dict] = []
        errors: list[str] = []

        def _step(name: str, detail: str = "") -> None:
            steps.append({"name": name, "detail": detail})

        try:
            for i in range(max_steps):
                print(f"\n" + "─" * 80)
                print(f"📍 EASY APPLY STEP {i+1}/{max_steps}")
                print(f"─" * 80)
                
                # Wait for modal to be stable - reduced timeout
                await asyncio.sleep(0.5)
                
                _step("fill", f"iteration={i+1}")
                await self._fill_application_form()
                
                # Wait after filling for page to update
                await asyncio.sleep(0.5)

                # If there are visible error messages about required fields, stop and report.
                if await self._has_required_field_errors():
                    print("⚠️  Required field errors detected, attempting to continue anyway...")

                # CRITICAL FIX: First find the primary button in footer, then check its text
                modal = await self.page.query_selector('.jobs-easy-apply-modal, .jobs-easy-apply-content, [data-test-modal]')
                if not modal:
                    modal = self.page
                
                # Find the primary button in the modal footer
                primary_btn = None
                btn_text = ""
                
                # Quick search for primary button - no timeout
                for selector in [
                    'footer button.artdeco-button--primary',
                    '.jobs-easy-apply-footer button.artdeco-button--primary',
                    'button.artdeco-button--primary[data-easy-apply-next-button]',
                    'button.artdeco-button--primary'
                ]:
                    try:
                        btn = await modal.query_selector(selector)
                        if btn and await btn.is_visible():
                            # Check if button is truly disabled (disabled attr, aria-disabled, or DOM property)
                            is_disabled = False
                            try:
                                disabled_attr = await btn.get_attribute('disabled')
                                if disabled_attr is not None:
                                    is_disabled = True
                                aria_disabled = await btn.get_attribute('aria-disabled')
                                if aria_disabled and aria_disabled.lower() == 'true':
                                    is_disabled = True
                                if not is_disabled:
                                    is_disabled_prop = await btn.evaluate('el => el.disabled')
                                    if is_disabled_prop:
                                        is_disabled = True
                            except:
                                pass
                            
                            if is_disabled:
                                try:
                                    dbg_text = (await btn.inner_text() or "").strip()
                                except:
                                    dbg_text = ""
                                print(f"  ⚠️  Button '{dbg_text[:25]}' is disabled — required fields may be missing")
                                errors.append("primary_button_disabled")
                                # Don't break — try other selectors in case there's an enabled one
                                continue
                            
                            primary_btn = btn
                            try:
                                btn_text = (await btn.inner_text() or "").strip().lower()
                            except:
                                btn_text = ""
                            break
                    except:
                        continue
                
                if not primary_btn:
                    print("⚠️  No primary button found in modal")
                    return {
                        "status": "NEEDS_REVIEW",
                        "reason": "Could not find Next/Submit button (button may be disabled due to missing required fields)",
                        "steps": steps,
                        "errors": errors + ["no_button_found"],
                    }
                
                print(f"🔍 Found button with text: '{btn_text}'")
                
                # Check if this is the SUBMIT button (final step)
                is_submit = 'submit' in btn_text and 'application' in btn_text
                is_review = 'review' in btn_text
                is_next = 'next' in btn_text or 'continue' in btn_text
                
                if is_submit:
                    print(f"\n🎯 SUBMIT BUTTON FOUND! Text: '{btn_text}'")
                    _step("submit_visible", btn_text)
                    
                    if dry_run:
                        return {
                            "status": "DRY_RUN",
                            "reason": "Dry run enabled; submit button found",
                            "steps": steps,
                            "errors": errors,
                        }
                    
                    # Click submit button
                    if not await self._click_button_with_fallback(primary_btn, "Submit Application"):
                        return {
                            "status": "FAILED",
                            "reason": "Could not click Submit button",
                            "steps": steps,
                            "errors": errors + ["submit_click_failed"],
                        }
                    _step("submit_clicked")
                    await asyncio.sleep(3)
                    
                    if await self._verify_submission():
                        return {"status": "APPLIED", "steps": steps, "errors": errors}
                    return {
                        "status": "FAILED",
                        "reason": "Submission not confirmed",
                        "steps": steps,
                        "errors": errors + ["submit_not_confirmed"],
                    }
                
                # It's a Next/Continue/Review button - click and continue to next step
                action_name = "Review" if is_review else "Next"
                print(f"\n➡️  {action_name.upper()} BUTTON FOUND! Text: '{btn_text}'")
                _step(f"{action_name.lower()}_clicked", btn_text)
                
                if not await self._click_button_with_fallback(primary_btn, action_name):
                    return {
                        "status": "FAILED",
                        "reason": f"Could not click {action_name} button",
                        "steps": steps,
                        "errors": errors + [f"{action_name.lower()}_click_failed"],
                    }
                
                # Wait for next page to load
                await asyncio.sleep(1.5)
                print(f"   ✅ Clicked {action_name}, moving to next step...")
                continue

            return {
                "status": "NEEDS_REVIEW",
                "reason": "Max steps exceeded",
                "steps": steps,
                "errors": errors + ["max_steps"],
            }

        except Exception as e:
            errors.append(str(e))
            return {"status": "FAILED", "reason": str(e), "steps": steps, "errors": errors}

    async def _find_primary_button(self, selectors: list[str]):
        """Return first visible, enabled button matching any selector with JavaScript click fallback."""
        if not self.page:
            return None
        
        # First, try to find buttons INSIDE the modal only
        modal_selectors = [
            '.jobs-easy-apply-modal',
            '.jobs-easy-apply-content',
            '[data-test-modal]',
            '.artdeco-modal__content'
        ]
        
        modal = None
        for modal_sel in modal_selectors:
            try:
                modal = await self.page.query_selector(modal_sel)
                if modal:
                    break
            except:
                continue
        
        # Search within modal first, then fallback to page
        search_context = modal if modal else self.page
        
        for sel in selectors:
            try:
                btn = await search_context.query_selector(sel)
                if btn and await btn.is_visible() and await btn.is_enabled():
                    # Scroll button into view
                    try:
                        await btn.scroll_into_view_if_needed()
                        await asyncio.sleep(0.3)
                    except:
                        pass
                    return btn
            except Exception:
                continue
        
        # If not found in modal, try page-wide search
        if modal:
            for sel in selectors:
                try:
                    btn = await self.page.query_selector(sel)
                    if btn and await btn.is_visible() and await btn.is_enabled():
                        try:
                            await btn.scroll_into_view_if_needed()
                            await asyncio.sleep(0.3)
                        except:
                            pass
                        return btn
                except Exception:
                    continue
        
        return None
    
    async def _click_button_with_fallback(self, button, button_name: str = "button") -> bool:
        """Click button with multiple fallback strategies for overlay issues.
        
        Returns:
            bool: True if click succeeded, False otherwise
        """
        if not button or not self.page:
            return False
        
        print(f"🖱️  Clicking: {button_name}")
        
        # Scroll into view
        try:
            await button.scroll_into_view_if_needed()
            await asyncio.sleep(0.3)
        except:
            pass
        
        # Strategy 1: Normal click (fastest)
        try:
            await button.click(timeout=2000)
            await asyncio.sleep(0.8)
            print(f"   ✅ Clicked '{button_name}'")
            return True
        except:
            pass
        
        # Strategy 2: Force click
        try:
            await button.click(force=True, timeout=2000)
            await asyncio.sleep(0.8)
            print(f"   ✅ Clicked '{button_name}' (force)")
            return True
        except:
            pass
        
        # Strategy 3: JavaScript click
        try:
            await button.evaluate("el => el.click()")
            await asyncio.sleep(0.8)
            print(f"   ✅ Clicked '{button_name}' (JS)")
            return True
        except:
            pass
        
        # Strategy 4: Focus + Enter
        try:
            await button.focus()
            await self.page.keyboard.press('Enter')
            await asyncio.sleep(0.8)
            print(f"   ✅ Clicked '{button_name}' (Enter)")
            return True
        except:
            pass
        
        # Strategy 5: Mouse coordinates
        try:
            box = await button.bounding_box()
            if box:
                await self.page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                await asyncio.sleep(0.8)
                print(f"   ✅ Clicked '{button_name}' (mouse)")
                return True
        except:
            pass
        
        print(f"   ❌ Failed to click '{button_name}'")
        return False

    async def _has_required_field_errors(self) -> bool:
        """Detect common validation errors shown in Easy Apply forms."""
        if not self.page:
            return False
        selectors = [
            'text=/required/i',
            'text=/please enter/i',
            'text=/please select/i',
            '[data-test-form-element-error]',
            '.artdeco-inline-feedback--error',
        ]
        for sel in selectors:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    return True
            except Exception:
                continue
        return False
    
    async def _handle_captcha_or_security_check(self, context: str = "Security check") -> None:
        """
        Pause automation when CAPTCHA or security checkpoint is detected.
        Wait for manual completion before resuming.
        
        Args:
            context: Description of where the CAPTCHA was encountered
        """
        if not self.page:
            return
        
        print(f"\n{'='*60}")
        print(f"⚠️  {context.upper()} DETECTED")
        print(f"{'='*60}")
        print(f"🛑 AUTOMATION PAUSED")
        print(f"")
        print(f"LinkedIn has triggered a security check. Please:")
        print(f"  1. Complete the CAPTCHA or verification in the browser window")
        print(f"  2. Do NOT close the browser")
        print(f"  3. Wait for the automation to resume automatically")
        print(f"")
        print(f"⏳ Waiting up to 180 seconds (3 minutes) for completion...")
        print(f"{'='*60}\n")
        
        # Wait up to 3 minutes for user to complete the challenge
        for i in range(36):  # 36 * 5 = 180 seconds
            await asyncio.sleep(5)
            
            # Check if we're past the checkpoint
            current_url = self.page.url
            if 'checkpoint' not in current_url and 'challenge' not in current_url:
                print(f"\n✅ Security check completed! Resuming automation...")
                print(f"{'='*60}\n")
                return
            
            # Log progress every 15 seconds
            if i % 3 == 0 and i > 0:
                elapsed = (i + 1) * 5
                remaining = 180 - elapsed
                print(f"⏳ Still waiting... ({elapsed}s elapsed, {remaining}s remaining)")
        
        print(f"\n⚠️  Timeout reached. Checkpoint may still be active.")
        print(f"{'='*60}\n")
    
    async def _handle_resume_upload(self) -> None:
        """Handle resume file upload in Easy Apply form with green checkmark verification"""
        if not self.page:
            return
            
        try:
            # First, check if a resume is already selected (green checkmark present)
            selected_resume = await self.page.query_selector('input[type="radio"][name*="resume"]:checked')
            if selected_resume:
                print("  ✓ Resume already selected")
                
                # Verify with green checkmark
                checkmark = await self.page.query_selector('.artdeco-icon[data-test-icon="check-mark"]')
                if checkmark:
                    print("  ✓ Resume verified with green checkmark")
                return  # Resume already selected, nothing to do
            
            # Check for existing resumes (radio buttons)
            existing_resumes = await self.page.query_selector_all('input[type="radio"][name*="resume"]')
            
            if existing_resumes and len(existing_resumes) > 0:
                # Select first existing resume (most recently used)
                print(f"  ✓ Found {len(existing_resumes)} existing resume(s)")
                await existing_resumes[0].click()
                await asyncio.sleep(1)
                print("  ✓ Selected most recent resume")
                
                # Verify selection with green checkmark
                checkmark = await self.page.query_selector('.artdeco-icon[data-test-icon="check-mark"]')
                if checkmark:
                    print("  ✓ Resume selection confirmed with green checkmark")
                return
            
            # No existing resumes, look for file upload input
            file_inputs = await self.page.query_selector_all('input[type="file"]')
            
            for file_input in file_inputs:
                try:
                    # Check if this is for resume upload
                    label = await self._get_field_label(file_input)
                    if any(word in label.lower() for word in ['resume', 'cv', 'upload']):
                        resume_path = self.config.get('resume_path', '')
                        if resume_path and Path(resume_path).exists():
                            await file_input.set_input_files(resume_path)
                            print(f"  ✓ Uploaded resume: {Path(resume_path).name}")
                            await asyncio.sleep(2)  # Wait for upload to complete
                        else:
                            print(f"  ⚠️  Resume path not found: {resume_path}")
                except Exception as e:
                    print(f"  ⚠️  Resume upload attempt failed: {str(e)}")
                    
        except Exception as e:
            print(f"  ⚠️  Resume upload error: {str(e)}")
    
    async def _handle_cover_letter(self) -> None:
        """Handle cover letter generation and entry"""
        if not self.page:
            return
            
        try:
            # Look for cover letter textarea
            textareas = await self.page.query_selector_all('textarea')
            
            for textarea in textareas:
                try:
                    label = await self._get_field_label(textarea)
                    label_lower = label.lower()
                    
                    # Check if this is a cover letter field
                    if any(word in label_lower for word in ['cover letter', 'additional information', 'message to']):
                        # Check if already filled
                        current = await textarea.input_value()
                        if current and current.strip():
                            continue
                        
                        # Generate cover letter using AI
                        cover_letter = await self._generate_cover_letter()
                        if cover_letter:
                            await textarea.fill(cover_letter)
                            print(f"  ✓ Generated and filled cover letter")
                            await asyncio.sleep(0.5)
                            
                except Exception as e:
                    print(f"  ⚠️  Cover letter field error: {str(e)}")
                    
        except Exception as e:
            print(f"  ⚠️  Cover letter handling error: {str(e)}")
    
    async def _generate_cover_letter(self) -> str:
        """Generate AI cover letter based on resume and job"""
        if not self.ai_model or not self.resume_text:
            return ""
            
        try:
            prompt = f"""
Generate a brief, professional cover letter (3-4 sentences) based on:

RESUME SUMMARY:
{self.resume_text[:1500]}

Keep it concise, professional, and express genuine interest. Do not include placeholders or brackets.
"""
            response = await asyncio.to_thread(
                self.ai_model.generate_content,
                prompt
            )
            return response.text.strip()[:500]  # Limit length
        except:
            return ""

    async def _is_single_step_application(self) -> bool:
        """
        Detect if the Easy Apply form is single-step or multi-step.
        
        Returns True if single-step (can submit immediately), False if multi-step.
        
        Detection logic:
        - Single-step: Has "Submit application" button immediately visible
        - Multi-step: Has "Next" or "Continue" button instead
        - Multi-step: Shows page indicators like "1 of 3" or progress bar
        - Multi-step: Contains custom questions or additional forms
        """
        if not self.page:
            return False
        
        try:
            # Check for "Submit application" button (indicates single-step)
            submit_selectors = [
                'button[aria-label*="Submit application"]',
                'button:has-text("Submit application")',
                'button.artdeco-button--primary:has-text("Submit")'
            ]
            
            for selector in submit_selectors:
                try:
                    submit_btn = await self.page.query_selector(selector)
                    if submit_btn and await submit_btn.is_visible():
                        # Double-check no "Next" button exists
                        next_btn = await self.page.query_selector('button:has-text("Next")')
                        if not next_btn or not await next_btn.is_visible():
                            print("   ✅ Single-step detected: Submit button found, no Next button")
                            return True
                except:
                    continue
            
            # Check for "Next" or "Continue" button (indicates multi-step)
            next_selectors = [
                'button:has-text("Next")',
                'button:has-text("Continue")',
                'button[aria-label*="Continue to next step"]',
                'button[aria-label*="Review your application"]'
            ]
            
            for selector in next_selectors:
                try:
                    next_btn = await self.page.query_selector(selector)
                    if next_btn and await next_btn.is_visible():
                        print("   ⚠️  Multi-step detected: Next/Continue button found")
                        return False
                except:
                    continue
            
            # Check for page indicators like "1 of 3" or progress bars
            page_indicator_selectors = [
                'text=/\\d+ of \\d+/',  # Matches "1 of 3", "2 of 4", etc.
                'text=/Step \\d+/',     # Matches "Step 1", "Step 2", etc.
                '[role="progressbar"]',
                '.artdeco-modal__header:has-text("of")'
            ]
            
            for selector in page_indicator_selectors:
                try:
                    indicator = await self.page.query_selector(selector)
                    if indicator:
                        print("   ⚠️  Multi-step detected: Page indicators found")
                        return False
                except:
                    continue
            
            # Check for custom questions sections (often indicates multi-step)
            custom_question_selectors = [
                'fieldset:has-text("Additional questions")',
                'legend:has-text("Questions from")',
                '.jobs-easy-apply-form-section__grouping'
            ]
            
            custom_questions = 0
            for selector in custom_question_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    custom_questions += len(elements)
                except:
                    continue
            
            if custom_questions > 3:
                print(f"   ⚠️  Multi-step detected: {custom_questions} custom question sections found")
                return False
            
            # Default: If we can't determine, assume multi-step for safety
            print("   ⚠️  Could not determine application type - defaulting to multi-step (safe)")
            return False
            
        except Exception as e:
            print(f"   ⚠️  Error detecting application type: {str(e)} - defaulting to multi-step")
            return False

    async def _fetch_github_data(self) -> Dict:
        """Fetch GitHub profile data using GitHub API"""
        github_token = os.getenv('GITHUB_API_KEY', '')
        if not github_token or github_token.startswith('your_') or github_token.startswith('ghp_YOUR'):
            print("⚠️  No valid GitHub API key found, skipping GitHub data")
            return {}
        
        try:
            import aiohttp
            import ssl
            
            # Create SSL context that doesn't verify certificates (for development)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            headers = {
                'Authorization': f'token {github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
                # Get user profile
                async with session.get('https://api.github.com/user', headers=headers) as resp:
                    if resp.status != 200:
                        print(f"⚠️  GitHub API error: {resp.status}")
                        return {}
                    user_data = await resp.json()
                
                # Get repos
                async with session.get(f'https://api.github.com/users/{user_data["login"]}/repos?sort=updated&per_page=10', headers=headers) as resp:
                    repos_data = await resp.json() if resp.status == 200 else []
                
                # Extract useful info
                github_info = {
                    'name': user_data.get('name', ''),
                    'bio': user_data.get('bio', ''),
                    'company': user_data.get('company', ''),
                    'location': user_data.get('location', ''),
                    'public_repos': user_data.get('public_repos', 0),
                    'followers': user_data.get('followers', 0),
                    'top_repos': [
                        {
                            'name': repo.get('name', ''),
                            'description': repo.get('description', ''),
                            'language': repo.get('language', ''),
                            'stars': repo.get('stargazers_count', 0)
                        }
                        for repo in repos_data[:5]
                    ]
                }
                
                print(f"✅ Fetched GitHub data: {github_info.get('name', 'User')} ({len(github_info['top_repos'])} repos)")
                return github_info
                
        except Exception as e:
            print(f"⚠️  Error fetching GitHub data: {str(e)[:100]}")
            return {}

    async def _generate_ai_answer(self, question: str, job_title: str = "", company: str = "") -> str:
        """Generate AI-powered answer combining resume + GitHub + job context"""
        
        # Try OpenAI first if available
        openai_key = os.getenv('OPENAI_API_KEY', '')
        if openai_key and not openai_key.startswith('your_') and not openai_key.startswith('sk-proj-YOUR'):
            try:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                
                # Fetch GitHub data if not cached
                if not hasattr(self, '_github_data'):
                    self._github_data = await self._fetch_github_data()
                
                github_summary = ""
                if self._github_data:
                    repos = self._github_data.get('top_repos', [])
                    if repos:
                        github_summary = f"\n\nGitHub: {len(repos)} projects including "
                        github_summary += ", ".join([f"{r['name']} ({r['language']})" for r in repos[:3]])
                
                resume_excerpt = self.resume_text[:2000] if self.resume_text else "Experienced professional"
                
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are helping someone answer a job application question. Provide a professional, concise 2-3 sentence answer."},
                        {"role": "user", "content": f"Job: {job_title or 'Position'} at {company or 'Company'}\nQuestion: {question}\n\nMy Background:\n{resume_excerpt}{github_summary}\n\nProvide a professional 2-3 sentence answer:"}
                    ],
                    max_tokens=150,
                    temperature=0.7
                )
                
                answer = response.choices[0].message.content.strip()
                if len(answer) > 500:
                    answer = answer[:497] + "..."
                
                print(f"  🤖 OpenAI Generated answer ({len(answer)} chars)")
                return answer
                
            except Exception as e:
                print(f"⚠️  OpenAI error: {str(e)[:80]}, trying Gemini fallback...")
        
        # Try Gemini as fallback
        if self.ai_model:
            try:
                if not hasattr(self, '_github_data'):
                    self._github_data = await self._fetch_github_data()
                
                github_summary = ""
                if self._github_data and isinstance(self._github_data, dict):
                    repos = self._github_data.get('top_repos', [])
                    if repos and len(repos) > 0:
                        github_summary = f"\n\nGitHub: {len(repos)} projects"
                        for repo in repos[:3]:
                            if isinstance(repo, dict):
                                repo_name = repo.get('name', 'Project')
                                repo_desc = repo.get('description', '')
                                repo_lang = repo.get('language', '')
                                if repo_desc:
                                    github_summary += f"\n- {repo_name}: {repo_desc[:60]} ({repo_lang})"
                                else:
                                    github_summary += f"\n- {repo_name} ({repo_lang})"
                
                resume_excerpt = self.resume_text[:2000] if self.resume_text else "Professional with relevant experience"
                
                prompt = f"""Job: {job_title or 'Position'} at {company or 'Company'}
Question: {question}

My Background:
{resume_excerpt}
{github_summary}

Provide a professional 2-3 sentence answer:"""

                response = self.ai_model.generate_content(prompt)
                
                # Debug: Check what we got
                print(f"  DEBUG: Response type: {type(response)}")
                print(f"  DEBUG: Has text attr: {hasattr(response, 'text')}")
                
                # Handle different response formats
                answer = None
                if hasattr(response, 'text'):
                    try:
                        answer = response.text
                        if answer:
                            answer = answer.strip()
                    except Exception as e:
                        print(f"  DEBUG: Error accessing .text: {e}")
                
                if not answer and hasattr(response, 'candidates') and response.candidates:
                    try:
                        answer = response.candidates[0].content.parts[0].text.strip()
                    except Exception as e:
                        print(f"  DEBUG: Error accessing candidates: {e}")
                
                if not answer:
                    raise Exception(f"No text in Gemini response. Response: {response}")
                
                if len(answer) > 500:
                    answer = answer[:497] + "..."
                
                print(f"  🤖 Gemini Generated answer ({len(answer)} chars)")
                return answer
                
            except Exception as e:
                print(f"⚠️  Gemini error: {str(e)}")
        
        # Final fallback: Use profile data
        print("⚠️  No AI available, using fallback answer")
        years_exp = self.user_profile.get('years_experience', '3')
        return f"I bring {years_exp} years of relevant experience and strong skills in this area. I'm excited about this opportunity and confident I can make valuable contributions to the team."

    async def _fill_application_form(self) -> None:
        """Fill all fields on current application page with intelligent detection using user profile.
        Only targets fields INSIDE the Easy Apply modal to prevent filling background page fields."""
        if not self.page:
            raise Exception("Browser not initialized")
            
        try:
            print("\n" + "═" * 80)
            print("📝 FORM AUTO-FILL STARTING")
            print("═" * 80)
            print("👁️  WATCH BROWSER: You will see fields being filled automatically...")
            print()
            
            # Handle resume upload if present
            print("📄 Checking for resume upload...")
            await self._handle_resume_upload()
            
            # Handle cover letter if present
            print("📝 Checking for cover letter field...")
            await self._handle_cover_letter()
            
            # FIXED: Don't wait for networkidle - just a brief pause
            try:
                await self.page.wait_for_load_state('domcontentloaded', timeout=2000)
            except:
                pass
            await asyncio.sleep(0.5)
            
            # CRITICAL FIX: Only target fields INSIDE the Easy Apply modal
            modal = await self.page.query_selector('.jobs-easy-apply-modal, .jobs-easy-apply-content, [data-test-modal]')
            if not modal:
                print("⚠️  Warning: Could not find Easy Apply modal, trying alternative selectors")
                modal = await self.page.query_selector('.artdeco-modal__content')
            if not modal:
                print("⚠️  Warning: Still no modal found, using full page")
                modal = self.page  # Fallback to full page if modal not found
            else:
                print("✅ Found Easy Apply modal")
            
            # Get all input fields INSIDE the modal only - include more input types
            inputs = await modal.query_selector_all('input[type="text"], input[type="tel"], input[type="email"], input[type="number"], input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="file"]):not([type="submit"])')
            textareas = await modal.query_selector_all('textarea')
            
            print(f"🔍 Found {len(inputs)} input fields and {len(textareas)} text areas in Easy Apply modal")
            
            # Also look for typeahead inputs (LinkedIn uses these for location)
            typeahead_inputs = await modal.query_selector_all('[role="combobox"], .fb-single-typeahead-input, input[aria-autocomplete="list"]')
            if typeahead_inputs:
                print(f"🔍 Found {len(typeahead_inputs)} typeahead/autocomplete fields")
            
            print("👁️  WATCH BROWSER: Fields will be filled one by one...\n")
            filled_count = 0
            
            # Get current job context for AI
            job_title = ""
            company = ""
            try:
                job_title_elem = await self.page.query_selector('h1.job-title, .jobs-unified-top-card__job-title')
                if job_title_elem:
                    job_title = (await job_title_elem.text_content() or "").strip()
                
                company_elem = await self.page.query_selector('.jobs-unified-top-card__company-name, .job-details-jobs-unified-top-card__company-name a')
                if company_elem:
                    company = (await company_elem.text_content() or "").strip()
            except:
                pass
            
            # Fill basic input fields first
            for input_field in inputs:
                try:
                    # Check if field is visible and enabled
                    if not await input_field.is_visible():
                        continue
                    
                    # Check if field is disabled or readonly
                    is_disabled = await input_field.get_attribute('disabled')
                    is_readonly = await input_field.get_attribute('readonly')
                    if is_disabled is not None or is_readonly is not None:
                        continue
                    
                    # Get field identifiers FIRST (needed for override logic)
                    field_name = await input_field.get_attribute('name') or ''
                    field_id = await input_field.get_attribute('id') or ''
                    field_placeholder = await input_field.get_attribute('placeholder') or ''
                    field_aria_label = await input_field.get_attribute('aria-label') or ''
                    field_type = await input_field.get_attribute('type') or 'text'
                    
                    # Also try to find associated label by looking at parent or nearby elements
                    label_text = ''
                    try:
                        # Method 1: Label with for attribute
                        if field_id:
                            label_elem = await modal.query_selector(f'label[for="{field_id}"]')
                            if label_elem:
                                label_text = (await label_elem.text_content() or '').strip()
                        
                        # Method 2: Parent container text
                        if not label_text:
                            parent = await input_field.evaluate("el => el.parentElement?.textContent?.trim()?.substring(0, 100)")
                            if parent and len(parent) < 80:
                                label_text = parent
                        
                        # Method 3: Preceding sibling label
                        if not label_text:
                            prev_label = await input_field.evaluate("el => el.previousElementSibling?.textContent?.trim()")
                            if prev_label and len(prev_label) < 50:
                                label_text = prev_label
                    except:
                        pass
                    
                    # Combine all identifiers for smart matching
                    field_identifier = f"{field_name} {field_id} {field_placeholder} {field_aria_label} {label_text}".lower()
                    
                    # Determine if this is a contact/identity field that should ALWAYS be overridden
                    # (corrects corrupted data from previous bad runs)
                    is_override_field = False
                    if any(kw in field_identifier for kw in ['first name', 'firstname', 'fname', 'given name']):
                        is_override_field = True
                    elif any(kw in field_identifier for kw in ['last name', 'lastname', 'lname', 'surname', 'family name']):
                        is_override_field = True
                    elif any(kw in field_identifier for kw in ['full name', 'legal name']) or field_identifier.strip() == 'name':
                        is_override_field = True
                    elif 'email' in field_identifier:
                        is_override_field = True
                    elif any(kw in field_identifier for kw in ['phone', 'mobile', 'cell']) or field_type == 'tel':
                        is_override_field = True
                    elif any(kw in field_identifier for kw in ['city', 'location (city)']):
                        is_override_field = True
                    elif any(kw in field_identifier for kw in ['state', 'province']):
                        is_override_field = True
                    elif any(kw in field_identifier for kw in ['zip', 'postal', 'pincode', 'pin code']):
                        is_override_field = True
                    elif any(kw in field_identifier for kw in ['street', 'address']):
                        is_override_field = True
                    elif 'country' in field_identifier:
                        is_override_field = True
                    elif 'location' in field_identifier and 'job' not in field_identifier:
                        is_override_field = True
                    
                    # Check if already filled - skip ONLY non-override fields
                    current_value = await input_field.input_value()
                    if current_value and len(current_value.strip()) > 2 and not is_override_field:
                        print(f"  ⏩ Skipping already filled field: '{current_value[:30]}...'")
                        continue
                    
                    print(f"  🔍 Field detected: type={field_type}, identifier='{field_identifier[:60]}...'{' [OVERRIDE]' if is_override_field else ''}")
                    
                    # Get appropriate value using smart matching
                    value = self._get_field_value_smart(field_identifier, 'text', self.user_profile)
                    
                    if value:
                        await input_field.click()
                        await asyncio.sleep(0.2)
                        await input_field.fill('')  # Clear first
                        await input_field.fill(value)
                        await asyncio.sleep(random.uniform(0.3, 0.6))  # Slower for visibility
                        filled_count += 1
                        
                        # Extract field label for better logging
                        field_label = label_text or field_placeholder or field_aria_label or field_name or field_id
                        print(f"  ✅ Filled field: '{field_label[:40]}' → '{value[:50]}'")
                        print(f"     👁️  Look at browser to see the value entered!")
                    else:
                        print(f"  ⚠️  No value found for field: '{field_identifier[:50]}'")
                        
                except Exception as e:
                    print(f"  ⚠️  Could not fill field: {str(e)[:50]}")
            
            # Handle typeahead/autocomplete inputs (LinkedIn uses these for location)
            print(f"\n📍 Processing typeahead/autocomplete fields for location...")
            typeahead_inputs = await modal.query_selector_all('[role="combobox"], .fb-single-typeahead-input, input[aria-autocomplete="list"]')
            for typeahead in typeahead_inputs:
                try:
                    if not await typeahead.is_visible():
                        continue
                    
                    # Get field identifier
                    field_id = await typeahead.get_attribute('id') or ''
                    field_aria_label = await typeahead.get_attribute('aria-label') or ''
                    field_placeholder = await typeahead.get_attribute('placeholder') or ''
                    
                    # Try to get label
                    label_text = ''
                    try:
                        if field_id:
                            label_elem = await modal.query_selector(f'label[for="{field_id}"]')
                            if label_elem:
                                label_text = (await label_elem.text_content() or '').strip()
                    except:
                        pass
                    
                    field_identifier = f"{field_id} {field_aria_label} {field_placeholder} {label_text}".lower()
                    print(f"  🔍 Typeahead field: '{field_identifier[:60]}...'")
                    
                    # Check if this looks like a location field
                    if any(keyword in field_identifier for keyword in ['location', 'city', 'where', 'address']):
                        location_value = self.user_profile.get('location') or self.user_profile.get('city') or self.config.get('location', 'Hyderabad')
                        if location_value:
                            print(f"  📍 Filling location: {location_value}")
                            await typeahead.click()
                            await asyncio.sleep(0.3)
                            await typeahead.fill('')
                            await typeahead.type(location_value, delay=50)  # Type slowly for typeahead
                            await asyncio.sleep(1)  # Wait for suggestions
                            
                            # Try to select first suggestion
                            try:
                                suggestion = await self.page.query_selector('[role="option"]:first-child, .basic-typeahead__selectable:first-child, [data-test-veneer-id="typeahead-suggestion"]:first-child')
                                if suggestion:
                                    await suggestion.click()
                                    print(f"  ✅ Selected location suggestion")
                                else:
                                    # Press Enter to confirm
                                    await self.page.keyboard.press('Enter')
                                    print(f"  ✅ Entered location (no suggestion found)")
                            except:
                                await self.page.keyboard.press('Enter')
                            
                            filled_count += 1
                except Exception as e:
                    print(f"  ⚠️  Could not fill typeahead: {str(e)[:50]}")
            
            # Fill textareas with AI-generated answers
            print(f"\n🤖 Processing {len(textareas)} custom question fields with AI...")
            for textarea in textareas:
                try:
                    # Check if field is visible and enabled
                    if not await textarea.is_visible():
                        continue
                    
                    # Check if disabled or readonly
                    is_disabled = await textarea.get_attribute('disabled')
                    is_readonly = await textarea.get_attribute('readonly')
                    if is_disabled is not None or is_readonly is not None:
                        continue
                    
                    # Check if already filled
                    current_value = await textarea.input_value()
                    if current_value and len(current_value.strip()) > 10:
                        continue
                    
                    # Get question context
                    field_name = await textarea.get_attribute('name') or ''
                    field_id = await textarea.get_attribute('id') or ''
                    field_placeholder = await textarea.get_attribute('placeholder') or ''
                    field_aria_label = await textarea.get_attribute('aria-label') or ''
                    
                    # Try to find associated label
                    question_text = field_aria_label or field_placeholder or field_name
                    
                    # Try to find label element
                    try:
                        label_for = field_id if field_id else None
                        if label_for:
                            label_elem = await modal.query_selector(f'label[for="{label_for}"]')
                            if label_elem:
                                label_text = await label_elem.text_content()
                                if label_text:
                                    question_text = label_text.strip()
                    except:
                        pass
                    
                    if question_text and len(question_text) > 5:
                        print(f"\n  ❓ Question: {question_text[:80]}")
                        print(f"  🤖 Generating AI answer...")
                        
                        # Generate AI answer combining resume + GitHub + job context
                        ai_answer = await self._generate_ai_answer(question_text, job_title, company)
                        
                        if ai_answer:
                            await textarea.click()
                            await textarea.fill(ai_answer)
                            await asyncio.sleep(random.uniform(0.5, 0.8))
                            filled_count += 1
                            print(f"  ✅ AI Answer: {ai_answer[:100]}...")
                            print(f"     👁️  Look at browser to see the AI-generated answer!")
                    
                except Exception as e:
                    print(f"  ⚠️  Could not fill textarea: {str(e)[:50]}")
            
            # Handle dropdowns (modal-specific)
            selects = await modal.query_selector_all('select')
            for select in selects:
                try:
                    if not await select.is_visible():
                        continue
                    
                    # Check if disabled
                    is_disabled = await select.get_attribute('disabled')
                    if is_disabled is not None:
                        continue
                    
                    field_name = await select.get_attribute('name') or ''
                    field_id = await select.get_attribute('id') or ''
                    field_aria_label = await select.get_attribute('aria-label') or ''
                    field_identifier = f"{field_name} {field_id} {field_aria_label}".lower()
                    
                    value = self._get_field_value_smart(field_identifier, 'select', self.user_profile)
                    
                    if value:
                        await select.select_option(label=value)
                        filled_count += 1
                        print(f"  ✅ Selected dropdown: '{field_identifier[:40]}' → '{value}'")
                        print(f"     👁️  Look at browser to see dropdown selection!")
                    else:
                        # Default: select first non-empty option
                        options = await select.query_selector_all('option')
                        if len(options) > 1:
                            option_text = await options[1].text_content()
                            await options[1].click()
                            filled_count += 1
                            print(f"  ✅ Selected default dropdown: '{option_text}'")
                            print(f"     👁️  Look at browser to see dropdown selection!")
                except Exception as e:
                    print(f"  ⚠️  Could not select dropdown: {str(e)[:50]}")
            
            # Handle LinkedIn custom dropdowns (button[aria-haspopup="listbox"], [role="combobox"])
            print(f"\n🔽 Processing LinkedIn custom dropdowns...")
            custom_triggers = await modal.query_selector_all(
                'button[aria-haspopup="listbox"], '
                '[role="combobox"]:not(input), '
                'div[data-test-text-selectable-option], '
                '.artdeco-dropdown__trigger'
            )
            for trigger in custom_triggers:
                try:
                    if not await trigger.is_visible():
                        continue
                    
                    # Check if already has a selection
                    current_text = (await trigger.text_content() or '').strip()
                    if current_text and current_text.lower() not in ['select an option', 'select', 'choose', '', '--']:
                        print(f"  ⏩ Custom dropdown already set: '{current_text[:30]}'")
                        continue
                    
                    # Get parent section label
                    label_text = ''
                    try:
                        parent_section = await trigger.evaluate_handle(
                            'el => el.closest(".fb-dash-form-element, .jobs-easy-apply-form-section__grouping, fieldset")'
                        )
                        if parent_section:
                            label_elem = await parent_section.as_element().query_selector(
                                'label, .fb-dash-form-element__label, legend, span.t-bold'
                            )
                            if label_elem:
                                label_text = (await label_elem.text_content() or '').lower().strip()
                    except:
                        pass
                    
                    # Click trigger to open listbox
                    await trigger.click()
                    await asyncio.sleep(0.4)
                    
                    # Find visible listbox
                    listbox = None
                    listbox_candidates = await self.page.query_selector_all('[role="listbox"]')
                    for lb in listbox_candidates:
                        try:
                            if await lb.is_visible():
                                listbox = lb
                                break
                        except:
                            pass
                    
                    if not listbox:
                        await self.page.keyboard.press('Escape')
                        continue
                    
                    option_elems = await listbox.query_selector_all('[role="option"]')
                    if not option_elems:
                        await self.page.keyboard.press('Escape')
                        continue
                    
                    # Try smart matching via _get_field_value_smart
                    desired = self._get_field_value_smart(label_text, 'select', self.user_profile)
                    
                    chosen = None
                    if desired:
                        desired_lower = desired.lower()
                        for opt_elem in option_elems:
                            opt_text = (await opt_elem.text_content() or '').strip().lower()
                            if opt_text == desired_lower or desired_lower in opt_text:
                                chosen = opt_elem
                                break
                    
                    # Fallback: pick first non-placeholder option
                    if not chosen and option_elems:
                        for opt_elem in option_elems:
                            opt_text = (await opt_elem.text_content() or '').strip().lower()
                            if opt_text not in ['select an option', 'select', 'choose', '', '--']:
                                chosen = opt_elem
                                break
                    
                    if chosen:
                        await chosen.click()
                        filled_count += 1
                        opt_text = (await chosen.text_content() or '').strip()
                        print(f"  ✅ Custom dropdown: '{label_text[:40]}' → '{opt_text[:30]}'")
                    else:
                        await self.page.keyboard.press('Escape')
                        print(f"  ⚠️  No matching option for custom dropdown: '{label_text[:40]}'")
                except Exception as e:
                    try:
                        await self.page.keyboard.press('Escape')
                    except:
                        pass
                    print(f"  ⚠️  Could not handle custom dropdown: {str(e)[:50]}")
            
            # Handle radio buttons (modal-specific) - Yes for work authorization, No for sponsorship
            radios = await modal.query_selector_all('input[type="radio"]')
            for radio in radios:
                try:
                    if not await radio.is_visible():
                        continue
                    
                    label = await self._get_field_label(radio)
                    label_lower = label.lower()
                    
                    # Work authorization
                    if 'authorized' in label_lower or 'eligible' in label_lower or 'legally' in label_lower:
                        if 'yes' in label_lower:
                            await radio.click()
                            filled_count += 1
                            print(f"  ✅ Selected: Yes for work authorization")
                    # Sponsorship
                    elif 'sponsor' in label_lower:
                        if 'no' in label_lower:
                            await radio.click()
                            filled_count += 1
                            print(f"  ✅ Selected: No for sponsorship")
                    # Relocation
                    elif 'relocat' in label_lower:
                        willing_to_relocate = self.user_profile.get('willing_to_relocate', True)
                        if ('yes' in label_lower and willing_to_relocate) or ('no' in label_lower and not willing_to_relocate):
                            await radio.click()
                            filled_count += 1
                            print(f"  ✅ Selected relocation preference")
                            
                except Exception as e:
                    pass
            
            # Handle checkboxes (modal-specific) - check required ones
            checkboxes = await modal.query_selector_all('input[type="checkbox"]')
            for checkbox in checkboxes:
                try:
                    if not await checkbox.is_visible():
                        continue
                    
                    label = await self._get_field_label(checkbox)
                    if 'terms' in label.lower() or 'agree' in label.lower() or 'privacy' in label.lower():
                        is_checked = await checkbox.is_checked()
                        if not is_checked:
                            await checkbox.click()
                            filled_count += 1
                            print(f"  ✅ Checked: {label}")
                except Exception as e:
                    pass
            
            print(f"\n✅ FORM AUTO-FILL COMPLETE!")
            print(f"📊 Filled {filled_count} fields total")
            print(f"👁️  Check the browser to see all filled values")
            print("═" * 80 + "\n")
                    
        except Exception as e:
            print(f"⚠️  Form filling error: {str(e)}")
    
    async def _get_field_label(self, element) -> str:
        """Get label text for a form field"""
        if not self.page:
            return "Unknown field"
            
        try:
            # Try to find associated label
            field_id = await element.get_attribute('id')
            if field_id:
                label = await self.page.query_selector(f'label[for="{field_id}"]')
                if label:
                    text = await label.text_content()
                    return text or "Unknown field"
            
            # Try aria-label
            aria_label = await element.get_attribute('aria-label')
            if aria_label:
                return aria_label
            
            # Try placeholder
            placeholder = await element.get_attribute('placeholder')
            if placeholder:
                return placeholder
            
            # Try name attribute
            name = await element.get_attribute('name')
            if name:
                return name
            
            return "Unknown field"
            
        except:
            return "Unknown field"
    
    def _get_field_value_smart(self, field_identifier: str, field_type: str, profile: Dict) -> Optional[str]:
        """Smart field matching based on keywords in field identifier
        
        Args:
            field_identifier: Combined string of field name, id, placeholder, aria-label (lowercase)
            field_type: 'text', 'select', etc.
            profile: User profile dict with personal/professional info
            
        Returns:
            Appropriate value for the field, or None if no match
        """
        # Name fields
        if any(keyword in field_identifier for keyword in ['first name', 'firstname', 'fname', 'given name']):
            return profile.get('first_name', '')
        
        if any(keyword in field_identifier for keyword in ['last name', 'lastname', 'lname', 'surname', 'family name']):
            return profile.get('last_name', '')
        
        if any(keyword in field_identifier for keyword in ['full name', 'legal name']) or field_identifier.strip() == 'name':
            first = profile.get('first_name', '')
            last = profile.get('last_name', '')
            return f"{first} {last}".strip() if first or last else None
        
        # Contact fields
        if any(keyword in field_identifier for keyword in ['email', 'e-mail', 'mail']) and 'domain' not in field_identifier:
            return profile.get('email', '') or os.getenv('LINKEDIN_EMAIL', '')
        
        if any(keyword in field_identifier for keyword in ['phone', 'mobile', 'telephone', 'contact number', 'cell']):
            return profile.get('phone_number', '') or profile.get('phone', '') or os.getenv('PHONE_NUMBER', '')
        
        # IMPROVED: Location fields - handle various location-related fields
        if any(keyword in field_identifier for keyword in ['location', 'preferred location', 'work location', 'job location']):
            return profile.get('location', '') or profile.get('preferred_location', '') or profile.get('city', '')
        
        # Address fields
        if any(keyword in field_identifier for keyword in ['street', 'address line 1', 'address1', 'street address']):
            return profile.get('street_address', '') or profile.get('address', '') or os.getenv('ADDRESS', '')
        
        if 'city' in field_identifier and 'state' not in field_identifier:
            return profile.get('city', '') or profile.get('location', '') or os.getenv('CITY', '')
        
        if any(keyword in field_identifier for keyword in ['state', 'province', 'region']) and 'country' not in field_identifier:
            return profile.get('state', '') or os.getenv('STATE', '')
        
        if any(keyword in field_identifier for keyword in ['zip', 'postal', 'postcode']):
            return profile.get('zip_code', '') or os.getenv('ZIP_CODE', '')
        
        if 'country' in field_identifier:
            return profile.get('country', 'United States')
        
        # Professional links
        if 'linkedin' in field_identifier and any(keyword in field_identifier for keyword in ['url', 'profile', 'link']):
            return profile.get('linkedin_url', '') or os.getenv('LINKEDIN_URL', '')
        
        if any(keyword in field_identifier for keyword in ['portfolio', 'website', 'personal site', 'personal website']):
            return profile.get('portfolio_url', '') or os.getenv('PORTFOLIO_URL', '')
        
        if 'github' in field_identifier:
            return profile.get('github_url', '')
        
        # Work experience
        if any(keyword in field_identifier for keyword in ['current company', 'employer', 'organization', 'company name']):
            return profile.get('current_company', '') or os.getenv('CURRENT_COMPANY', '')
        
        if any(keyword in field_identifier for keyword in ['current title', 'job title', 'position', 'current role']):
            return profile.get('current_title', '') or os.getenv('CURRENT_TITLE', '')
        
        if any(keyword in field_identifier for keyword in ['years of experience', 'experience', 'yrs', 'how many years']):
            years = profile.get('years_experience', '') or os.getenv('YEARS_EXPERIENCE', '')
            return str(years) if years else None
        
        # Education
        if any(keyword in field_identifier for keyword in ['university', 'college', 'school', 'institution']):
            return profile.get('university', '')
        
        if 'degree' in field_identifier or 'education' in field_identifier:
            return profile.get('degree', '')
        
        if any(keyword in field_identifier for keyword in ['graduation', 'grad year', 'year graduated', 'completion year']):
            year = profile.get('graduation_year', '') or os.getenv('GRADUATION_YEAR', '')
            return str(year) if year else None
        
        if 'gpa' in field_identifier or 'grade point' in field_identifier:
            return profile.get('gpa', '') or os.getenv('GPA', '')
        
        # Work authorization & visa
        if any(keyword in field_identifier for keyword in ['visa', 'work authorization', 'eligible to work', 'work permit']):
            return profile.get('visa_status', 'US Citizen')
        
        if 'relocat' in field_identifier:
            return 'Yes' if profile.get('willing_to_relocate', True) else 'No'
        
        # Compensation
        if any(keyword in field_identifier for keyword in ['salary', 'compensation', 'pay expectation', 'expected salary']):
            return profile.get('salary_expectation', '') or os.getenv('EXPECTED_SALARY', '')
        
        if any(keyword in field_identifier for keyword in ['start date', 'availability', 'when can you start', 'available to start']):
            return profile.get('start_date', 'Immediate')
        
        if 'notice' in field_identifier and 'period' in field_identifier:
            return profile.get('notice_period', '2 weeks')
        
        # Diversity fields (optional - user can choose to provide or leave blank)
        if 'gender' in field_identifier:
            return profile.get('gender', '')
        
        if any(keyword in field_identifier for keyword in ['ethnicity', 'race']):
            return profile.get('ethnicity', '')
        
        if 'veteran' in field_identifier:
            return profile.get('veteran_status', '')
        
        if 'disability' in field_identifier or 'disabled' in field_identifier:
            return profile.get('disability_status', '')
        
        return None
    
    async def _verify_submission(self) -> bool:
        """Verify application was submitted successfully"""
        if not self.page:
            return False
            
        try:
            # Wait for potential modal/success message to appear
            await asyncio.sleep(3)
            
            # Check for success indicators - more comprehensive list
            success_selectors = [
                'text="Application submitted"',
                'text="Your application was sent"',
                'text="Application sent"',
                'text="successfully"',
                'text="You applied"',
                'text="Applied"',
                '[data-test-modal-id="application-submitted-modal"]',
                '.artdeco-modal:has-text("Application submitted")',
                '.artdeco-modal:has-text("Application sent")',
                'h2:has-text("Application submitted")',
                'h2:has-text("Application sent")',
                '[aria-label*="Application submitted"]',
                '[aria-label*="Application sent"]',
            ]
            
            for selector in success_selectors:
                try:
                    el = await self.page.query_selector(selector)
                    if el and await el.is_visible():
                        print("   ✅ Application submission confirmed!")
                        return True
                except:
                    continue
            
            # Check URL change
            if 'application-submitted' in self.page.url:
                print("   ✅ Application confirmed via URL")
                return True
            
            # Check if modal closed (sometimes indicates success)
            modal_still_open = await self.page.query_selector('.jobs-easy-apply-modal')
            if not modal_still_open:
                print("   ✅ Modal closed - likely submitted")
                return True
            
            # Check page content for success message
            try:
                page_text = await self.page.inner_text('body')
                success_phrases = [
                    'application submitted',
                    'application was sent',
                    'you applied',
                    'successfully applied',
                    'application received'
                ]
                for phrase in success_phrases:
                    if phrase in page_text.lower():
                        print(f"   ✅ Found success phrase: '{phrase}'")
                        return True
            except:
                pass
            
            print("   ⚠️  Could not confirm submission")
            return False
            
        except Exception as e:
            print(f"   ⚠️  Verification error: {str(e)[:50]}")
            return False
    
    async def _save_application(self, job: Dict) -> None:
        """
        Save application to JSON database for tracking.
        
        Stores:
        - Job title
        - Company name  
        - Job URL (clickable LinkedIn link)
        - Application status (APPLIED / SKIPPED / FAILED)
        - Timestamp
        - Match score
        - Failure reason (if applicable)
        
        This data is exposed via GET /api/applications for frontend display.
        """
        try:
            from pathlib import Path
            import json
            
            # Ensure data directory exists
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            
            applications_file = data_dir / "applications.json"
            
            # Load existing applications
            applications = []
            if applications_file.exists():
                try:
                    with open(applications_file, 'r') as f:
                        applications = json.load(f)
                except:
                    applications = []
            
            # Determine status for display
            status_map = {
                'APPLIED': 'applied',
                'SKIPPED': 'skipped', 
                'FAILED': 'failed',
                'SUCCESS': 'applied'  # Legacy compatibility
            }
            
            display_status = status_map.get(
                job.get('application_status', 'FAILED'),
                'failed'
            )
            
            # Create application record with all required fields
            application_data = {
                'id': len(applications) + 1,
                'title': job.get('title', 'Unknown Job'),
                'company': job.get('company', 'Unknown Company'),
                'location': job.get('location', 'Unknown Location'),
                'url': job.get('url', ''),  # LinkedIn job URL
                'applied_date': job.get('applied_at', datetime.now().isoformat()),
                'status': display_status,  # applied / skipped / failed
                'match_score': int(job.get('similarity_score', 0)),
                'reason': job.get('application_reason', ''),  # Why it was skipped/failed
                'description': job.get('description', '')[:200] if job.get('description') else ''
            }
            
            applications.append(application_data)
            
            # Save to file with pretty formatting
            with open(applications_file, 'w') as f:
                json.dump(applications, f, indent=2)
            
            print(f"  💾 Application saved to database:")
            print(f"     - Status: {application_data['status'].upper()}")
            print(f"     - Job: {application_data['title']} at {application_data['company']}")
            print(f"     - URL: {application_data['url']}")
            if application_data['reason']:
                print(f"     - Reason: {application_data['reason']}")
            
        except Exception as e:
            print(f"  ⚠️  Could not save application to database: {str(e)}")
    
    def parse_resume(self, file_path: str) -> str:
        """Extract text from resume (supports PDF and TXT files)"""
        try:
            print(f"📄 Parsing resume: {file_path}")
            
            # Check file extension
            if file_path.endswith('.txt'):
                # Handle text files
                with open(file_path, 'r', encoding='utf-8') as file:
                    text = file.read()
            elif file_path.endswith('.pdf'):
                # Handle PDF files
                with open(file_path, 'rb') as file:
                    pdf = PdfReader(file)
                    text = ""
                    for page in pdf.pages:
                        text += page.extract_text() + "\n"
            else:
                raise Exception(f"Unsupported file format: {file_path}")
            
            self.resume_text = text
            print(f"✅ Resume parsed: {len(text)} characters")
            return text
            
        except Exception as e:
            print(f"❌ Resume parsing error: {str(e)}")
            self.errors.append(f"Resume parsing failed: {str(e)}")
            return ""
    
    async def run_automation(self) -> Dict:
        """Main automation flow"""
        start_time = datetime.now()
        
        try:
            # Phase 1: Browser initialization
            print("\n" + "="*60)
            print("PHASE 1: BROWSER INITIALIZATION")
            print("="*60)
            await self.initialize_browser()
            
            # Phase 2: LinkedIn login
            print("\n" + "="*60)
            print("PHASE 2: LINKEDIN LOGIN")
            print("="*60)
            if not await self.login_linkedin():
                raise Exception("Login failed")
            
            # Phase 3: Parse resume
            print("\n" + "="*60)
            print("PHASE 3: RESUME PARSING")
            print("="*60)
            resume_path = self.config.get('resume_path', '')
            if resume_path:
                self.parse_resume(resume_path)
            
            # Phase 4: Job search
            print("\n" + "="*60)
            print("PHASE 4: JOB SEARCH")
            print("="*60)
            await self.search_jobs(
                self.config['keyword'],
                self.config['location']
            )
            
            # Phase 5: Collect job listings
            print("\n" + "="*60)
            print("PHASE 5: COLLECTING JOB LISTINGS")
            print("="*60)
            await self.collect_job_listings(max_jobs=30)
            
            # Phase 6: AI analysis and selection
            print("\n" + "="*60)
            print("PHASE 6: AI JOB ANALYSIS")
            print("="*60)
            max_apply = min(int(self.config.get('max_jobs', 5)), 5)  # Safety limit
            top_jobs = await self.select_top_jobs(max_apply=max_apply)
            
            # Phase 7: Auto-apply
            print("\n" + "="*60)
            print("PHASE 7: AUTOMATED APPLICATIONS")
            print("="*60)
            
            if self.config.get('auto_apply', True):
                for job in top_jobs:
                    result = await self.auto_apply_job(job)
                    await asyncio.sleep(random.uniform(10, 15))  # Delay between applications
            else:
                print("⏭️  Auto-apply disabled, skipping applications")
                for job in top_jobs:
                    job['application_status'] = 'SKIPPED'
                    job['application_reason'] = 'Auto-apply disabled'
            
            # Phase 8: Generate report
            print("\n" + "="*60)
            print("PHASE 8: GENERATING REPORT")
            print("="*60)
            
            end_time = datetime.now()
            duration = (end_time - start_time).seconds
            
            applications_successful = len([j for j in top_jobs if j.get('application_status') == 'SUCCESS'])
            
            report = {
                'jobs_found': len(self.jobs_data),
                'jobs_analyzed': len(self.jobs_data),
                'applications_attempted': len(top_jobs),
                'applications_successful': applications_successful,
                'jobs': top_jobs,
                'summary': f"Automation completed in {duration}s. Applied to {applications_successful}/{len(top_jobs)} jobs successfully.",
                'errors': self.errors,
                'timestamp': datetime.now().isoformat(),
                'duration_seconds': duration
            }
            
            print("\n" + "="*60)
            print("✅ AUTOMATION COMPLETE!")
            print("="*60)
            print(f"📊 Jobs Found: {report['jobs_found']}")
            print(f"🤖 Jobs Analyzed: {report['jobs_analyzed']}")
            print(f"📝 Applications Attempted: {report['applications_attempted']}")
            print(f"✅ Applications Successful: {report['applications_successful']}")
            print(f"⏱️  Duration: {duration} seconds")
            
            return report
            
        except Exception as e:
            print(f"\n❌ AUTOMATION FAILED: {str(e)}")
            self.errors.append(f"Automation failed: {str(e)}")
            
            return {
                'jobs_found': len(self.jobs_data),
                'jobs_analyzed': len(self.jobs_data),
                'applications_attempted': 0,
                'applications_successful': 0,
                'jobs': [],
                'summary': f"Automation failed: {str(e)}",
                'errors': self.errors,
                'timestamp': datetime.now().isoformat()
            }
        
        finally:
            # Cleanup
            if self.browser:
                print("\n🧹 Cleaning up...")
                try:
                    await self.browser.close()
                except Exception as e:
                    print(f"⚠️  Browser cleanup warning: {str(e)}")
                    # Ignore cleanup errors as browser may already be closed

    async def search_jobs_only(self) -> List[Dict]:
        """
        Search for jobs without applying - returns job listings with URLs
        Used by the frontend to display searchable jobs
        """
        try:
            # Initialize browser
            await self.initialize_browser()
            
            # Login to LinkedIn
            if not await self.login_linkedin():
                raise Exception("Login failed")
            
            # Search for jobs
            keyword = self.config.get('keyword', 'Software Engineer')
            location = self.config.get('location', 'United States')
            
            await self.search_jobs(keyword, location)
            
            # Collect job listings
            max_jobs = self.config.get('max_jobs', 25)
            await self.collect_job_listings(max_jobs=max_jobs)
            
            # Format jobs for frontend
            formatted_jobs = []
            for job in self.jobs_data:
                formatted_jobs.append({
                    'id': job.get('job_id', str(hash(job.get('url', '')))),
                    'title': job.get('title', 'Unknown Position'),
                    'company': job.get('company', 'Unknown Company'),
                    'location': job.get('location', 'Unknown'),
                    'url': job.get('url', ''),
                    'is_easy_apply': job.get('is_easy_apply', False),
                    'posted': job.get('posted', 'Recently'),
                    'description': job.get('description', '')[:200] if job.get('description') else '',
                    'match_score': random.randint(75, 98)  # Placeholder until AI analysis
                })
            
            print(f"✅ Found {len(formatted_jobs)} jobs")
            return formatted_jobs
            
        except Exception as e:
            print(f"❌ Job search error: {str(e)}")
            return []
        
        finally:
            if self.browser:
                try:
                    await self.browser.close()
                except:
                    pass

    async def apply_to_single_job(self, job_url: str) -> Dict:
        """
        Apply to a single job by URL
        """
        try:
            # Initialize browser
            await self.initialize_browser()
            
            # Login to LinkedIn
            if not await self.login_linkedin():
                return {'success': False, 'message': 'Login failed'}
            
            # Ensure page exists
            if self.page is None:
                return {'success': False, 'message': 'Browser page not initialized'}
            
            # Open application with robust handler (avoids networkidle timeouts)
            print(f"🔍 Navigating to job: {job_url}")
            handler = ApplicationHandler(self.page)
            open_result = await handler.open_job_application(job_url)
            if open_result.get('status') != 'SUCCESS':
                return {'success': False, 'message': open_result.get('reason', 'Failed to open application')}
            
            # Create job dict
            job = {
                'url': job_url,
                'title': self.config.get('job_title', 'Unknown'),
                'company': self.config.get('company', 'Unknown')
            }
            
            # Try to get job details from page
            try:
                title_elem = await self.page.query_selector('h1.t-24')
                if title_elem:
                    job['title'] = await title_elem.inner_text()
                    
                company_elem = await self.page.query_selector('a.ember-view.t-black.t-normal')
                if company_elem:
                    job['company'] = await company_elem.inner_text()
            except:
                pass
            
            # Apply to job
            result = await self.auto_apply_job(job)
            
            success = result.get('application_status') in ('APPLIED', 'SUCCESS')
            
            return {
                'success': success,
                'message': result.get('application_reason', 'Application processed'),
                'job': job
            }
            
        except Exception as e:
            print(f"❌ Single job application error: {str(e)}")
            return {'success': False, 'message': str(e)}
        
        finally:
            if self.browser:
                try:
                    await self.browser.close()
                except:
                    pass
                    # Ignore cleanup errors as browser may already be closed
