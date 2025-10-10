"""Site-specific patterns for enhanced DOM element detection.

This module contains patterns for identifying key elements on major e-commerce
and other websites that may not be easily detected through generic selectors.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# Walmart-specific patterns
WALMART_PATTERNS = {
    "product_items": [
        "[data-item-id]",  # Main product item identifier
        "[data-product-id]",  # Alternative product identifier
        "div[role='group'][data-item-id]",  # Product groups
        "a[link-identifier]",  # Product links
    ],
    "reviews": [
        "div[data-testid='enhanced-review-content']",  # Review content
        "div[class*='overflow-visible'][class*='b--none']",  # Review containers
        "section[data-dca-id][data-dca-type='module']",  # Review sections
    ],
    "review_button": [
        "button[data-dca-intent='viewAllReviews']",  # View all reviews button
        "button[data-testid='review-text-more-button']",  # View more review text
    ],
    "price": [
        "div[data-automation-id='product-price']",
        "span[class*='price']",
    ],
    "add_to_cart": [
        "button[data-automation-id='add-to-cart']",
        "button[data-dca-intent='cartAddition']",
    ],
    "search_input": [
        "input[data-automation-id='search-input']",
        "input[type='search']",
    ],
}

# Amazon-specific patterns
AMAZON_PATTERNS = {
    "product_items": [
        "[data-asin]",
        "div[data-component-type='s-search-result']",
    ],
    "reviews": [
        "div[data-hook='review']",
        "div[id*='customer_review']",
    ],
    "price": [
        "span[class='a-price']",
        "span[data-a-color='price']",
    ],
}

# eBay-specific patterns
EBAY_PATTERNS = {
    "product_items": [
        "li[data-view='mi:']",
        "div[class*='s-item']",
    ],
}

# Site pattern registry
SITE_PATTERNS: Dict[str, Dict[str, List[str]]] = {
    "walmart.com": WALMART_PATTERNS,
    "amazon.com": AMAZON_PATTERNS,
    "ebay.com": EBAY_PATTERNS,
}


def get_patterns_for_url(url: str) -> Dict[str, List[str]]:
    """Get site-specific patterns based on URL.
    
    Args:
        url: The current page URL
        
    Returns:
        Dictionary of pattern types to selectors, or empty dict if no patterns
    """
    url_lower = url.lower()
    for domain, patterns in SITE_PATTERNS.items():
        if domain in url_lower:
            return patterns
    return {}


def get_product_selectors_for_url(url: str) -> List[str]:
    """Get product item selectors for the current URL.
    
    Args:
        url: The current page URL
        
    Returns:
        List of CSS selectors for product items
    """
    patterns = get_patterns_for_url(url)
    return patterns.get("product_items", [])


def get_review_selectors_for_url(url: str) -> List[str]:
    """Get review element selectors for the current URL.
    
    Args:
        url: The current page URL
        
    Returns:
        List of CSS selectors for review elements
    """
    patterns = get_patterns_for_url(url)
    return patterns.get("reviews", [])
