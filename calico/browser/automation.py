"""Core browser automation classes using Playwright."""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright.sync_api import sync_playwright

from .config import (
    USER_AGENT_POOL,
    VIEWPORT_POOL,
    DEFAULT_VIEWPORT,
    get_chrome_args,
    get_font_injection_script,
    get_minimal_stealth_script,
    get_context_options as get_default_context_options,
)

logger = logging.getLogger(__name__)


@dataclass
class BrowserConfig:
    """Configuration for browser automation."""
    
    headless: bool = False
    browser_type: str = "chromium"  # chromium, firefox, webkit
    viewport: Optional[Dict[str, int]] = None
    user_agent: Optional[str] = None
    locale: Optional[str] = None
    timezone: Optional[str] = None
    geolocation: Optional[Dict[str, float]] = None
    permissions: List[str] = field(default_factory=list)
    slow_mo: int = 0  # Slow down operations by this many milliseconds
    timeout: int = 30000  # Default timeout in milliseconds
    
    # Anti-detection features
    stealth_mode: bool = False  # Enable stealth context options
    randomize_viewport: bool = False  # Randomize viewport from pool
    randomize_user_agent: bool = False  # Randomize UA from pool
    human_like_delays: bool = True  # Add realistic wait/interaction gaps
    extra_http_headers: Optional[Dict[str, str]] = None
    bypass_csp: bool = True  # Bypass Content Security Policy
    inject_cookies: Optional[Dict[str, Any]] = None  # Pre-inject cookies
    use_patchright: bool = True  # Use Patchright instead of standard Playwright
    
    # Persistent profile (reduces incognito detection)
    user_data_dir: Optional[str] = None  # Path to persistent profile directory
    # Setting this enables persistent storage, cookies, and extension state
    # which makes the browser look less like incognito mode
    
    # GPU/Hardware settings (reduces VM detection)
    enable_gpu: bool = True  # Enable GPU acceleration
    
    def __post_init__(self):
        if self.viewport is None:
            if self.randomize_viewport:
                self.viewport = random.choice(VIEWPORT_POOL)
            else:
                self.viewport = DEFAULT_VIEWPORT.copy()
        
        # Always set a platform-appropriate user agent if not specified
        if self.user_agent is None:
            if self.randomize_user_agent:
                self.user_agent = random.choice(USER_AGENT_POOL)
            else:
                # Use the first (latest) platform-appropriate UA
                self.user_agent = USER_AGENT_POOL[0]


@dataclass
class BrowserSession:
    """Represents an active browser session."""
    
    browser: Browser
    context: BrowserContext
    page: Page
    config: BrowserConfig
    
    async def close(self):
        """Close the browser session."""
        try:
            await self.page.close()
            await self.context.close()
            await self.browser.close()
        except Exception as e:
            logger.error(f"Error closing browser session: {e}")


class BrowserAutomation:
    """Main class for Playwright browser automation."""
    
    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self._playwright = None
        self._sessions: List[BrowserSession] = []
        
    async def __aenter__(self):
        """Async context manager entry."""
        # Use Patchright if configured, otherwise use standard Playwright
        if self.config.use_patchright:
            try:
                from patchright.async_api import async_playwright as patchright_async_playwright
                self._playwright = await patchright_async_playwright().start()
                logger.info("Using Patchright (patched Playwright) for enhanced bot detection evasion")
            except ImportError:
                logger.warning("Patchright not installed, falling back to standard Playwright. Install with: pip install patchright")
                self._playwright = await async_playwright().start()
        else:
            self._playwright = await async_playwright().start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_all_sessions()
        if self._playwright:
            await self._playwright.stop()
            
    async def create_session(self, config: Optional[BrowserConfig] = None) -> BrowserSession:
        """Create a new browser session."""
        if not self._playwright:
            raise RuntimeError("BrowserAutomation not started. Use async context manager.")
            
        session_config = config or self.config
        
        # Get browser type
        if session_config.browser_type == "chromium":
            browser_launcher = self._playwright.chromium
        elif session_config.browser_type == "firefox":
            browser_launcher = self._playwright.firefox
        elif session_config.browser_type == "webkit":
            browser_launcher = self._playwright.webkit
        else:
            raise ValueError(f"Unsupported browser type: {session_config.browser_type}")
            
        # Build launch arguments for stealth mode
        launch_args = get_chrome_args(
            stealth_mode=session_config.stealth_mode and session_config.browser_type == "chromium",
            headless=session_config.headless,
            enable_gpu=session_config.enable_gpu,
            extra_args=None
        ) if session_config.browser_type == "chromium" else []
        
        # Build launch options
        launch_options = {
            "headless": session_config.headless,
            "slow_mo": session_config.slow_mo,
        }
        
        # Add args for Chromium
        if launch_args:
            launch_options["args"] = launch_args
        
        # Add persistent profile if specified (reduces incognito detection)
        if session_config.user_data_dir:
            # Use launch_persistent_context for persistent profile
            logger.info(f"Using persistent profile at: {session_config.user_data_dir}")
            
            # Context options for persistent profile
            context_options = {
                "viewport": session_config.viewport,
                "user_agent": session_config.user_agent,  # Always set UA
                "locale": session_config.locale or "en-US",
                "timezone_id": session_config.timezone or "America/New_York",
                "bypass_csp": session_config.bypass_csp,
            }
            
            # Add stealth options for persistent profile
            if session_config.stealth_mode:
                context_options.update({
                    "color_scheme": "light",
                    "device_scale_factor": 1,
                    "has_touch": False,
                    "is_mobile": False,
                })
            
            if session_config.permissions:
                context_options["permissions"] = session_config.permissions
            if session_config.geolocation:
                context_options["geolocation"] = session_config.geolocation
            
            # Launch with persistent context
            context = await browser_launcher.launch_persistent_context(
                user_data_dir=session_config.user_data_dir,
                **launch_options,
                **context_options
            )
            
            # Add init scripts for persistent context
            await context.add_init_script(get_font_injection_script())
            if session_config.stealth_mode:
                await context.add_init_script(get_minimal_stealth_script())
            
            # Get the first page or create one
            pages = context.pages
            if pages:
                page = pages[0]
            else:
                page = await context.new_page()
            
            # Create a dummy browser object (context acts as both browser and context)
            session = BrowserSession(
                browser=context,  # type: ignore
                context=context,
                page=page,
                config=session_config
            )
            
        else:
            # Standard launch (non-persistent)
            browser = await browser_launcher.launch(**launch_options)
            
            # Create context with anti-detection options
            context_options = {
                "viewport": session_config.viewport,
                "user_agent": session_config.user_agent,  # Always set UA
            }
            
            if session_config.locale:
                context_options["locale"] = session_config.locale
            if session_config.timezone:
                context_options["timezone_id"] = session_config.timezone
            if session_config.geolocation:
                context_options["geolocation"] = session_config.geolocation
            if session_config.permissions:
                context_options["permissions"] = session_config.permissions
            if session_config.bypass_csp:
                context_options["bypass_csp"] = True
                
            # Add stealth context options
            if session_config.stealth_mode:
                context_options.update({
                    "locale": session_config.locale or "en-US",
                    "timezone_id": session_config.timezone or "America/New_York",
                    "color_scheme": "light",
                    "device_scale_factor": 1,
                    "has_touch": False,
                    "is_mobile": False,
                })
                
                # Use platform-appropriate headers from config.py
                if not session_config.extra_http_headers:
                    from .config import get_context_options
                    stealth_opts = get_context_options(
                        stealth_mode=True,
                        user_agent=session_config.user_agent
                    )
                    if "extra_http_headers" in stealth_opts:
                        context_options["extra_http_headers"] = stealth_opts["extra_http_headers"]
                else:
                    context_options["extra_http_headers"] = session_config.extra_http_headers
            
            # Create context
            context = await browser.new_context(**context_options)
            
            # Set default timeout
            context.set_default_timeout(session_config.timeout)
            
            # Force system fonts for text rendering (fixes Chromium font issues on Linux)
            await context.add_init_script(get_font_injection_script())
            
            # Add minimal stealth script to fix navigator properties
            if session_config.stealth_mode:
                await context.add_init_script(get_minimal_stealth_script())
            
            # Create page
            page = await context.new_page()
            
            # Inject cookies if provided
            if session_config.inject_cookies:
                await context.add_cookies(session_config.inject_cookies)
            
            session = BrowserSession(
                browser=browser,
                context=context,
                page=page,
                config=session_config
            )
        
        self._sessions.append(session)
        logger.info(f"Created new browser session with {session_config.browser_type} (stealth={session_config.stealth_mode}, persistent={session_config.user_data_dir is not None})")
        
        return session
    
    async def _inject_stealth_scripts(self, page: Page):
        """Inject anti-detection scripts into page."""
        stealth_script = """
        // Override navigator.webdriver
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Add chrome object if missing
        if (!window.chrome) {
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
        }
        
        // Override plugins and mimeTypes
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                {
                    0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                    description: "Portable Document Format",
                    filename: "internal-pdf-viewer",
                    length: 1,
                    name: "Chrome PDF Plugin"
                }
            ]
        });
        
        // Add realistic permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({state: Notification.permission}) :
                originalQuery(parameters)
        );
        """
        await page.add_init_script(stealth_script)
        
    async def close_session(self, session: BrowserSession):
        """Close a specific browser session."""
        await session.close()
        if session in self._sessions:
            self._sessions.remove(session)
            
    async def close_all_sessions(self):
        """Close all active browser sessions."""
        for session in self._sessions.copy():
            await self.close_session(session)
            
    def create_sync_session(self, config: Optional[BrowserConfig] = None):
        """Create a synchronous browser session for simple use cases."""
        return SyncBrowserSession(config or self.config)


class SyncBrowserSession:
    """Synchronous browser session for simple automation tasks."""
    
    def __init__(self, config: BrowserConfig):
        self.config = config
        self._playwright = None
        self._browser = None
        self._context = None 
        self._page = None
        
    def __enter__(self):
        """Sync context manager entry."""
        # Use Patchright if configured, otherwise use standard Playwright
        if self.config.use_patchright:
            try:
                from patchright.sync_api import sync_playwright as patchright_sync_playwright
                self._playwright = patchright_sync_playwright().start()
                logger.info("Using Patchright (patched Playwright) for enhanced bot detection evasion")
            except ImportError:
                logger.warning("Patchright not installed, falling back to standard Playwright. Install with: pip install patchright")
                self._playwright = sync_playwright().start()
        else:
            self._playwright = sync_playwright().start()
        
        # Get browser type
        if self.config.browser_type == "chromium":
            browser_launcher = self._playwright.chromium
        elif self.config.browser_type == "firefox":
            browser_launcher = self._playwright.firefox
        elif self.config.browser_type == "webkit":
            browser_launcher = self._playwright.webkit
        else:
            raise ValueError(f"Unsupported browser type: {self.config.browser_type}")
        
        # Build launch arguments for stealth mode
        launch_args = get_chrome_args(
            stealth_mode=self.config.stealth_mode and self.config.browser_type == "chromium",
            headless=self.config.headless,
            extra_args=None
        ) if self.config.stealth_mode and self.config.browser_type == "chromium" else []
            
        # Launch browser
        self._browser = browser_launcher.launch(
            headless=self.config.headless,
            slow_mo=self.config.slow_mo,
            args=launch_args if launch_args else None
        )
        
        # Create context
        context_options = {
            "viewport": self.config.viewport,
        }
        
        if self.config.user_agent:
            context_options["user_agent"] = self.config.user_agent
        if self.config.locale:
            context_options["locale"] = self.config.locale
        if self.config.timezone:
            context_options["timezone_id"] = self.config.timezone
        if self.config.geolocation:
            context_options["geolocation"] = self.config.geolocation
        if self.config.permissions:
            context_options["permissions"] = self.config.permissions
        if self.config.extra_http_headers:
            context_options["extra_http_headers"] = self.config.extra_http_headers
        if self.config.bypass_csp:
            context_options["bypass_csp"] = True
            
        # Add stealth context options
        if self.config.stealth_mode:
            context_options.update({
                "locale": self.config.locale or "en-US",
                "timezone_id": self.config.timezone or "America/New_York",
                "color_scheme": "light",
                "device_scale_factor": 1,
                "has_touch": False,
                "is_mobile": False,
            })
            if not self.config.extra_http_headers:
                context_options["extra_http_headers"] = {
                    "Accept-Language": "en-US,en;q=0.9",
                    "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                }
            
        self._context = self._browser.new_context(**context_options)
        
        # Set default timeout
        self._context.set_default_timeout(self.config.timeout)
        
        # Inject cookies if provided
        if self.config.inject_cookies:
            self._context.add_cookies(self.config.inject_cookies)
        
        # Force system fonts for text rendering (fixes Chromium font issues on Linux)
        self._context.add_init_script("""
            const style = document.createElement('style');
            style.textContent = `
                * { 
                    font-family: "Liberation Sans", "DejaVu Sans", "Noto Sans", Arial, sans-serif !important; 
                }
                code, pre, tt, kbd, samp {
                    font-family: "Liberation Mono", "DejaVu Sans Mono", "Noto Mono", "Courier New", monospace !important;
                }
            `;
            if (document.head) {
                document.head.appendChild(style);
            } else {
                document.addEventListener('DOMContentLoaded', () => {
                    document.head.appendChild(style);
                });
            }
        """)
        
        # Create page
        self._page = self._context.new_page()
        
        # Add stealth scripts if enabled
        if self.config.stealth_mode:
            self._inject_stealth_scripts_sync(self._page)
        
        logger.info(f"Created sync browser session with {self.config.browser_type} (stealth={self.config.stealth_mode})")
        return self
    
    def _inject_stealth_scripts_sync(self, page):
        """Inject anti-detection scripts into page (sync version)."""
        stealth_script = """
        // Override navigator.webdriver
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Add chrome object if missing
        if (!window.chrome) {
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
        }
        
        // Override plugins and mimeTypes
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                {
                    0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                    description: "Portable Document Format",
                    filename: "internal-pdf-viewer",
                    length: 1,
                    name: "Chrome PDF Plugin"
                }
            ]
        });
        
        // Add realistic permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({state: Notification.permission}) :
                originalQuery(parameters)
        );
        """
        page.add_init_script(stealth_script)
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit."""
        try:
            if self._page:
                self._page.close()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.error(f"Error closing sync browser session: {e}")
            
    @property
    def page(self):
        """Get the current page."""
        if not self._page:
            raise RuntimeError("Browser session not started")
        return self._page
        
    @property
    def context(self):
        """Get the browser context.""" 
        if not self._context:
            raise RuntimeError("Browser session not started")
        return self._context
        
    @property
    def browser(self):
        """Get the browser instance."""
        if not self._browser:
            raise RuntimeError("Browser session not started") 
        return self._browser