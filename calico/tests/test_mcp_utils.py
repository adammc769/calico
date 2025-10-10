"""Tests for MCP utility helpers (screenshots, OCR integration, telemetry)."""
from __future__ import annotations

import base64
from io import BytesIO

import pytest
from PIL import Image

from calico.vision.ocr import OCRResult, fetch_and_ocr
from calico.utils.mcp_planning import submit_plan
from calico.utils.mcp_screenshot import fetch_screenshot_bytes, fetch_screenshot_image
from calico.utils.mcp_telemetry import emit_telemetry_event


def _make_png_bytes(size: int = 2) -> bytes:
    image = Image.new("RGB", (size, size), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class ScreenshotClientStub:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.calls: list[tuple[str, dict]] = []

    async def call(self, method: str, params: dict) -> dict:
        self.calls.append((method, params))
        return self._payload


class NotifyClientStub:
    def __init__(self) -> None:
        self.notifications: list[tuple[str, dict]] = []

    async def notify(self, method: str, params: dict) -> None:
        self.notifications.append((method, params))


class PlanClientStub:
    def __init__(self, result: dict) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._result = result

    async def call(self, method: str, params: dict):
        self.calls.append((method, params))
        return self._result


@pytest.mark.asyncio
async def test_fetch_screenshot_bytes_decodes_payload() -> None:
    png_bytes = _make_png_bytes()
    payload = {
        "data": base64.b64encode(png_bytes).decode("ascii"),
        "mimeType": "image/png",
        "encoding": "base64",
        "width": 2,
        "height": 2,
        "timestamp": "2025-01-01T00:00:00Z",
    }
    client = ScreenshotClientStub(payload)

    result_bytes, metadata = await fetch_screenshot_bytes(client, "session-1")

    assert result_bytes == png_bytes
    assert metadata["mimeType"] == "image/png"
    assert client.calls and client.calls[0][0] == "captureScreenshot"


@pytest.mark.asyncio
async def test_fetch_screenshot_image_returns_pillow_image() -> None:
    png_bytes = _make_png_bytes()
    payload = {
        "data": base64.b64encode(png_bytes).decode("ascii"),
        "mimeType": "image/png",
        "encoding": "base64",
        "width": 2,
        "height": 2,
        "timestamp": "2025-01-01T00:00:00Z",
    }
    client = ScreenshotClientStub(payload)

    image, metadata = await fetch_screenshot_image(client, "session-xyz")

    assert isinstance(image, Image.Image)
    assert image.size == (2, 2)
    assert metadata["timestamp"] == "2025-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_fetch_and_ocr_uses_custom_extractor() -> None:
    png_bytes = _make_png_bytes()
    payload = {
        "data": base64.b64encode(png_bytes).decode("ascii"),
        "mimeType": "image/png",
        "encoding": "base64",
        "width": 2,
        "height": 2,
        "timestamp": "2025-01-01T00:00:00Z",
        "clip": {"x": 0.0, "y": 0.0, "width": 2.0, "height": 2.0},
    }
    client = ScreenshotClientStub(payload)

    captured: dict[str, bytes] = {}

    def extractor(data: bytes) -> OCRResult:
        captured["bytes"] = data
        return OCRResult(text="hello", annotations=[])

    result, metadata = await fetch_and_ocr(
        client,
        "session-alpha",
        extractor=extractor,
    )

    assert result.text == "hello"
    assert captured["bytes"] == png_bytes
    assert metadata["clip"]["width"] == 2.0


@pytest.mark.asyncio
async def test_emit_telemetry_event_sends_notification() -> None:
    client = NotifyClientStub()

    payload = await emit_telemetry_event(
        client,
        session_id="session-123",
        kind="action",
        message="clicked",
        data={"selector": "#submit"},
        audience="extension",
        timestamp="2025-01-01T00:00:00Z",
    )

    assert client.notifications
    method, params = client.notifications[0]
    assert method == "telemetry.emit"
    assert params == payload
    assert params["event"]["message"] == "clicked"
    assert params["event"]["timestamp"] == "2025-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_emit_telemetry_event_validates_kind() -> None:
    client = NotifyClientStub()

    with pytest.raises(ValueError):
        await emit_telemetry_event(client, session_id="s", kind="invalid", message="oops")


@pytest.mark.asyncio
async def test_submit_plan_normalizes_commands() -> None:
    result_payload = {"accepted": True, "executedCommands": 2, "plannerNote": "done"}
    client = PlanClientStub(result_payload)

    result = await submit_plan(
        client,
        session_id="session-1",
        profile_id="profile-7",
        commands=[{"command": "click", "params": {"selector": "#a"}}, {"command": "hover"}],
        goal="demo",
        summary="manual plan",
    )

    assert client.calls
    method, params = client.calls[0]
    assert method == "submitPlan"
    assert params["sessionId"] == "session-1"
    assert params["profileId"] == "profile-7"
    assert len(params["commands"]) == 2
    assert params["commands"][0]["command"] == "click"
    assert params["commands"][1]["command"] == "hover"
    assert result == result_payload


@pytest.mark.asyncio
async def test_submit_plan_requires_commands() -> None:
    client = PlanClientStub({})

    with pytest.raises(ValueError):
        await submit_plan(client, session_id="s", profile_id="p", commands=[])
