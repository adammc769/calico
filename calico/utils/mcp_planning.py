"""Helpers for interacting with MCP plan submission endpoints."""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Sequence

from calico.utils.mcp_client import MCPClient
from calico.utils.mcp_contracts import PlanSubmissionResult, PlannedCommandPayload, PlanStep

__all__ = ["submit_plan"]


def _normalize_commands(commands: Sequence[Mapping[str, Any]]) -> list[PlannedCommandPayload]:
    normalized: list[PlannedCommandPayload] = []
    for command in commands:
        name = str(command.get("command", "")).strip()
        if not name:
            continue
        params = command.get("params")
        payload: PlannedCommandPayload = {"command": name}
        if isinstance(params, Mapping):
            payload["params"] = dict(params)
        normalized.append(payload)
    return normalized


async def submit_plan(
    client: MCPClient,
    *,
    session_id: str,
    profile_id: str,
    commands: Sequence[Mapping[str, Any]],
    goal: str = "",
    summary: str | None = None,
    note: str | None = None,
    steps: Sequence[PlanStep] | None = None,
    dom_candidates: Sequence[Mapping[str, Any]] | None = None,
) -> PlanSubmissionResult:
    """Submit a precomputed plan to the MCP service for execution."""

    payload: MutableMapping[str, Any] = {}
    payload["sessionId"] = session_id
    payload["profileId"] = profile_id
    if goal:
        payload["goal"] = goal
    if summary:
        payload["summary"] = summary
    if note:
        payload["note"] = note
    if steps:
        payload["steps"] = list(steps)
    if dom_candidates:
        payload["domCandidates"] = [dict(candidate) for candidate in dom_candidates]

    normalized_commands = _normalize_commands(commands)
    if not normalized_commands:
        raise ValueError("submit_plan requires at least one command with a 'command' field")
    payload["commands"] = normalized_commands

    result = await client.call("submitPlan", dict(payload))
    if not isinstance(result, Mapping):
        raise ValueError("submitPlan returned an unexpected payload")
    return PlanSubmissionResult(**result)
