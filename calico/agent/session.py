from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from .actions import AIAction
from .executor import AIActionExecutor
from .llm import LLMClient, LLMPlan
from .state import SessionState

logger = logging.getLogger(__name__)


class AISession:
    """Coordinates the reasoning loop between the LLM and Playwright."""

    def __init__(
        self,
        llm: LLMClient,
        executor: AIActionExecutor,
        *,
        max_turns: int = 8,
        max_failures: int = 5,
        history_limit: int = 10,
        mcp_client: Optional[Any] = None,  # Phase 2: MCP client for full context enhancement
        enable_full_context: bool = True,   # Phase 2: Enable comprehensive intelligence
        progress_callback: Optional[Any] = None,  # Callback for progress updates
    ) -> None:
        self._llm = llm
        self._executor = executor
        self._max_turns = max_turns
        self._max_failures = max_failures
        self._history_limit = history_limit
        self._mcp_client = mcp_client
        self._enable_full_context = enable_full_context
        self._progress_callback = progress_callback
        
        # Phase 2: Initialize context enhancer if MCP client available
        self._context_enhancer = None
        if self._enable_full_context and self._mcp_client:
            try:
                from .context_enhancer import ContextEnhancer
                # Get session_storage from executor if available
                session_storage = getattr(self._executor, '_session_storage', None)
                self._context_enhancer = ContextEnhancer(
                    mcp_client=self._mcp_client,
                    enable_visual_context=True,
                    session_storage=session_storage
                )
                logger.info("Phase 2 context enhancement enabled")
            except Exception as e:
                logger.warning("Failed to initialize Phase 2 context enhancer, falling back to Phase 1", exc_info=e)
    
    def _emit_progress(self, event_type: str, data: dict) -> None:
        """Emit a progress event if callback is registered."""
        if self._progress_callback:
            try:
                self._progress_callback(event_type, data)
            except Exception as e:
                logger.warning(f"Progress callback failed for {event_type}: {e}")

    async def run(self, goal: str, *, context: Mapping[str, Any] | None = None, session_id: Optional[str] = None) -> SessionState:
        state = SessionState(goal=goal)
        error: Optional[str] = None

        for _ in range(self._max_turns):
            state.increment_turn()
            
            # Update context with current URL from the page
            current_context = dict(context or {})
            try:
                current_url = self._executor.page.url
                current_context["url"] = current_url
                logger.debug(f"Current page URL: {current_url}")
            except Exception as e:
                logger.debug(f"Could not get current URL: {e}")
                # Keep existing URL from context if available
            
            # Emit turn_start event
            self._emit_progress("turn_start", {
                "turn": state.turn_count,
                "goal": goal,
            })
            
            # === PHASE 2: COMPREHENSIVE CONTEXT ENHANCEMENT ===
            if self._context_enhancer:
                try:
                    logger.info("Using Phase 2: Comprehensive context enhancement")
                    plan = await self._llm.plan_actions(
                        goal=goal,
                        context=current_context,
                        state=state.to_prompt_dict(history_limit=self._history_limit),
                        error=error,
                        context_enhancer=self._context_enhancer,
                        session_id=session_id,
                    )
                    
                except Exception as e:
                    logger.error("Phase 2 enhancement failed, falling back to Phase 1", exc_info=e)
                    # Fallback to Phase 1
                    page_analysis = await self._generate_phase1_fallback(current_context, state)
                    try:
                        plan = await self._llm.plan_actions(
                            goal=goal,
                            context=current_context,
                            state=state.to_prompt_dict(history_limit=self._history_limit),
                            error=error,
                            page_analysis=page_analysis,
                        )
                    except TypeError:
                        # For backward compatibility with simpler LLMClient implementations
                        plan = await self._llm.plan_actions(
                            goal=goal,
                            context=current_context,
                            state=state.to_prompt_dict(history_limit=self._history_limit),
                            error=error,
                        )
                    
            else:
                # === PHASE 1: FORM INTELLIGENCE (Fallback) ===
                logger.debug("Using Phase 1: Form intelligence context")
                page_analysis = await self._generate_phase1_fallback(current_context, state)
                try:
                    plan = await self._llm.plan_actions(
                        goal=goal,
                        context=current_context,
                        state=state.to_prompt_dict(history_limit=self._history_limit),
                        error=error,
                        page_analysis=page_analysis,
                    )
                except TypeError:
                    plan = await self._llm.plan_actions(
                        goal=goal,
                        context=current_context,
                        state=state.to_prompt_dict(history_limit=self._history_limit),
                        error=error,
                    )
                
            state.record_reasoning(plan.reasoning)
            logger.info(f"Turn {state.turn_count}: {plan.reasoning[:150]}..." if len(plan.reasoning) > 150 else f"Turn {state.turn_count}: {plan.reasoning}")
            
            # Emit reasoning_complete event
            self._emit_progress("reasoning_complete", {
                "turn": state.turn_count,
                "reasoning": plan.reasoning,
                "actions_planned": len(plan.actions),
            })

            if plan.done and not plan.actions:
                state.mark_completed()
                logger.info("Goal completed - no further actions needed")
                
                # Emit turn_complete event
                self._emit_progress("turn_complete", {
                    "turn": state.turn_count,
                    "completed": True,
                    "actions": 0,
                })
                return state

            error = None
            for idx, action in enumerate(plan.actions, 1):
                logger.info(f"Executing action {idx}/{len(plan.actions)}: {action.type} → {action.target[:50] if action.target else 'N/A'}")
                
                # Emit action_start event
                self._emit_progress("action_start", {
                    "turn": state.turn_count,
                    "action": action.to_dict(),
                    "index": idx,
                    "total": len(plan.actions),
                })
                
                result = await self._executor.execute(action)
                state.record_event(action, result)
                
                # Emit action_complete event with full data
                self._emit_progress("action_complete", {
                    "turn": state.turn_count,
                    "action": action.to_dict(),  # Includes metadata with extracted_text
                    "result": {
                        "success": result.success,
                        "message": result.message,
                        "should_retry": result.should_retry,
                        "data": result.data,  # Include result data (candidates, OCR, etc.)
                    },
                    "index": idx,
                    "total": len(plan.actions),
                })
                
                if result.success:
                    logger.info(f"  ✓ Action succeeded")
                else:
                    logger.warning(f"  ✗ Action failed: {result.message[:100]}")
                    error = result.message
                    if plan.recovery_actions:
                        logger.info("Attempting recovery actions...")
                        recovery_error = await self._execute_recovery_actions(state, plan)
                        if recovery_error is not None:
                            error = recovery_error
                    break
            
            # Emit turn_complete event
            self._emit_progress("turn_complete", {
                "turn": state.turn_count,
                "completed": plan.done,
                "actions": len(plan.actions),
                "success_count": len([e for e in state.events if e.result.success and e.step > len(state.events) - len(plan.actions)]),
            })

            if state.failure_count > self._max_failures:
                logger.error(f"Maximum failures exceeded ({self._max_failures})")
                state.mark_failed(error or "Too many failed actions")
                return state

            if plan.done and error is None:
                state.mark_completed()
                return state

            if error is None and not plan.actions:
                state.mark_failed("LLM returned no actions to execute")
                return state

        if not state.completed and state.final_error is None:
            state.mark_failed("Reached maximum reasoning turns without completion")
        return state
    
    async def _generate_phase1_fallback(self, context, state) -> Optional[Mapping[str, Any]]:
        """Generate Phase 1 fallback analysis when Phase 2 is unavailable"""
        try:
            from .llm import analyze_page_for_intelligence
            
            page_context = {
                "url": context.get("url") if context else "",
                "turn": state.turn_count,
                "previous_failures": [
                    event.result.message for event in state.events 
                    if not event.result.success and "timeout" in event.result.message.lower()
                ]
            }
            
            return analyze_page_for_intelligence(page_context)
            
        except Exception as e:
            logger.warning("Phase 1 fallback generation failed", exc_info=e)
            return None

    async def _execute_recovery_actions(self, state: SessionState, plan: LLMPlan) -> Optional[str]:
        last_error: Optional[str] = None
        for action in plan.recovery_actions:
            result = await self._executor.execute(action)
            state.record_event(action, result, phase="recovery")
            if not result.success:
                last_error = result.message
                break
        return last_error

    async def _extract_dom_candidates(self, session_id: str) -> List[Dict[str, Any]]:
        """Extract DOM candidates using form_components utility."""
        try:
            # Use MCP to get DOM snapshot and extract candidates
            if not self._mcp_client:
                return []
                
            # Get page content via MCP
            dom_result = await self._mcp_client.call(
                "get_dom_snapshot", 
                {"sessionId": session_id, "format": "html"}, 
                timeout=10
            )
            
            if not dom_result or not dom_result.get("content"):
                logger.warning("No DOM content received from MCP")
                return []
                
            # For now, return a simplified approach
            # In a full implementation, this would parse the HTML and extract candidates
            logger.info("DOM extraction completed via MCP")
            return []
            
        except Exception as e:
            logger.warning(f"Failed to extract DOM candidates: {e}")
            return []

    async def _process_candidates(self, candidates: List[Dict[str, Any]], goal: str) -> List[Dict[str, Any]]:
        """Filter and score candidates based on relevance to goal."""
        if not candidates:
            return []
            
        # Score candidates based on goal keywords
        goal_keywords = goal.lower().split()
        
        scored_candidates = []
        for candidate in candidates:
            score = 0
            
            # Score based on candidate attributes
            for field in ["name", "id", "placeholder", "label", "tag"]:
                value = candidate.get(field, "")
                if value and isinstance(value, str):
                    for keyword in goal_keywords:
                        if keyword in value.lower():
                            score += 1
            
            # Boost score if candidate has fuzzy matches
            if candidate.get("fuzzy_matches"):
                score += 2
                
            if score > 0:
                candidate["relevance_score"] = score
                scored_candidates.append(candidate)
        
        # Sort by score and return top candidates
        scored_candidates.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return scored_candidates[:10]

    def _detect_page_type(self, url: str) -> str:
        """Detect page type from URL for enhanced selector strategies."""
        if not url:
            return "unknown"
            
        url_lower = url.lower()
        if "google.com" in url_lower:
            if "images" in url_lower:
                return "google_images_search"
            return "google_search"
        elif any(term in url_lower for term in ["login", "signin", "auth"]):
            return "login_page"
        elif "search" in url_lower:
            return "search_page"
        else:
            return "general_page"
