"""Utilities for extracting text content from the DOM for context reasoning."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from playwright.sync_api import ElementHandle, Page

from .dom_regions import DEFAULT_REGION, FormRegion, classify_dom_region

TEXT_SELECTOR = (
	"h1, h2, h3, h4, h5, h6, "
	"p, li, dt, dd, blockquote, code, pre, "
	"label, legend, caption, summary, "
	"button, a[role='button'], [role='heading'], [role='alert'], [role='status']"
)
"""CSS selector that targets common textual elements for page understanding."""

FORM_VALUE_SELECTOR = "input, textarea, select"
"""CSS selector used to capture text currently present in form controls."""

@dataclass
class TextChunk:
    """Structured representation of visible text content.

    The ``source`` field indicates whether the text came from a DOM node's visible
    text content (``"node"``) or from the current value of a form control
    (``"controlValue"``).
    """

    tag: str
    text: str
    region: FormRegion = DEFAULT_REGION
    role: Optional[str] = None
    aria_label: Optional[str] = None
    source: str = "node"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _extract_text(element: ElementHandle) -> str:
    text = (element.inner_text() or "").strip()
    if text:
        return text
    text_content = element.text_content()
    if text_content:
        return text_content.strip()
    return ""


def collect_page_text(
    page: Page,
    selector: str = TEXT_SELECTOR,
    *,
    min_length: int = 1,
    drop_duplicates: bool = True,
    include_empty: bool = False,
    include_form_values: bool = True,
) -> List[TextChunk]:
    """Collect textual DOM nodes for page understanding.

    Parameters
    ----------
    page:
        Playwright page to scrape.
    selector:
        CSS selector for candidate text elements.
    min_length:
        Minimum length for text to be included (after stripping).
    drop_duplicates:
        Skip duplicate text entries when true.
    include_empty:
        When true, include nodes that fail the length check (useful for debugging).
    include_form_values:
        When true (default), surface the current value of ``input``, ``textarea``, and
        ``select`` elements as additional text chunks.
    """

    handles: Iterable[ElementHandle] = page.query_selector_all(selector)
    chunks: List[TextChunk] = []
    seen: Set[Tuple[str, str, FormRegion, str]] = set()

    for element in handles:
        try:
            text = _extract_text(element)
            if not text and not include_empty:
                continue
            if len(text) < min_length and not include_empty:
                continue

            region = classify_dom_region(element)
            tag = (element.evaluate("el => el.tagName") or "").upper()
            role = element.get_attribute("role")
            aria_label = element.get_attribute("aria-label")

            signature = (text, tag, region, "node")
            if drop_duplicates and signature in seen:
                continue
            seen.add(signature)

            chunks.append(
                TextChunk(
                    tag=tag or "",
                    text=text,
                    region=region,
                    role=role,
                    aria_label=aria_label,
                    source="node",
                )
            )
        except Exception:
            continue

    if include_form_values:
        controls: Iterable[ElementHandle] = page.query_selector_all(FORM_VALUE_SELECTOR)
        for control in controls:
            try:
                value = control.evaluate(
                    """
                    (el) => {
                        const tagName = (el.tagName || "").toUpperCase();
                        if (tagName === "INPUT" || tagName === "TEXTAREA") {
                            return el.value || "";
                        }
                        if (tagName === "SELECT") {
                            if (el.selectedOptions && el.selectedOptions.length) {
                                return Array.from(el.selectedOptions)
                                    .map(option => (option.innerText || option.textContent || "").trim())
                                    .filter(Boolean)
                                    .join(" ");
                            }
                            return el.value || "";
                        }
                        return "";
                    }
                    """
                )
            except Exception:
                continue

            if not value and not include_empty:
                continue
            value_str = (value or "").strip()
            if not value_str and not include_empty:
                continue
            if len(value_str) < min_length and not include_empty:
                continue

            try:
                region = classify_dom_region(control)
            except Exception:
                region = DEFAULT_REGION

            tag = (control.evaluate("el => el.tagName") or "").upper()
            role = control.get_attribute("role")
            aria_label = control.get_attribute("aria-label")

            signature = (value_str, tag, region, "controlValue")
            if drop_duplicates and signature in seen:
                continue
            seen.add(signature)

            chunks.append(
                TextChunk(
                    tag=tag or "",
                    text=value_str,
                    region=region,
                    role=role,
                    aria_label=aria_label,
                    source="controlValue",
                )
            )

    return chunks


def collect_page_text_dicts(**kwargs: Any) -> List[Dict[str, Any]]:
    """Wrapper returning dictionaries instead of dataclasses."""

    return [chunk.to_dict() for chunk in collect_page_text(**kwargs)]


def print_page_text(page: Page, **kwargs: Any) -> None:
    """Convenience helper to print collected text chunks."""

    for chunk in collect_page_text(page, **kwargs):
        print(chunk.to_dict())
