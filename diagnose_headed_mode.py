#!/usr/bin/env python3
"""Diagnostic script for headed mode issues."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def diagnose():
    """Run diagnostics for headed mode."""
    print("\n" + "="*80)
    print("🔍 HEADED MODE DIAGNOSTICS")
    print("="*80)
    
    # Check 1: Environment variables
    print("\n1️⃣  Checking environment variables...")
    display = os.environ.get('DISPLAY', 'not set')
    print(f"   DISPLAY: {display}")
    
    if display == 'not set' and sys.platform.startswith('linux'):
        print("   ⚠️  DISPLAY not set - may prevent GUI on Linux")
        print("   💡 Try: export DISPLAY=:0")
    else:
        print("   ✅ Display environment looks okay")
    
    # Check 2: Import and config
    print("\n2️⃣  Checking imports and configuration...")
    try:
        from calico.browser.automation import BrowserAutomation, BrowserConfig
        print("   ✅ Imports successful")
        
        config = BrowserConfig(headless=False, stealth_mode=True)
        print(f"   ✅ Config created: headless={config.headless}")
    except Exception as e:
        print(f"   ❌ Import/config failed: {e}")
        return
    
    # Check 3: Browser launch
    print("\n3️⃣  Testing browser launch (headed mode)...")
    print("   ⚠️  Browser window should appear for 5 seconds...")
    
    try:
        async with BrowserAutomation(config) as browser:
            session = await browser.create_session()
            print(f"   ✅ Browser launched (headless={session.config.headless})")
            
            await session.page.goto("data:text/html,<h1>Headed Mode Test</h1>")
            print("   ✅ Page loaded")
            
            print("   ⏱️  Keeping browser open for 5 seconds...")
            await asyncio.sleep(5)
            
            await browser.close_session(session)
            print("   ✅ Browser closed")
    except Exception as e:
        print(f"   ❌ Browser launch failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Check 4: Verify Playwright installation
    print("\n4️⃣  Checking Playwright installation...")
    try:
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "playwright", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"   ✅ Playwright version: {result.stdout.strip()}")
    except Exception as e:
        print(f"   ⚠️  Could not check Playwright version: {e}")
    
    print("\n" + "="*80)
    print("✅ DIAGNOSTICS COMPLETE")
    print("="*80)
    
    print("\n📝 Summary:")
    print("   If the browser window appeared, headed mode is working correctly.")
    print("   If no window appeared:")
    print("     - Check DISPLAY environment variable (Linux)")
    print("     - Verify you're not running in a headless environment (SSH, Docker)")
    print("     - Check X11 forwarding is enabled (if remote)")
    print("     - Try running without stealth_mode first")
    print("\n💡 Common issues:")
    print("   - Running over SSH without X11 forwarding")
    print("   - Running in Docker without display")
    print("   - Running in WSL without X server")
    print("   - Firewall blocking display connections")
    print()


if __name__ == "__main__":
    asyncio.run(diagnose())
