"""Playwright-powered browser automation for Calico."""

from .automation import (
    BrowserAutomation,
    BrowserConfig,
    BrowserSession,
)
from .actions import (
    ClickAction,
    FillAction,
    NavigateAction,
    ScreenshotAction,
    WaitAction,
)
from .bundling import (
    TaskBundle,
    BundledTask,
    TaskSiteConfig,
    TaskBundleExecutor,
    TaskBundleBuilder,
    TaskStatus,
    BundleStatus,
    get_bundle_executor,
    get_bundle_builder,
)
from .ai_bundling import (
    AIBundlingAgent,
    TaskIntent,
    get_ai_bundling_agent,
)
from .config import (
    USER_AGENT_POOL,
    VIEWPORT_POOL,
    DEFAULT_VIEWPORT,
    get_chrome_args,
    get_font_injection_script,
    get_minimal_stealth_script,
    get_context_options,
)

__all__ = [
    "BrowserAutomation",
    "BrowserConfig", 
    "BrowserSession",
    "ClickAction",
    "FillAction",
    "NavigateAction",
    "ScreenshotAction",
    "WaitAction",
    # Task bundling
    "TaskBundle",
    "BundledTask", 
    "TaskSiteConfig",
    "TaskBundleExecutor",
    "TaskBundleBuilder",
    "TaskStatus",
    "BundleStatus",
    "get_bundle_executor",
    "get_bundle_builder",
    # AI bundling
    "AIBundlingAgent",
    "TaskIntent",
    "get_ai_bundling_agent",
    # Browser configuration
    "USER_AGENT_POOL",
    "VIEWPORT_POOL",
    "DEFAULT_VIEWPORT",
    "get_chrome_args",
    "get_font_injection_script",
    "get_minimal_stealth_script",
    "get_context_options",
]