"""Image preprocessing utilities for OCR pipelines."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Mapping, Optional

from PIL import Image, ImageFilter, ImageOps

from .screenshots import BoundingBox, crop_image_bytes


@dataclass(slots=True)
class PreprocessConfig:
    """Configuration knobs for OCR-oriented image preprocessing."""

    threshold: int = 160
    scale: float = 2.0
    denoise: bool = True
    grayscale: bool = True

    def validate(self) -> None:
        if not (0 <= self.threshold <= 255):
            raise ValueError("threshold must be in [0, 255]")
        if self.scale <= 0:
            raise ValueError("scale must be positive")


def preprocess_image_bytes(image_bytes: bytes, *, config: Optional[PreprocessConfig] = None) -> bytes:
    """Apply denoising, resizing, and thresholding to raw image bytes."""

    cfg = config or PreprocessConfig()
    cfg.validate()

    with Image.open(BytesIO(image_bytes)) as image:
        working = image.convert("L") if cfg.grayscale else image.copy()

        if cfg.denoise:
            working = working.filter(ImageFilter.MedianFilter(size=3))

        if cfg.scale and cfg.scale != 1.0:
            new_size = (
                max(1, int(round(working.width * cfg.scale))),
                max(1, int(round(working.height * cfg.scale))),
            )
            working = working.resize(new_size, resample=Image.LANCZOS)

        if cfg.grayscale:
            working = ImageOps.autocontrast(working)

        # Apply binary thresholding while keeping grayscale output for OCR compatibility
        def _threshold(pixel: int) -> int:
            return 255 if pixel >= cfg.threshold else 0

        if working.mode != "L":
            working = working.convert("L")
        working = working.point(_threshold, mode="L")

        output = BytesIO()
        working.save(output, format="PNG")
        return output.getvalue()


def preprocess_element_image(
    page_image_bytes: bytes,
    bounding_box: Mapping[str, float],
    *,
    config: Optional[PreprocessConfig] = None,
) -> bytes:
    """Crop a page screenshot to an element bounding box and preprocess the result."""

    box = BoundingBox.from_mapping(bounding_box)
    cropped_bytes = crop_image_bytes(page_image_bytes, box)
    return preprocess_image_bytes(cropped_bytes, config=config)