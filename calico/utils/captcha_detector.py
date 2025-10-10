"""CAPTCHA detection and handling utilities."""
from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, Callable

from playwright.async_api import Page

logger = logging.getLogger(__name__)


class CaptchaDetector:
    """Detects and handles CAPTCHAs during browser automation."""
    
    # Common CAPTCHA indicators
    CAPTCHA_SELECTORS = [
        # reCAPTCHA
        'iframe[src*="recaptcha"]',
        'iframe[src*="google.com/recaptcha"]',
        '.g-recaptcha',
        '#g-recaptcha',
        '[data-sitekey]',  # reCAPTCHA v2/v3
        
        # hCaptcha
        'iframe[src*="hcaptcha"]',
        '.h-captcha',
        '#h-captcha',
        '[data-hcaptcha-sitekey]',
        
        # Generic CAPTCHA indicators
        '[class*="captcha" i]',
        '[id*="captcha" i]',
        '[name*="captcha" i]',
        'img[alt*="captcha" i]',
        'img[src*="captcha" i]',
        
        # Cloudflare
        '#challenge-stage',
        '.cf-challenge',
        '[id*="cf-challenge"]',
        
        # Bot detection / challenge pages
        '[class*="robot-check" i]',
        '[id*="robot-check" i]',
        '[class*="bot-check" i]',
        'body:has-text("checking your browser")',
        'body:has-text("verify you are human")',
        'body:has-text("security check")',
        'body:has-text("access denied")',
        'body:has-text("unusual activity")',
    ]
    
    # HTTP status codes that might indicate bot detection
    BOT_DETECTION_STATUSES = [403, 412, 429, 503]
    
    def __init__(self, session_id: str, notification_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None):
        """Initialize captcha detector.
        
        Args:
            session_id: Unique session identifier
            notification_callback: Optional callback to notify about captcha detection
        """
        self.session_id = session_id
        self.notification_callback = notification_callback
        self.captcha_dir = Path("sessions") / session_id / "captcha"
        self.captcha_dir.mkdir(parents=True, exist_ok=True)
        
        # Track detected captchas
        self.detected_captchas: Dict[str, Dict[str, Any]] = {}
    
    async def check_for_captcha(self, page: Page) -> Optional[Dict[str, Any]]:
        """Check if the current page contains a CAPTCHA.
        
        Args:
            page: Playwright page to check
            
        Returns:
            Dict with captcha info if detected, None otherwise
        """
        try:
            # Check for common captcha selectors
            for selector in self.CAPTCHA_SELECTORS:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        # CAPTCHA detected!
                        captcha_type = self._identify_captcha_type(selector)
                        captcha_id = str(uuid.uuid4())[:8]
                        url = page.url
                        
                        # Take screenshot of the captcha
                        screenshot_path = await self._save_captcha_screenshot(page, captcha_id)
                        
                        captcha_info = {
                            "captcha_id": captcha_id,
                            "type": captcha_type,
                            "selector": selector,
                            "url": url,
                            "screenshot_path": str(screenshot_path),
                            "api_url": f"/api/captcha/{self.session_id}/{captcha_id}",
                            "solved": False,
                        }
                        
                        # Store for tracking
                        self.detected_captchas[captcha_id] = captcha_info
                        
                        # Notify via callback
                        if self.notification_callback:
                            self.notification_callback("playwright.captcha_detected", captcha_info)
                        
                        logger.warning(f"CAPTCHA detected: {captcha_type} at {url}")
                        logger.info(f"Screenshot saved to: {screenshot_path}")
                        
                        return captcha_info
                        
                except Exception as e:
                    # Selector might fail, continue to next one
                    logger.debug(f"Selector '{selector}' check failed: {e}")
                    continue
            
            # Also check page title and content for bot detection
            title = await page.title()
            if any(keyword in title.lower() for keyword in ["captcha", "verify", "challenge", "robot", "bot check"]):
                captcha_id = str(uuid.uuid4())[:8]
                screenshot_path = await self._save_captcha_screenshot(page, captcha_id)
                
                captcha_info = {
                    "captcha_id": captcha_id,
                    "type": "unknown",
                    "selector": "title-based",
                    "url": page.url,
                    "screenshot_path": str(screenshot_path),
                    "api_url": f"/api/captcha/{self.session_id}/{captcha_id}",
                    "solved": False,
                }
                
                self.detected_captchas[captcha_id] = captcha_info
                
                if self.notification_callback:
                    self.notification_callback("playwright.captcha_detected", captcha_info)
                
                logger.warning(f"Possible CAPTCHA detected from title: {title}")
                return captcha_info
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking for CAPTCHA: {e}")
            return None
    
    async def _save_captcha_screenshot(self, page: Page, captcha_id: str) -> Path:
        """Save a screenshot of the captcha page.
        
        Args:
            page: Playwright page
            captcha_id: Unique captcha identifier
            
        Returns:
            Path to the saved screenshot
        """
        screenshot_path = self.captcha_dir / f"{captcha_id}.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        return screenshot_path
    
    def _identify_captcha_type(self, selector: str) -> str:
        """Identify the type of CAPTCHA based on selector.
        
        Args:
            selector: CSS selector that matched
            
        Returns:
            CAPTCHA type string
        """
        selector_lower = selector.lower()
        
        if "recaptcha" in selector_lower:
            return "reCAPTCHA"
        elif "hcaptcha" in selector_lower:
            return "hCaptcha"
        elif "cloudflare" in selector_lower or "cf-challenge" in selector_lower:
            return "Cloudflare"
        elif "robot" in selector_lower or "bot" in selector_lower:
            return "Bot Detection"
        else:
            return "Generic CAPTCHA"
    
    def get_captcha_info(self, captcha_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a detected captcha.
        
        Args:
            captcha_id: Captcha identifier
            
        Returns:
            Captcha info dict or None if not found
        """
        return self.detected_captchas.get(captcha_id)
    
    def mark_captcha_solved(self, captcha_id: str, solution: Optional[str] = None):
        """Mark a captcha as solved.
        
        Args:
            captcha_id: Captcha identifier
            solution: Optional solution data
        """
        if captcha_id in self.detected_captchas:
            self.detected_captchas[captcha_id]["solved"] = True
            if solution:
                self.detected_captchas[captcha_id]["solution"] = solution
            logger.info(f"Captcha {captcha_id} marked as solved")
    
    async def wait_for_captcha_solution(self, captcha_id: str, timeout: int = 300) -> bool:
        """Wait for a captcha to be solved by a human.
        
        Args:
            captcha_id: Captcha identifier
            timeout: Maximum time to wait in seconds (default: 5 minutes)
            
        Returns:
            True if solved within timeout, False otherwise
        """
        start_time = asyncio.get_event_loop().time()
        
        while True:
            # Check if solved
            captcha_info = self.get_captcha_info(captcha_id)
            if captcha_info and captcha_info.get("solved", False):
                return True
            
            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                logger.warning(f"Captcha {captcha_id} solution timeout after {timeout}s")
                return False
            
            # Wait a bit before checking again
            await asyncio.sleep(2)
    
    def get_all_captchas(self) -> Dict[str, Dict[str, Any]]:
        """Get all detected captchas for this session.
        
        Returns:
            Dict mapping captcha_id to captcha info
        """
        return self.detected_captchas.copy()
    
    async def check_bot_detection_response(self, status_code: int, url: str, page: Page) -> Optional[Dict[str, Any]]:
        """Check if an HTTP response indicates bot detection.
        
        Args:
            status_code: HTTP status code
            url: Request URL
            page: Playwright page
            
        Returns:
            Bot detection info if detected, None otherwise
        """
        if status_code in self.BOT_DETECTION_STATUSES:
            logger.warning(f"Potential bot detection: HTTP {status_code} at {url}")
            
            # Take screenshot
            captcha_id = str(uuid.uuid4())[:8]
            screenshot_path = await self._save_captcha_screenshot(page, captcha_id)
            
            detection_info = {
                "captcha_id": captcha_id,
                "type": "Bot Detection / HTTP Error",
                "selector": f"http-{status_code}",
                "url": url,
                "status_code": status_code,
                "screenshot_path": str(screenshot_path),
                "api_url": f"/api/captcha/{self.session_id}/{captcha_id}",
                "solved": False,
            }
            
            self.detected_captchas[captcha_id] = detection_info
            
            if self.notification_callback:
                self.notification_callback("playwright.captcha_detected", detection_info)
            
            return detection_info
        
        return None
