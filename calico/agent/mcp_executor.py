"""Executor that proxies Calico actions to the Playwright MCP backend."""
from __future__ import annotations

import asyncio
import base64
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Dict, Optional, Tuple

from .actions import AIAction, ActionExecutionError, ActionResult, ActionValidationError
from calico.utils.mcp_client import MCPClient, MCPError, NotificationHandler
from calico.utils.session_storage import SessionStorage

logger = logging.getLogger(__name__)

# For mcp backend
class MCPActionExecutor:
    """Drop-in replacement for :class:`AIActionExecutor` using MCP."""

    def __init__(
        self,
        client: MCPClient,
        session_id: str,
        *,
        timeout: float = 30.0,
        max_action_retries: int = 1,
        session_storage: Optional[SessionStorage] = None,
    ) -> None:
        self._client = client
        self._session_id = session_id
        self._timeout = timeout
        self._max_action_retries = max_action_retries
        self._lock = asyncio.Lock()
        self._session_storage = session_storage or SessionStorage(session_id=session_id)

    async def execute(self, action: AIAction) -> ActionResult:
        attempts = 0
        last_error: str | None = None
        while attempts <= self._max_action_retries:
            try:
                result = await self._execute_once(action)
                payload: Dict[str, Any] = {"attempts": attempts + 1}
                if result is not None:
                    payload["result"] = result
                
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
                
                # Save DOM snapshot on action failures
                await self._save_dom_snapshot_on_failure(action, last_error)
                
                self._session_storage.save_action_data(
                    action=action.to_dict(),
                    result={"success": False, "error": last_error, "error_type": "validation"}
                )
                return ActionResult(success=False, message=str(exc), should_retry=False, data=exc.data)
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
            except MCPError as exc:
                last_error = str(exc)
                recoverable = exc.code in {-32000, -32001}
                # Log MCP errors
                self._session_storage.save_log(
                    f"MCP error: {action.type} on {action.target} - {last_error} (code: {exc.code}, attempt {attempts + 1})",
                    log_type="playwright",
                    level="ERROR"
                )
                
                # Save DOM snapshot on MCP errors
                await self._save_dom_snapshot_on_failure(action, last_error)
                
                if attempts >= self._max_action_retries or not recoverable:
                    self._session_storage.save_action_data(
                        action=action.to_dict(),
                        result={"success": False, "error": last_error, "error_type": "mcp", "code": exc.code, "attempts": attempts + 1}
                    )
                    return ActionResult(success=False, message=str(exc), should_retry=recoverable, data={"code": exc.code})
                attempts += 1
                await asyncio.sleep(min(0.2 * attempts, 1.0))
            except Exception as exc:  # pragma: no cover - defensive
                last_error = str(exc)
                # Log unexpected errors
                self._session_storage.save_log(
                    f"Unexpected error: {action.type} on {action.target} - {last_error} (attempt {attempts + 1})",
                    log_type="error",
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
        # Check for redirect loop prevention for goto actions
        if action.type == "goto":
            try:
                # Get current URL from MCP
                url_result = await self._client.call(
                    "getUrl",
                    {"sessionId": self._session_id},
                    timeout=5
                )
                current_url = url_result if isinstance(url_result, str) else str(url_result)
                target_url = action.target
                
                # Normalize URLs for comparison
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
                    return None
                
                # Check if URLs are essentially the same (ignoring fragments and trailing slashes)
                current_normalized = f"{current_parsed.scheme}://{current_parsed.netloc}{current_parsed.path.rstrip('/')}"
                target_normalized = f"{target_parsed.scheme}://{target_parsed.netloc}{target_parsed.path.rstrip('/')}"
                
                if current_normalized == target_normalized:
                    logger.info(f"Already at target URL {current_url}, skipping unnecessary navigation")
                    return None
            except Exception as e:
                logger.debug(f"Could not check for redirect loop: {e}, proceeding with navigation")
        
        method, params = self._build_request(action)
        params.setdefault("sessionId", self._session_id)
        async with self._lock:
            logger.debug("Dispatching MCP action", extra={"method": method, "params": {k: v for k, v in params.items() if k != "sessionId"}})
            result = await self._client.call(method, params, timeout=self._timeout)
            
            # Handle screenshot results - save to session storage
            if action.type == "screenshot" and result:
                try:
                    # If result contains base64 image data, decode and save it
                    if isinstance(result, dict) and "data" in result:
                        image_data = base64.b64decode(result["data"])
                    elif isinstance(result, bytes):
                        image_data = result
                    else:
                        logger.warning(f"Screenshot result type not recognized: {type(result)}")
                        return result
                    
                    # Generate screenshot name
                    screenshot_name = action.metadata.get("name") or f"{action.target.replace('/', '_').replace(' ', '_')}"
                    
                    # Save to session storage
                    saved_path = self._session_storage.save_screenshot(
                        image_data=image_data,
                        name=screenshot_name,
                        action_context={
                            "action_type": action.type,
                            "target": action.target,
                            "metadata": action.metadata
                        }
                    )
                    
                    logger.info(f"Screenshot saved to: {saved_path}")
                    
                    # Return the saved path info
                    return {
                        "screenshot_path": str(saved_path),
                        "session_id": self._session_id,
                        "original_result": result if isinstance(result, dict) else None
                    }
                except Exception as e:
                    logger.error(f"Failed to save screenshot: {e}", exc_info=True)
                    # Return original result if save fails
                    return result
            
            return result

    def _expand_selector_with_fallbacks(self, selector: str) -> str:
        """Expand a selector to include common fallbacks for better reliability."""
        # If selector already has commas, assume it's already a multi-selector
        if ',' in selector:
            return selector
            
        original_selector = selector
        enhanced_selector = selector
        
        # Enhanced patterns for Google search results - addresses the timeout issue
        if any(pattern in selector for pattern in ['div#search div.g', 'div.g', '.g']):
            enhanced_selector = 'div[data-ved], div.g, .tF2Cxc, [data-result-index], .kvH3mc, .MjjYud, .hlcw0c, div[jscontroller][lang], .yuRUbf, div.kvH3mc div.Z26q7c, div[data-async-context], .ULSxyf, div#search div.g'
            
        # Enhanced patterns for Google Images results
        elif any(pattern in selector for pattern in ['.rg_i', '.isv-r', 'div[data-ri]']):
            enhanced_selector = 'div[data-ved], .rg_i, .isv-r, div[jsname], [data-result-index], .mNsIhb, div[data-ri], .bRMDJf, .islir, div[data-async-context]'
            
        # Common fallback patterns for search inputs
        elif 'input[name="q"]' in selector or selector == 'input[name="q"]':
            enhanced_selector = 'input[name="q"], input[type="search"], input[placeholder*="search" i], textarea[name="q"], #search-input, [name="search"], [aria-label*="search" i]'
            
        # Common fallback patterns for email inputs  
        elif 'input[name="email"]' in selector or selector == 'input[name="email"]':
            enhanced_selector = 'input[name="email"], input[type="email"], input[placeholder*="email" i], #email, [name="email"]'
            
        # Common fallback patterns for password inputs
        elif 'input[name="password"]' in selector or selector == 'input[name="password"]':
            enhanced_selector = 'input[name="password"], input[type="password"], input[placeholder*="password" i], #password, [name="password"]'
            
        # Common fallback patterns for submit buttons
        elif 'button[type="submit"]' in selector or selector == 'button[type="submit"]':
            enhanced_selector = 'button[type="submit"], input[type="submit"], button:has-text("Submit"), button:has-text("Search"), [role="button"][type="submit"]'
        
        # Walmart product items - expand data-item-id to include container
        elif 'data-item-id' in selector or '[data-item-id]' in selector:
            enhanced_selector = '[data-testid="list-view"], [data-item-id], div[role="group"][data-item-id], [data-product-id]'
            
        # For other inputs, add basic fallbacks
        elif selector.startswith('input[name='):
            name_match = selector.split('"')[1] if '"' in selector else selector.split("'")[1] if "'" in selector else None
            if name_match:
                enhanced_selector = f'{selector}, #{name_match}, [name="{name_match}"]'
        
        # Log when we enhance a selector
        if enhanced_selector != original_selector:
            logger.debug("Enhanced selector with fallbacks", extra={
                "original": original_selector, 
                "enhanced": enhanced_selector
            })
                
        return enhanced_selector

    def _build_request(self, action: AIAction) -> Tuple[str, Dict[str, Any]]:
        timeout_ms = int(self._timeout * 1000)

        if action.type == "goto":
            return "navigate", {"url": action.target, "timeoutMs": timeout_ms, "waitUntil": action.metadata.get("wait_until", "networkidle")}

        if action.type == "wait_for":
            state = action.metadata.get("state")
            enhanced_selector = self._expand_selector_with_fallbacks(action.target)
            params: Dict[str, Any] = {"selector": enhanced_selector, "timeoutMs": action.metadata.get("timeout_ms", timeout_ms)}
            if state:
                params["state"] = state
            return "waitForSelector", params

        if action.type == "hover":
            enhanced_selector = self._expand_selector_with_fallbacks(action.target)
            params = {
                "selector": enhanced_selector,
                "timeoutMs": action.metadata.get("timeout_ms", timeout_ms),
            }
            position = action.metadata.get("position") if isinstance(action.metadata, dict) else None
            if isinstance(position, dict):
                x = position.get("x")
                y = position.get("y")
                if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    params["position"] = {"x": float(x), "y": float(y)}
            return "hover", params

        if action.type == "check":
            enhanced_selector = self._expand_selector_with_fallbacks(action.target)
            params = {
                "selector": enhanced_selector,
                "timeoutMs": action.metadata.get("timeout_ms", timeout_ms),
            }
            force = action.metadata.get("force") if isinstance(action.metadata, dict) else None
            if isinstance(force, bool):
                params["force"] = force
            return "check", params

        if action.type == "uncheck":
            enhanced_selector = self._expand_selector_with_fallbacks(action.target)
            params = {
                "selector": enhanced_selector,
                "timeoutMs": action.metadata.get("timeout_ms", timeout_ms),
            }
            force = action.metadata.get("force") if isinstance(action.metadata, dict) else None
            if isinstance(force, bool):
                params["force"] = force
            return "uncheck", params

        if action.type == "click":
            enhanced_selector = self._expand_selector_with_fallbacks(action.target)
            params = {
                "selector": enhanced_selector,
                "timeoutMs": action.metadata.get("timeout_ms", timeout_ms),
                "button": action.metadata.get("button", "left"),
            }
            return "click", params

        if action.type == "fill":
            if action.value is None:
                raise ActionValidationError("fill action requires a value", recoverable=False)
            enhanced_selector = self._expand_selector_with_fallbacks(action.target)
            params = {
                "selector": enhanced_selector,
                "text": action.value,
                "timeoutMs": action.metadata.get("timeout_ms", timeout_ms),
                "delayMs": action.metadata.get("delay_ms"),
            }
            return "type", params

        if action.type == "press":
            # Press is for keyboard keys (Enter, Escape, etc.)
            # If no value provided but target is a button/clickable element, use click instead
            if not action.value:
                # Check if this looks like it should be a click action instead
                target_lower = action.target.lower() if action.target else ""
                if any(keyword in target_lower for keyword in ['button', 'submit', 'link', 'a[', '[role="button"]']):
                    # This should be a click, not a press - auto-correct the action
                    enhanced_selector = self._expand_selector_with_fallbacks(action.target)
                    params = {"selector": enhanced_selector}
                    return "click", params
                else:
                    raise ActionValidationError(
                        "press action requires a key value (like 'Enter', 'Escape', etc.). "
                        "To click an element, use 'click' action instead.",
                        recoverable=False
                    )
            params = {"key": action.value, "delayMs": action.metadata.get("delay_ms")}
            return "pressKey", params

        if action.type == "screenshot":
            # Target can be 'full_page', 'viewport', or a selector for element screenshots
            params = {}
            if action.target == "full_page":
                params["fullPage"] = True
            elif action.target == "viewport":
                params["fullPage"] = False
            else:
                # Element screenshot - use target as selector
                enhanced_selector = self._expand_selector_with_fallbacks(action.target)
                params["selector"] = enhanced_selector
                params["timeoutMs"] = action.metadata.get("timeout_ms", timeout_ms)
            
            # Optional format and quality parameters
            params["format"] = action.metadata.get("format", "png")
            if "quality" in action.metadata:
                params["quality"] = action.metadata["quality"]
            
            return "screenshot", params

        if action.type == "delay":
            # Handle time-based delays - target should be duration in milliseconds or seconds
            duration_str = action.target.strip()
            
            # Parse duration from various formats
            duration_ms = None
            if duration_str.endswith("ms"):
                duration_ms = int(duration_str[:-2])
            elif duration_str.endswith("s"):
                duration_ms = int(float(duration_str[:-1]) * 1000)
            elif duration_str.isdigit():
                # Assume milliseconds if just a number
                duration_ms = int(duration_str)
            else:
                # Try to extract number and assume seconds
                import re
                match = re.search(r'(\d+(?:\.\d+)?)', duration_str)
                if match:
                    duration_ms = int(float(match.group(1)) * 1000)
                else:
                    raise ActionValidationError(f"Invalid delay duration: {duration_str}", recoverable=False)
            
            # Use a simple wait via JavaScript execution
            params = {
                "script": f"await new Promise(resolve => setTimeout(resolve, {duration_ms}))",
                "timeoutMs": duration_ms + 5000  # Add buffer for timeout
            }
            return "evaluateScript", params
        
        if action.type in {"extract", "extract_text", "get_text"}:
            # Extract text from element or page
            if action.target == "body" or not action.target:
                # Extract all page text
                # Use textContent as fallback for innerText (headless rendering issue)
                params = {
                    "script": "() => document.body.innerText || document.body.textContent || ''",
                    "timeoutMs": action.metadata.get("timeout_ms", timeout_ms)
                }
                return "evaluateScript", params
            else:
                # Extract text from specific element
                # Use textContent instead of innerText for better headless compatibility
                enhanced_selector = self._expand_selector_with_fallbacks(action.target)
                params = {
                    "selector": enhanced_selector,
                    "timeoutMs": action.metadata.get("timeout_ms", timeout_ms)
                }
                return "textContent", params

        raise ActionValidationError(f"Unsupported action type: {action.type}", recoverable=False)
    
    async def _save_dom_snapshot_on_failure(self, action: AIAction, error: str) -> None:
        """
        Save a DOM snapshot when an action fails via MCP.
        Only saves one snapshot per unique URL to avoid duplicates.
        
        Args:
            action: The action that failed
            error: The error message
        """
        try:
            # Get current page URL via MCP
            url_result = await self._client.call(
                "evaluate", 
                {"sessionId": self._session_id, "script": "() => window.location.href"},
                timeout=5.0
            )
            current_url = url_result if isinstance(url_result, str) else str(url_result)
            
            # Get HTML content via MCP
            dom_result = await self._client.call(
                "get_dom_snapshot",
                {"sessionId": self._session_id, "format": "html"},
                timeout=10.0
            )
            
            if not dom_result or not dom_result.get("content"):
                logger.debug("No DOM content received from MCP for snapshot")
                return
            
            html_content = dom_result.get("content", "")
            
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
                logger.info(f"Saved DOM snapshot for failed action via MCP: {snapshot_path}")
            else:
                logger.debug(f"DOM snapshot already exists for URL: {current_url}")
                
        except Exception as e:
            logger.error(f"Failed to save DOM snapshot via MCP: {e}", exc_info=True)


async def create_mcp_executor(
    *,
    url: str,
    session_id: str,
    request_timeout: float = 30.0,
    max_action_retries: int = 1,
    notification_handler: NotificationHandler | None = None,
) -> tuple[MCPActionExecutor, Callable[[], Awaitable[None]]]:
    """Instantiate an :class:`MCPActionExecutor` and its cleanup coroutine."""

    client = MCPClient(url, request_timeout=request_timeout, notification_handler=notification_handler)
    await client.connect()

    executor = MCPActionExecutor(
        client,
        session_id,
        timeout=request_timeout,
        max_action_retries=max_action_retries,
    )

    async def cleanup() -> None:
        try:
            await client.call("close_session", {"sessionId": session_id}, timeout=request_timeout)
        except MCPError as exc:
            logger.warning("Failed to close MCP session", extra={"sessionId": session_id, "error": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Unexpected error closing MCP session", extra={"sessionId": session_id, "error": str(exc)})
        finally:
            await client.close()

    return executor, cleanup