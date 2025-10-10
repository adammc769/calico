"""Are You Headless (arh.antoinevastel.com) test page configuration."""
from __future__ import annotations

from typing import Any, Dict

from . import StealthTestPage, register_stealth_page


async def extract_arh_data(page) -> Dict[str, Any]:
    """Extract Are You Headless detection results from the page.
    
    Args:
        page: Playwright page object
        
    Returns:
        Dictionary containing detection data
    """
    try:
        # Wait a bit for tests to complete
        await page.wait_for_timeout(3000)
        
        # Extract detection results
        data = await page.evaluate("""
            () => {
                const results = {};
                
                // Get all result elements
                const resultElements = document.querySelectorAll('.test-result');
                resultElements.forEach(element => {
                    const label = element.querySelector('.test-label')?.innerText || 'unknown';
                    const status = element.querySelector('.test-status')?.innerText || 'unknown';
                    const value = element.querySelector('.test-value')?.innerText || '';
                    
                    results[label] = {
                        'status': status,
                        'value': value
                    };
                });
                
                // If no structured results, get text content
                if (Object.keys(results).length === 0) {
                    const body = document.body.innerText;
                    results['page_content'] = body.substring(0, 500);
                }
                
                return results;
            }
        """)
        
        return data
    except Exception as e:
        return {
            "error": f"Failed to extract ARH data: {str(e)}"
        }


def validate_arh_results(data: Dict[str, Any]) -> bool:
    """Validate Are You Headless detection results.
    
    Args:
        data: ARH detection data
        
    Returns:
        True if not detected as headless, False otherwise
    """
    if "error" in data:
        print(f"⚠️  Extraction error: {data['error']}")
        return False
    
    # Check for headless indicators
    headless_detected = False
    
    for label, result in data.items():
        if isinstance(result, dict):
            status = result.get('status', '').lower()
            value = result.get('value', '').lower()
            
            # Look for positive headless indicators
            if 'headless' in status or 'headless' in value:
                if 'not' not in status and 'not' not in value:
                    headless_detected = True
                    print(f"   ❌ {label}: {result}")
            elif status in ['fail', 'failed', 'detected']:
                print(f"   ⚠️  {label}: {result}")
        elif isinstance(result, str):
            if 'headless' in result.lower():
                print(f"   ⚠️  Found 'headless' in content")
    
    if headless_detected:
        print("❌ Detected as headless browser")
        return False
    else:
        print("✅ Not detected as headless")
        return True


# Register the ARH test page
ARH_PAGE = register_stealth_page(StealthTestPage(
    name="arh",
    url="https://arh.antoinevastel.com/bots/areyouheadless",
    description="Are You Headless - Headless Browser Detection",
    validator=validate_arh_results,
    extractor=extract_arh_data,
    expected_keys=[],  # Dynamic keys based on tests
    timeout=15000,
    wait_for_selector="body"
))
