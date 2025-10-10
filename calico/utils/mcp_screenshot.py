"""Helpers for requesting screenshots from the MCP service."""
from __future__ import annotations

import base64
from io import BytesIO
from typing import Mapping, Tuple

from PIL import Image

from calico.utils.mcp_client import MCPClient
from calico.utils.mcp_contracts import ClipRegion, ScreenshotRequestParams, ScreenshotResult

__all__ = [
    "request_screenshot",
    "fetch_screenshot_bytes",
    "fetch_screenshot_image",
]


def _coerce_clip(clip: Mapping[str, float]) -> ClipRegion:
    x = clip.get("x", clip.get("left"))
    y = clip.get("y", clip.get("top"))
    width = clip.get("width")
    height = clip.get("height")
    right = clip.get("right")
    bottom = clip.get("bottom")

    if x is None:
        raise ValueError("clip mapping must include 'x' or 'left'")
    if y is None:
        raise ValueError("clip mapping must include 'y' or 'top'")

    if width is None and right is not None:
        width = float(right) - float(x)
    if height is None and bottom is not None:
        height = float(bottom) - float(y)

    if width is None or height is None:
        raise ValueError("clip mapping must include width/height or right/bottom")

    return {
        "x": float(x),
        "y": float(y),
        "width": float(width),
        "height": float(height),
    }


def _build_params(
    session_id: str,
    *,
    selector: str | None,
    clip: Mapping[str, float] | None,
    full_page: bool | None,
    omit_background: bool | None,
    scale: str | None,
    image_format: str,
    quality: int | None,
) -> ScreenshotRequestParams:
    params: ScreenshotRequestParams = {
        "sessionId": session_id,
        "format": image_format,
    }
    if selector:
        params["selector"] = selector
    if clip:
        params["clip"] = _coerce_clip(clip)
    if full_page is not None:
        params["fullPage"] = full_page
    if omit_background is not None:
        params["omitBackground"] = omit_background
    if scale:
        params["scale"] = scale  # type: ignore[assignment]
    if quality is not None:
        params["quality"] = int(quality)
    return params


async def request_screenshot(
    client: MCPClient,
    session_id: str,
    *,
    selector: str | None = None,
    clip: Mapping[str, float] | None = None,
    full_page: bool | None = None,
    omit_background: bool | None = None,
    scale: str | None = "device",
    image_format: str = "png",
    quality: int | None = None,
) -> ScreenshotResult:
    """Call the MCP ``captureScreenshot`` method and return the raw payload."""

    if image_format not in {"png", "jpeg"}:
        raise ValueError("image_format must be 'png' or 'jpeg'")
    if scale and scale not in {"device", "css"}:
        raise ValueError("scale must be 'device' or 'css'")

    params = _build_params(
        session_id,
        selector=selector,
        clip=clip,
        full_page=full_page,
        omit_background=omit_background,
        scale=scale,
        image_format=image_format,
        quality=quality,
    )
    result = await client.call("captureScreenshot", params)
    if not isinstance(result, dict) or "data" not in result:
        raise ValueError("captureScreenshot returned an unexpected payload")
    return result  # type: ignore[return-value]


async def fetch_screenshot_bytes(
    client: MCPClient,
    session_id: str,
    **kwargs,
) -> Tuple[bytes, ScreenshotResult]:
    """Return the decoded bytes for an MCP screenshot response."""

    result = await request_screenshot(client, session_id, **kwargs)
    data = result.get("data")
    if not isinstance(data, str):
        raise ValueError("screenshot payload did not include base64 data")
    image_bytes = base64.b64decode(data)
    return image_bytes, result


async def fetch_screenshot_image(
    client: MCPClient,
    session_id: str,
    **kwargs,
) -> Tuple[Image.Image, ScreenshotResult]:
    """Return a Pillow image decoded from an MCP screenshot response."""

    image_bytes, result = await fetch_screenshot_bytes(client, session_id, **kwargs)
    image = Image.open(BytesIO(image_bytes))
    image.load()
    return image, result
