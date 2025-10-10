"""Modular stealth testing framework for browser automation.

This module provides a flexible testing framework for validating stealth
capabilities against various bot detection services.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from dotenv import load_dotenv

from calico.browser.automation import BrowserAutomation, BrowserConfig

# Load .env configuration
load_dotenv()

# Import all test pages to register them
from calico.tests.stealth_pages import get_all_stealth_pages, get_stealth_page
from calico.tests.stealth_pages.botd_page import BOTD_PAGE
from calico.tests.stealth_pages.sannysoft_page import SANNYSOFT_PAGE
from calico.tests.stealth_pages.arh_page import ARH_PAGE
from calico.tests.stealth_pages.fingerprint_page import FINGERPRINT_PAGE

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool = False) -> bool:
    """Convert environment variable to boolean flag."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_browser_config_from_env() -> BrowserConfig:
    """Create BrowserConfig from .env file settings.
    
    Returns:
        BrowserConfig configured from environment variables
    """
    return BrowserConfig(
        headless=_env_flag("PLAYWRIGHT_HEADLESS", default=True),
        browser_type=os.getenv("PLAYWRIGHT_BROWSER", "chromium"),
        stealth_mode=_env_flag("PLAYWRIGHT_STEALTH_MODE", default=True),
        use_patchright=_env_flag("PLAYWRIGHT_USE_PATCHRIGHT", default=True),
        timeout=int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000")),
        randomize_viewport=True,
        randomize_user_agent=True,
        human_like_delays=True,
    )


@dataclass
class StealthTestResult:
    """Result of a stealth test."""
    
    page_name: str
    url: str
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    screenshot_path: Optional[str] = None


class StealthTester:
    """Stealth testing orchestrator."""
    
    def __init__(self, config: Optional[BrowserConfig] = None):
        """Initialize stealth tester.
        
        Args:
            config: Browser configuration to test with. If None, loads from .env
        """
        if config is None:
            # Load configuration from .env file
            config = get_browser_config_from_env()
            logger.info("Loaded browser configuration from .env file")
        
        self.config = config
        self.results: List[StealthTestResult] = []
    
    async def test_page(
        self,
        page_name: str,
        save_screenshot: bool = False,
        screenshot_dir: Optional[Path] = None
    ) -> StealthTestResult:
        """Test a single stealth page.
        
        Args:
            page_name: Name of the page to test
            save_screenshot: Whether to save a screenshot
            screenshot_dir: Directory to save screenshots
            
        Returns:
            StealthTestResult with test outcome
        """
        test_page = get_stealth_page(page_name)
        if not test_page:
            return StealthTestResult(
                page_name=page_name,
                url="",
                success=False,
                data={},
                error=f"Test page '{page_name}' not found"
            )
        
        logger.info(f"Testing {test_page.name}: {test_page.url}")
        
        try:
            async with BrowserAutomation(self.config) as browser:
                session = await browser.create_session()
                page = session.page
                
                # Navigate to test page
                await page.goto(test_page.url, timeout=test_page.timeout)
                
                # Wait for specific selector if provided
                if test_page.wait_for_selector:
                    await page.wait_for_selector(
                        test_page.wait_for_selector,
                        timeout=test_page.timeout
                    )
                
                # Wait for custom function if provided
                if test_page.wait_for_function:
                    await page.wait_for_function(
                        test_page.wait_for_function,
                        timeout=test_page.timeout
                    )
                
                # Give page time to run all checks
                await page.wait_for_timeout(2000)
                
                # Extract data using page-specific extractor
                import inspect
                if inspect.iscoroutinefunction(test_page.extractor):
                    data = await test_page.extractor(page)
                else:
                    data = test_page.extractor(page)
                
                # Validate results
                success = test_page.validator(data)
                
                # Save screenshot if requested
                screenshot_path = None
                if save_screenshot:
                    if screenshot_dir is None:
                        screenshot_dir = Path("sessions/stealth_tests")
                    screenshot_dir.mkdir(parents=True, exist_ok=True)
                    
                    screenshot_path = str(screenshot_dir / f"{page_name}_test.png")
                    await page.screenshot(path=screenshot_path)

                await browser.close_session(session)
                
                result = StealthTestResult(
                    page_name=test_page.name,
                    url=test_page.url,
                    success=success,
                    data=data,
                    screenshot_path=screenshot_path
                )
                
                self.results.append(result)
                return result
                
        except Exception as e:
            logger.error(f"Error testing {page_name}: {e}", exc_info=True)
            result = StealthTestResult(
                page_name=test_page.name,
                url=test_page.url,
                success=False,
                data={},
                error=str(e)
            )
            self.results.append(result)
            return result
    
    async def test_all_pages(
        self,
        save_screenshots: bool = False,
        screenshot_dir: Optional[Path] = None
    ) -> List[StealthTestResult]:
        """Test all registered stealth pages.
        
        Args:
            save_screenshots: Whether to save screenshots
            screenshot_dir: Directory to save screenshots
            
        Returns:
            List of test results
        """
        pages = get_all_stealth_pages()
        results = []
        
        for page in pages:
            result = await self.test_page(
                page.name,
                save_screenshot=save_screenshots,
                screenshot_dir=screenshot_dir
            )
            results.append(result)
        
        return results
    
    def print_summary(self):
        """Print summary of all test results."""
        if not self.results:
            print("No test results available")
            return
        
        print("\n" + "="*80)
        print("STEALTH TEST SUMMARY")
        print("="*80)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        failed = total - passed
        
        print(f"\nTotal tests: {total}")
        print(f"Passed: {passed} ({passed/total*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total*100:.1f}%)")
        
        print("\nDetailed Results:")
        print("-"*80)
        
        for result in self.results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            print(f"\n{status} - {result.page_name}")
            print(f"   URL: {result.url}")
            
            if result.error:
                print(f"   Error: {result.error}")
            
            if result.screenshot_path:
                print(f"   Screenshot: {result.screenshot_path}")
        
        print("\n" + "="*80)
        
        return passed, failed


# Pytest fixtures and tests

@pytest.fixture
async def stealth_tester():
    """Create a stealth tester with default config."""
    return StealthTester()


@pytest.fixture
async def patchright_tester():
    """Create a stealth tester with Patchright enabled."""
    config = get_browser_config_from_env()
    # Ensure Patchright is enabled for this fixture
    config.use_patchright = True
    config.stealth_mode = True
    return StealthTester(config)


@pytest.mark.asyncio
async def test_botd_detection():
    """Test BotD bot detection."""
    tester = StealthTester()
    result = await tester.test_page("botd", save_screenshot=True)
    
    assert result.success, f"BotD detected bot: {result.data}"
    assert not result.data.get("detectionResult", {}).get("bot", True)


@pytest.mark.asyncio
async def test_sannysoft_detection():
    """Test Sannysoft bot detection."""
    tester = StealthTester()
    result = await tester.test_page("sannysoft", save_screenshot=True)
    
    assert result.success, f"Sannysoft detected bot: {result.data}"


@pytest.mark.asyncio
async def test_arh_headless_detection():
    """Test Are You Headless detection."""
    tester = StealthTester()
    result = await tester.test_page("arh", save_screenshot=True)
    
    assert result.success, f"ARH detected headless: {result.data}"


@pytest.mark.asyncio
async def test_fingerprint_detection():
    """Test FingerprintJS local bot detection."""
    tester = StealthTester()
    result = await tester.test_page("fingerprint", save_screenshot=True)
    
    assert result.success, f"FingerprintJS detection failed: {result.data}"
    assert result.data.get("visitorId"), "No visitor ID generated"


@pytest.mark.asyncio
async def test_all_stealth_pages():
    """Test all stealth pages with default config."""
    tester = StealthTester()
    results = await tester.test_all_pages(save_screenshots=True)
    
    tester.print_summary()
    
    # At least 70% should pass
    passed = sum(1 for r in results if r.success)
    pass_rate = (passed / len(results)) * 100
    
    assert pass_rate >= 70, f"Pass rate too low: {pass_rate:.1f}%"


@pytest.mark.asyncio
async def test_patchright_stealth():
    """Test stealth with Patchright enabled."""
    config = get_browser_config_from_env()
    # Ensure Patchright and stealth are enabled
    config.use_patchright = True
    config.stealth_mode = True
    
    tester = StealthTester(config)
    result = await tester.test_page("botd", save_screenshot=True)
    
    assert result.success, f"BotD detected bot with Patchright: {result.data}"


# Standalone execution
async def main():
    """Run stealth tests standalone."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run stealth tests")
    parser.add_argument(
        "--page",
        type=str,
        help="Test specific page (botd, sannysoft, arh, fingerprint, or 'all')"
    )
    parser.add_argument(
        "--patchright",
        action="store_true",
        help="Use Patchright instead of standard Playwright (overrides .env)"
    )
    parser.add_argument(
        "--no-screenshots",
        action="store_true",
        help="Don't save screenshots"
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run in headed mode (visible browser, overrides .env)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (overrides .env)"
    )
    parser.add_argument(
        "--stealth",
        action="store_true",
        help="Enable stealth mode (overrides .env)"
    )
    parser.add_argument(
        "--no-stealth",
        action="store_true",
        help="Disable stealth mode (overrides .env)"
    )
    args = parser.parse_args()
    
    # Start with .env configuration
    config = get_browser_config_from_env()
    
    # Apply CLI overrides
    if args.headed:
        config.headless = False
    elif args.headless:
        config.headless = True
    
    if args.stealth:
        config.stealth_mode = True
    elif args.no_stealth:
        config.stealth_mode = False
    
    if args.patchright:
        config.use_patchright = True
    
    print("\n" + "="*80)
    print("🕵️  STEALTH TESTING FRAMEWORK")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  Source: .env file (with CLI overrides)")
    print(f"  Headless: {config.headless}")
    print(f"  Browser: {config.browser_type}")
    print(f"  Patchright: {config.use_patchright}")
    print(f"  Stealth mode: {config.stealth_mode}")
    print(f"  Randomization: {config.randomize_viewport and config.randomize_user_agent}")
    print(f"  Timeout: {config.timeout}ms")
    
    tester = StealthTester(config)
    
    # Test specific page or all pages
    if args.page and args.page != "all":
        print(f"\n🎯 Testing page: {args.page}")
        result = await tester.test_page(
            args.page,
            save_screenshot=not args.no_screenshots
        )
        
        if result.success:
            print(f"\n✅ Test passed for {args.page}")
        else:
            print(f"\n❌ Test failed for {args.page}")
            if result.error:
                print(f"   Error: {result.error}")
    else:
        print("\n🎯 Testing all pages...")
        await tester.test_all_pages(save_screenshots=not args.no_screenshots)
    
    # Print summary
    tester.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
