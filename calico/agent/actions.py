from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Literal, Mapping, Optional

ActionType = Literal[
    "goto",
    "click",  # Click element or at coordinates (x, y)
    "fill",
    "press",
    "hover",
    "wait_for",
    "check",
    "uncheck",
    "screenshot",
    "delay",  # Added delay action for time-based waits
    "extract",  # Extract text from element
    "extract_text",  # Extract text from element
    "get_text",  # Get text from element
    "click_coordinates",  # Click at specific x, y coordinates
]


@dataclass(slots=True)
class AIAction:
    """Structured representation of a Playwright action suggested by an LLM."""

    type: ActionType
    target: str
    value: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AIAction":
        """Create an :class:`AIAction` from a loosely typed mapping."""

        if "type" not in payload:
            raise ValueError("Action payload must include a 'type'")
        action_type = payload["type"]
        if action_type not in {"goto", "click", "fill", "press", "hover", "wait_for", "check", "uncheck", "screenshot", "delay", "extract", "extract_text", "get_text", "click_coordinates"}:
            raise ValueError(f"Unsupported action type: {action_type!r}")

        target = payload.get("target") or payload.get("selector")
        if action_type == "goto":
            target = target or payload.get("url")
        # Extract actions can have optional target (extract all page text if no target)
        if action_type in {"extract", "extract_text", "get_text"}:
            if not target:
                target = "body"  # Default to body if no selector provided
        if not isinstance(target, str) or not target.strip():
            raise ValueError("Action payload must include a non-empty 'target' or 'url'")

        value = payload.get("value")
        if value is None:
            value = payload.get("text")

        metadata = dict(payload.get("metadata") or {})
        confidence = payload.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
                raise ValueError("confidence must be numeric") from exc

        return cls(
            type=action_type,  # type: ignore[arg-type]
            target=target.strip(),
            value=value,
            confidence=confidence,
            metadata=metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "target": self.target,
            "value": self.value,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class ActionResult:
    """Outcome emitted by :class:`AIActionExecutor`."""

    success: bool
    message: str = ""
    should_retry: bool = False
    recovery_actions: list[AIAction] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    @property
    def error(self) -> Optional[str]:
        return None if self.success else self.message or self.data.get("error")  # type: ignore[return-value]


class ActionValidationError(RuntimeError):
    """Raised when a target element fails precondition checks."""

    def __init__(self, message: str, *, recoverable: bool = True, data: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.recoverable = recoverable
        self.data = data or {}


class ActionExecutionError(RuntimeError):
    """Raised when Playwright fails to execute an action."""

    def __init__(self, message: str, *, recoverable: bool = False, data: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.recoverable = recoverable
        self.data = data or {}
