"""Stealth test pages configuration and validators."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Awaitable, Union


@dataclass
class StealthTestPage:
    """Configuration for a stealth test page."""
    
    name: str
    url: str
    description: str
    validator: Callable[[Dict[str, Any]], bool]
    extractor: Callable[[Any], Union[Dict[str, Any], Awaitable[Dict[str, Any]]]]  # Sync or async
    expected_keys: list[str]
    timeout: int = 30000
    wait_for_selector: Optional[str] = None
    wait_for_function: Optional[str] = None


# Registry of all stealth test pages
STEALTH_TEST_PAGES: Dict[str, StealthTestPage] = {}


def register_stealth_page(page: StealthTestPage) -> StealthTestPage:
    """Register a stealth test page."""
    STEALTH_TEST_PAGES[page.name] = page
    return page


def get_stealth_page(name: str) -> Optional[StealthTestPage]:
    """Get a stealth test page by name."""
    return STEALTH_TEST_PAGES.get(name)


def get_all_stealth_pages() -> list[StealthTestPage]:
    """Get all registered stealth test pages."""
    return list(STEALTH_TEST_PAGES.values())


# Import all test pages to register them
from .botd_page import BOTD_PAGE
from .sannysoft_page import SANNYSOFT_PAGE
from .arh_page import ARH_PAGE
from .fingerprint_page import FINGERPRINT_PAGE

__all__ = [
    'StealthTestPage',
    'register_stealth_page',
    'get_stealth_page',
    'get_all_stealth_pages',
    'BOTD_PAGE',
    'SANNYSOFT_PAGE',
    'ARH_PAGE',
    'FINGERPRINT_PAGE',
]
