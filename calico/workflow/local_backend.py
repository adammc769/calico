"""Local Playwright backend for direct browser automation without MCP."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable, Tuple
from pathlib import Path

from playwright.async_api import async_playwright, Playwright

from calico.agent import AIAction, AIActionExecutor
from calico.agent.actions import ActionResult
from calico.workflow.config import get_settings
from calico.browser.config import (
    get_chrome_args,
    get_font_injection_script,
    get_minimal_stealth_script,
    get_context_options as get_default_context_options,
    USER_AGENT_POOL,
)

logger = logging.getLogger(__name__)


async def create_local_executor(
    session_id: str,
    headless: bool = True,
    stealth_mode: bool = True,  # Add stealth mode control
    max_action_retries: int = 3,
    notification_handler: Callable[[str, dict], None] | None = None,
) -> Tuple[AIActionExecutor, Callable[[], Awaitable[None]]]:
    """Create a local Playwright executor without MCP.
    
    Args:
        session_id: Unique session identifier
        headless: Whether to run browser in headless mode
        stealth_mode: Whether to inject stealth/anti-detection scripts
        max_action_retries: Maximum number of retries for failed actions
        notification_handler: Optional callback for notifications
        
    Returns:
        Tuple of (executor, cleanup_function)
    """
    import os
    from pathlib import Path
    
    logger.info(f"Creating local Playwright executor for session {session_id}")
    
    # Setup console log file
    from calico.utils.session_storage import SessionStorage

    storage = SessionStorage(session_id=session_id)
    session_dir = storage.session_dir
    console_log_path = session_dir / "console.log"
    console_log_file = open(console_log_path, "a", encoding="utf-8")
    
    def log_to_file(message: str):
        """Log message to console log file."""
        console_log_file.write(f"{message}\n")
        console_log_file.flush()
    
    try:
        # Get settings for patchright preference
        settings = get_settings()
        
        # Launch Playwright or Patchright based on settings
        if settings.playwright_use_patchright:
            try:
                from patchright.async_api import async_playwright as patchright_async_playwright
                logger.debug("Starting Patchright (patched Playwright)...")
                playwright = await patchright_async_playwright().start()
                logger.info("Using Patchright for enhanced bot detection evasion")
            except ImportError:
                logger.warning("Patchright not installed, falling back to standard Playwright. Install with: pip install patchright")
                logger.debug("Starting standard Playwright...")
                playwright = await async_playwright().start()
        else:
            logger.debug("Starting standard Playwright...")
            playwright = await async_playwright().start()
        
        logger.debug(f"Launching browser (headless={headless}, stealth_mode={stealth_mode})...")
        
        # Build Chrome arguments using centralized config
        chrome_args = get_chrome_args(
            stealth_mode=stealth_mode,
            headless=headless,
            extra_args=None
        )
        
        # Launch browser - respect headless parameter
        browser = await playwright.chromium.launch(
            headless=headless,  # Properly respect the headless parameter
            args=chrome_args,
            timeout=60000,  # 60 second timeout
            chromium_sandbox=False,
        )
        
        logger.debug("Creating browser context...")
        
        # Use a recent Chrome user agent (update regularly for best results)
        user_agent = USER_AGENT_POOL[0]  # Latest Chrome
        
        # Get context options from centralized config
        context_options = get_default_context_options(
            viewport={"width": 1920, "height": 1080},
            user_agent=user_agent,
            locale="en-US",
            timezone_id="America/New_York",
            stealth_mode=stealth_mode,
        )
        
        context = await browser.new_context(**context_options)
        
        logger.debug("Creating new page...")
        page = await context.new_page()
        
        # Force system fonts for text rendering (fixes Chromium font issues on Linux)
        logger.debug("Injecting font CSS...")
        await page.add_init_script(get_font_injection_script())
        
        # Inject anti-detection scripts only if stealth mode is enabled
        if stealth_mode:
            logger.debug("Injecting anti-detection scripts...")
            # Load the stealth init script from external file
            # This avoids Python string escaping issues with large inline scripts
            stealth_script_path = Path(__file__).parent / "stealth_init.js"
            
            try:
                with open(stealth_script_path, 'r', encoding='utf-8') as f:
                    stealth_script = f.read()
                logger.debug(f"Loaded stealth script from {stealth_script_path} ({len(stealth_script)} bytes)")
                
                # Inject the anti-detection script
                await page.add_init_script(stealth_script)
                logger.debug("Anti-detection scripts injected successfully")
            except Exception as e:
                logger.warning(f"Failed to load stealth script from {stealth_script_path}: {e}")
                logger.warning("Continuing without full stealth protection")
                # Add minimal protection
                await page.add_init_script(get_minimal_stealth_script())
        else:
            logger.debug("Stealth mode disabled, skipping anti-detection scripts")
        
        # Set up Playwright event listeners for real-time feedback
        if notification_handler:
            # Check if the notification handler is async or sync
            import inspect
            is_async_handler = inspect.iscoroutinefunction(notification_handler)
            
            # Helper to safely call handler (sync or async)
            def safe_notify(event_type: str, data: dict):
                """Safely call notification handler (sync or async)."""
                try:
                    if is_async_handler:
                        # Schedule async callback without awaiting
                        asyncio.create_task(notification_handler(event_type, data))
                    else:
                        # Call sync callback directly
                        notification_handler(event_type, data)
                except Exception as e:
                    logger.warning(f"Error in {event_type} notification handler: {e}")
            
            # Console messages from the browser
            def handle_console(msg):
                log_message = f"[{msg.type}] {msg.text}"
                log_to_file(log_message)
                safe_notify("playwright.console", {
                    "type": msg.type,
                    "text": msg.text,
                    "location": f"{msg.location.get('url', 'unknown')}:{msg.location.get('lineNumber', 0)}" if msg.location else "unknown"
                })
            
            page.on("console", handle_console)
            
            # Page navigation events
            def handle_navigation(frame):
                if frame == page.main_frame:
                    safe_notify("playwright.navigation", {
                        "url": frame.url,
                        "name": frame.name or "main"
                    })
            
            page.on("framenavigated", handle_navigation)
            
            # Page errors
            def handle_page_error(error):
                safe_notify("playwright.error", {
                    "message": str(error),
                    "stack": getattr(error, 'stack', None)
                })
            
            page.on("pageerror", handle_page_error)
            
            # Request events (for network activity visibility)
            def handle_request(request):
                safe_notify("playwright.request", {
                    "url": request.url,
                    "method": request.method,
                    "resource_type": request.resource_type
                })
            
            page.on("request", handle_request)
            
            # Response events
            def handle_response(response):
                safe_notify("playwright.response", {
                    "url": response.url,
                    "status": response.status,
                    "ok": response.ok
                })
            
            page.on("response", handle_response)
            
            # Page load events
            def handle_load():
                safe_notify("playwright.load", {
                    "url": page.url,
                    "title": None  # Will be fetched separately if needed
                })
            
            page.on("load", handle_load)
            
            # DOM content loaded - check for captcha
            async def check_for_captcha():
                """Check if the page contains a captcha challenge."""
                try:
                    # Wait a bit for page to settle
                    await asyncio.sleep(1)
                    
                    # Check for common captcha indicators
                    captcha_detected = await page.evaluate("""
                        () => {
                            // Check for reCAPTCHA
                            if (document.querySelector('iframe[src*="recaptcha"]') || 
                                document.querySelector('.g-recaptcha') ||
                                document.querySelector('[class*="recaptcha"]')) {
                                return {detected: true, type: 'recaptcha'};
                            }
                            
                            // Check for hCaptcha
                            if (document.querySelector('iframe[src*="hcaptcha"]') ||
                                document.querySelector('.h-captcha') ||
                                document.querySelector('[class*="hcaptcha"]')) {
                                return {detected: true, type: 'hcaptcha'};
                            }
                            
                            // Check for Cloudflare challenge
                            if (document.querySelector('#challenge-form') ||
                                document.querySelector('.cf-challenge') ||
                                document.title.includes('Just a moment') ||
                                document.body.textContent.includes('Checking your browser')) {
                                return {detected: true, type: 'cloudflare'};
                            }
                            
                            // Check for generic bot detection
                            const bodyText = document.body.textContent.toLowerCase();
                            if (bodyText.includes('verify you are human') ||
                                bodyText.includes('bot detection') ||
                                bodyText.includes('automated access') ||
                                bodyText.includes('robot test')) {
                                return {detected: true, type: 'generic'};
                            }
                            
                            return {detected: false};
                        }
                    """)
                    
                    if captcha_detected.get('detected'):
                        captcha_type = captcha_detected.get('type', 'unknown')
                        logger.warning(f"Captcha detected: {captcha_type} on {page.url}")
                        
                        # Take screenshot of the captcha
                        screenshot_bytes = await page.screenshot(full_page=True)
                        
                        # Get HTML content for context
                        html_content = await page.content()
                        
                        # Save captcha using session storage
                        from calico.utils.session_storage import SessionStorage
                        storage = SessionStorage(session_id=session_id)
                        captcha_info = storage.save_captcha(
                            screenshot_data=screenshot_bytes,
                            captcha_type=captcha_type,
                            url=page.url,
                            html_content=html_content
                        )
                        
                        # Notify handler
                        safe_notify("playwright.captcha_detected", {
                            "type": captcha_type,
                            "url": page.url,
                            "captcha_id": captcha_info['captcha_id'],
                            "api_url": captcha_info['api_url']
                        })
                        
                        logger.info(f"Captcha saved: {captcha_info['captcha_id']}")
                        
                except Exception as e:
                    logger.debug(f"Error checking for captcha: {e}")
            
            def handle_domcontentloaded():
                # Schedule async captcha check - ensure it's properly awaited by getting the event loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If event loop is running, create task
                        loop.create_task(check_for_captcha())
                    else:
                        # If no event loop running, schedule it
                        asyncio.ensure_future(check_for_captcha())
                except Exception as e:
                    logger.debug(f"Could not schedule captcha check: {e}")
                
                # Notify handler
                safe_notify("playwright.domcontentloaded", {
                    "url": page.url
                })
            
            page.on("domcontentloaded", handle_domcontentloaded)
        
        # Create executor with the page
        logger.debug("Creating executor...")
        executor = AIActionExecutor(
            page=page,
            timeout=30.0,
            max_action_retries=max_action_retries,
            session_id=session_id
        )
        
        # Define cleanup function
        async def cleanup():
            """Clean up browser resources."""
            logger.info(f"Cleaning up local Playwright executor for session {session_id}")
            
            # Close console log file
            try:
                console_log_file.close()
                logger.debug("Console log file closed")
            except Exception as e:
                logger.debug(f"Console log file close error: {e}")
            
            # Close page first
            try:
                if page and not page.is_closed():
                    await asyncio.wait_for(page.close(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.debug("Page close timed out")
            except Exception as e:
                logger.debug(f"Page close error (may already be closed): {e}")
            
            # Close context
            try:
                if context:
                    await asyncio.wait_for(context.close(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.debug("Context close timed out")
            except Exception as e:
                logger.debug(f"Context close error (may already be closed): {e}")
            
            # Close browser
            try:
                if browser:
                    await asyncio.wait_for(browser.close(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.debug("Browser close timed out")
            except Exception as e:
                logger.debug(f"Browser close error (may already be closed): {e}")
            
            # Stop playwright
            try:
                if playwright:
                    await asyncio.wait_for(playwright.stop(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.debug("Playwright stop timed out")
            except Exception as e:
                logger.debug(f"Playwright stop error (may already be stopped): {e}")
            
            logger.info("Cleanup completed")
        
        logger.info(f"✓ Local Playwright executor ready for session {session_id}")
        return executor, cleanup
        
    except Exception as e:
        logger.error(f"Failed to create local executor: {e}", exc_info=True)
        raise
