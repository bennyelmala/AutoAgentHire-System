"""
Enhanced LinkedIn Job Application Handler
Fixes application opening issues and improves form filling reliability
"""

import asyncio
import random
import time
from typing import Dict, Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError


class ApplicationHandler:
    """
    Handles LinkedIn Easy Apply form interactions with robust error handling
    """
    
    def __init__(self, page: Page):
        self.page = page
    
    async def open_job_application(self, job_url: str, max_retries: int = 3) -> Dict:
        """
        Open LinkedIn job application with retry logic and better error handling
        
        Args:
            job_url: LinkedIn job URL
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dict with status and details
        """
        print(f"\n📂 Opening job application: {job_url}")
        
        for attempt in range(max_retries):
            try:
                print(f"   Attempt {attempt + 1}/{max_retries}...")
                
                # Navigate to job URL with multiple wait strategies
                print("   ➤ Navigating to job page...")
                await self.page.goto(job_url, wait_until='domcontentloaded', timeout=30000)
                
                # Wait for page to stabilize
                await asyncio.sleep(random.uniform(2, 3))
                
                # Wait for job details to load
                print("   ➤ Waiting for job details to load...")
                await self._wait_for_job_details()
                
                # Verify we're on the correct page
                current_url = self.page.url
                if 'linkedin.com/jobs' not in current_url:
                    raise Exception(f"Not on LinkedIn jobs page. Current URL: {current_url}")
                
                print("   ✅ Job page loaded successfully")
                
                # Find and click Easy Apply button with multiple strategies
                print("   ➤ Looking for Easy Apply button...")
                easy_apply_clicked = await self._click_easy_apply_button()
                
                if not easy_apply_clicked:
                    if attempt < max_retries - 1:
                        print(f"   ⚠️  Easy Apply button not found, retrying...")
                        await asyncio.sleep(2)
                        continue
                    else:
                        return {
                            'status': 'FAILED',
                            'reason': 'Easy Apply button not found after retries',
                            'error': 'button_not_found'
                        }
                
                print("   ✅ Easy Apply button clicked")
                
                # Wait for application modal to appear
                print("   ➤ Waiting for application modal...")
                modal_opened = await self._wait_for_application_modal()
                
                if not modal_opened:
                    if attempt < max_retries - 1:
                        print(f"   ⚠️  Modal did not open, retrying...")
                        # Close any error dialogs
                        await self._close_error_dialogs()
                        await asyncio.sleep(2)
                        continue
                    else:
                        return {
                            'status': 'FAILED',
                            'reason': 'Application modal did not open',
                            'error': 'modal_not_opened'
                        }
                
                print("   ✅ Application modal opened successfully")
                
                # Success - application is open and ready
                return {
                    'status': 'SUCCESS',
                    'reason': 'Application opened successfully',
                    'modal_open': True
                }
                
            except PlaywrightTimeoutError as e:
                print(f"   ⚠️  Timeout error: {str(e)[:100]}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(3)
                    continue
                else:
                    return {
                        'status': 'FAILED',
                        'reason': f'Timeout after {max_retries} attempts',
                        'error': 'timeout'
                    }
            
            except Exception as e:
                print(f"   ⚠️  Error: {str(e)[:100]}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(3)
                    continue
                else:
                    return {
                        'status': 'FAILED',
                        'reason': f'Error: {str(e)}',
                        'error': 'exception'
                    }
        
        return {
            'status': 'FAILED',
            'reason': f'Failed to open application after {max_retries} attempts',
            'error': 'max_retries_exceeded'
        }
    
    async def _wait_for_job_details(self, timeout: int = 10000) -> bool:
        """Wait for job details section to load"""
        try:
            # Wait for any of these key elements that indicate job page loaded
            selectors = [
                '.jobs-unified-top-card',
                '.job-view-layout',
                'h1.t-24',  # Job title
                '.jobs-details',
            ]
            
            for selector in selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=timeout)
                    if element:
                        return True
                except:
                    continue
            
            return False
        except Exception as e:
            print(f"   ⚠️  Error waiting for job details: {str(e)[:50]}")
            return False
    
    async def _click_easy_apply_button(self) -> bool:
        """
        Find and click Easy Apply button using multiple strategies
        
        Returns:
            bool: True if clicked successfully
        """
        print("   🔍 Looking for Easy Apply button with multiple selectors...")
        
        # First, close any open modals that might be blocking
        try:
            close_buttons = await self.page.query_selector_all('button[aria-label*="Dismiss"], button[data-test-modal-close-btn]')
            for close_btn in close_buttons:
                try:
                    if await close_btn.is_visible():
                        print("   🚪 Closing interfering modal...")
                        await close_btn.click()
                        await asyncio.sleep(0.5)
                except:
                    pass
        except:
            pass
        
        # Multiple selector strategies for Easy Apply button (LinkedIn 2024/2025)
        # Prefer "Easy Apply" explicitly; generic "Apply" can be an external apply.
        selectors = [
            # Top-card specific (most reliable)
            '.jobs-unified-top-card button:has-text("Easy Apply")',
            '.jobs-unified-top-card button[aria-label*="Easy Apply"]',
            '.jobs-unified-top-card button.jobs-apply-button',
            '.jobs-details-top-card button:has-text("Easy Apply")',

            # Current LinkedIn selectors
            'button.jobs-apply-button--top-card:has-text("Easy Apply")',
            'button.jobs-apply-button:has-text("Easy Apply")',
            'button.artdeco-button--primary:has-text("Easy Apply")',

            # Text / aria fallbacks
            'button:has-text("Easy Apply")',
            'button[aria-label*="Easy Apply"]',
            'a:has-text("Easy Apply")',

            # Last resort: "Apply" (could be offsite)
            '.jobs-unified-top-card button:has-text("Apply")',
            'button.jobs-apply-button--top-card',
            'button.jobs-apply-button',
        ]
        
        # First, list candidate apply-ish controls for debugging (including aria-label and anchors)
        try:
            candidates = await self.page.query_selector_all('button, a')
            print(f"   📊 Found {len(candidates)} clickable candidates (button/a), checking for Apply...")
            shown = 0
            for el in candidates:
                if shown >= 25:
                    break
                try:
                    text = (await el.inner_text()) or ""
                    aria = (await el.get_attribute('aria-label')) or ""
                    combined = f"{text} {aria}".strip().lower()
                    if any(k in combined for k in ("easy apply", "apply", "bewerben", "candidature")):
                        print(f"      • Candidate: text='{text.strip()[:60]}' aria='{aria.strip()[:60]}'")
                        shown += 1
                except Exception:
                    continue
        except Exception:
            pass

        # Strategy: if explicit selector tries fail, do a DOM scan inside the top-card to find an Easy Apply control.
        async def find_easy_apply_by_scan() -> Optional[object]:
            containers = [
                '.jobs-unified-top-card',
                '.jobs-details-top-card',
                'main',
            ]
            for csel in containers:
                try:
                    container = await self.page.query_selector(csel)
                    if not container:
                        continue
                    els = await container.query_selector_all('button, a')
                    for el in els:
                        try:
                            if not await el.is_visible():
                                continue
                            text = (await el.inner_text()) or ""
                            aria = (await el.get_attribute('aria-label')) or ""
                            combined = f"{text} {aria}".strip().lower()
                            if "easy apply" in combined:
                                return el
                        except Exception:
                            continue
                except Exception:
                    continue
            return None
        
        for idx, selector in enumerate(selectors, 1):
            try:
                print(f"   [{idx}/{len(selectors)}] Trying selector: {selector[:50]}...")
                
                # Find button
                button = await self.page.wait_for_selector(selector, timeout=2000)
                
                if not button:
                    continue
                
                # Check if button is visible and enabled
                if not await button.is_visible():
                    print(f"       ↳ Found but not visible")
                    continue
                
                if not await button.is_enabled():
                    print(f"       ↳ Found but disabled")
                    continue
                
                # Get button text to verify it's the right button
                button_text = (await button.inner_text()) or ""
                aria_label = (await button.get_attribute('aria-label')) or ""
                print(f"       ✓ Found button: '{button_text.strip()}'")
                
                # Verify it's an Apply button
                verify_text = f"{button_text} {aria_label}".lower()
                if 'apply' not in verify_text:
                    print(f"       ↳ Not an Apply button, skipping")
                    continue

                # Prefer Easy Apply; if selector matched generic Apply but not Easy Apply, keep trying others first
                if 'easy apply' not in verify_text and 'apply' in verify_text:
                    print("       ↳ Generic Apply detected (might be offsite); will still try click but may skip")
                
                # Try to click with multiple strategies
                print(f"       👆 Attempting to click...")
                clicked = await self._robust_click(button, "Easy Apply")
                if clicked:
                    print(f"       ✅ Successfully clicked Easy Apply button!")
                    return True
                    
            except PlaywrightTimeoutError:
                # This selector didn't work, try next one
                print(f"       ↳ Timeout (button not found with this selector)")
                continue
            except Exception as e:
                print(f"       ⚠️  Error: {str(e)[:60]}")
                continue
        
        print(f"   ❌ Easy Apply button not found with any selector")

        try:
            scanned = await find_easy_apply_by_scan()
            if scanned:
                print("   🔎 Found Easy Apply via DOM scan, attempting click...")
                clicked = await self._robust_click(scanned, "Easy Apply (scan)")
                if clicked:
                    return True
        except Exception:
            pass
        
        # Take screenshot for debugging
        try:
            screenshot_path = f"debug_screenshots/no_easy_apply_button_{int(time.time())}.png"
            await self.page.screenshot(path=screenshot_path)
            print(f"   📸 Screenshot saved to: {screenshot_path}")
        except:
            pass
        
        return False
    
    async def _robust_click(self, element, element_name: str = "element") -> bool:
        """
        Click element with multiple fallback strategies
        
        Returns:
            bool: True if click succeeded
        """
        strategies = [
            ("Normal click", lambda e: e.click()),
            ("Click with force", lambda e: e.click(force=True)),
            ("JavaScript click", lambda e: e.evaluate("element => element.click()")),
            ("Dispatch click event", lambda e: e.dispatch_event("click")),
        ]
        
        for strategy_name, click_func in strategies:
            try:
                await click_func(element)
                print(f"   ✓ {element_name} clicked using: {strategy_name}")
                await asyncio.sleep(random.uniform(1, 2))
                return True
            except Exception as e:
                print(f"   ⚠️  {strategy_name} failed: {str(e)[:50]}")
                continue
        
        return False
    
    async def _wait_for_application_modal(self, timeout: int = 10000) -> bool:
        """
        Wait for Easy Apply modal to appear
        
        Returns:
            bool: True if modal appeared
        """
        modal_selectors = [
            '.jobs-easy-apply-modal',
            '[data-test-modal-id="easy-apply-modal"]',
            '.artdeco-modal[role="dialog"]',
            'div[data-test-modal-container]',
            '[aria-label*="Easy Apply"]',
        ]
        
        for selector in modal_selectors:
            try:
                element = await self.page.wait_for_selector(selector, timeout=timeout)
                if element and await element.is_visible():
                    # Double-check modal content loaded
                    await asyncio.sleep(1)
                    return True
            except:
                continue
        
        return False
    
    async def _close_error_dialogs(self):
        """Close any error dialogs or overlays that might be blocking"""
        close_selectors = [
            'button[aria-label*="Dismiss"]',
            'button[aria-label*="Close"]',
            'button.artdeco-modal__dismiss',
            '.artdeco-modal__dismiss',
        ]
        
        for selector in close_selectors:
            try:
                button = await self.page.query_selector(selector)
                if button and await button.is_visible():
                    await button.click()
                    await asyncio.sleep(0.5)
            except:
                continue
    
    async def has_captcha_or_security_check(self) -> bool:
        """
        Check if page has CAPTCHA or security verification
        
        Returns:
            bool: True if security check detected
        """
        security_indicators = [
            'checkpoint/challenge',
            'security/challenge',
            'captcha',
            'verification',
        ]
        
        current_url = self.page.url.lower()
        
        for indicator in security_indicators:
            if indicator in current_url:
                return True
        
        # Check for CAPTCHA elements on page
        captcha_selectors = [
            'iframe[src*="recaptcha"]',
            'iframe[src*="captcha"]',
            '[data-test-id="captcha"]',
            '.g-recaptcha',
        ]
        
        for selector in captcha_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    return True
            except:
                continue
        
        return False
