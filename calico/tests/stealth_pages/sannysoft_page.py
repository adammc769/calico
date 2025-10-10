"""Sannysoft bot detection test page configuration."""
from __future__ import annotations

from typing import Any, Dict

from . import StealthTestPage, register_stealth_page


async def extract_sannysoft_data(page) -> Dict[str, Any]:
    """Extract Sannysoft detection results from the page.
    
    Args:
        page: Playwright page object
        
    Returns:
        Dictionary containing detection data
    """
    try:
        # Extract various detection markers from the page
        data = await page.evaluate("""
            () => {
                const results = {};
                
                // Get all table rows
                const rows = document.querySelectorAll('tr');
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 2) {
                        const label = cells[0].innerText.trim();
                        const value = cells[1].innerText.trim();
                        const style = cells[1].style.backgroundColor;
                        
                        // Classify result based on background color
                        let status = 'unknown';
                        if (style.includes('rgb(255, 0, 0)') || style.includes('red')) {
                            status = 'failed';  // Red = bot detected
                        } else if (style.includes('rgb(0, 128, 0)') || style.includes('green')) {
                            status = 'passed';  // Green = looks human
                        } else if (style.includes('rgb(255, 255, 0)') || style.includes('yellow')) {
                            status = 'warning';  // Yellow = suspicious
                        }
                        
                        results[label] = {
                            'value': value,
                            'status': status
                        };
                    }
                });
                
                return results;
            }
        """)
        
        return data
    except Exception as e:
        return {
            "error": f"Failed to extract Sannysoft data: {str(e)}"
        }


def validate_sannysoft_results(data: Dict[str, Any]) -> bool:
    """Validate Sannysoft detection results.
    
    Args:
        data: Sannysoft detection data
        
    Returns:
        True if most checks passed, False otherwise
    """
    if "error" in data:
        print(f"⚠️  Extraction error: {data['error']}")
        return False
    
    # Count results
    total = 0
    passed = 0
    failed = 0
    warnings = 0
    
    for label, result in data.items():
        if isinstance(result, dict) and 'status' in result:
            total += 1
            status = result['status']
            
            if status == 'passed':
                passed += 1
            elif status == 'failed':
                failed += 1
                print(f"   ❌ {label}: {result['value']}")
            elif status == 'warning':
                warnings += 1
                print(f"   ⚠️  {label}: {result['value']}")
    
    if total == 0:
        print("❌ No detection checks found")
        return False
    
    # Calculate pass rate
    pass_rate = (passed / total) * 100
    
    print(f"✅ Sannysoft results: {passed}/{total} passed ({pass_rate:.1f}%)")
    print(f"   Warnings: {warnings}, Failed: {failed}")
    
    # Consider it a pass if at least 70% checks passed and no critical failures
    return pass_rate >= 70 and failed <= 2


# Register the Sannysoft test page
SANNYSOFT_PAGE = register_stealth_page(StealthTestPage(
    name="sannysoft",
    url="https://bot.sannysoft.com/",
    description="Sannysoft Bot Detection Test",
    validator=validate_sannysoft_results,
    extractor=extract_sannysoft_data,
    expected_keys=[],  # Dynamic keys based on detection tests
    timeout=20000,
    wait_for_selector="table"
))
