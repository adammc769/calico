"""FingerprintJS local bot detection test page configuration."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from . import StealthTestPage, register_stealth_page


async def extract_fingerprint_data(page) -> Dict[str, Any]:
    """Extract FingerprintJS detection results from the local page.
    
    Args:
        page: Playwright page object
        
    Returns:
        Dictionary containing FingerprintJS data
    """
    try:
        # Wait for page to load and detection to complete
        await page.wait_for_load_state("networkidle", timeout=15000)
        
        # Wait for the detection to complete (indicated by status change)
        await page.wait_for_selector("#visitor-id", timeout=15000)
        
        # Extract all the detection data from the page
        data = await page.evaluate("""
            () => {
                const result = {};
                
                // Get visitor ID
                const visitorIdEl = document.getElementById('visitor-id');
                if (visitorIdEl) {
                    result.visitorId = visitorIdEl.textContent.trim();
                }
                
                // Get status
                const statusEl = document.getElementById('status');
                if (statusEl) {
                    result.status = statusEl.textContent.trim();
                }
                
                // Parse the full result from the pre tag
                const fullResultEl = document.getElementById('full-result');
                if (fullResultEl) {
                    try {
                        result.fullResult = JSON.parse(fullResultEl.textContent);
                    } catch (e) {
                        result.fullResultError = "Failed to parse full result JSON";
                    }
                }
                
                // Get detail items
                const detailItems = document.querySelectorAll('.detail-item');
                const details = {};
                detailItems.forEach(item => {
                    const label = item.querySelector('.detail-label');
                    if (label) {
                        const key = label.textContent.replace(':', '').trim();
                        const value = item.textContent.replace(label.textContent, '').trim();
                        details[key] = value;
                    }
                });
                result.details = details;
                
                return result;
            }
        """)
        
        return data
        
    except Exception as e:
        return {
            "error": f"Failed to extract FingerprintJS data: {str(e)}"
        }


def validate_fingerprint_results(data: Dict[str, Any]) -> bool:
    """Validate FingerprintJS detection results.
    
    Args:
        data: FingerprintJS detection data
        
    Returns:
        True if detection completed successfully, False otherwise
    """
    if "error" in data:
        print(f"⚠️  Extraction error: {data['error']}")
        return False
    
    # Check if we got a visitor ID
    if not data.get("visitorId"):
        print("❌ No visitor ID found")
        return False
    
    # Check status
    status = data.get("status", "")
    if "Error" in status:
        print(f"❌ FingerprintJS reported error: {status}")
        return False
    
    if "Complete" not in status:
        print(f"⚠️  Detection may not be complete: {status}")
        return False
    
    print("✅ FingerprintJS detection completed successfully")
    print(f"   Visitor ID: {data.get('visitorId', 'N/A')[:20]}...")
    
    # Print key details
    if "details" in data:
        details = data["details"]
        confidence = details.get("Confidence Score", "N/A")
        browser = details.get("Browser Name", "N/A")
        os = details.get("OS", "N/A")
        
        print(f"   Confidence: {confidence}")
        print(f"   Browser: {browser}")
        print(f"   OS: {os}")
    
    # Check full result if available
    if "fullResult" in data:
        full_result = data["fullResult"]
        
        # Check for any bot-related indicators in components
        if "components" in full_result:
            components = full_result["components"]
            
            # These are good signs (we have real values)
            indicators = {
                "timezone": components.get("timezone", {}).get("value"),
                "language": components.get("language", {}).get("value"),
                "platform": components.get("platform", {}).get("value"),
                "screenResolution": components.get("screenResolution", {}).get("value"),
            }
            
            missing = [k for k, v in indicators.items() if not v]
            if missing:
                print(f"   ⚠️  Missing indicators: {', '.join(missing)}")
    
    return True


def get_local_file_url() -> str:
    """Get the file:// URL for the local bot detection page.
    
    Returns:
        file:// URL to the local HTML page
    """
    # Get the path to the local HTML file
    current_file = Path(__file__)
    html_file = current_file.parent / "local" / "bot_detection.html"
    
    # Convert to absolute path and file URL
    abs_path = html_file.resolve()
    file_url = abs_path.as_uri()
    
    return file_url


# Register the FingerprintJS local test page
FINGERPRINT_PAGE = register_stealth_page(StealthTestPage(
    name="fingerprint",
    url=get_local_file_url(),
    description="FingerprintJS Local Bot Detection Test",
    validator=validate_fingerprint_results,
    extractor=extract_fingerprint_data,
    expected_keys=[
        "visitorId",
        "status",
        "details",
        "fullResult"
    ],
    timeout=20000,
    wait_for_selector="#visitor-id"
))
