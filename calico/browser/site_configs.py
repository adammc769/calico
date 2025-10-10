"""Pre-configured site configurations for popular job sites."""
from __future__ import annotations

from calico.browser.actions import (
    NavigateAction, ClickAction, FillAction, WaitAction, 
    ScreenshotAction, TypeAction, SelectAction
)
from calico.browser.automation import BrowserConfig
from calico.browser.bundling import TaskSiteConfig


# Site-specific anti-detection configurations
SITE_DETECTION_CONFIGS = {
    "indeed": {
        "stealth_mode": True,
        "randomize_viewport": True,
        "randomize_user_agent": True,
        "human_like_delays": True,
        "extra_wait_ms": 2000,  # Extra wait after navigation
    },
    "linkedin": {
        "stealth_mode": True,
        "randomize_viewport": True,
        "randomize_user_agent": True,
        "human_like_delays": True,
        "bypass_csp": True,  # LinkedIn has strict CSP
        "extra_wait_ms": 3000,
    },
    "glassdoor": {
        "stealth_mode": True,
        "randomize_viewport": True,
        "randomize_user_agent": True,
        "human_like_delays": True,
        "extra_wait_ms": 2500,
    },
    "ziprecruiter": {
        "stealth_mode": True,
        "randomize_viewport": True,
        "randomize_user_agent": True,
        "human_like_delays": True,
        "extra_wait_ms": 1500,
    },
    "monster": {
        "stealth_mode": True,
        "randomize_viewport": True,
        "randomize_user_agent": True,
        "human_like_delays": True,
        "extra_wait_ms": 1500,
    },
    "walmart": {
        "stealth_mode": True,
        "randomize_viewport": True,
        "randomize_user_agent": True,
        "human_like_delays": True,
        "extra_wait_ms": 2000,  # Walmart has bot detection
        "selectors": {
            "search_input": 'input[name="q"], input[type="search"], #search-box-input',
            "product_items": '[data-item-id]',  # Individual products identified by data-item-id
            "product_links": 'a[link-identifier]',
            "add_to_cart": 'button[data-automation-id="add-to-cart"]',
        }
    },
    "amazon": {
        "stealth_mode": True,
        "randomize_viewport": True,
        "randomize_user_agent": True,
        "human_like_delays": True,
        "extra_wait_ms": 2500,  # Amazon has strong bot detection
    },
}


def apply_site_detection_config(site_name: str, browser_config: BrowserConfig) -> BrowserConfig:
    """Apply site-specific anti-detection configuration to a BrowserConfig.
    
    Args:
        site_name: Name of the site (lowercase)
        browser_config: Existing browser config to modify
        
    Returns:
        Modified browser config with site-specific settings applied
    """
    detection_config = SITE_DETECTION_CONFIGS.get(site_name.lower(), {})
    
    # Apply detection settings
    if detection_config.get("stealth_mode"):
        browser_config.stealth_mode = True
    if detection_config.get("randomize_viewport"):
        browser_config.randomize_viewport = True
    if detection_config.get("randomize_user_agent"):
        browser_config.randomize_user_agent = True
    if detection_config.get("human_like_delays"):
        browser_config.human_like_delays = True
    if detection_config.get("bypass_csp"):
        browser_config.bypass_csp = True
    
    return browser_config


def create_indeed_config() -> TaskSiteConfig:
    """Create configuration for Indeed job applications."""
    
    actions = [
        # Navigate to job search
        NavigateAction(url="https://indeed.com/jobs", wait_until="networkidle"),
        WaitAction(condition_type="selector", condition_value="#searchform"),
        
        # Search for jobs
        FillAction(selector="input[name='q']", text="software engineer"),
        FillAction(selector="input[name='l']", text="Remote"),
        ClickAction(selector="button[type='submit']"),
        
        # Wait for results and take screenshot
        WaitAction(condition_type="load_state", condition_value="networkidle"),
        ScreenshotAction(path="indeed_search_results.png"),
        
        # Click on first job (if available)
        WaitAction(condition_type="selector", condition_value="[data-testid='job-title']"),
        ClickAction(selector="[data-testid='job-title']:first-of-type"),
        
        # Take screenshot of job details
        WaitAction(condition_type="timeout", condition_value=2000),
        ScreenshotAction(path="indeed_job_details.png"),
    ]
    
    browser_config = BrowserConfig(
        headless=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        timeout=45000
    )
    browser_config = apply_site_detection_config("indeed", browser_config)
    
    return TaskSiteConfig(
        site_name="indeed",
        base_url="https://indeed.com",
        browser_config=browser_config,
        custom_actions=actions,
        retry_attempts=3,
        timeout_seconds=300
    )


def create_ziprecruiter_config() -> TaskSiteConfig:
    """Create configuration for ZipRecruiter job applications."""
    
    actions = [
        NavigateAction(url="https://www.ziprecruiter.com/jobs", wait_until="networkidle"),
        WaitAction(condition_type="selector", condition_value="#search-jobs-form"),
        
        # Search for jobs
        FillAction(selector="input[name='search']", text="python developer"),
        FillAction(selector="input[name='location']", text="San Francisco, CA"),
        ClickAction(selector="button[type='submit']"),
        
        # Wait for results
        WaitAction(condition_type="load_state", condition_value="networkidle"),
        ScreenshotAction(path="ziprecruiter_results.png"),
        
        # Click first job
        WaitAction(condition_type="selector", condition_value=".job_content"),
        ClickAction(selector=".job_content:first-of-type .job_link"),
        
        WaitAction(condition_type="timeout", condition_value=3000),
        ScreenshotAction(path="ziprecruiter_job_details.png"),
    ]
    
    browser_config = BrowserConfig(
        headless=True,
        viewport={"width": 1920, "height": 1080},
        timeout=40000
    )
    browser_config = apply_site_detection_config("ziprecruiter", browser_config)
    
    return TaskSiteConfig(
        site_name="ziprecruiter", 
        base_url="https://www.ziprecruiter.com",
        browser_config=browser_config,
        custom_actions=actions,
        retry_attempts=2
    )


def create_linkedin_config() -> TaskSiteConfig:
    """Create configuration for LinkedIn job applications."""
    
    actions = [
        NavigateAction(url="https://www.linkedin.com/jobs", wait_until="networkidle"),
        WaitAction(condition_type="selector", condition_value=".jobs-search-box"),
        
        # Search jobs
        FillAction(selector="input[aria-label*='Search jobs']", text="full stack developer"),
        FillAction(selector="input[aria-label*='Location']", text="New York, NY"),
        ClickAction(selector="button[aria-label='Search']"),
        
        # Wait and screenshot
        WaitAction(condition_type="load_state", condition_value="networkidle"),
        ScreenshotAction(path="linkedin_results.png"),
        
        # Click first job if available
        WaitAction(condition_type="selector", condition_value=".job-card-container"),
        ClickAction(selector=".job-card-container:first-of-type .job-card-list__title"),
        
        WaitAction(condition_type="timeout", condition_value=2000),
        ScreenshotAction(path="linkedin_job_details.png"),
    ]
    
    browser_config = BrowserConfig(
        headless=True,
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        timeout=50000
    )
    browser_config = apply_site_detection_config("linkedin", browser_config)
    
    return TaskSiteConfig(
        site_name="linkedin",
        base_url="https://www.linkedin.com",
        browser_config=browser_config,
        custom_actions=actions,
        retry_attempts=3
    )


def create_glassdoor_config() -> TaskSiteConfig:
    """Create configuration for Glassdoor job search."""
    
    actions = [
        NavigateAction(url="https://www.glassdoor.com/Job/jobs.htm", wait_until="networkidle"),
        WaitAction(condition_type="selector", condition_value="#searchBar-jobTitle"),
        
        # Job search
        FillAction(selector="#searchBar-jobTitle", text="data scientist"),
        FillAction(selector="#searchBar-location", text="Austin, TX"),
        ClickAction(selector="button[data-test='search-button']"),
        
        WaitAction(condition_type="load_state", condition_value="networkidle"),
        ScreenshotAction(path="glassdoor_results.png"),
        
        # Click first job
        WaitAction(condition_type="selector", condition_value="[data-test='job-title']"),
        ClickAction(selector="[data-test='job-title']:first-of-type"),
        
        WaitAction(condition_type="timeout", condition_value=2000),
        ScreenshotAction(path="glassdoor_job_details.png"),
    ]
    
    browser_config = BrowserConfig(
        headless=True,
        timeout=35000
    )
    browser_config = apply_site_detection_config("glassdoor", browser_config)
    
    return TaskSiteConfig(
        site_name="glassdoor",
        base_url="https://www.glassdoor.com",
        browser_config=browser_config,
        custom_actions=actions
    )


def create_monster_config() -> TaskSiteConfig:
    """Create configuration for Monster job search."""
    
    actions = [
        NavigateAction(url="https://www.monster.com/jobs", wait_until="networkidle"),
        WaitAction(condition_type="selector", condition_value="#searchQuery"),
        
        # Search
        FillAction(selector="#searchQuery", text="devops engineer"),
        FillAction(selector="#searchLocation", text="Seattle, WA"),
        ClickAction(selector="button[type='submit']"),
        
        WaitAction(condition_type="load_state", condition_value="networkidle"),
        ScreenshotAction(path="monster_results.png"),
        
        # Click first result
        WaitAction(condition_type="selector", condition_value=".job-title"),
        ClickAction(selector=".job-title:first-of-type a"),
        
        WaitAction(condition_type="timeout", condition_value=2000),
        ScreenshotAction(path="monster_job_details.png"),
    ]
    
    browser_config = BrowserConfig(headless=True)
    browser_config = apply_site_detection_config("monster", browser_config)
    
    return TaskSiteConfig(
        site_name="monster",
        base_url="https://www.monster.com",
        browser_config=browser_config,
        custom_actions=actions
    )


def get_all_job_site_configs() -> list[TaskSiteConfig]:
    """Get all pre-configured job site configurations."""
    
    return [
        create_indeed_config(),
        create_ziprecruiter_config(), 
        create_linkedin_config(),
        create_glassdoor_config(),
        create_monster_config(),
    ]


def register_all_job_sites(builder):
    """Register all job site configurations with a bundle builder."""
    
    configs = get_all_job_site_configs()
    
    for config in configs:
        builder.register_site_config(config)
        
    return [config.site_name for config in configs]