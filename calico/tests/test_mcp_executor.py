"""Tests for the MCP executor integration."""
from __future__ import annotations

import pytest

from calico.agent.actions import AIAction, ActionValidationError
from calico.agent.mcp_executor import MCPActionExecutor, create_mcp_executor


class StubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, float | None]] = []

    async def call(self, method: str, params: dict, timeout: float | None = None):
        self.calls.append((method, params, timeout))
        return {"ok": True}

    async def close(self) -> None:  # pragma: no cover - compatibility hook
        pass


@pytest.mark.asyncio
async def test_execute_dispatches_to_mcp_client():
    client = StubClient()
    executor = MCPActionExecutor(client, "session-123", timeout=2.5)

    action = AIAction(type="click", target="#submit")
    result = await executor.execute(action)

    assert result.success is True
    assert client.calls, "expected MCP client to receive a call"
    method, params, timeout = client.calls[0]
    assert method == "click"
    assert params["selector"] == "#submit"
    assert params["sessionId"] == "session-123"
    assert timeout == pytest.approx(2.5)


@pytest.mark.asyncio
async def test_hover_action_includes_position_metadata():
    client = StubClient()
    executor = MCPActionExecutor(client, "session-xyz")

    action = AIAction(
        type="hover",
        target="#menu",
        metadata={"position": {"x": 12, "y": 34}, "timeout_ms": 4000},
    )

    result = await executor.execute(action)

    assert result.success is True
    method, params, timeout = client.calls[-1]
    assert method == "hover"
    assert params["selector"] == "#menu"
    assert params["position"] == {"x": 12.0, "y": 34.0}
    assert params["timeoutMs"] == 4000
    assert timeout == pytest.approx(30.0)


@pytest.mark.asyncio
async def test_check_action_maps_force_flag():
    client = StubClient()
    executor = MCPActionExecutor(client, "session-check")

    action = AIAction(
        type="check",
        target="#agree",
        metadata={"force": True, "timeout_ms": 5000},
    )

    result = await executor.execute(action)

    assert result.success is True
    method, params, _ = client.calls[-1]
    assert method == "check"
    assert params["selector"] == "#agree"
    assert params["force"] is True
    assert params["timeoutMs"] == 5000


def test_fill_action_requires_value():
    client = StubClient()
    executor = MCPActionExecutor(client, "session-123")

    action = AIAction(type="fill", target="#input", value=None)
    with pytest.raises(ActionValidationError):
        executor._build_request(action)


@pytest.mark.asyncio
async def test_unsupported_actions_raise():
    client = StubClient()
    executor = MCPActionExecutor(client, "session-123")

    action = AIAction(type="drag", target="#item")
    result = await executor.execute(action)

    assert result.success is False
    assert result.should_retry is False
    assert "Unsupported action type" in (result.message or "")


@pytest.mark.asyncio
async def test_create_mcp_executor_invokes_cleanup(monkeypatch):
    events: list[str] = []

    class ClientDouble:
        def __init__(self, url: str, request_timeout: float, notification_handler=None) -> None:
            events.append(f"init:{url}:{request_timeout}")
            self._closed = False

        async def connect(self) -> None:
            events.append("connect")

        async def call(self, method: str, params: dict, timeout: float | None = None):
            events.append(f"call:{method}:{params.get('sessionId')}")
            return {"ok": True}

        async def close(self) -> None:
            events.append("close")
            self._closed = True

    monkeypatch.setattr("calico.agent.mcp_executor.MCPClient", ClientDouble)

    executor, cleanup = await create_mcp_executor(
        url="ws://example.test:7001",
        session_id="session-abc",
        request_timeout=5.0,
        max_action_retries=1,
    )

    assert isinstance(executor, MCPActionExecutor)
    assert events[0].startswith("init")

    await cleanup()
    assert "call:close_session:session-abc" in events
    assert events[-1] == "close"