# FingerprintJS Bot Detection Page

This directory contains a local test page for bot detection using the FingerprintJS library. This page is integrated with the stealth testing framework.

## Files

- `bot_detection.html` - Main bot detection test page with FingerprintJS

## Usage

### Via Stealth Testing Framework (Recommended)

The page is integrated with the calico stealth testing framework:

```bash
# Test the fingerprint page
python3 -m calico.tests.test_stealth --page fingerprint --headed

# Run pytest test
pytest calico/tests/test_stealth.py::test_fingerprint_detection

# Test all stealth pages (including fingerprint)
python3 -m calico.tests.test_stealth
```

### Manual Browser Testing

You can also open the page directly in a browser for manual testing:

#### Method 1: Direct File Access
```bash
# Open in your default browser (Linux)
xdg-open calico/tests/stealth_pages/local/bot_detection.html

# Open in your default browser (macOS)
open calico/tests/stealth_pages/local/bot_detection.html

# Open in your default browser (Windows)
start calico\tests\stealth_pages\local\bot_detection.html
```

#### Method 2: Simple HTTP Server
```bash
# From repository root
python3 -m http.server 8000

# Then visit: http://localhost:8000/calico/tests/stealth_pages/local/bot_detection.html
```

## Features

The page uses FingerprintJS to:
- Generate a unique visitor ID based on browser fingerprinting
- Display comprehensive visitor information including:
  - Confidence score for identification
  - Browser name and version
  - Operating system details
  - Device type
  - Screen resolution
  - Timezone and language settings
  - Platform information
  - Full fingerprinting result in JSON format

## How It Works

The page uses the FingerprintJS CDN (`fpjscdn.net`) to load the library and generate a unique identifier for each visitor based on various browser and device characteristics. This can help:

1. **Detect bots and automated browsers** - Automated tools often have inconsistent or missing fingerprinting signals
2. **Identify unique visitors** - Even across incognito mode or after clearing cookies
3. **Test stealth capabilities** - Verify that your browser automation passes fingerprinting checks

### Integration with Test Framework

The `fingerprint_page.py` module provides:
- **Extractor function**: Extracts the visitor ID, status, and detailed results from the page
- **Validator function**: Checks if fingerprinting completed successfully and analyzes the results
- **Automatic registration**: Page is automatically available in the stealth testing framework

## API Key

**Note:** The API key used (`9wUc8GBl3kTD3yyxZHy6`) is a public demo key included in the script. For production use:
- Sign up at [FingerprintJS](https://fingerprint.com/)
- Get your own API key
- Replace it in the HTML file

## Testing Results

When tested via the stealth framework, the validator checks:
- ✅ Visitor ID was successfully generated
- ✅ Detection completed without errors
- ✅ All expected components are present (timezone, language, platform, etc.)
- ⚠️ Warnings for any missing fingerprinting indicators

## See Also

- [Stealth Pages README](../README.md) - Full documentation of the stealth testing framework
- [Test Stealth Module](../../test_stealth.py) - Main testing module
- [FingerprintJS Documentation](https://dev.fingerprint.com/) - Official FingerprintJS docs
