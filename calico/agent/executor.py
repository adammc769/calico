from __future__ import annotations

import asyncio
import logging
import random
import math
from typing import Any, Optional, Tuple

from .actions import AIAction, ActionExecutionError, ActionResult, ActionValidationError
from calico.utils.session_storage import SessionStorage
from calico.utils.bot_detection.mouse import human_mouse_move

logger = logging.getLogger(__name__)

# For local backend
class AIActionExecutor:
    """Executes LLM-authored actions against a Playwright page."""

    def __init__(
        self, 
        page: Any, 
        *, 
        timeout: float = 5.0, 
        max_action_retries: int = 1,
        session_id: Optional[str] = None,
        session_storage: Optional[SessionStorage] = None
    ) -> None:
        self._page = page
        self._timeout = timeout
        self._max_action_retries = max_action_retries
        self._session_storage = session_storage or SessionStorage(session_id=session_id)
        self._last_mouse_position: Optional[Tuple[float, float]] = None  # Track for realistic movements

    @property
    def page(self) -> Any:
        return self._page

    async def execute(self, action: AIAction) -> ActionResult:
        # Add realistic human-like delay using log-normal distribution
        # (humans don't have uniform reaction times!)
        mu = math.log(0.3)  # Median delay ~300ms
        sigma = 0.5  # Variance
        delay = random.lognormvariate(mu, sigma)
        delay = min(delay, 2.0)  # Cap at 2 seconds to avoid excessive delays
        delay = max(delay, 0.05)  # Min 50ms
        await asyncio.sleep(delay)
        
        attempts = 0
        last_error = ""
        while attempts <= self._max_action_retries:
            try:
                result = await self._execute_once(action)
                payload = {"attempts": attempts + 1}
                if result is not None:
                    payload["result"] = result
                
                # Include extracted text in result data for easier access
                if action.type in {"extract", "extract_text", "get_text"}:
                    extracted_text = action.metadata.get("extracted_text", "")
                    payload["extracted_text"] = extracted_text
                    # Also include character count for visibility
                    payload["text_length"] = len(extracted_text)
                
                # Log action execution
                self._session_storage.save_log(
                    f"Action executed: {action.type} on {action.target} - Success",
                    log_type="action",
                    level="INFO"
                )
                
                # Save action data for training
                self._session_storage.save_action_data(
                    action=action.to_dict(),
                    result={"success": True, "data": payload, "attempts": attempts + 1}
                )
                
                return ActionResult(success=True, message="ok", data=payload)
            except ActionValidationError as exc:
                last_error = str(exc)
                # Log validation errors
                self._session_storage.save_log(
                    f"Action validation error: {action.type} on {action.target} - {last_error}",
                    log_type="error",
                    level="ERROR"
                )
                
                # Save DOM snapshot on action failures (particularly wait_for failures)
                await self._save_dom_snapshot_on_failure(action, last_error)
                
                self._session_storage.save_action_data(
                    action=action.to_dict(),
                    result={"success": False, "error": last_error, "error_type": "validation"}
                )
                if not exc.recoverable or attempts >= self._max_action_retries:
                    return ActionResult(success=False, message=str(exc), should_retry=False, data=exc.data)
                attempts += 1
                await asyncio.sleep(min(0.2 * attempts, 1.0))
            except ActionExecutionError as exc:
                last_error = str(exc)
                # Log execution errors
                self._session_storage.save_log(
                    f"Action execution error: {action.type} on {action.target} - {last_error} (attempt {attempts + 1})",
                    log_type="error",
                    level="ERROR"
                )
                
                # Save DOM snapshot on action failures
                await self._save_dom_snapshot_on_failure(action, last_error)
                
                if not exc.recoverable or attempts >= self._max_action_retries:
                    self._session_storage.save_action_data(
                        action=action.to_dict(),
                        result={"success": False, "error": last_error, "error_type": "execution", "attempts": attempts + 1}
                    )
                    return ActionResult(success=False, message=str(exc), should_retry=exc.recoverable, data=exc.data)
                attempts += 1
                await asyncio.sleep(min(0.2 * attempts, 1.0))
            except Exception as exc:  # pragma: no cover - unexpected Playwright runtime errors
                last_error = str(exc)
                # Log unexpected errors
                self._session_storage.save_log(
                    f"Unexpected error: {action.type} on {action.target} - {last_error} (attempt {attempts + 1})",
                    log_type="playwright",
                    level="ERROR"
                )
                
                # Save DOM snapshot on unexpected failures
                await self._save_dom_snapshot_on_failure(action, last_error)
                
                if attempts >= self._max_action_retries:
                    self._session_storage.save_action_data(
                        action=action.to_dict(),
                        result={"success": False, "error": last_error, "error_type": "unknown", "attempts": attempts + 1}
                    )
                    return ActionResult(success=False, message=str(exc), should_retry=False)
                attempts += 1
                await asyncio.sleep(min(0.2 * attempts, 1.0))
        return ActionResult(success=False, message=last_error or "unknown error", should_retry=False)

    async def _execute_once(self, action: AIAction) -> Any:
        try:
            if action.type == "goto":
                # Check for redirect loop prevention
                current_url = self._page.url
                target_url = action.target
                
                # Normalize URLs for comparison (remove trailing slashes, fragments, query params for auth pages)
                from urllib.parse import urlparse, urljoin
                
                # Resolve relative URL against current URL
                resolved_target = urljoin(current_url, target_url)
                
                # Parse both URLs
                current_parsed = urlparse(current_url)
                target_parsed = urlparse(resolved_target)
                
                # Check if we're on an auth page and trying to navigate to another auth page on the same domain
                auth_keywords = ["login", "signin", "signup", "register", "auth", "authentication"]
                current_path_lower = current_parsed.path.lower()
                target_path_lower = target_parsed.path.lower()
                
                current_is_auth = any(keyword in current_path_lower for keyword in auth_keywords)
                target_is_auth = any(keyword in target_path_lower for keyword in auth_keywords)
                same_domain = current_parsed.netloc == target_parsed.netloc
                
                # If we're already on an auth page and trying to go to another auth page on same domain, skip
                if current_is_auth and target_is_auth and same_domain:
                    logger.info(f"Preventing redirect loop: already on auth page {current_url}, skipping navigation to {resolved_target}")
                    return
                
                # Check if URLs are essentially the same (ignoring fragments and trailing slashes)
                current_normalized = f"{current_parsed.scheme}://{current_parsed.netloc}{current_parsed.path.rstrip('/')}"
                target_normalized = f"{target_parsed.scheme}://{target_parsed.netloc}{target_parsed.path.rstrip('/')}"
                
                if current_normalized == target_normalized:
                    logger.info(f"Already at target URL {current_url}, skipping unnecessary navigation")
                    return
                
                await self._page.goto(
                    action.target,
                    wait_until="networkidle",
                    timeout=int(self._timeout * 1000),
                )
                # Explicit additional wait to ensure all async operations complete
                await self._page.wait_for_load_state("networkidle")
                return

            if action.type == "wait_for":
                # Enhanced wait_for with multiple selector support
                # Try multiple selectors separated by commas
                selectors = [s.strip() for s in action.target.split(',')]
                state = action.metadata.get("state", "visible")
                timeout = action.metadata.get("timeout_ms", int(self._timeout * 1000))
                
                # Try each selector in sequence
                last_error = None
                for selector in selectors:
                    if not selector:
                        continue
                    try:
                        await self._page.wait_for_selector(selector, state=state, timeout=timeout)
                        logger.info(f"Successfully found element with selector: {selector}")
                        return  # Success!
                    except Exception as e:
                        last_error = e
                        logger.debug(f"Selector '{selector}' not found, trying next...")
                        continue
                
                # If all selectors failed, raise error
                if last_error:
                    raise ActionValidationError(
                        f"None of the provided selectors were found on the page: {action.target}",
                        recoverable=True,
                        data={"action": action.to_dict(), "selectors_tried": selectors}
                    )
                return
            
            # Screenshot action
            if action.type == "screenshot":
                # Target can be 'full_page', 'viewport', or a selector for element screenshots
                if action.target == "full_page":
                    screenshot_bytes = await self._page.screenshot(full_page=True, timeout=int(self._timeout * 1000))
                elif action.target == "viewport":
                    screenshot_bytes = await self._page.screenshot(full_page=False, timeout=int(self._timeout * 1000))
                else:
                    # Element screenshot
                    locator = self._page.locator(action.target)
                    screenshot_bytes = await locator.screenshot(timeout=int(self._timeout * 1000))
                
                # Save screenshot to session storage
                try:
                    screenshot_name = action.metadata.get("name") or f"{action.target.replace('/', '_').replace(' ', '_')}"
                    saved_path = self._session_storage.save_screenshot(
                        image_data=screenshot_bytes,
                        name=screenshot_name,
                        action_context={
                            "action_type": action.type,
                            "target": action.target,
                            "metadata": action.metadata
                        }
                    )
                    logger.info(f"Screenshot saved to: {saved_path}")
                    
                    # Return saved path info
                    return {
                        "screenshot_path": str(saved_path),
                        "size_bytes": len(screenshot_bytes)
                    }
                except Exception as e:
                    logger.error(f"Failed to save screenshot: {e}", exc_info=True)
                    # Still store in metadata for backward compatibility
                    action.metadata["screenshot_bytes"] = screenshot_bytes
                    action.metadata["screenshot_size"] = len(screenshot_bytes)
                    return
            
            # Extract actions - get text from element or page
            if action.type in {"extract", "extract_text", "get_text"}:
                if action.target == "body" or not action.target:
                    # Extract all page text
                    # Use textContent as fallback for innerText (headless rendering issue)
                    text = await self._page.evaluate("() => document.body.innerText || document.body.textContent || ''")
                else:
                    # Extract text from specific element(s)
                    # Support extracting from multiple elements (e.g., top 5 items)
                    locator = self._page.locator(action.target)
                    
                    # Check if multiple elements should be extracted
                    try:
                        count = await locator.count()
                        logger.info(f"Found {count} elements matching '{action.target}'")
                        
                        if count == 0:
                            raise ActionValidationError(
                                f"No elements found matching '{action.target}'",
                                recoverable=True,
                                data={"action": action.to_dict()}
                            )
                        
                        # Extract text from all matching elements
                        texts = []
                        for i in range(count):
                            try:
                                elem_locator = locator.nth(i)
                                # Wait for element to be attached
                                await elem_locator.wait_for(state="attached", timeout=int(self._timeout * 1000))
                                # Get text content
                                elem_text = await elem_locator.text_content(timeout=int(self._timeout * 1000))
                                if elem_text:
                                    texts.append(elem_text.strip())
                            except Exception as e:
                                logger.debug(f"Failed to extract text from element {i}: {e}")
                                continue
                        
                        # Join all extracted texts with clear separators
                        text = "\n\n".join(texts) if texts else ""
                        logger.info(f"Extracted text from {len(texts)} elements ({len(text)} chars total)")
                        
                    except Exception as exc:
                        raise ActionValidationError(
                            f"Failed to extract text from '{action.target}': {exc}",
                            recoverable=True,
                            data={"action": action.to_dict()}
                        ) from exc
                
                # Store extracted text in action metadata for retrieval
                action.metadata["extracted_text"] = text
                action.metadata["element_count"] = len(texts) if 'texts' in locals() else 1
                return
            
            # Delay action
            if action.type == "delay":
                import asyncio
                delay_ms = int(action.metadata.get("duration_ms", 1000))
                await asyncio.sleep(delay_ms / 1000.0)
                return
            
            # Click at specific coordinates action
            if action.type == "click_coordinates":
                try:
                    # Extract x, y from metadata or parse from target
                    if "x" in action.metadata and "y" in action.metadata:
                        x = float(action.metadata["x"])
                        y = float(action.metadata["y"])
                    else:
                        # Try to parse from target like "x,y" or "x y"
                        coords = action.target.replace(",", " ").split()
                        if len(coords) != 2:
                            raise ActionValidationError(
                                "click_coordinates requires x,y in metadata or target like '100,200'",
                                recoverable=False
                            )
                        x = float(coords[0])
                        y = float(coords[1])
                    
                    # Get current mouse position or initialize
                    if self._last_mouse_position is None:
                        viewport = self._page.viewport_size
                        start_x = viewport['width'] / 2
                        start_y = viewport['height'] / 2
                    else:
                        start_x, start_y = self._last_mouse_position
                    
                    # Use human-like movement
                    duration = random.uniform(0.5, 1.5)
                    steps = random.randint(30, 60)
                    await human_mouse_move(
                        self._page,
                        start=(start_x, start_y),
                        end=(x, y),
                        duration=duration,
                        steps=steps
                    )
                    
                    # Update position and click
                    self._last_mouse_position = (x, y)
                    await asyncio.sleep(random.uniform(0.05, 0.15))
                    await self._page.mouse.click(x, y)
                    
                    logger.info(f"Clicked at coordinates ({x:.1f}, {y:.1f})")
                    return
                    
                except (ValueError, KeyError) as e:
                    raise ActionValidationError(
                        f"Invalid coordinates for click_coordinates: {e}",
                        recoverable=False
                    )

            locator = self._page.locator(action.target)
            await self._ensure_target_ready(locator, action)

            if action.type == "click":
                # Use human-like click with mouse movement
                await self._human_like_click(locator)
                return
            if action.type == "fill":
                if action.value is None:
                    raise ActionValidationError("fill action requires a value", recoverable=False)
                # Use human-like typing
                await self._human_like_type(locator, action.value)
                return
            if action.type == "press":
                # Press is for keyboard keys (Enter, Escape, etc.)
                # If no value provided but target is a button/clickable element, use click instead
                if action.value is None:
                    # Check if this looks like it should be a click action instead
                    target_lower = action.target.lower()
                    if any(keyword in target_lower for keyword in ['button', 'submit', 'link', 'a[', '[role="button"]']):
                        # This should be a click, not a press - auto-correct the action
                        await locator.click(timeout=int(self._timeout * 1000))
                        return
                    else:
                        raise ActionValidationError(
                            "press action requires a value (keyboard key like 'Enter', 'Escape', etc.). "
                            "To click an element, use 'click' action instead.",
                            recoverable=False
                        )
                await locator.press(action.value, timeout=int(self._timeout * 1000))
                return
            if action.type == "hover":
                await locator.hover(timeout=int(self._timeout * 1000))
                return
            if action.type == "check":
                await locator.check(timeout=int(self._timeout * 1000))
                return
            if action.type == "uncheck":
                await locator.uncheck(timeout=int(self._timeout * 1000))
                return
        except ActionValidationError:
            raise
        except Exception as exc:
            raise ActionExecutionError(
                f"Failed to execute {action.type} on {action.target}: {exc}",
                recoverable=False,
                data={"action": action.to_dict()},
            ) from exc

        raise ActionValidationError(f"Unsupported action type: {action.type}", recoverable=False)

    async def _ensure_target_ready(self, locator: Any, action: AIAction) -> None:
        try:
            await locator.wait_for(state="attached", timeout=int(self._timeout * 1000))
        except Exception as exc:  # pragma: no cover - passthrough
            raise ActionValidationError(
                f"Timed out waiting for target {action.target}", recoverable=True, data={"action": action.to_dict()}
            ) from exc

        visible = True
        enabled = True
        try:
            visible = await locator.is_visible()
        except Exception:  # pragma: no cover - locator API variance
            visible = True
        if not visible:
            raise ActionValidationError(
                f"Target {action.target} is not visible", recoverable=True, data={"action": action.to_dict()}
            )

        try:
            enabled = await locator.is_enabled()
        except Exception:  # pragma: no cover - locator API variance
            enabled = True
        if not enabled:
            raise ActionValidationError(
                f"Target {action.target} is not enabled", recoverable=True, data={"action": action.to_dict()}
            )

    async def _human_like_click(self, locator: Any) -> None:
        """
        Simulate human-like mouse movement and click at specific coordinates.
        Uses coordinate-based clicking to combat hidden bot detection elements.
        """
        try:
            # Get element position
            box = await locator.bounding_box(timeout=int(self._timeout * 1000))
            if not box:
                # Fallback to element click if no bounding box
                logger.debug("No bounding box available, using element click")
                await locator.click(timeout=int(self._timeout * 1000))
                return
            
            # Occasionally scroll into view like a human would
            if random.random() < 0.3:  # 30% chance
                await self._random_scroll()
            
            # Calculate target click position (random point within element)
            # Humans don't click exact center
            target_x = box['x'] + random.uniform(box['width'] * 0.3, box['width'] * 0.7)
            target_y = box['y'] + random.uniform(box['height'] * 0.3, box['height'] * 0.7)
            
            # Log coordinates for OCR matching and debugging
            self._session_storage.save_log(
                f"Element bounding box: x={box['x']:.1f}, y={box['y']:.1f}, width={box['width']:.1f}, height={box['height']:.1f}; "
                f"Click target: ({target_x:.1f}, {target_y:.1f})",
                log_type="action",
                level="DEBUG"
            )
            
            # Get current mouse position (or use page center as start)
            if self._last_mouse_position is None:
                # Initialize to page center
                viewport = self._page.viewport_size
                start_x = viewport['width'] / 2
                start_y = viewport['height'] / 2
            else:
                start_x, start_y = self._last_mouse_position
            
            # Use human-like Bézier curve movement from bot_detection
            duration = random.uniform(0.5, 1.5)  # Variable speed
            steps = random.randint(30, 60)  # More steps for smoother movement
            await human_mouse_move(
                self._page,
                start=(start_x, start_y),
                end=(target_x, target_y),
                duration=duration,
                steps=steps
            )
            
            # Update last position
            self._last_mouse_position = (target_x, target_y)
            
            # Small delay before click (human reaction time)
            await asyncio.sleep(random.uniform(0.05, 0.15))
            
            # Click at specific coordinates instead of clicking the element
            # This combats hidden bot detection elements
            await self._page.mouse.click(target_x, target_y)
            
            logger.debug(f"Clicked at coordinates ({target_x:.1f}, {target_y:.1f})")
            
        except Exception as e:
            # Fallback to simple element click on any error
            logger.debug(f"Coordinate-based click failed, using element click: {e}")
            await locator.click(timeout=int(self._timeout * 1000))

    async def _human_like_type(self, locator: Any, text: str) -> None:
        """Type like a human with random delays between keystrokes."""
        try:
            # Click to focus with human-like behavior
            await self._human_like_click(locator)
            
            # Small pause after clicking (human reaction time)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            # Clear existing text first
            await locator.fill("", timeout=int(self._timeout * 1000))
            
            # Type each character with realistic delays
            for char in text:
                await locator.type(char, delay=random.uniform(50, 150))  # 50-150ms per keystroke
                
                # Occasionally add longer pauses (thinking/looking at keyboard)
                if random.random() < 0.05:  # 5% chance of longer pause
                    await asyncio.sleep(random.uniform(0.3, 0.7))
        except Exception as e:
            # Fallback to direct fill on any error
            logger.debug(f"Human-like typing failed, using direct fill: {e}")
            await locator.fill(text, timeout=int(self._timeout * 1000))

    async def _random_scroll(self) -> None:
        """Occasionally scroll to simulate human browsing."""
        try:
            if random.random() < 0.3:  # 30% chance
                scroll_amount = random.randint(100, 300)
                direction = random.choice([1, -1])  # Up or down
                await self._page.evaluate(f"window.scrollBy(0, {scroll_amount * direction})")
                await asyncio.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            logger.debug(f"Random scroll failed: {e}")
    
    async def _save_dom_snapshot_on_failure(self, action: AIAction, error: str) -> None:
        """
        Save a DOM snapshot when an action fails.
        Only saves one snapshot per unique URL to avoid duplicates.
        
        Args:
            action: The action that failed
            error: The error message
        """
        try:
            # Get current URL
            current_url = self._page.url
            
            # Get HTML content
            html_content = await self._page.content()
            
            # Save DOM snapshot (will skip if already saved for this URL)
            snapshot_path = self._session_storage.save_dom_snapshot(
                html_content=html_content,
                url=current_url,
                action_context={
                    "action_type": action.type,
                    "target": action.target,
                    "value": action.value,
                    "metadata": action.metadata,
                    "error": error
                }
            )
            
            if snapshot_path:
                logger.info(f"Saved DOM snapshot for failed action: {snapshot_path}")
            else:
                logger.debug(f"DOM snapshot already exists for URL: {current_url}")
                
        except Exception as e:
            logger.error(f"Failed to save DOM snapshot: {e}", exc_info=True)

