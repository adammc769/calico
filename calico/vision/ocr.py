"""OCR helpers leveraging Google Cloud Vision and pytesseract."""
from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Callable, Iterable, List, Mapping, Optional, Tuple

from PIL import Image

try:  # pragma: no cover - optional dependency resolution
    from google.cloud import vision
except ImportError:  # pragma: no cover - handled gracefully at runtime
    vision = None

try:  # pragma: no cover - optional dependency resolution
    import pytesseract
except ImportError:  # pragma: no cover - handled gracefully at runtime
    pytesseract = None

from .preprocess import PreprocessConfig, preprocess_element_image, preprocess_image_bytes
from calico.utils.mcp_client import MCPClient
from calico.utils.mcp_contracts import ScreenshotResult
from calico.utils.mcp_screenshot import fetch_screenshot_bytes


@dataclass
class OCRAnnotation:
    """Fine-grained OCR result with text and bounding polygon."""

    description: str
    bounding_poly: Optional[List[dict]] = None
    confidence: Optional[float] = None


@dataclass
class OCRResult:
    """Top-level OCR result containing full text and annotations."""

    text: str
    annotations: List[OCRAnnotation] = field(default_factory=list)


def build_vision_client() -> Any:
    """Construct a Google Cloud Vision client using application credentials."""

    if vision is None:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "google-cloud-vision is not installed. Install it via requirements.txt to use this helper."
        )
    return vision.ImageAnnotatorClient()


def _parse_vision_response(response: Any) -> OCRResult:
    text = response.full_text_annotation.text if response.full_text_annotation else ""
    annotations: List[OCRAnnotation] = []
    for annotation in response.text_annotations:
        bounding_poly = None
        if annotation.bounding_poly and annotation.bounding_poly.vertices:
            bounding_poly = [
                {"x": vertex.x or 0, "y": vertex.y or 0}
                for vertex in annotation.bounding_poly.vertices
            ]
        annotations.append(
            OCRAnnotation(
                description=annotation.description or "",
                bounding_poly=bounding_poly,
                confidence=annotation.confidence if hasattr(annotation, "confidence") else None,
            )
        )
    return OCRResult(text=text.strip(), annotations=annotations)


def extract_text_with_vision(
    image_bytes: bytes,
    *,
    client: Optional[Any] = None,
    language_hints: Optional[Iterable[str]] = None,
    bounding_box: Optional[Mapping[str, float]] = None,
    preprocess_config: Optional[PreprocessConfig] = None,
) -> OCRResult:
    """Run text detection using Google Cloud Vision.

    When ``bounding_box`` is provided, the image bytes are treated as a full-page
    screenshot. The screenshot is cropped to the specified region, preprocessed,
    and then submitted to the Vision API. If only ``preprocess_config`` is
    provided, preprocessing is applied to the supplied image bytes without
    cropping.
    """

    if vision is None:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "google-cloud-vision is not installed. Install it via requirements.txt to use this helper."
        )
    if client is None:
        client = build_vision_client()

    payload_bytes = image_bytes
    if bounding_box is not None:
        payload_bytes = preprocess_element_image(image_bytes, bounding_box, config=preprocess_config)
    elif preprocess_config is not None:
        payload_bytes = preprocess_image_bytes(image_bytes, config=preprocess_config)

    image = vision.Image(content=payload_bytes)
    image_context = None
    if language_hints:
        image_context = {"language_hints": list(language_hints)}

    response = client.text_detection(image=image, image_context=image_context)
    if response.error.message:
        raise RuntimeError(f"Vision API error: {response.error.message}")

    return _parse_vision_response(response)


def extract_text_with_tesseract(
    image_bytes: bytes,
    *,
    lang: str = "eng",
    config: Optional[str] = None,
    bounding_box: Optional[Mapping[str, float]] = None,
    preprocess_config: Optional[PreprocessConfig] = None,
) -> OCRResult:
    """Run OCR using pytesseract as a local fallback.

    Supports optional preprocessing and element-level cropping. When
    ``bounding_box`` is provided the input bytes are treated as a page
    screenshot and are cropped and preprocessed before recognition.
    """

    if pytesseract is None:  # pragma: no cover - optional dependency
        raise RuntimeError("pytesseract is not installed. Install it to use the fallback OCR helper.")

    payload_bytes = image_bytes
    if bounding_box is not None:
        payload_bytes = preprocess_element_image(image_bytes, bounding_box, config=preprocess_config)
    elif preprocess_config is not None:
        payload_bytes = preprocess_image_bytes(image_bytes, config=preprocess_config)

    with Image.open(BytesIO(payload_bytes)) as image:
        text = pytesseract.image_to_string(image, lang=lang, config=config or "")

    return OCRResult(text=text.strip())


def _clip_to_bounding_box(clip: Mapping[str, float]) -> Optional[Mapping[str, float]]:
    left = clip.get("left", clip.get("x"))
    top = clip.get("top", clip.get("y"))
    width = clip.get("width")
    height = clip.get("height")
    right = clip.get("right")
    bottom = clip.get("bottom")

    if left is None or top is None:
        return None

    if width is None and right is not None:
        width = float(right) - float(left)
    if height is None and bottom is not None:
        height = float(bottom) - float(top)

    if width is None or height is None:
        return None

    return {
        "left": float(left),
        "top": float(top),
        "width": float(width),
        "height": float(height),
    }


async def fetch_and_ocr(
    client: MCPClient,
    session_id: str,
    *,
    selector: Optional[str] = None,
    clip: Optional[Mapping[str, float]] = None,
    backend: str = "tesseract",
    preprocess_config: Optional[PreprocessConfig] = None,
    language_hints: Optional[Iterable[str]] = None,
    vision_client: Optional[Any] = None,
    tesseract_lang: str = "eng",
    tesseract_config: Optional[str] = None,
    bounding_box: Optional[Mapping[str, float]] = None,
    extractor: Optional[Callable[[bytes], OCRResult]] = None,
) -> Tuple[OCRResult, ScreenshotResult]:
    """Fetch a screenshot via MCP and run OCR against it.

    Parameters
    ----------
    client:
        Connected :class:`~calico.utils.mcp_client.MCPClient` instance.
    session_id:
        MCP session identifier used when Calico created the executor.
    selector:
        Optional CSS selector to target before capturing the screenshot.
    clip:
        Optional clip rectangle in Playwright coordinates.
    backend:
        OCR backend to use when ``extractor`` is not provided. Supported
        values are ``"vision"`` (Google Cloud Vision) and ``"tesseract"``.
    preprocess_config:
        Optional preprocessing configuration applied before OCR.
    language_hints:
        Language hints forwarded to Google Vision when ``backend="vision"``.
    vision_client:
        Optional pre-existing Vision client instance.
    tesseract_lang:
        Language passed to pytesseract when ``backend="tesseract"``.
    tesseract_config:
        Additional pytesseract configuration string.
    bounding_box:
        When provided, crop the screenshot to this bounding box before OCR.
        Falls back to ``clip`` if available.
    extractor:
        Custom callable that receives the screenshot bytes and returns an
        :class:`OCRResult`. When provided, ``backend`` is ignored.

    Returns
    -------
    Tuple[OCRResult, ScreenshotResult]
        The OCR output and the raw screenshot metadata returned by MCP.
    """

    screenshot_bytes, screenshot_payload = await fetch_screenshot_bytes(
        client,
        session_id,
        selector=selector,
        clip=clip,
        full_page=False if clip or selector else None,
    )

    effective_bbox: Optional[Mapping[str, float]] = bounding_box
    returned_clip = screenshot_payload.get("clip")
    if effective_bbox is None and isinstance(returned_clip, MappingABC):
        effective_bbox = _clip_to_bounding_box(returned_clip)
    if effective_bbox is None and clip is not None:
        effective_bbox = _clip_to_bounding_box(clip)

    if extractor is not None:
        result = extractor(screenshot_bytes)
    else:
        if backend == "vision":
            result = extract_text_with_vision(
                screenshot_bytes,
                client=vision_client,
                language_hints=language_hints,
                bounding_box=effective_bbox,
                preprocess_config=preprocess_config,
            )
        elif backend == "tesseract":
            result = extract_text_with_tesseract(
                screenshot_bytes,
                lang=tesseract_lang,
                config=tesseract_config,
                bounding_box=effective_bbox,
                preprocess_config=preprocess_config,
            )
        else:
            raise ValueError(f"Unsupported OCR backend: {backend}")

    return result, screenshot_payload
