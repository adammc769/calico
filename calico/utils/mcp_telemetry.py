"""Utilities for emitting telemetry events via the MCP transport."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Mapping, Optional, Sequence

from calico.utils.mcp_client import MCPClient
from calico.utils.mcp_contracts import (
    JSONValue,
    HuggingFaceTelemetryPayload,
    OCRTelemetryPayload,
    ReasoningTraceEntry,
    TelemetryEventPayload,
    TelemetryNotificationParams,
)

__all__ = ["emit_telemetry_event"]

_ALLOWED_KINDS = {"reasoning", "action", "observation", "ocr", "error", "custom"}
_ALLOWED_AUDIENCE = {"extension", "all"}


async def emit_telemetry_event(
    client: MCPClient,
    *,
    session_id: str,
    kind: str,
    message: str,
    data: Optional[Mapping[str, JSONValue]] = None,
    audience: Optional[str] = None,
    timestamp: Optional[str] = None,
    ocr_text: Optional[str] = None,
    ocr_chunks: Optional[Sequence[str]] = None,
    ocr_language: Optional[str] = None,
    ocr_confidence: Optional[float] = None,
    hf_model: Optional[str] = None,
    hf_latency_ms: Optional[float] = None,
    hf_scores: Optional[Sequence[Mapping[str, JSONValue]]] = None,
    reasoning_steps: Optional[Sequence[Mapping[str, JSONValue]]] = None,
) -> TelemetryNotificationParams:
    """Send a telemetry event to the MCP service.

    Parameters
    ----------
    client:
        Connected :class:`~calico.utils.mcp_client.MCPClient` instance.
    session_id:
        The MCP session that should receive/broadcast the event.
    kind:
        One of ``reasoning``, ``action``, ``observation``, ``ocr``, ``error``,
        or ``custom``.
    message:
        Human-readable summary of the event.
    data:
        Optional structured payload attached to the event.
    audience:
        When provided, restrict the event to the ``extension`` audience;
        otherwise the MCP service will broadcast to all listeners.
    timestamp:
        Override the event timestamp. Defaults to ``datetime.now(UTC)``.

    Returns
    -------
    TelemetryNotificationParams
        Payload dispatched via ``telemetry.emit`` (useful for testing).
    """

    if kind not in _ALLOWED_KINDS:
        raise ValueError(f"Unsupported telemetry kind: {kind}")
    if audience and audience not in _ALLOWED_AUDIENCE:
        raise ValueError(f"Unsupported telemetry audience: {audience}")

    event: TelemetryEventPayload = {
        "sessionId": session_id,
        "kind": kind,  # type: ignore[assignment]
        "message": message,
        "timestamp": timestamp or datetime.now(UTC).isoformat(),
    }
    if data:
        event["data"] = dict(data)

    if any(value is not None for value in (ocr_text, ocr_chunks, ocr_language, ocr_confidence)):
        ocr_payload: OCRTelemetryPayload = {}
        if ocr_text:
            ocr_payload["text"] = ocr_text
        if ocr_chunks:
            ocr_payload["chunks"] = [chunk for chunk in ocr_chunks if chunk]
        if ocr_language:
            ocr_payload["language"] = ocr_language
        if ocr_confidence is not None:
            ocr_payload["confidence"] = float(ocr_confidence)
        if ocr_payload:
            event["ocr"] = ocr_payload

    if hf_scores or hf_model or hf_latency_ms is not None:
        hf_payload: HuggingFaceTelemetryPayload = {
            "scoredSelectors": [],
        }
        if hf_model:
            hf_payload["model"] = hf_model
        if hf_latency_ms is not None:
            hf_payload["latencyMs"] = float(hf_latency_ms)
        if hf_scores:
            scores: list[dict[str, JSONValue]] = []
            for score in hf_scores:
                if not isinstance(score, Mapping):
                    continue
                selector = score.get("selector")
                raw_score = score.get("score")
                if not isinstance(selector, str) or not isinstance(raw_score, (int, float)):
                    continue
                entry: dict[str, JSONValue] = {
                    "selector": selector,
                    "score": float(raw_score),
                }
                label = score.get("label")
                if isinstance(label, str) and label:
                    entry["label"] = label
                text_preview = score.get("textPreview")
                if isinstance(text_preview, str) and text_preview:
                    entry["textPreview"] = text_preview
                context_snippet = score.get("contextSnippet")
                if isinstance(context_snippet, str) and context_snippet:
                    entry["contextSnippet"] = context_snippet
                scores.append(entry)
            if scores:
                hf_payload["scoredSelectors"] = scores
            else:
                hf_payload.pop("scoredSelectors", None)
        if hf_payload.get("scoredSelectors") or hf_model or hf_latency_ms is not None:
            event["huggingFace"] = hf_payload

    if reasoning_steps:
        trace: list[ReasoningTraceEntry] = []
        for step in reasoning_steps:
            if not isinstance(step, Mapping):
                continue
            thought = step.get("thought")
            if not isinstance(thought, str) or not thought.strip():
                continue
            trace_entry: ReasoningTraceEntry = {"thought": thought.strip()}
            evidence = step.get("evidence")
            if isinstance(evidence, str) and evidence.strip():
                trace_entry["evidence"] = evidence.strip()
            confidence = step.get("confidence")
            if isinstance(confidence, (int, float)):
                trace_entry["confidence"] = float(confidence)
            action = step.get("action")
            if isinstance(action, str) and action.strip():
                trace_entry["action"] = action.strip()
            trace.append(trace_entry)
        if trace:
            event["reasoningTrace"] = trace

    payload: TelemetryNotificationParams = {"event": event}
    if audience:
        payload["audience"] = audience  # type: ignore[assignment]

    await client.notify("telemetry.emit", payload)
    return payload
