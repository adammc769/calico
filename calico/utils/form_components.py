"""Utilities for collecting form-related elements with Playwright.

The `collect_form_components` helper is geared toward downstream AI reasoning
pipelines. It walks the document for common form controls and returns a
structure that is straightforward to serialize or feed into LLM prompts. Use
`collect_form_candidates` when you need a reduced JSON payload with just the
salient attributes (``tag``, ``type``, ``id``, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from playwright.sync_api import ElementHandle, Page

from .dom_regions import DEFAULT_REGION, FormRegion, classify_dom_region
from .fuzzy_forms import match_form_field_candidate

CONTROL_SELECTOR = "input, textarea, select, button"
"""CSS selector that targets the most common form elements."""

DEFAULT_CANDIDATE_FIELDS: Sequence[str] = (
    "tag",
    "type",
    "name",
    "id",
    "placeholder",
    "label",
    "autocomplete",
    "data_attributes",
)
"""Default keys returned by :func:`collect_form_candidates`."""


def _extract_label(element: ElementHandle) -> Optional[str]:
    try:
        label_text = element.evaluate(
            """
            (el) => {
                const parts = [];
                if (el.labels && el.labels.length) {
                    for (const label of el.labels) {
                        const text = label.innerText || label.textContent || "";
                        if (text) {
                            parts.push(text.trim());
                        }
                    }
                }
                const ariaLabelledBy = el.getAttribute("aria-labelledby");
                if (ariaLabelledBy) {
                    for (const id of ariaLabelledBy.split(/\\s+/).filter(Boolean)) {
                        const node = document.getElementById(id);
                        if (node) {
                            const text = node.innerText || node.textContent || "";
                            if (text) {
                                parts.push(text.trim());
                            }
                        }
                    }
                }
                if (parts.length) {
                    return parts.join(" ").trim();
                }
                const forId = el.getAttribute("id");
                if (forId) {
                    const label = document.querySelector(`label[for="${forId}"]`);
                    if (label) {
                        const text = label.innerText || label.textContent || "";
                        if (text) {
                            return text.trim();
                        }
                    }
                }
                return "";
            }
            """
        )
    except Exception:
        return None
    if not label_text:
        return None
    label_text = str(label_text).strip()
    return label_text or None


def _extract_value(element: ElementHandle) -> Optional[str]:
    try:
        value = element.evaluate(
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
        return None
    if not value:
        return None
    value = str(value).strip()
    return value or None


def _extract_data_attributes(element: ElementHandle) -> Dict[str, str]:
    try:
        attributes = element.evaluate(
            """
            (el) => {
                const output = {};
                if (!el || !el.getAttributeNames) {
                    return output;
                }
                for (const name of el.getAttributeNames()) {
                    if (name && name.toLowerCase().startsWith("data-")) {
                        output[name] = el.getAttribute(name) || "";
                    }
                }
                return output;
            }
            """
        )
    except Exception:
        return {}

    if not attributes:
        return {}

    return {
        str(key): str(value) if value is not None else ""
        for key, value in attributes.items()
    }

@dataclass
class FormComponent:
    """Lightweight description of a form-oriented DOM element."""

    tag: str
    type: Optional[str]
    name: Optional[str]
    element_id: Optional[str]
    placeholder: Optional[str]
    text: str
    label: Optional[str]
    autocomplete: Optional[str]
    value: Optional[str]
    aria_label: Optional[str]
    aria_labelledby: Optional[str]
    role: Optional[str]
    region: FormRegion = DEFAULT_REGION
    data_attributes: Dict[str, str] = field(default_factory=dict)
    bounding_box: Optional[Dict[str, float]] = None

    @classmethod
    def from_element(
        cls,
        element: ElementHandle,
        *,
        region: Optional[FormRegion] = None,
    ) -> "FormComponent":
        tag = element.evaluate("el => el.tagName")
        text = element.inner_text() or ""
        try:
            bounding_box = element.evaluate(
                """
                (el) => {
                    if (!el || !el.getBoundingClientRect) {
                        return null;
                    }
                    const rect = el.getBoundingClientRect();
                    return {
                        top: rect.top,
                        left: rect.left,
                        right: rect.right,
                        bottom: rect.bottom,
                        width: rect.width,
                        height: rect.height,
                    };
                }
                """
            )
        except Exception:
            bounding_box = None

        return cls(
            tag=tag,
            type=element.get_attribute("type"),
            name=element.get_attribute("name"),
            element_id=element.get_attribute("id"),
            placeholder=element.get_attribute("placeholder"),
            text=text.strip(),
            label=_extract_label(element),
            autocomplete=element.get_attribute("autocomplete"),
            value=_extract_value(element),
            data_attributes=_extract_data_attributes(element),
            aria_label=element.get_attribute("aria-label"),
            aria_labelledby=element.get_attribute("aria-labelledby"),
            role=element.get_attribute("role"),
            region=region or DEFAULT_REGION,
            bounding_box=bounding_box,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_candidate(
        self,
        *,
        fields: Optional[Sequence[str]] = None,
        drop_empty: bool = True,
        include_fuzzy_matches: bool = True,
        fuzzy_score_cutoff: int = 75,
        fuzzy_limit: int = 5,
    fallback_resolver: Optional[Callable[[Dict[str, Any]], Sequence[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """Return a reduced dictionary suitable for downstream reasoning."""

        mapping: Dict[str, Any] = {
            "tag": (self.tag or "").upper(),
            "type": self.type,
            "name": self.name,
            "id": self.element_id,
            "placeholder": self.placeholder,
            "label": self.label,
            "autocomplete": self.autocomplete,
            "text": self.text,
            "value": self.value,
            "data_attributes": self.data_attributes,
            "region": self.region,
            "ariaLabel": self.aria_label,
            "ariaLabelledBy": self.aria_labelledby,
            "role": self.role,
        }

        selected_fields = list(fields or DEFAULT_CANDIDATE_FIELDS)
        if "region" not in selected_fields:
            selected_fields.append("region")

        candidate: Dict[str, Any] = {}

        for key in selected_fields:
            value = mapping.get(key)
            if drop_empty and key != "region" and (
                value is None or (isinstance(value, str) and not value.strip())
            ):
                continue
            if value is not None:
                candidate[key] = value

        candidate["bounding_box"] = self.bounding_box
        if include_fuzzy_matches:
            fuzzy_matches = match_form_field_candidate(
                mapping,
                score_cutoff=fuzzy_score_cutoff,
                limit=fuzzy_limit,
                fallback_resolver=fallback_resolver,
            )
            candidate["fuzzy_matches"] = fuzzy_matches
            if fuzzy_matches:
                best_match = max(fuzzy_matches, key=lambda item: item.get("score", 0.0))
                candidate["canonical_field"] = best_match.get("field")
                candidate["score"] = best_match.get("score", 0.0)
                candidate["score_percent"] = best_match.get(
                    "score_percent",
                    float(best_match.get("score", 0.0)) * 100.0,
                )
                candidate["score_breakdown"] = best_match.get("breakdown", {})
                candidate["score_contributors"] = best_match.get("contributors", [])
                candidate["score_weights_applied"] = best_match.get("weights_applied", 0.0)
            else:
                candidate["score"] = 0.0
                candidate["score_percent"] = 0.0

        return candidate


def collect_form_components(page: Page, selector: str = CONTROL_SELECTOR) -> List[FormComponent]:
    """Return a list of :class:`FormComponent` objects for the given page.

    Parameters
    ----------
    page:
        The Playwright :class:`Page` instance currently in scope.
    selector:
        Optional CSS selector override. Defaults to ``input, textarea, select, button``.

    Returns
    -------
    list of FormComponent
        A stable ordering of discovered controls in DOM tree order.
    """

    element_handles: Iterable[ElementHandle] = page.query_selector_all(selector)
    components: List[FormComponent] = []

    for element in element_handles:
        try:
            region = classify_dom_region(element)
            components.append(FormComponent.from_element(element, region=region))
        except Exception:
            # Ignore elements that disappear between the query and attribute fetch.
            continue

    return components


def print_form_components(page: Page, selector: str = CONTROL_SELECTOR) -> None:
    """Convenience wrapper that prints collected form components as dictionaries."""

    for component in collect_form_components(page, selector=selector):
        print(component.to_dict())


def collect_form_candidates(
    page: Page,
    selector: str = CONTROL_SELECTOR,
    *,
    fields: Optional[Sequence[str]] = None,
    drop_empty: bool = True,
    include_fuzzy_matches: bool = True,
    fuzzy_score_cutoff: int = 75,
    fuzzy_limit: int = 5,
    fallback_resolver: Optional[Callable[[Dict[str, Any]], Sequence[Dict[str, Any]]]] = None,
) -> List[Dict[str, Any]]:
    """Return reduced dictionaries representing likely form controls."""

    candidates: List[Dict[str, Any]] = []

    for component in collect_form_components(page, selector=selector):
        candidate = component.to_candidate(
            fields=fields,
            drop_empty=drop_empty,
            include_fuzzy_matches=include_fuzzy_matches,
            fuzzy_score_cutoff=fuzzy_score_cutoff,
            fuzzy_limit=fuzzy_limit,
            fallback_resolver=fallback_resolver,
        )
        if candidate:
            candidates.append(candidate)

    return candidates
