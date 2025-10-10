"""Vision utilities for OCR and visual element recognition."""

from .screenshots import (
    BoundingBox,
    capture_element_screenshot,
    capture_page_clip,
    capture_page_screenshot,
    crop_image_bytes,
)
from .preprocess import (
    PreprocessConfig,
    preprocess_element_image,
    preprocess_image_bytes,
)
from .ocr import (
    OCRAnnotation,
    OCRResult,
    build_vision_client,
    fetch_and_ocr,
    extract_text_with_vision,
    extract_text_with_tesseract,
)
from .ocr_dom_matcher import (
    BoundingBox as OCRBoundingBox,
    OCRDOMMatch,
    OCRDOMMatcher,
    match_ocr_with_dom,
)

__all__ = [
    "BoundingBox",
    "capture_element_screenshot",
    "capture_page_clip",
    "capture_page_screenshot",
    "crop_image_bytes",
    "PreprocessConfig",
    "preprocess_image_bytes",
    "preprocess_element_image",
    "OCRAnnotation",
    "OCRResult",
    "build_vision_client",
    "fetch_and_ocr",
    "extract_text_with_vision",
    "extract_text_with_tesseract",
    "OCRBoundingBox",
    "OCRDOMMatch",
    "OCRDOMMatcher",
    "match_ocr_with_dom",
]
