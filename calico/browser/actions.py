"""Browser action classes for Calico automation."""
from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

from playwright.async_api import Page

logger = logging.getLogger(__name__)


def get_human_delay(min_ms: int = 50, max_ms: int = 200) -> int:
    """Get a random human-like delay in milliseconds."""
    return random.randint(min_ms, max_ms)


class BrowserAction(ABC):
    """Base class for browser actions."""
    
    @abstractmethod
    async def execute(self, page: Page) -> Any:
        """Execute the action on the given page."""
        pass
        
    @abstractmethod
    def describe(self) -> str:
        """Return a human-readable description of the action."""
        pass
    
    async def add_human_delay(self):
        """Add a realistic human-like delay between actions."""
        delay_ms = get_human_delay()
        await asyncio.sleep(delay_ms / 1000)


@dataclass
class NavigateAction(BrowserAction):
    """Navigate to a URL."""
    
    url: str
    wait_until: str = "networkidle"  # load, domcontentloaded, networkidle (default changed to networkidle)
    timeout: Optional[int] = None
    
    async def execute(self, page: Page) -> None:
        """Execute navigation."""
        logger.info(f"Navigating to: {self.url}")
        await page.goto(
            self.url, 
            wait_until=self.wait_until,
            timeout=self.timeout
        )
        # Explicit additional wait to ensure all async operations complete
        # This catches late-loading resources that may still be pending
        await page.wait_for_load_state(self.wait_until)
        
    def describe(self) -> str:
        return f"Navigate to {self.url}"


@dataclass 
class ClickAction(BrowserAction):
    """Click on an element."""
    
    selector: str
    button: str = "left"  # left, right, middle
    click_count: int = 1
    delay: Optional[int] = None
    force: bool = False
    no_wait_after: bool = False
    timeout: Optional[int] = None
    
    async def execute(self, page: Page) -> None:
        """Execute click action."""
        logger.info(f"Clicking element: {self.selector}")
        await page.click(
            self.selector,
            button=self.button,
            click_count=self.click_count,
            delay=self.delay,
            force=self.force,
            no_wait_after=self.no_wait_after,
            timeout=self.timeout
        )
        
    def describe(self) -> str:
        return f"Click {self.selector}"


@dataclass
class FillAction(BrowserAction):
    """Fill text into an input field."""
    
    selector: str
    text: str
    force: bool = False
    no_wait_after: bool = False  
    timeout: Optional[int] = None
    
    async def execute(self, page: Page) -> None:
        """Execute fill action."""
        logger.info(f"Filling text into {self.selector}: {self.text}")
        await page.fill(
            self.selector,
            self.text,
            force=self.force,
            no_wait_after=self.no_wait_after,
            timeout=self.timeout
        )
        
    def describe(self) -> str:
        return f"Fill '{self.text}' into {self.selector}"


@dataclass
class TypeAction(BrowserAction):
    """Type text into an element (with realistic typing)."""
    
    selector: str
    text: str
    delay: Optional[int] = None
    no_wait_after: bool = False
    timeout: Optional[int] = None
    
    async def execute(self, page: Page) -> None:
        """Execute type action."""
        logger.info(f"Typing text into {self.selector}: {self.text}")
        await page.type(
            self.selector,
            self.text,
            delay=self.delay,
            no_wait_after=self.no_wait_after,
            timeout=self.timeout
        )
        
    def describe(self) -> str:
        return f"Type '{self.text}' into {self.selector}"


@dataclass
class WaitAction(BrowserAction):
    """Wait for various conditions."""
    
    condition_type: str  # selector, timeout, load_state, function
    condition_value: Union[str, int, Dict[str, Any]]
    timeout: Optional[int] = None
    
    async def execute(self, page: Page) -> Any:
        """Execute wait action."""
        logger.info(f"Waiting for {self.condition_type}: {self.condition_value}")
        
        if self.condition_type == "selector":
            await page.wait_for_selector(
                str(self.condition_value),
                timeout=self.timeout
            )
        elif self.condition_type == "timeout":
            await page.wait_for_timeout(int(self.condition_value))
        elif self.condition_type == "load_state":
            await page.wait_for_load_state(
                str(self.condition_value),
                timeout=self.timeout
            )
        elif self.condition_type == "function":
            if isinstance(self.condition_value, dict):
                await page.wait_for_function(
                    self.condition_value.get("expression", ""),
                    timeout=self.timeout
                )
        else:
            raise ValueError(f"Unknown wait condition type: {self.condition_type}")
            
    def describe(self) -> str:
        return f"Wait for {self.condition_type}: {self.condition_value}"


@dataclass
class ScreenshotAction(BrowserAction):
    """Take a screenshot of the page or element."""
    
    path: Union[str, Path]
    selector: Optional[str] = None  # If None, captures full page
    full_page: bool = False
    clip: Optional[Dict[str, float]] = None
    quality: Optional[int] = None
    omit_background: bool = False
    timeout: Optional[int] = None
    
    async def execute(self, page: Page) -> bytes:
        """Execute screenshot action."""
        path_str = str(self.path)
        logger.info(f"Taking screenshot: {path_str}")
        
        if self.selector:
            element = await page.query_selector(self.selector)
            if not element:
                raise ValueError(f"Element not found: {self.selector}")
            return await element.screenshot(
                path=path_str,
                timeout=self.timeout,
                quality=self.quality,
                omit_background=self.omit_background
            )
        else:
            return await page.screenshot(
                path=path_str,
                full_page=self.full_page,
                clip=self.clip,
                quality=self.quality,
                omit_background=self.omit_background,
                timeout=self.timeout
            )
            
    def describe(self) -> str:
        if self.selector:
            return f"Screenshot element {self.selector} to {self.path}"
        return f"Screenshot page to {self.path}"


@dataclass
class SelectAction(BrowserAction):
    """Select option(s) from a select element."""
    
    selector: str
    values: Union[str, list[str]]
    force: bool = False
    no_wait_after: bool = False
    timeout: Optional[int] = None
    
    async def execute(self, page: Page) -> list[str]:
        """Execute select action."""
        logger.info(f"Selecting options in {self.selector}: {self.values}")
        return await page.select_option(
            self.selector,
            self.values,
            force=self.force,
            no_wait_after=self.no_wait_after,
            timeout=self.timeout
        )
        
    def describe(self) -> str:
        return f"Select {self.values} in {self.selector}"


@dataclass
class CheckAction(BrowserAction):
    """Check or uncheck a checkbox."""
    
    selector: str
    checked: bool = True
    force: bool = False
    no_wait_after: bool = False
    timeout: Optional[int] = None
    
    async def execute(self, page: Page) -> None:
        """Execute check action."""
        action_word = "Checking" if self.checked else "Unchecking"
        logger.info(f"{action_word} checkbox: {self.selector}")
        
        if self.checked:
            await page.check(
                self.selector,
                force=self.force,
                no_wait_after=self.no_wait_after,
                timeout=self.timeout
            )
        else:
            await page.uncheck(
                self.selector,
                force=self.force,
                no_wait_after=self.no_wait_after, 
                timeout=self.timeout
            )
            
    def describe(self) -> str:
        action = "Check" if self.checked else "Uncheck"
        return f"{action} {self.selector}"


@dataclass
class HoverAction(BrowserAction):
    """Hover over an element."""
    
    selector: str
    force: bool = False
    no_wait_after: bool = False
    timeout: Optional[int] = None
    
    async def execute(self, page: Page) -> None:
        """Execute hover action."""
        logger.info(f"Hovering over element: {self.selector}")
        await page.hover(
            self.selector,
            force=self.force,
            no_wait_after=self.no_wait_after,
            timeout=self.timeout
        )
        
    def describe(self) -> str:
        return f"Hover over {self.selector}"


@dataclass
class EvaluateAction(BrowserAction):
    """Execute JavaScript in the page context."""
    
    expression: str
    arg: Any = None
    
    async def execute(self, page: Page) -> Any:
        """Execute JavaScript evaluation."""
        logger.info(f"Evaluating JavaScript: {self.expression}")
        if self.arg is not None:
            return await page.evaluate(self.expression, self.arg)
        else:
            return await page.evaluate(self.expression)
            
    def describe(self) -> str:
        return f"Evaluate JavaScript: {self.expression}"