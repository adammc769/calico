# Stealth Test Pages

This directory contains modular configurations for testing browser automation stealth capabilities against various bot detection services.

## Structure

Each test page is defined in its own module with three key components:

1. **Extractor function**: Extracts detection data from the page (async)
2. **Validator function**: Validates whether the test passed or failed
3. **Page configuration**: Registers the page with URL, timeouts, and selectors

## Available Test Pages

### BotD (FingerprintJS Bot Detection)
**Module**: `botd_page.py`  
**URL**: https://fingerprintjs.github.io/BotD/main/  
**Description**: FingerprintJS's comprehensive bot detection test

**Checks**:
- WebDriver property
- Chrome automation indicators
- Headless browser markers
- Plugin inconsistencies
- WebGL fingerprinting
- And many more detectors

**Expected Result Format**:
```json
{
  "bot": false,
  "botKind": null
}
```

Or full format:
```json
{
  "isError": false,
  "detectionResult": {"bot": false},
  "detectionTime": 12,
  "collectorsResults": {...}
}
```

### Sannysoft Bot Detection
**Module**: `sannysoft_page.py`  
**URL**: https://bot.sannysoft.com/  
**Description**: Comprehensive bot detection test with color-coded results

**Checks**:
- User Agent
- WebDriver
- Chrome properties
- Permissions
- Plugins
- Languages
- And more

**Results**: Color-coded table (green=pass, red=fail, yellow=warning)

### Are You Headless (ARH)
**Module**: `arh_page.py`  
**URL**: https://arh.antoinevastel.com/bots/areyouheadless  
**Description**: Specifically tests for headless browser indicators

**Checks**:
- Headless-specific properties
- Browser behavior differences
- Rendering inconsistencies

### FingerprintJS Local Bot Detection
**Module**: `fingerprint_page.py`  
**URL**: file:///.../local/bot_detection.html (local file)  
**Description**: Local FingerprintJS test page for comprehensive browser fingerprinting

**Checks**:
- Generates unique visitor ID based on browser fingerprinting
- Confidence score for identification
- Browser name and version
- Operating system
- Device type
- Screen resolution
- Timezone and language
- Platform information

**Features**:
- Uses the official FingerprintJS CDN library
- Real-time detection display
- Detailed component analysis
- Full JSON result output

**Expected Result Format**:
```json
{
  "visitorId": "abc123...",
  "status": "Detection Complete ✓",
  "details": {
    "Confidence Score": "99.5",
    "Browser Name": "Chrome",
    "OS": "Linux"
  },
  "fullResult": {
    "visitorId": "...",
    "confidence": {...},
    "components": {...}
  }
}
```

## Adding New Test Pages

To add a new test page, create a new module in this directory:

```python
"""Your test page description."""
from __future__ import annotations

from typing import Any, Dict
from . import StealthTestPage, register_stealth_page


async def extract_your_page_data(page) -> Dict[str, Any]:
    """Extract data from your test page.
    
    Args:
        page: Playwright page object
        
    Returns:
        Dictionary containing test data
    """
    try:
        # Wait for page to be ready
        await page.wait_for_selector(".results", timeout=10000)
        
        # Extract data using JavaScript
        data = await page.evaluate("""
            () => {
                // Your extraction logic
                return {
                    "passed": true,
                    "details": {...}
                };
            }
        """)
        
        return data
    except Exception as e:
        return {"error": str(e)}


def validate_your_page_results(data: Dict[str, Any]) -> bool:
    """Validate test results.
    
    Args:
        data: Extracted test data
        
    Returns:
        True if test passed, False otherwise
    """
    if "error" in data:
        print(f"⚠️  Error: {data['error']}")
        return False
    
    # Your validation logic
    if data.get("passed", False):
        print("✅ Test passed")
        return True
    else:
        print("❌ Test failed")
        return False


# Register the page
YOUR_PAGE = register_stealth_page(StealthTestPage(
    name="yourpage",
    url="https://example.com/bot-test",
    description="Your Test Page Description",
    validator=validate_your_page_results,
    extractor=extract_your_page_data,
    expected_keys=["passed", "details"],
    timeout=30000,
    wait_for_selector=".results"
))
```

## Configuration Options

### StealthTestPage Parameters

- `name` (str): Unique identifier for the page
- `url` (str): URL of the test page
- `description` (str): Human-readable description
- `validator` (callable): Function to validate results
- `extractor` (callable): Async function to extract data
- `expected_keys` (list): Expected keys in result data
- `timeout` (int): Navigation timeout in milliseconds (default: 30000)
- `wait_for_selector` (str, optional): CSS selector to wait for
- `wait_for_function` (str, optional): JavaScript function to wait for

## Usage

### Via Test Module

```python
from calico.tests.test_stealth import StealthTester
from calico.browser.automation import BrowserConfig

# Create tester with configuration
config = BrowserConfig(
    headless=True,
    stealth_mode=True,
    use_patchright=True,
    randomize_viewport=True,
    randomize_user_agent=True
)

tester = StealthTester(config)

# Test specific page
result = await tester.test_page("botd", save_screenshot=True)

# Test all pages
results = await tester.test_all_pages(save_screenshots=True)

# Print summary
tester.print_summary()
```

### Via Command Line

**Note**: Tests now use `.env` configuration by default. CLI options override .env settings.

```bash
# Test specific page (uses .env config)
python3 -m calico.tests.test_stealth --page botd

# Override to headed mode
python3 -m calico.tests.test_stealth --page botd --headed

# Test fingerprint (local) page
python3 -m calico.tests.test_stealth --page fingerprint

# Test all pages
python3 -m calico.tests.test_stealth

# Override to enable Patchright
python3 -m calico.tests.test_stealth --page botd --patchright

# Override to enable stealth mode
python3 -m calico.tests.test_stealth --page botd --stealth

# Without screenshots
python3 -m calico.tests.test_stealth --no-screenshots
```

### Environment Configuration

The tests read configuration from your `.env` file:

```bash
PLAYWRIGHT_BROWSER=chromium              # Browser: chromium | firefox | webkit
PLAYWRIGHT_HEADLESS=false                # Headless mode: true | false
PLAYWRIGHT_STEALTH_MODE=false            # Stealth features: true | false
PLAYWRIGHT_TIMEOUT=30000                 # Timeout in milliseconds
PLAYWRIGHT_USE_PATCHRIGHT=true           # Patchright fork: true | false
```

CLI arguments override these settings.

### Via Pytest

```bash
# Run all stealth tests
pytest calico/tests/test_stealth.py

# Run specific test
pytest calico/tests/test_stealth.py::test_botd_detection

# Run with Patchright
pytest calico/tests/test_stealth.py::test_patchright_stealth
```

## Extractor Best Practices

### Use Async/Await
All extractors must be async functions:
```python
async def extract_data(page):
    await page.wait_for_selector(".results")
    data = await page.evaluate("() => {...}")
    return data
```

### Handle Errors Gracefully
Always wrap in try/except:
```python
try:
    # Extraction logic
    return data
except Exception as e:
    return {"error": str(e)}
```

### Wait for Content
Give page time to load:
```python
await page.wait_for_load_state("networkidle")
await page.wait_for_selector(".results")
await page.wait_for_timeout(2000)  # Additional wait if needed
```

### Extract JSON When Possible
Look for JSON in various places:
```python
data = await page.evaluate("""
    () => {
        // Check <pre> or <code> tags
        const pre = document.querySelector('pre');
        if (pre) {
            try {
                return JSON.parse(pre.textContent);
            } catch(e) {}
        }
        
        // Check window object
        if (window.results) return window.results;
        
        // Manual extraction
        return {
            key: document.querySelector('.value').textContent
        };
    }
""")
```

## Validator Best Practices

### Be Informative
Print clear messages about what failed:
```python
if bot_detected:
    print(f"❌ Bot detected")
    print(f"   Reason: {reason}")
    print(f"   Details: {details}")
    return False
```

### Handle Multiple Formats
Support different result structures:
```python
# Simple format
if "bot" in data and "detectionResult" not in data:
    return not data["bot"]

# Complex format
if "detectionResult" in data:
    return not data["detectionResult"]["bot"]
```

### Calculate Statistics
Show pass rates and summaries:
```python
total = len(checks)
passed = sum(1 for c in checks if c["passed"])
print(f"✅ {passed}/{total} checks passed ({passed/total*100:.1f}%)")
```

## Testing Tips

### Use Patchright for Better Results
Patchright provides enhanced bot detection evasion:
```bash
python3 -m calico.tests.test_stealth --patchright
```

### Enable All Stealth Features
Maximize evasion capabilities:
```python
config = BrowserConfig(
    headless=True,
    use_patchright=True,
    stealth_mode=True,
    randomize_viewport=True,
    randomize_user_agent=True,
    human_like_delays=True
)
```

### Save Screenshots for Debugging
Screenshots help debug failures:
```python
result = await tester.test_page("botd", save_screenshot=True)
# Check: sessions/stealth_tests/botd_test.png
```

### Test in Headed Mode During Development
See what's happening:
```bash
python3 -m calico.tests.test_stealth --headed --page botd
```

## Common Issues

### TimeoutError
**Cause**: Page took too long to load or selector never appeared  
**Solution**: Increase timeout or adjust wait selector

### "Could not parse JSON"
**Cause**: Data format changed or not in expected location  
**Solution**: Check page source, update extractor

### "Bot detected"
**Cause**: Detection system identified automation  
**Solution**: Enable more stealth features, use Patchright, test in headed mode

### Async/Await Errors
**Cause**: Extractor not using async/await properly  
**Solution**: Ensure all extractors are async and await Playwright calls

## Result Interpretation

### Pass Rates

- **90-100%**: Excellent stealth
- **70-89%**: Good stealth, minor detection
- **50-69%**: Moderate stealth, some detection
- **<50%**: Poor stealth, significant detection

### What Detectors Check

- **webdriver**: navigator.webdriver property
- **chrome**: window.chrome object presence
- **plugins**: Plugin list consistency
- **permissions**: Permissions API behavior
- **webgl**: WebGL fingerprinting
- **user-agent**: User agent consistency
- **languages**: Language list format
- **headless**: Headless-specific markers

## Maintenance

### Updating Tests
Test pages may change over time. Update extractors when:
- Page structure changes
- Selectors change
- Data format changes

### Adding More Pages
Consider adding tests for:
- Cloudflare bot detection
- PerimeterX
- DataDome
- Custom detection systems

### Monitoring Results
Track test results over time to:
- Verify stealth improvements
- Catch regressions
- Compare configurations
