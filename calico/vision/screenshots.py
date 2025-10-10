"""Screenshot helpers backed by Playwright and Pillow."""
from __future__ import annotations

import math
from dataclasses import dataclass
from io import BytesIO
from typing import Mapping, Optional

from PIL import Image
from playwright.sync_api import ElementHandle, Page


@dataclass
class BoundingBox:
    """Normalized representation of a rectangular region."""

    left: float
    top: float
    width: float
    height: float

    def to_clip(self) -> dict[str, float]:
        """Convert to Playwright clip dictionary."""

        return {
            "x": self.left,
            "y": self.top,
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, float]) -> "BoundingBox":
        """Construct a bounding box from a mapping of coordinates."""

        if not data:
            raise ValueError("bounding_box mapping cannot be empty")

        left = float(data.get("left", data.get("x", 0.0)))
        top = float(data.get("top", data.get("y", 0.0)))

        width = data.get("width")
        height = data.get("height")

        right = data.get("right")
        bottom = data.get("bottom")

        if width is None and right is not None:
            width = float(right) - left
        if height is None and bottom is not None:
            height = float(bottom) - top

        if width is None or height is None:
            raise ValueError("bounding_box mapping must include width/height or right/bottom")

        width = float(width)
        height = float(height)
        if width <= 0 or height <= 0:
            raise ValueError("bounding_box dimensions must be positive")

        return cls(left=left, top=top, width=width, height=height)

    def aligned(self) -> "BoundingBox":
        """Return a bounding box aligned to pixel boundaries."""

        left = math.floor(self.left)
        top = math.floor(self.top)
        right = math.ceil(self.left + self.width)
        bottom = math.ceil(self.top + self.height)

        width = max(1, right - left)
        height = max(1, bottom - top)
        return BoundingBox(left=float(left), top=float(top), width=float(width), height=float(height))


def capture_page_screenshot(
    page: Page,
    *,
    path: Optional[str] = None,
    full_page: bool = True,
    scale: str = "device",
) -> bytes:
    """Capture a screenshot of the current page."""

    return page.screenshot(path=path, full_page=full_page, scale=scale)


def capture_page_clip(
    page: Page,
    bounding_box: BoundingBox,
    *,
    path: Optional[str] = None,
    scale: str = "device",
) -> bytes:
    """Capture a clipped screenshot of the page."""

    return page.screenshot(path=path, clip=bounding_box.to_clip(), scale=scale)


def capture_element_screenshot(
    element: ElementHandle,
    *,
    path: Optional[str] = None,
) -> bytes:
    """Capture a screenshot of a specific element."""

    return element.screenshot(path=path)


def crop_image_bytes(
    image_bytes: bytes,
    bounding_box: BoundingBox,
    *,
    image_format: str = "PNG",
) -> bytes:
    """Crop an in-memory image and return the resulting bytes."""

    aligned_box = bounding_box.aligned()

    with Image.open(BytesIO(image_bytes)) as image:
        left = int(aligned_box.left)
        top = int(aligned_box.top)
        right = int(aligned_box.left + aligned_box.width)
        bottom = int(aligned_box.top + aligned_box.height)
        cropped = image.crop((left, top, right, bottom))
        output = BytesIO()
        cropped.save(output, format=image_format)
        return output.getvalue()
