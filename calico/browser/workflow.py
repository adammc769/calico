"""Browser automation workflow integration with Calico AI agents."""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Union

from calico.browser.actions import BrowserAction
from calico.browser.automation import BrowserSession

logger = logging.getLogger(__name__)


def get_human_interaction_delay(min_ms: int = 300, max_ms: int = 1200) -> float:
    """Get a random human-like delay between interactions in seconds."""
    return random.randint(min_ms, max_ms) / 1000


@dataclass
class BrowserWorkflowSpec:
    """Specification for a browser automation workflow."""
    
    browser_actions: List[BrowserAction]
    session_id: Optional[str] = None
    description: Optional[str] = None
    
    def __post_init__(self):
        if not self.description:
            action_descriptions = [action.describe() for action in self.browser_actions]
            self.description = f"Browser workflow: {', '.join(action_descriptions)}"


class WorkflowResult:
    """Result of a workflow execution."""
    
    def __init__(self, success: bool, data: Dict[str, Any] = None, error: str = None):
        self.success = success
        self.data = data or {}
        self.error = error


class BrowserWorkflowExecutor:
    """Executes browser workflow actions using active sessions."""
    
    def __init__(self, human_like_delays: bool = False):
        self._sessions: Dict[str, BrowserSession] = {}
        self.human_like_delays = human_like_delays
        
    def register_session(self, session_id: str, session: BrowserSession):
        """Register a browser session for use in workflows."""
        self._sessions[session_id] = session
        logger.info(f"Registered browser session: {session_id}")
        
    def unregister_session(self, session_id: str):
        """Unregister a browser session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Unregistered browser session: {session_id}")
            
    async def execute_workflow(
        self, 
        actions: Sequence[BrowserAction],
        session_id: Optional[str] = None,
        human_like_delays: Optional[bool] = None
    ) -> WorkflowResult:
        """Execute a sequence of browser actions.
        
        Args:
            actions: Sequence of browser actions to execute
            session_id: Optional session ID to use
            human_like_delays: Override instance setting for human-like delays
        """
        # Use provided setting or fall back to instance setting
        use_delays = human_like_delays if human_like_delays is not None else self.human_like_delays
        
        # Use default session if none specified
        if session_id is None:
            if not self._sessions:
                return WorkflowResult(
                    success=False,
                    error="No browser sessions available"
                )
            session_id = next(iter(self._sessions.keys()))
            
        if session_id not in self._sessions:
            return WorkflowResult(
                success=False,
                error=f"Browser session not found: {session_id}"
            )
            
        session = self._sessions[session_id]
        results = []
        
        # Check if session config has human_like_delays enabled
        if hasattr(session.config, 'human_like_delays') and session.config.human_like_delays:
            use_delays = True
        
        try:
            for i, action in enumerate(actions):
                logger.info(f"Executing action {i+1}/{len(actions)}: {action.describe()}")
                
                # Add human-like delay before action (except for first action)
                if use_delays and i > 0:
                    delay = get_human_interaction_delay()
                    logger.debug(f"Adding human-like delay: {delay:.2f}s")
                    await asyncio.sleep(delay)
                
                try:
                    result = await action.execute(session.page)
                    results.append({
                        "action": action.describe(),
                        "success": True,
                        "result": result
                    })
                except Exception as e:
                    error_msg = f"Action failed: {action.describe()} - {str(e)}"
                    logger.error(error_msg)
                    results.append({
                        "action": action.describe(),
                        "success": False,
                        "error": str(e)
                    })
                    
                    # Decide whether to continue or stop on error
                    # For now, we'll stop on first error
                    return WorkflowResult(
                        success=False,
                        error=error_msg,
                        data={
                            "completed_actions": results,
                            "failed_at": i
                        }
                    )
                    
            return WorkflowResult(
                success=True,
                data={
                    "actions_executed": len(actions),
                    "results": results,
                    "session_id": session_id
                }
            )
            
        except Exception as e:
            error_msg = f"Workflow execution failed: {str(e)}"
            logger.error(error_msg)
            return WorkflowResult(
                success=False,
                error=error_msg,
                data={"completed_actions": results}
            )
            
    async def execute_workflow_spec(self, spec: BrowserWorkflowSpec) -> WorkflowResult:
        """Execute a BrowserWorkflowSpec."""
        return await self.execute_workflow(
            actions=spec.browser_actions,
            session_id=spec.session_id
        )
        
    def get_session_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all registered sessions."""
        info = {}
        for session_id, session in self._sessions.items():
            info[session_id] = {
                "browser_type": session.config.browser_type,
                "headless": session.config.headless,
                "viewport": session.config.viewport,
                "current_url": None  # Will be populated async
            }
        return info
        
    async def get_page_info(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current page information for a session."""
        if session_id is None:
            if not self._sessions:
                return {"error": "No sessions available"}
            session_id = next(iter(self._sessions.keys()))
            
        if session_id not in self._sessions:
            return {"error": f"Session not found: {session_id}"}
            
        session = self._sessions[session_id]
        try:
            return {
                "session_id": session_id,
                "url": session.page.url,
                "title": await session.page.title(),
                "viewport": session.page.viewport_size,
            }
        except Exception as e:
            return {"error": f"Failed to get page info: {str(e)}"}


# Global workflow executor instance
_workflow_executor = BrowserWorkflowExecutor()


def get_workflow_executor() -> BrowserWorkflowExecutor:
    """Get the global browser workflow executor instance."""
    return _workflow_executor