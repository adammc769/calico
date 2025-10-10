"""Utilities for grouping related DOM elements into structured units."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from playwright.sync_api import ElementHandle, Page

from .dom_regions import DEFAULT_REGION, FormRegion, classify_dom_region
from .form_components import CONTROL_SELECTOR, FormComponent
from .fuzzy_forms import select_best_candidates_by_field
from .page_text import TEXT_SELECTOR, TextChunk
from .site_patterns import get_product_selectors_for_url

_UNIT_BASE_SELECTORS: Tuple[str, ...] = (
    "form",
    "fieldset",
    "article",
    "section",
    "main",
    "aside",
    "header",
    "footer",
    "li",
    "tr",
    "table",
)

_CONTAINER_KEYWORDS: Tuple[str, ...] = (
    "card",
    "tile",
    "result",
    "listing",
    "job",
    "item",
    "entry",
    "module",
    "panel",
    "wrap",
    "group",
    "container",
    "box",
    "row",
    "column",
    "col-",
)

_DATA_ATTR_KEYWORDS: Tuple[str, ...] = (
    "card",
    "result",
    "tile",
    "job",
    "listing",
    "item",
    "entry",
)

_ROLE_KEYWORDS: Tuple[str, ...] = (
    "group",
    "region",
    "list",
    "listitem",
    "article",
    "row",
    "tabpanel",
)

_UNIT_SELECTOR = ", ".join(
    list(_UNIT_BASE_SELECTORS)
    + [f"div[class*='{kw}']" for kw in _CONTAINER_KEYWORDS]
    + [f"div[class*='{kw.upper()}']" for kw in _CONTAINER_KEYWORDS]
    + [f"div[data-testid*='{kw}']" for kw in _DATA_ATTR_KEYWORDS]
    + [f"div[data-test*='{kw}']" for kw in _DATA_ATTR_KEYWORDS]
    + [f"[role='{role}']" for role in _ROLE_KEYWORDS]
)

_FORM_VALUE_SELECTOR = "input, textarea, select"


@dataclass
class DomUnit:
    """Structured representation of a logical DOM unit.

    A unit bundles together container metadata, contextual text, and any form
    components nested beneath the container. This is well-suited to downstream
    automation that needs to reason about "cards" or grouped records (jobs,
    search results, etc.).
    """

    tag: str
    unit_type: str
    element_id: Optional[str]
    classes: List[str] = field(default_factory=list)
    role: Optional[str] = None
    aria_label: Optional[str] = None
    aria_labelledby: Optional[str] = None
    data_attributes: Dict[str, str] = field(default_factory=dict)
    region: FormRegion = DEFAULT_REGION
    text_summary: Optional[str] = None
    bounding_box: Optional[Dict[str, float]] = None
    text_chunks: List[TextChunk] = field(default_factory=list)
    form_components: List[FormComponent] = field(default_factory=list)
    form_candidates: List[Dict[str, Any]] = field(default_factory=list)
    form_field_rankings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tag": self.tag,
            "unit_type": self.unit_type,
            "id": self.element_id,
            "classes": self.classes,
            "role": self.role,
            "aria_label": self.aria_label,
            "aria_labelledby": self.aria_labelledby,
            "data_attributes": self.data_attributes,
            "region": self.region,
            "text_summary": self.text_summary,
            "bounding_box": self.bounding_box,
            "text_chunks": [chunk.to_dict() for chunk in self.text_chunks],
            "form_components": [component.to_dict() for component in self.form_components],
            "form_candidates": self.form_candidates,
            "form_field_rankings": self.form_field_rankings,
        }


def _gather_element_metadata(element: ElementHandle) -> Dict[str, Any]:
    try:
        return element.evaluate(
            """
            (el) => {
                const attrNames = el.getAttributeNames ? el.getAttributeNames() : [];
                const dataAttrs = {};
                const attrs = {};
                for (const name of attrNames) {
                    const value = el.getAttribute(name) || "";
                    attrs[name] = value;
                    if (name && name.toLowerCase().startsWith("data-")) {
                        dataAttrs[name] = value;
                    }
                }
                const rect = el.getBoundingClientRect();
                return {
                    tag: (el.tagName || "").toLowerCase(),
                    id: el.id || "",
                    classes: Array.from(el.classList || []),
                    role: el.getAttribute("role") || "",
                    ariaLabel: el.getAttribute("aria-label") || "",
                    ariaLabelledBy: el.getAttribute("aria-labelledby") || "",
                    dataAttributes: dataAttrs,
                    attributes: attrs,
                    boundingBox: {
                        x: rect.left,  // x coordinate for OCR matching
                        y: rect.top,   // y coordinate for OCR matching
                        top: rect.top,
                        left: rect.left,
                        right: rect.right,
                        bottom: rect.bottom,
                        width: rect.width,
                        height: rect.height,
                    },
                };
            }
            """
        )
    except Exception:
        return {
            "tag": "",
            "id": "",
            "classes": [],
            "role": "",
            "ariaLabel": "",
            "ariaLabelledBy": "",
            "dataAttributes": {},
            "attributes": {},
            "boundingBox": None,
        }


def _extract_text_summary(element: ElementHandle, *, limit: Optional[int]) -> Optional[str]:
    try:
        raw_text = element.inner_text() or ""
    except Exception:
        return None
    text = raw_text.strip()
    if not text:
        return None
    if limit is not None and len(text) > limit:
        return text[: limit].rstrip() + "…"
    return text


def _collect_text_chunks_within(
    element: ElementHandle,
    *,
    selector: str,
    min_length: int,
    drop_duplicates: bool,
    include_empty: bool,
    include_form_values: bool,
) -> List[TextChunk]:
    handles: Iterable[ElementHandle] = element.query_selector_all(selector)
    chunks: List[TextChunk] = []
    seen: set[Tuple[str, str, FormRegion, str]] = set()
    for handle in handles:
        try:
            text = (handle.inner_text() or "").strip()
            if not text and not include_empty:
                continue
            if len(text) < min_length and not include_empty:
                continue
            region = classify_dom_region(handle)
            tag = (handle.evaluate("el => el.tagName") or "").upper()
            role = handle.get_attribute("role")
            aria_label = handle.get_attribute("aria-label")
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
        controls: Iterable[ElementHandle] = element.query_selector_all(_FORM_VALUE_SELECTOR)
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


def _collect_form_components_within(element: ElementHandle) -> List[FormComponent]:
    handles: Iterable[ElementHandle] = element.query_selector_all(CONTROL_SELECTOR)
    components: List[FormComponent] = []
    for handle in handles:
        try:
            region = classify_dom_region(handle)
            components.append(FormComponent.from_element(handle, region=region))
        except Exception:
            continue
    return components


def _infer_unit_type(tag: str, classes: List[str], role: Optional[str]) -> str:
    lowered_classes = [cls.lower() for cls in classes]
    if tag == "tr":
        return "table-row"
    if tag == "table":
        return "table"
    if tag == "li":
        return "list-item"
    if tag == "form":
        return "form"
    if tag == "fieldset":
        return "form-section"
    if tag == "article":
        return "article"
    if tag == "section":
        return "section"
    if tag in {"header", "footer", "aside"}:
        return tag
    if role in {"group", "region", "listitem", "article"}:
        return role
    if any(keyword in cls for cls in lowered_classes for keyword in _CONTAINER_KEYWORDS):
        return "card"
    return "container"


def _looks_like_unit(metadata: Dict[str, Any]) -> bool:
    tag = metadata.get("tag", "")
    role = metadata.get("role") or ""
    classes: List[str] = metadata.get("classes") or []

    if tag in {"form", "fieldset", "article", "section", "main", "aside", "header", "footer", "li", "tr", "table"}:
        return True
    if role in _ROLE_KEYWORDS:
        return True
    lowered_classes = [cls.lower() for cls in classes]
    for keyword in _CONTAINER_KEYWORDS:
        if any(keyword in cls for cls in lowered_classes):
            return True
    if metadata.get("dataAttributes"):
        # If an element carries any data attributes, it's often a logical unit wrapper.
        return True
    return False


def collect_dom_units(
    page: Page,
    *,
    include_text_summary: bool = True,
    include_text_chunks: bool = True,
    include_form_components: bool = True,
    include_form_candidates: bool = True,
    text_selector: str = TEXT_SELECTOR,
    min_text_length: int = 1,
    drop_duplicate_text: bool = True,
    include_empty_text: bool = False,
    include_control_values: bool = True,
    candidate_fields: Optional[Sequence[str]] = None,
    drop_empty_candidates: bool = True,
    include_fuzzy_matches: bool = True,
    fuzzy_score_cutoff: int = 75,
    fuzzy_limit: int = 5,
    fuzzy_fallback_resolver: Optional[Callable[[Dict[str, Any]], Sequence[Dict[str, Any]]]] = None,
    ambiguity_resolver: Optional[Callable[[str, Sequence[Tuple[int, Dict[str, Any], Dict[str, Any]]]], Optional[int]]] = None,
    unknown_field_resolver: Optional[Callable[[Sequence[Tuple[int, Dict[str, Any]]]], Sequence[Dict[str, Any]]]] = None,
    field_score_tolerance: float = 0.05,
    text_summary_limit: Optional[int] = 2000,
    limit: Optional[int] = None,
) -> List[DomUnit]:
    """Collect logical DOM units with optional text and form metadata."""

    # Build selector with site-specific patterns
    current_url = page.url
    site_selectors = get_product_selectors_for_url(current_url)
    
    # Combine base selector with site-specific selectors
    if site_selectors:
        combined_selector = _UNIT_SELECTOR + ", " + ", ".join(site_selectors)
    else:
        combined_selector = _UNIT_SELECTOR
    
    candidate_elements: Iterable[ElementHandle] = page.query_selector_all(combined_selector)
    units: List[DomUnit] = []
    for element in candidate_elements:
        metadata = _gather_element_metadata(element)
        if not _looks_like_unit(metadata):
            continue

        region = classify_dom_region(element)
        tag = (metadata.get("tag") or "").upper() or (element.evaluate("el => el.tagName") or "").upper()
        unit_type = _infer_unit_type(metadata.get("tag", ""), metadata.get("classes", []), metadata.get("role"))
        text_summary: Optional[str] = None
        text_chunks: List[TextChunk] = []
        if include_text_summary:
            text_summary = _extract_text_summary(element, limit=text_summary_limit)
        if include_text_chunks:
            text_chunks = _collect_text_chunks_within(
                element,
                selector=text_selector,
                min_length=min_text_length,
                drop_duplicates=drop_duplicate_text,
                include_empty=include_empty_text,
                include_form_values=include_control_values,
            )

        form_components: List[FormComponent] = []
        form_candidates: List[Dict[str, Any]] = []
        field_rankings: Dict[str, Any] = {}
        if include_form_components or include_form_candidates:
            form_components = _collect_form_components_within(element) if include_form_components or include_form_candidates else []
            if include_form_candidates:
                for component in form_components:
                    candidate = component.to_candidate(
                        fields=candidate_fields,
                        drop_empty=drop_empty_candidates,
                        include_fuzzy_matches=include_fuzzy_matches,
                        fuzzy_score_cutoff=fuzzy_score_cutoff,
                        fuzzy_limit=fuzzy_limit,
                        fallback_resolver=fuzzy_fallback_resolver,
                    )
                    if candidate:
                        form_candidates.append(candidate)
                if include_fuzzy_matches and form_candidates:
                    field_rankings = select_best_candidates_by_field(
                        form_candidates,
                        resolver=ambiguity_resolver,
                        unknown_field_resolver=unknown_field_resolver,
                        score_tolerance=field_score_tolerance,
                    )
            if not include_form_components:
                form_components = []

        unit = DomUnit(
            tag=tag,
            unit_type=unit_type,
            element_id=metadata.get("id") or None,
            classes=metadata.get("classes") or [],
            role=metadata.get("role") or None,
            aria_label=metadata.get("ariaLabel") or None,
            aria_labelledby=metadata.get("ariaLabelledBy") or None,
            data_attributes=metadata.get("dataAttributes") or {},
            region=region,
            text_summary=text_summary,
            bounding_box=metadata.get("boundingBox"),
            text_chunks=text_chunks,
            form_components=form_components,
            form_candidates=form_candidates,
            form_field_rankings=field_rankings,
        )
        units.append(unit)
        if limit is not None and len(units) >= limit:
            break
    return units


__all__ = [
    "DomUnit",
    "collect_dom_units",
]
