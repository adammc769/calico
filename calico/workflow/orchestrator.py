"""Workflow orchestration helpers for multi-agent coordination."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import Future
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Protocol

from calico.agent import AIAction, AIActionExecutor, AISession, LLMClient, OpenAILLMClient
from calico.agent.actions import ActionResult
from calico.workflow.config import get_settings
from calico.workflow.db import AgentEvent, AgentRun, get_session, init_db
from calico.workflow.graph import get_graph_service
from calico.workflow.backends import get_backend_registry, ExecutorFactory

logger = logging.getLogger(__name__)

class ActionExecutor(Protocol):
    async def execute(self, action: AIAction) -> ActionResult:
        ...


class AgentRunError(RuntimeError):
    """Raised when an agent session fails to complete successfully."""

    def __init__(self, message: str, result: "AgentSessionResult") -> None:
        super().__init__(message)
        self.result = result


@dataclass(slots=True)
class AgentSessionResult:
    """Structured result describing an agent session."""

    run_id: int
    agent_name: str
    goal: str
    completed: bool
    status: str
    final_error: Optional[str]
    reasoning: Sequence[str]
    events: Sequence[Dict[str, Any]]
    data: Optional[Dict[str, Any]] = None  # Added missing data field

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "agent_name": self.agent_name,
            "goal": self.goal,
            "completed": self.completed,
            "status": self.status,
            "final_error": self.final_error,
            "reasoning": list(self.reasoning),
            "events": list(self.events),
            "data": self.data,  # Include data field
        }


def _serialize_event(event: SessionEvent) -> Dict[str, Any]:
    result_payload: Dict[str, Any] = {
        "success": event.result.success,
        "message": event.result.message,
        "should_retry": event.result.should_retry,
    }
    if event.result.data:
        result_payload["data"] = event.result.data

    # Serialize action, but filter out non-JSON-serializable data like bytes
    action_dict = event.action.to_dict()
    if "metadata" in action_dict and isinstance(action_dict["metadata"], dict):
        # Remove screenshot bytes but keep size info
        metadata = action_dict["metadata"].copy()
        if "screenshot_bytes" in metadata:
            del metadata["screenshot_bytes"]
        # Keep other useful info like screenshot_size, extracted_text, etc.
        action_dict["metadata"] = metadata

    payload: Dict[str, Any] = {
        "step": event.step,
        "phase": event.phase,
        "timestamp": event.timestamp.isoformat(),
        "action": action_dict,
        "result": result_payload,
    }
    return payload


def _run_coroutine_threadsafe(coro: Awaitable[Any]) -> Any:
    future: Future[Any] = Future()

    def worker() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(coro)
        except Exception as exc:  # pragma: no cover - propagated to caller
            future.set_exception(exc)
        else:
            future.set_result(result)
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:  # pragma: no cover - defensive cleanup
                pass
            loop.close()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join()
    return future.result()


def _determine_backend_mode(settings) -> str:
    """Determine which backend mode to use based on configuration."""
    # Priority: BACKEND_MODE env var > USE_MCP_BACKEND legacy flag > default
    if hasattr(settings, 'backend_mode') and settings.backend_mode:
        return settings.backend_mode
    
    # Legacy support: if USE_MCP_BACKEND is explicitly set
    if hasattr(settings, 'use_mcp_backend'):
        return "mcp" if settings.use_mcp_backend else "default"
    
    # Default to MCP
    return "mcp"


def _create_backend_executor_factory(
    backend_mode: str,
    session_identifier: str,
    settings,
    notification_handler=None
) -> ExecutorFactory:
    """Create executor factory for the specified backend."""
    registry = get_backend_registry()
    
    if backend_mode == "mcp":
        return registry.create_executor_factory(
            backend_name="mcp",
            session_id=session_identifier,
            url=settings.mcp_ws_url,
            request_timeout=settings.mcp_request_timeout_seconds,
            max_action_retries=settings.agent_max_retries,
            notification_handler=notification_handler,
        )
    else:
        # Try to create executor for the specified backend
        try:
            return registry.create_executor_factory(
                backend_name=backend_mode,
                session_id=session_identifier,
                notification_handler=notification_handler,
            )
        except ValueError as exc:
            available_backends = list(registry.get_available_backends().keys())
            raise ValueError(
                f"Backend '{backend_mode}' is not available. "
                f"Available backends: {available_backends}. "
                f"Only 'mcp' backend is provided with Calico. "
                f"Other backends can be registered via the backend registry."
            ) from exc


async def _legacy_default_executor_factory() -> Tuple[AIActionExecutor, Callable[[], Awaitable[None]]]:
    """Legacy default executor factory (deprecated, raises error)."""
    raise RuntimeError(
        "Direct Playwright executor is no longer supported. "
        "Calico now requires the MCP backend. "
        "Please ensure BACKEND_MODE=mcp or USE_MCP_BACKEND=true is set, "
        "and that the playwright-mcp service is running."
    )


def _build_llm_client(agent_name: str, config: Mapping[str, Any] | None) -> LLMClient:
    cfg = dict(config or {})

    client = cfg.get("client")
    if client is not None:
        if not hasattr(client, "plan_actions"):
            raise TypeError("llm_config['client'] must implement plan_actions")
        return client  # type: ignore[return-value]

    factory = cfg.get("factory")
    if callable(factory):
        produced = factory(agent_name=agent_name, config=cfg)
        if produced is None or not hasattr(produced, "plan_actions"):
            raise TypeError("llm_config factory did not return a valid LLM client")
        return produced  # type: ignore[return-value]

    model = cfg.get("model") or os.getenv("OPENAI_MODEL") or "gpt-4o"
    temperature = float(cfg.get("temperature", 0.2))
    system_prompt = cfg.get("system_prompt")
    api_key = cfg.get("api_key")
    if api_key:
        os.environ.setdefault("OPENAI_API_KEY", api_key)

    return OpenAILLMClient(model=model, temperature=temperature, system_prompt=system_prompt)


def run_agent_session(
    agent_name: str,
    goal: str,
    context: Mapping[str, Any] | None = None,
    workflow_id: Optional[str] = None,
    llm_config: Mapping[str, Any] | None = None,
    executor_factory: Optional[ExecutorFactory] = None,
    raise_on_failure: bool = True,
) -> AgentSessionResult:
    """Execute an agent session end-to-end and persist its outcome.
    
    This is a synchronous wrapper that creates its own event loop in a thread.
    For use in async contexts, use run_agent_session_async() instead.
    """
    return _run_agent_session_sync(
        agent_name=agent_name,
        goal=goal,
        context=context,
        workflow_id=workflow_id,
        llm_config=llm_config,
        executor_factory=executor_factory,
        raise_on_failure=raise_on_failure,
    )


async def run_agent_session_async(
    agent_name: str,
    goal: str,
    context: Mapping[str, Any] | None = None,
    workflow_id: Optional[str] = None,
    llm_config: Mapping[str, Any] | None = None,
    executor_factory: Optional[ExecutorFactory] = None,
    raise_on_failure: bool = True,
    progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> AgentSessionResult:
    """Execute an agent session end-to-end and persist its outcome (async version).
    
    This version runs in the current event loop and should be used from async contexts.
    
    Args:
        agent_name: Name identifying this agent
        goal: The task/goal to accomplish
        context: Additional context for the session
        workflow_id: Optional workflow identifier
        llm_config: LLM configuration (model, max_turns, etc.)
        executor_factory: Optional custom executor factory
        raise_on_failure: Whether to raise exception on failure
        progress_callback: Optional callback for real-time progress updates.
                          Called with (event_type: str, data: dict)
                          
    Progress callback events:
        - "session_start": {"goal": str, "session_id": str}
        - "turn_start": {"turn": int, "goal": str}
        - "reasoning_complete": {"turn": int, "reasoning": str}
        - "action_start": {"turn": int, "action": dict, "index": int, "total": int}
        - "action_complete": {"turn": int, "action": dict, "result": dict, "index": int}
        - "turn_complete": {"turn": int, "completed": bool, "actions": int}
        - "session_complete": {"status": str, "turns": int, "events": int}
    """
    return await _run_agent_session_impl(
        agent_name=agent_name,
        goal=goal,
        context=context,
        workflow_id=workflow_id,
        llm_config=llm_config,
        executor_factory=executor_factory,
        raise_on_failure=raise_on_failure,
        progress_callback=progress_callback,
    )


def _run_agent_session_sync(
    agent_name: str,
    goal: str,
    context: Mapping[str, Any] | None = None,
    workflow_id: Optional[str] = None,
    llm_config: Mapping[str, Any] | None = None,
    executor_factory: Optional[ExecutorFactory] = None,
    raise_on_failure: bool = True,
) -> AgentSessionResult:
    """Synchronous implementation that creates its own event loop."""
    async def _wrapper():
        return await _run_agent_session_impl(
            agent_name=agent_name,
            goal=goal,
            context=context,
            workflow_id=workflow_id,
            llm_config=llm_config,
            executor_factory=executor_factory,
            raise_on_failure=raise_on_failure,
        )
    
    try:
        return _run_coroutine_threadsafe(_wrapper())
    except AgentRunError:
        raise
    except Exception as exc:
        # Error handling moved to _run_agent_session_impl
        raise


async def _run_agent_session_impl(
    agent_name: str,
    goal: str,
    context: Mapping[str, Any] | None = None,
    workflow_id: Optional[str] | None = None,
    llm_config: Mapping[str, Any] | None = None,
    executor_factory: Optional[ExecutorFactory] = None,
    raise_on_failure: bool = True,
    progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> AgentSessionResult:
    """Core implementation of agent session execution with optional progress callbacks."""

    init_db()
    graph = get_graph_service()

    with get_session() as session:
        started = datetime.now(UTC)
        run = AgentRun(
            goal=goal,
            agent_name=agent_name,
            status="running",
            session_id=str(uuid.uuid4()),
            started_at=started,
        )
        session.add(run)
        session.flush()
        run_id = run.id
        run_session_token = run.session_id
    
    # Emit session_start event
    if progress_callback:
        try:
            progress_callback("session_start", {
                "goal": goal,
                "session_id": run_session_token,
                "agent_name": agent_name,
                "run_id": run_id,
            })
        except Exception as e:
            logger.warning(f"Progress callback failed: {e}")

    graph.upsert_agent_run(run_id=run_id, agent_name=agent_name, goal=goal, status="running")
    if workflow_id:
        graph.link_workflow_run(workflow_id=workflow_id, run_id=run_id)

    start_time = time.time()
    llm_settings = dict(llm_config or {})
    settings = get_settings()
    backend_mode = _determine_backend_mode(settings)
    
    if executor_factory is None:
        session_identifier = f"{settings.mcp_session_prefix}:{run_session_token}" if settings.mcp_session_prefix else run_session_token

        def _handle_notification(method: str, params: Dict[str, Any]) -> None:
            """Handle notifications from the backend (synchronous to avoid coroutine warnings)."""
            payload = params if isinstance(params, Mapping) else {}
            message = payload.get("message") if isinstance(payload.get("message"), str) else None
            details = {k: v for k, v in payload.items() if k != "message"}

            # Forward Playwright events to progress callback if registered
            if progress_callback and method.startswith("playwright."):
                try:
                    # Check if callback is async and handle appropriately
                    import inspect
                    if inspect.iscoroutinefunction(progress_callback):
                        # Schedule async callback without awaiting (to avoid blocking)
                        asyncio.create_task(progress_callback(method, payload))
                    else:
                        # Call sync callback directly
                        progress_callback(method, payload)
                except Exception as e:
                    logger.warning(f"Progress callback failed for {method}: {e}")

            if method == "log.emit":
                level = str(payload.get("level", "info")).lower()
                log_func = getattr(logger, level, logger.info)
                log_func(
                    "Backend[%s] %s",
                    session_identifier,
                    message or "",
                    extra={"details": details, "method": method, "session_id": session_identifier, "backend": backend_mode},
                )
            elif method == "task.update":
                logger.debug(
                    "Backend task update",
                    extra={
                        "session_id": session_identifier,
                        "backend": backend_mode,
                        "tasks": details.get("tasks"),
                    },
                )
            else:
                logger.debug(
                    "Backend notification",
                    extra={
                        "session_id": session_identifier,
                        "backend": backend_mode,
                        "method": method,
                        "params": params,
                    },
                )

        try:
            executor_factory = _create_backend_executor_factory(
                backend_mode=backend_mode,
                session_identifier=session_identifier,
                settings=settings,
                notification_handler=_handle_notification,
            )
            logger.info(f"Using backend: {backend_mode}")
        except Exception as exc:
            logger.error(f"Failed to create executor factory for backend '{backend_mode}': {exc}")
            raise
    llm_client = _build_llm_client(agent_name, llm_settings)

    async def _run() -> AgentSessionResult:
        executor, cleanup = await executor_factory()
        try:
            session_runner = AISession(
                llm_client,
                executor,
                max_turns=int(llm_settings.get("max_turns", 8)),
                max_failures=int(llm_settings.get("max_failures", 5)),
                progress_callback=progress_callback,  # Pass callback to session
            )
            state = await session_runner.run(goal, context=context)
        finally:
            try:
                await cleanup()
            except Exception as cleanup_error:
                logger.warning(f"Error during cleanup: {cleanup_error}")
                # Don't propagate cleanup errors

        events_payload = [_serialize_event(event) for event in state.events]
        completed = bool(state.completed)
        status = "completed" if completed and not state.final_error else "failed"
        result_payload = {
            "goal": goal,
            "completed": completed,
            "final_error": state.final_error,
            "turns": state.turn_count,
            "failures": state.failure_count,
            "reasoning": state.reasoning_log,
            "events": events_payload,
        }

        now = datetime.now(UTC)
        with get_session() as session_db:
            run_db = session_db.get(AgentRun, run_id)
            if run_db is not None:
                run_db.status = status
                run_db.result_payload = json.dumps(result_payload)
                run_db.error_message = state.final_error
                run_db.started_at = run_db.started_at or now
                run_db.finished_at = now

        with get_session() as session_db:
            for event_payload in events_payload:
                session_db.add(
                    AgentEvent(
                        run_id=run_id,
                        step=event_payload["step"],
                        phase=event_payload["phase"],
                        success=event_payload["result"]["success"],
                        message=event_payload["result"].get("message"),
                        data=json.dumps(event_payload),
                    )
                )

        for event_payload in events_payload:
            graph.append_event(
                run_id=run_id,
                step=event_payload["step"],
                phase=event_payload["phase"],
                success=event_payload["result"]["success"],
                message=event_payload["result"].get("message"),
                data=event_payload,
            )

        if status == "completed":
            graph.complete_run(run_id=run_id)
        else:
            graph.upsert_error(run_id=run_id, error=state.final_error or "Unknown agent failure")

        result = AgentSessionResult(
            run_id=run_id,
            agent_name=agent_name,
            goal=goal,
            completed=status == "completed",
            status=status,
            final_error=state.final_error,
            reasoning=list(state.reasoning_log),
            events=events_payload,
            data={"session_stats": {"total_events": len(events_payload)}},  # Add data field
        )
        
        # Emit session_complete event
        if progress_callback:
            try:
                progress_callback("session_complete", {
                    "status": status,
                    "turns": state.turn_count,
                    "events": len(events_payload),
                    "completed": completed,
                    "session_id": run_session_token,
                })
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
                
        if status != "completed" and raise_on_failure:
            raise AgentRunError(state.final_error or "Agent session failed", result)
        return result
        if status != "completed" and raise_on_failure:
            raise AgentRunError(state.final_error or "Agent session failed", result)
        return result

    try:
        return await _run()
    except AgentRunError:
        raise
    except Exception as exc:
        error_message = str(exc)
        logger.exception("Agent %s crashed", agent_name, exc_info=exc)
        now = datetime.now(UTC)
        failure_payload = {
            "goal": goal,
            "completed": False,
            "final_error": error_message,
            "events": [],
            "reasoning": [],
        }
        with get_session() as session_db:
            run_db = session_db.get(AgentRun, run_id)
            if run_db is not None:
                run_db.status = "failed"
                run_db.error_message = error_message
                run_db.finished_at = now
                run_db.result_payload = json.dumps(failure_payload)
                run_db.started_at = run_db.started_at or now
        graph.upsert_error(run_id=run_id, error=error_message)

        failure_result = AgentSessionResult(
            run_id=run_id,
            agent_name=agent_name,
            goal=goal,
            completed=False,
            status="failed",
            final_error=error_message,
            reasoning=[],
            events=[],
            data={"error_type": "execution_failure"},  # Add data field
        )
        if raise_on_failure:
            raise AgentRunError(error_message, failure_result) from exc
        return failure_result
    finally:
        elapsed = time.time() - start_time
        logger.info("Agent %s finished run %s in %.2fs", agent_name, run_id, elapsed)
        graph.close()


def orchestrate_workflow(
    *,
    goal: str,
    agents: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any] | None = None,
    workflow_id: Optional[str] = None,
    llm_config: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Coordinate multiple agents and persist the workflow graph."""

    if not agents:
        raise ValueError("At least one agent specification is required")

    workflow_id = workflow_id or str(uuid.uuid4())
    graph = get_graph_service()
    graph.start_workflow(workflow_id=workflow_id, goal=goal)

    results: List[AgentSessionResult] = []
    completed = True

    try:
        for spec in agents:
            if not isinstance(spec, Mapping):
                raise TypeError("each agent specification must be a mapping")
            agent_name = spec.get("agent_name")
            if not agent_name:
                raise ValueError("agent specification requires 'agent_name'")
            agent_goal = spec.get("goal", goal)
            agent_context = spec.get("context") or context
            agent_llm = spec.get("llm_config") or llm_config
            executor_factory = spec.get("executor_factory")

            try:
                result = run_agent_session(
                    agent_name=agent_name,
                    goal=agent_goal,
                    context=agent_context,
                    workflow_id=workflow_id,
                    llm_config=agent_llm,
                    executor_factory=executor_factory,
                    raise_on_failure=False,
                )
            except AgentRunError as exc:
                result = exc.result

            results.append(result)
            if not result.completed:
                completed = False

        workflow_status = "completed" if completed else "failed"
        graph.complete_workflow(workflow_id=workflow_id, status=workflow_status)

        return {
            "workflow_id": workflow_id,
            "goal": goal,
            "completed": completed,
            "agents": [result.to_dict() for result in results],
        }
    finally:
        graph.close()