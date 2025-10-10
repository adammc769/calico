#!/usr/bin/env python3
"""
Examples of using anti-bot detection features in Calico.

Run any example with: python3 examples/anti_bot_examples.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def example_basic_stealth():
    """Basic stealth configuration example."""
    print("\n" + "="*60)
    print("Example 1: Basic Stealth Configuration")
    print("="*60)
    
    from calico.browser.automation import BrowserAutomation, BrowserConfig
    
    config = BrowserConfig(
        headless=True,
        stealth_mode=True,           # Enable anti-detection
        randomize_viewport=True,      # Random viewport size
        randomize_user_agent=True,    # Random user agent
    )
    
    async with BrowserAutomation(config) as browser:
        session = await browser.create_session()
        
        print(f"✓ Browser session created")
        print(f"  Viewport: {session.config.viewport}")
        print(f"  User Agent: {session.config.user_agent[:60]}...")
        
        # Navigate to test page
        await session.page.goto("https://example.com", wait_until="networkidle")
        
        # Check detection
        result = await session.page.evaluate("""
            () => ({
                webdriver: navigator.webdriver,
                chrome: typeof window.chrome !== 'undefined',
                plugins: navigator.plugins.length
            })
        """)
        
        print(f"✓ Detection check:")
        print(f"  navigator.webdriver: {result['webdriver']}")
        print(f"  Chrome object: {result['chrome']}")
        print(f"  Plugins: {result['plugins']}")
        
        await browser.close_session(session)


async def example_human_like_workflow():
    """Example with human-like delays in workflow."""
    print("\n" + "="*60)
    print("Example 2: Human-Like Delays in Workflow")
    print("="*60)
    
    from calico.browser.automation import BrowserAutomation, BrowserConfig
    from calico.browser.workflow import BrowserWorkflowExecutor
    from calico.browser.actions import NavigateAction, WaitAction, EvaluateAction
    
    config = BrowserConfig(
        headless=True,
        stealth_mode=True,
        human_like_delays=True  # Enable human-like delays
    )
    
    async with BrowserAutomation(config) as browser:
        session = await browser.create_session()
        
        # Create workflow with multiple actions
        actions = [
            NavigateAction(url="https://example.com", wait_until="networkidle"),
            WaitAction(condition_type="timeout", condition_value=500),
            EvaluateAction(expression="document.title"),
            WaitAction(condition_type="timeout", condition_value=300),
        ]
        
        executor = BrowserWorkflowExecutor(human_like_delays=True)
        executor.register_session("demo", session)
        
        print("✓ Executing workflow with human-like delays...")
        import time
        start = time.time()
        
        result = await executor.execute_workflow(actions, session_id="demo")
        
        elapsed = time.time() - start
        print(f"✓ Workflow completed in {elapsed:.2f}s")
        print(f"  (includes realistic delays between actions)")
        print(f"  Success: {result.success}")
        
        await browser.close_session(session)


async def example_site_specific_config():
    """Example using site-specific configuration."""
    print("\n" + "="*60)
    print("Example 3: Site-Specific Configuration")
    print("="*60)
    
    from calico.browser.automation import BrowserAutomation, BrowserConfig
    from calico.browser.site_configs import apply_site_detection_config
    
    # Create base config
    config = BrowserConfig(headless=True)
    
    # Apply LinkedIn-specific detection bypass
    config = apply_site_detection_config("linkedin", config)
    
    print("✓ LinkedIn-specific config applied:")
    print(f"  Stealth mode: {config.stealth_mode}")
    print(f"  Randomize viewport: {config.randomize_viewport}")
    print(f"  Randomize UA: {config.randomize_user_agent}")
    print(f"  Human-like delays: {config.human_like_delays}")
    print(f"  Bypass CSP: {config.bypass_csp}")
    
    async with BrowserAutomation(config) as browser:
        session = await browser.create_session()
        print(f"✓ Session created with optimized settings for LinkedIn")
        await browser.close_session(session)


async def example_headed_mode():
    """Example using headed (visible) mode."""
    print("\n" + "="*60)
    print("Example 4: Headed Mode (Visible Browser)")
    print("="*60)
    print("Note: This will open a visible browser window")
    print("      Comment out this example if you don't want that")
    print("="*60)
    
    from calico.browser.automation import BrowserAutomation, BrowserConfig
    
    config = BrowserConfig(
        headless=False,        # Show browser window
        stealth_mode=True,     # Still apply anti-detection
        slow_mo=1000,          # Slow down for visibility (1 second)
    )
    
    async with BrowserAutomation(config) as browser:
        session = await browser.create_session()
        
        print("✓ Visible browser opened")
        print("  Watch the browser window...")
        
        await session.page.goto("https://example.com")
        print("  Navigated to example.com")
        
        await asyncio.sleep(3)  # Let you see it
        
        title = await session.page.title()
        print(f"  Page title: {title}")
        
        await browser.close_session(session)
        print("✓ Browser closed")


async def example_advanced_stealth():
    """Advanced stealth with all features."""
    print("\n" + "="*60)
    print("Example 5: Maximum Stealth Configuration")
    print("="*60)
    
    from calico.browser.automation import BrowserAutomation, BrowserConfig
    
    config = BrowserConfig(
        headless=True,
        stealth_mode=True,
        randomize_viewport=True,
        randomize_user_agent=True,
        human_like_delays=True,
        bypass_csp=True,
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
        timeout=60000,
    )
    
    print("✓ Maximum stealth configuration created:")
    print("  - Stealth mode enabled")
    print("  - Randomized viewport and user agent")
    print("  - Human-like delays between actions")
    print("  - CSP bypass enabled")
    print("  - Custom HTTP headers")
    print("  - Extended timeout (60s)")
    
    async with BrowserAutomation(config) as browser:
        session = await browser.create_session()
        
        print(f"✓ Session created with all anti-detection features")
        
        # Test on example.com
        await session.page.goto("https://example.com", wait_until="networkidle")
        
        # Comprehensive detection check
        detection = await session.page.evaluate("""
            () => ({
                webdriver: navigator.webdriver,
                platform: navigator.platform,
                vendor: navigator.vendor,
                chrome: typeof window.chrome !== 'undefined',
                plugins: navigator.plugins.length,
                languages: navigator.languages,
                hardwareConcurrency: navigator.hardwareConcurrency,
            })
        """)
        
        print("✓ Comprehensive detection check:")
        for key, value in detection.items():
            print(f"  {key}: {value}")
        
        await browser.close_session(session)


async def example_using_site_presets():
    """Example using pre-configured site settings."""
    print("\n" + "="*60)
    print("Example 6: Using Site Presets")
    print("="*60)
    
    from calico.browser.site_configs import (
        create_indeed_config,
        SITE_DETECTION_CONFIGS
    )
    
    print("Available site configurations:")
    for site_name in SITE_DETECTION_CONFIGS.keys():
        print(f"  - {site_name}")
    
    print("\n✓ Creating Indeed configuration...")
    indeed_config = create_indeed_config()
    
    print("  Site name:", indeed_config.site_name)
    print("  Base URL:", indeed_config.base_url)
    print("  Stealth mode:", indeed_config.browser_config.stealth_mode)
    print("  Randomize UA:", indeed_config.browser_config.randomize_user_agent)
    print("  Human delays:", indeed_config.browser_config.human_like_delays)
    print("  Actions defined:", len(indeed_config.custom_actions))
    print("\n✓ This config is ready to use for Indeed automation")


async def example_patchright_integration():
    """Example using Patchright for enhanced bot detection evasion."""
    print("\n" + "="*60)
    print("Example 7: Patchright Integration (Enhanced Evasion)")
    print("="*60)
    
    from calico.browser.automation import BrowserAutomation, BrowserConfig
    
    config = BrowserConfig(
        headless=True,
        use_patchright=True,  # Use patched Playwright
        stealth_mode=True,
        randomize_viewport=True,
        randomize_user_agent=True,
        human_like_delays=True
    )
    
    print("✓ Using Patchright (patched Playwright)")
    print("  - Enhanced bot detection evasion")
    print("  - Additional anti-fingerprinting measures")
    print("  - Works with all existing stealth features")
    
    async with BrowserAutomation(config) as browser:
        session = await browser.create_session()
        
        print(f"✓ Patchright session created")
        
        await session.page.goto("https://example.com", wait_until="networkidle")
        
        # Detection check
        result = await session.page.evaluate("""
            () => ({
                webdriver: navigator.webdriver,
                chrome: typeof window.chrome !== 'undefined',
                plugins: navigator.plugins.length
            })
        """)
        
        print(f"✓ Detection properties:")
        print(f"  navigator.webdriver: {result['webdriver']}")
        print(f"  chrome object: {result['chrome']}")
        print(f"  plugins: {result['plugins']}")
        
        await browser.close_session(session)
    
    print("✓ Patchright provides enhanced evasion over standard Playwright")


async def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("🛡️  Calico Anti-Bot Detection Examples")
    print("="*60)
    
    try:
        # Run examples
        await example_basic_stealth()
        await example_human_like_workflow()
        await example_site_specific_config()
        
        # Commented out by default - uncomment to see visible browser
        # await example_headed_mode()
        
        await example_advanced_stealth()
        await example_using_site_presets()
        await example_patchright_integration()
        
        print("\n" + "="*60)
        print("✅ All examples completed successfully!")
        print("="*60)
        print("\nNext steps:")
        print("  - Read ANTI_BOT_IMPROVEMENTS.md for full documentation")
        print("  - Check ANTI_BOT_QUICK_REFERENCE.md for quick tips")
        print("  - Run test_anti_bot_improvements.py for comprehensive tests")
        print("  - Run test_patchright_integration.py for Patchright tests")
        print()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Examples interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
