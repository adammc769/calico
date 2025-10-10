from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .actions import AIAction, ActionResult


@dataclass(slots=True)
class SessionEvent:
    """Represents a single attempt at executing an action."""

    step: int
    action: AIAction
    result: ActionResult
    phase: str = "action"
    timestamp: _dt.datetime = field(default_factory=lambda: _dt.datetime.now(_dt.timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "step": self.step,
            "phase": self.phase,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.to_dict(),
            "success": self.result.success,
            "message": self.result.message,
            "should_retry": self.result.should_retry,
        }
        if self.result.data:
            payload["data"] = self.result.data
        return payload


@dataclass
class SessionState:
    """Mutable state tracked across an AI-driven browsing session."""

    goal: str
    events: List[SessionEvent] = field(default_factory=list)
    reasoning_log: List[str] = field(default_factory=list)
    failure_count: int = 0
    turn_count: int = 0
    completed: bool = False
    final_error: Optional[str] = None

    def record_event(self, action: AIAction, result: ActionResult, *, phase: str = "action") -> SessionEvent:
        event = SessionEvent(step=len(self.events) + 1, action=action, result=result, phase=phase)
        self.events.append(event)
        if not result.success:
            self.failure_count += 1
        return event

    def record_reasoning(self, text: str) -> None:
        if text:
            self.reasoning_log.append(text)

    @property
    def step_count(self) -> int:
        return len(self.events)

    def mark_completed(self) -> None:
        self.completed = True

    def mark_failed(self, error: str) -> None:
        self.final_error = error
        self.completed = False

    def increment_turn(self) -> None:
        self.turn_count += 1

    def summarize_history(self, limit: int = 5) -> List[Dict[str, Any]]:
        history = self.events[-limit:]
        return [event.to_dict() for event in history]

    def to_prompt_dict(self, *, history_limit: int = 10) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "steps_completed": self.step_count,
            "turns": self.turn_count,
            "completed": self.completed,
            "failure_count": self.failure_count,
            "history": self.summarize_history(history_limit),
            "reasoning": self.reasoning_log[-history_limit:],
            "final_error": self.final_error,
        }

    def last_event(self) -> Optional[SessionEvent]:
        return self.events[-1] if self.events else None
