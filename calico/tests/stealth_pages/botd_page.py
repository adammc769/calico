"""BotD (Bot Detection) test page configuration."""
from __future__ import annotations

import json
import re
from typing import Any, Dict

from . import StealthTestPage, register_stealth_page


async def extract_botd_data(page) -> Dict[str, Any]:
    """Extract BotD detection results from the page.
    
    Args:
        page: Playwright page object
        
    Returns:
        Dictionary containing BotD detection data
    """
    try:
        # Wait for page to load
        await page.wait_for_load_state("networkidle", timeout=10000)
        
        # Click the "Detect" button if present
        try:
            detect_button = page.locator('button:has-text("Detect")')
            if await detect_button.count() > 0:
                await detect_button.click()
                # Wait for detection to complete
                await page.wait_for_timeout(5000)
        except:
            # Button might not be present or already clicked
            pass
        
        # Extract JSON data from <pre> or <code> tags
        data = await page.evaluate("""
            () => {
                // Look for JSON in pre/code tags
                const pres = Array.from(document.querySelectorAll('pre, code'));
                for (const el of pres) {
                    try {
                        const parsed = JSON.parse(el.textContent);
                        // Check if it looks like BotD results
                        if (parsed && (parsed.bot !== undefined || parsed.detectionResult)) {
                            return parsed;
                        }
                    } catch(e) {
                        continue;
                    }
                }
                
                // Try window object
                if (window.botdResult) return window.botdResult;
                if (window.detectionResult) return window.detectionResult;
                
                return null;
            }
        """)
        
        if data:
            return data
        
        return {
            "error": "No BotD results found on page"
        }
        
    except Exception as e:
        return {
            "error": f"Failed to extract BotD data: {str(e)}"
        }


def validate_botd_results(data: Dict[str, Any]) -> bool:
    """Validate BotD detection results.
    
    Args:
        data: BotD detection data
        
    Returns:
        True if bot was not detected, False otherwise
    """
    if "error" in data:
        print(f"⚠️  Extraction error: {data['error']}")
        return False
    
    # Handle simple format: {"bot": false/true, "botKind": "..."}
    if "bot" in data and "detectionResult" not in data:
        bot_detected = data.get("bot", True)
        bot_kind = data.get("botKind", "unknown")
        
        if bot_detected:
            print(f"❌ Bot detected by BotD")
            print(f"   Bot kind: {bot_kind}")
            return False
        else:
            print("✅ BotD did not detect bot")
            return True
    
    # Handle full format with detectionResult
    if "detectionResult" not in data:
        print(f"❌ Missing detectionResult key")
        print(f"   Available keys: {list(data.keys())}")
        return False
    
    # Check if there were errors
    if data.get("isError", True):
        print("❌ BotD reported an error during detection")
        return False
    
    # Check detection result
    detection_result = data.get("detectionResult", {})
    bot_detected = detection_result.get("bot", True)
    
    if bot_detected:
        print("❌ Bot was detected by BotD")
        return False
    
    # Print summary
    print("✅ BotD did not detect bot")
    print(f"   Collection time: {data.get('collectionTime', 'N/A')}ms")
    print(f"   Detection time: {data.get('detectionTime', 'N/A')}ms")
    
    # Print detector results summary
    if "detectorsResults" in data:
        detectors = data["detectorsResults"]
        total_detectors = len(detectors)
        failed_detectors = [name for name, result in detectors.items() if result.get("bot", False)]
        
        print(f"   Detectors passed: {total_detectors - len(failed_detectors)}/{total_detectors}")
        
        if failed_detectors:
            print(f"   ⚠️  Failed detectors: {', '.join(failed_detectors)}")
    
    return True


# Register the BotD test page
BOTD_PAGE = register_stealth_page(StealthTestPage(
    name="botd",
    url="https://fingerprintjs.github.io/BotD/main/",
    description="FingerprintJS BotD - Bot Detection Test",
    validator=validate_botd_results,
    extractor=extract_botd_data,
    expected_keys=[
        "isError",
        "collectionTime",
        "detectionTime",
        "detectionResult",
        "collectedData",
        "detectorsResults"
    ],
    timeout=30000,
    wait_for_selector=".logs-content",
    wait_for_function=None  # Disable wait_for_function, rely on selector and timeout
))
