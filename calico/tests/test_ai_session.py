import asyncio
from concurrent.futures import Future
import threading
from typing import Any, Dict, List, Mapping, Optional

import pytest

from calico.agent import AIAction, AIActionExecutor, AISession, LLMPlan


def run_async(coro):
    future: Future[Any] = Future()

    def _worker() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(coro)
        except Exception as exc:  # pragma: no cover - propagated via future
            future.set_exception(exc)
        else:
            future.set_result(result)
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:  # pragma: no cover - defensive cleanup
                pass
            loop.close()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join()
    return future.result()


def test_action_from_dict_validation() -> None:
    with pytest.raises(ValueError):
        AIAction.from_dict({"type": "click"})

    action = AIAction.from_dict({"type": "fill", "target": "#email", "value": "user@example.com", "confidence": "0.9"})
    assert action.type == "fill"
    assert action.target == "#email"
    assert action.value == "user@example.com"
    assert pytest.approx(action.confidence or 0.0, rel=1e-6) == 0.9

class StubLLMClient:
    def __init__(self, plans: List[LLMPlan]) -> None:
        self._plans = plans
        self.calls: List[Dict[str, Any]] = []

    async def plan_actions(
        self,
        *,
        goal: str,
        context: Mapping[str, Any] | None,
        state: Mapping[str, Any],
        error: str | None = None,
    ) -> LLMPlan:
        self.calls.append({"goal": goal, "context": context, "state": state, "error": error})
        if not self._plans:
            return LLMPlan(actions=[], reasoning="", done=True)
        return self._plans.pop(0)


class FakeLocator:
    def __init__(self, page: "FakePage", selector: str) -> None:
        self._page = page
        self._selector = selector

    async def wait_for(self, *, state: str, timeout: int) -> None:
        element = self._page.ensure_element(self._selector)
        if state == "attached" and not element["attached"]:
            raise TimeoutError(f"Selector {self._selector} not attached")

    async def is_visible(self) -> bool:
        element = self._page.ensure_element(self._selector)
        return self._page.evaluate_visibility(self._selector, element)

    async def is_enabled(self) -> bool:
        element = self._page.ensure_element(self._selector)
        return element["enabled"]

    async def click(self, *, timeout: int) -> None:
        self._page.actions.append(("click", self._selector))

    async def fill(self, value: str, *, timeout: int) -> None:
        self._page.actions.append(("fill", self._selector, value))
        self._page.values[self._selector] = value

    async def press(self, value: str, *, timeout: int) -> None:
        self._page.actions.append(("press", self._selector, value))

    async def hover(self, *, timeout: int) -> None:
        self._page.actions.append(("hover", self._selector))

    async def check(self, *, timeout: int) -> None:
        self._page.actions.append(("check", self._selector))

    async def uncheck(self, *, timeout: int) -> None:
        self._page.actions.append(("uncheck", self._selector))


class FakePage:
    def __init__(self) -> None:
        self.actions: List[Any] = []
        self.values: Dict[str, str] = {}
        self._elements: Dict[str, Dict[str, Any]] = {}

    def register_element(
        self,
        selector: str,
        *,
        visible: bool = True,
        enabled: bool = True,
        attached: bool = True,
        reveal_after_checks: Optional[int] = None,
    ) -> None:
        self._elements[selector] = {
            "visible": visible,
            "enabled": enabled,
            "attached": attached,
            "visibility_checks": 0,
            "reveal_after": reveal_after_checks,
        }

    def ensure_element(self, selector: str) -> Dict[str, Any]:
        if selector not in self._elements:
            raise TimeoutError(f"Unknown selector {selector}")
        return self._elements[selector]

    def evaluate_visibility(self, selector: str, element: Dict[str, Any]) -> bool:
        element["visibility_checks"] += 1
        reveal_after = element.get("reveal_after")
        if reveal_after is not None and element["visibility_checks"] >= reveal_after:
            element["visible"] = True
        return element["visible"]

    async def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.actions.append(("goto", url, wait_until))

    async def wait_for_selector(self, selector: str, *, state: str, timeout: int) -> None:
        element = self.ensure_element(selector)
        if not element["attached"]:
            raise TimeoutError(f"Selector {selector} not attached")
        if state == "visible":
            element["visible"] = True

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)


def test_session_runs_until_completion() -> None:
    page = FakePage()
    page.register_element("#submit")

    executor = AIActionExecutor(page, timeout=0.1)
    plans = [
        LLMPlan(actions=[AIAction.from_dict({"type": "goto", "target": "https://example.com"})], reasoning="navigating", done=False),
        LLMPlan(actions=[AIAction.from_dict({"type": "click", "target": "#submit"})], reasoning="submit form", done=True),
    ]
    llm = StubLLMClient(plans)
    session = AISession(llm, executor, max_turns=4)

    state = run_async(session.run("Submit the form"))

    assert state.completed is True
    assert state.step_count == 2
    assert page.actions == [("goto", "https://example.com", "domcontentloaded"), ("click", "#submit")]
    assert any("navigating" in entry for entry in state.reasoning_log)


def test_session_handles_failed_action_and_recovery() -> None:
    page = FakePage()
    page.register_element("#delayed", visible=False, reveal_after_checks=2)

    executor = AIActionExecutor(page, timeout=0.1, max_action_retries=0)
    failing_plan = LLMPlan(
        actions=[AIAction.from_dict({"type": "click", "target": "#delayed"})],
        reasoning="attempt click",
        done=False,
        recovery_actions=[
            AIAction.from_dict(
                {
                    "type": "wait_for",
                    "target": "#delayed",
                    "metadata": {"state": "visible", "timeout_ms": 50},
                }
            )
        ],
    )
    success_plan = LLMPlan(
        actions=[AIAction.from_dict({"type": "click", "target": "#delayed"})],
        reasoning="retry after wait",
        done=True,
    )
    llm = StubLLMClient([failing_plan, success_plan])
    session = AISession(llm, executor, max_turns=4)

    state = run_async(session.run("Click the delayed button"))

    assert state.completed is True
    assert state.failure_count >= 1
    # Click occurs once after recovery pipeline succeeds
    assert page.actions.count(("click", "#delayed")) == 1
    assert any(event.phase == "recovery" for event in state.events)
    assert state.reasoning_log[-1] == "retry after wait"


def test_session_stops_after_too_many_turns() -> None:
    page = FakePage()
    page.register_element("#missing", visible=False)
    executor = AIActionExecutor(page, timeout=0.1, max_action_retries=0)

    looping_plan = LLMPlan(actions=[AIAction.from_dict({"type": "click", "target": "#missing"})], reasoning="loop", done=False)
    llm = StubLLMClient([looping_plan] * 5)
    session = AISession(llm, executor, max_turns=3, max_failures=2)

    state = run_async(session.run("Attempt impossible click"))

    assert state.completed is False
    assert state.final_error is not None
    assert state.failure_count >= 3
    assert len(llm.calls) == 3