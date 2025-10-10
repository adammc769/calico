"""Centralized browser configuration and Chrome arguments."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Pool of realistic user agents for randomization
# IMPORTANT: Use platform-appropriate UAs to avoid osMismatch detection
# On Linux systems, use Linux UAs to match navigator.platform

# Linux user agents (use on Linux systems)
LINUX_USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]

# Windows user agents
WINDOWS_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]

# macOS user agents
MACOS_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# Auto-detect platform and use appropriate UAs
import platform as _platform
_system = _platform.system()
if _system == "Linux":
    USER_AGENT_POOL = LINUX_USER_AGENTS
elif _system == "Windows":
    USER_AGENT_POOL = WINDOWS_USER_AGENTS
elif _system == "Darwin":  # macOS
    USER_AGENT_POOL = MACOS_USER_AGENTS
else:
    USER_AGENT_POOL = LINUX_USER_AGENTS  # Default to Linux

# Common realistic viewport sizes (avoid tiny viewports that signal VMs)
VIEWPORT_POOL = [
    {"width": 1920, "height": 1080},  # Full HD - most common
    {"width": 1536, "height": 864},   # Laptop
    {"width": 1440, "height": 900},   # MacBook Pro
    {"width": 1366, "height": 768},   # Common laptop
    {"width": 2560, "height": 1440},  # 2K monitor
]

# Default viewport (use realistic size, not tiny)
DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}


@dataclass(frozen=True)
class ChromeArgs:
    """Immutable container for Chrome launch arguments."""
    
    # Base arguments (always included)
    BASE_ARGS: tuple[str, ...] = (
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--window-size=1920,1080',
    )
    
    # Memory optimization arguments (always included)
    MEMORY_ARGS: tuple[str, ...] = (
        '--js-flags=--max-old-space-size=4096',  # 4GB V8 heap
        '--max-old-space-size=4096',
    )
    
    # Stealth/Anti-detection arguments (conditional)
    STEALTH_ARGS: tuple[str, ...] = (
        '--disable-blink-features=AutomationControlled',
        '--disable-automation',
        '--disable-default-apps',
        '--disable-background-networking',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-breakpad',
        '--disable-client-side-phishing-detection',
        '--disable-component-extensions-with-background-pages',
        '--disable-hang-monitor',
        '--disable-ipc-flooding-protection',
        '--disable-popup-blocking',
        '--disable-prompt-on-repost',
        '--disable-sync',
        '--disable-renderer-backgrounding',
        '--disable-features=TranslateUI',
        '--metrics-recording-only',
        '--no-first-run',
        '--mute-audio',
        '--no-default-browser-check',
        '--no-pings',
        '--password-store=basic',
        '--use-mock-keychain',
    )
    
    # GPU/Hardware acceleration arguments (reduce VM detection)
    GPU_ARGS: tuple[str, ...] = (
        '--enable-features=VaapiVideoDecoder',  # Hardware video decoding
        '--use-gl=desktop',                      # Use desktop OpenGL
        '--enable-gpu-rasterization',            # GPU rasterization
        '--enable-zero-copy',                    # Zero-copy texture upload
    )
    
    # Codec/Media arguments (support H.264 and other codecs)
    MEDIA_ARGS: tuple[str, ...] = (
        '--enable-features=PlatformHEVCDecoderSupport',
        '--autoplay-policy=no-user-gesture-required',
    )
    
    # Headless mode argument
    HEADLESS_ARG: str = '--headless=new'
    
    def build_args(
        self,
        *,
        stealth_mode: bool = True,
        headless: bool = True,
        enable_gpu: bool = True,
        extra_args: Optional[List[str]] = None
    ) -> List[str]:
        """Build Chrome arguments list based on configuration.
        
        Args:
            stealth_mode: Include stealth/anti-detection arguments
            headless: Include headless mode argument
            enable_gpu: Enable GPU acceleration (reduces VM detection)
            extra_args: Additional custom arguments to append
            
        Returns:
            List of Chrome arguments
        """
        args = list(self.BASE_ARGS) + list(self.MEMORY_ARGS)
        
        if stealth_mode:
            args.extend(self.STEALTH_ARGS)
        
        # Add GPU and media args to reduce VM/codec detection
        if enable_gpu:
            args.extend(self.GPU_ARGS)
        args.extend(self.MEDIA_ARGS)
        
        if headless:
            args.append(self.HEADLESS_ARG)
        
        if extra_args:
            args.extend(extra_args)
        
        return args


# Global singleton instance
_chrome_args = ChromeArgs()


def get_chrome_args(
    *,
    stealth_mode: bool = True,
    headless: bool = True,
    enable_gpu: bool = True,
    extra_args: Optional[List[str]] = None
) -> List[str]:
    """Get Chrome launch arguments.
    
    This is the primary function to use for getting Chrome arguments throughout the codebase.
    
    Args:
        stealth_mode: Include stealth/anti-detection arguments (default: True)
        headless: Include headless mode argument (default: True)
        enable_gpu: Enable GPU acceleration to reduce VM detection (default: True)
        extra_args: Additional custom arguments to append
        
    Returns:
        List of Chrome arguments
        
    Example:
        >>> args = get_chrome_args(stealth_mode=True, headless=False)
        >>> # Returns base + memory + stealth + GPU args, but no headless
    """
    return _chrome_args.build_args(
        stealth_mode=stealth_mode,
        headless=headless,
        enable_gpu=enable_gpu,
        extra_args=extra_args
    )


# Font injection CSS (always active for consistent rendering)
FONT_INJECTION_SCRIPT = """
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
"""


def get_font_injection_script() -> str:
    """Get the font injection script for consistent text rendering.
    
    This script should be injected into every page to ensure consistent
    font rendering across different environments (especially Linux).
    
    Returns:
        JavaScript code as string
    """
    return FONT_INJECTION_SCRIPT


# Minimal stealth script (used when full stealth script file is unavailable)
MINIMAL_STEALTH_SCRIPT = """
    // Fix webdriver property
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    
    // Add chrome object
    window.chrome = { 
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };
    
    // Fix permissions
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
    
    // Ensure platform matches user agent
    // This is critical to avoid osMismatch detection
    Object.defineProperty(navigator, 'platform', {
        get: () => {
            const ua = navigator.userAgent;
            if (ua.includes('Win')) return 'Win32';
            if (ua.includes('Mac')) return 'MacIntel';
            if (ua.includes('Linux') && ua.includes('Android')) return 'Linux armv8l';
            if (ua.includes('Linux')) return 'Linux x86_64';
            return 'Linux x86_64';  // Default
        }
    });
"""


def get_minimal_stealth_script() -> str:
    """Get minimal stealth script as fallback.
    
    This is used when the full stealth_init.js file cannot be loaded.
    
    Returns:
        JavaScript code as string
    """
    return MINIMAL_STEALTH_SCRIPT


# Context options for standard browser configuration
def get_context_options(
    *,
    viewport: Optional[Dict[str, int]] = None,
    user_agent: Optional[str] = None,
    locale: str = "en-US",
    timezone_id: str = "America/New_York",
    stealth_mode: bool = True,
    extra_http_headers: Optional[Dict[str, str]] = None,
    **kwargs
) -> Dict:
    """Get browser context options with sensible defaults.
    
    IMPORTANT: Platform matching is critical to avoid osMismatch detection.
    The sec-ch-ua-platform header MUST match the actual platform and user agent.
    
    Args:
        viewport: Viewport size (default: 1920x1080)
        user_agent: User agent string (default: platform-appropriate Chrome)
        locale: Browser locale (default: en-US)
        timezone_id: Timezone (default: America/New_York)
        stealth_mode: Apply stealth-optimized settings (default: True)
        extra_http_headers: Custom HTTP headers
        **kwargs: Additional context options to include
        
    Returns:
        Dictionary of context options for browser.new_context()
    """
    if viewport is None:
        viewport = {"width": 1920, "height": 1080}
    
    if user_agent is None:
        user_agent = USER_AGENT_POOL[0]  # Use platform-appropriate UA
    
    options = {
        "viewport": viewport,
        "user_agent": user_agent,
        "locale": locale,
        "timezone_id": timezone_id,
    }
    
    if stealth_mode:
        options.update({
            "color_scheme": "light",
            "device_scale_factor": 1,
            "has_touch": False,
            "is_mobile": False,
        })
        
        # Auto-detect platform for sec-ch-ua-platform header
        # This MUST match the actual OS to avoid osMismatch detection
        if _system == "Linux":
            platform_header = '"Linux"'
        elif _system == "Windows":
            platform_header = '"Windows"'
        elif _system == "Darwin":
            platform_header = '"macOS"'
        else:
            platform_header = '"Linux"'
        
        if extra_http_headers is None:
            extra_http_headers = {
                "Accept-Language": "en-US,en;q=0.9",
                "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": platform_header,  # Match actual OS
            }
    
    if extra_http_headers:
        options["extra_http_headers"] = extra_http_headers
    
    # Merge any additional kwargs
    options.update(kwargs)
    
    return options


__all__ = [
    "USER_AGENT_POOL",
    "VIEWPORT_POOL",
    "DEFAULT_VIEWPORT",
    "ChromeArgs",
    "get_chrome_args",
    "get_font_injection_script",
    "get_minimal_stealth_script",
    "get_context_options",
]
