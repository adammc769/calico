"""Unit tests for vision helpers that do not require external services."""
from __future__ import annotations

from io import BytesIO

import math
from PIL import Image

from calico.vision import (
    BoundingBox,
    PreprocessConfig,
    crop_image_bytes,
    preprocess_element_image,
    preprocess_image_bytes,
)


def _create_sample_image(size: int = 10) -> bytes:
    image = Image.new("RGB", (size, size), color="white")
    for x in range(size):
        for y in range(size):
            if x < size // 2 and y < size // 2:
                image.putpixel((x, y), (255, 0, 0))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_bounding_box_to_clip() -> None:
    box = BoundingBox(left=1.5, top=2.5, width=50.0, height=75.0)
    clip = box.to_clip()
    assert clip == {"x": 1.5, "y": 2.5, "width": 50.0, "height": 75.0}


def test_bounding_box_from_mapping_and_alignment() -> None:
    mapping = {"left": 10.2, "top": 5.7, "right": 25.0, "bottom": 18.9}
    box = BoundingBox.from_mapping(mapping)
    assert math.isclose(box.left, 10.2)
    assert math.isclose(box.top, 5.7)
    assert math.isclose(box.width, 14.8)
    assert math.isclose(box.height, 13.2)

    aligned = box.aligned()
    assert aligned.left == 10.0
    assert aligned.top == 5.0
    assert aligned.width == 15.0
    assert aligned.height == 14.0


def test_crop_image_bytes() -> None:
    image_bytes = _create_sample_image()
    box = BoundingBox(left=0, top=0, width=5, height=5)
    cropped_bytes = crop_image_bytes(image_bytes, box)
    with Image.open(BytesIO(cropped_bytes)) as cropped:
        assert cropped.size == (5, 5)
        assert cropped.getpixel((0, 0)) == (255, 0, 0)
        assert cropped.getpixel((4, 4)) == (255, 0, 0)


def test_preprocess_image_bytes_thresholding_and_scaling() -> None:
    image = Image.new("L", (4, 4))
    for x in range(4):
        for y in range(4):
            image.putpixel((x, y), 200 if (x + y) % 2 == 0 else 50)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    processed = preprocess_image_bytes(buffer.getvalue(), config=PreprocessConfig(threshold=128, scale=2.0))

    with Image.open(BytesIO(processed)) as result:
        assert result.size == (8, 8)
        unique_values = set(result.getdata())
        assert unique_values.issubset({0, 255})


def test_preprocess_element_image_uses_bounding_box() -> None:
    base = Image.new("L", (10, 10), color=0)
    for x in range(2, 8):
        for y in range(2, 8):
            base.putpixel((x, y), 220)
    buffer = BytesIO()
    base.save(buffer, format="PNG")

    bbox = {"left": 2.3, "top": 2.1, "width": 4.6, "height": 5.4}
    processed = preprocess_element_image(buffer.getvalue(), bbox, config=PreprocessConfig(scale=1.0))

    with Image.open(BytesIO(processed)) as result:
        assert result.size == (5, 6)
        assert result.getpixel((0, 0)) == 255
        assert result.getpixel((result.width - 1, result.height - 1)) == 255
