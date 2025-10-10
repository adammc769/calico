"""Shared DOM region classification utilities."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Sequence

from playwright.sync_api import ElementHandle

FormRegion = Literal["popup", "header", "footer", "sidebar", "main", "text"]
DEFAULT_REGION: FormRegion = "text"

_POPUP_KEYWORDS = (
    "modal",
    "popup",
    "popover",
    "overlay",
    "dialog",
    "sheet",
    "lightbox",
    "tooltip",
)
_HEADER_KEYWORDS = (
    "header",
    "topbar",
    "masthead",
    "navbar",
    "top-nav",
    "appbar",
    "site-header",
)
_FOOTER_KEYWORDS = (
    "footer",
    "site-footer",
    "bottom",
    "copyright",
)
_SIDEBAR_KEYWORDS = (
    "sidebar",
    "side-bar",
    "sidenav",
    "drawer",
    "rail",
    "offcanvas",
)
_MAIN_KEYWORDS = (
    "main",
    "content",
    "article",
    "primary",
    "body",
    "text",
    "page",
)


def _gather_dom_context(element: ElementHandle) -> Dict[str, Any]:
    return element.evaluate(
        """
        (el) => {
            const ancestors = [];
            let node = el;
            while (node) {
                const getAttr = (attr) =>
                    node.getAttribute ? (node.getAttribute(attr) || "").toLowerCase() : "";
                ancestors.push({
                    tag: (node.tagName || "").toLowerCase(),
                    role: getAttr("role"),
                    id: (node.id || "").toLowerCase(),
                    classList: String(node.className || "").toLowerCase(),
                    ariaModal: getAttr("aria-modal"),
                });
                node = node.parentElement;
            }
            const rect = el.getBoundingClientRect();
            return {
                ancestors,
                rect: {
                    top: rect.top,
                    bottom: rect.bottom,
                    left: rect.left,
                    right: rect.right,
                },
                viewport: {
                    width: window.innerWidth || 0,
                    height: window.innerHeight || 0,
                },
            };
        }
        """
    )


def _combine_identifier(ancestor: Dict[str, Any]) -> str:
    return " ".join(filter(None, [ancestor.get("id"), ancestor.get("classList")])).strip()


def _any_keyword(ancestors: List[Dict[str, Any]], keywords: Sequence[str]) -> bool:
    for ancestor in ancestors:
        identifier = _combine_identifier(ancestor)
        if not identifier:
            continue
        if any(keyword in identifier for keyword in keywords):
            return True
    return False


def _any_tag(ancestors: List[Dict[str, Any]], tags: Sequence[str]) -> bool:
    return any(ancestor.get("tag") in tags for ancestor in ancestors)


def _any_role(ancestors: List[Dict[str, Any]], roles: Sequence[str]) -> bool:
    return any(ancestor.get("role") in roles for ancestor in ancestors)


def _is_near_top(rect: Dict[str, Any], viewport: Dict[str, Any]) -> bool:
    top = rect.get("top")
    if top is None:
        return False
    height = viewport.get("height") or 0
    threshold = max(120, height * 0.15) if height else 120
    return -threshold <= top <= threshold


def _is_near_bottom(rect: Dict[str, Any], viewport: Dict[str, Any]) -> bool:
    bottom = rect.get("bottom")
    if bottom is None:
        return False
    height = viewport.get("height") or 0
    if not height:
        return False
    threshold = max(120, height * 0.15)
    return height - threshold <= bottom <= height + threshold


def _is_near_side(rect: Dict[str, Any], viewport: Dict[str, Any]) -> bool:
    width = viewport.get("width") or 0
    if not width:
        return False
    left = rect.get("left")
    right = rect.get("right")
    threshold = max(160, width * 0.15)
    left_match = left is not None and -threshold <= left <= threshold
    right_match = right is not None and (width - threshold) <= right <= (width + threshold)
    return left_match or right_match


def _is_popup(ancestors: List[Dict[str, Any]]) -> bool:
    for ancestor in ancestors:
        tag = ancestor.get("tag")
        role = ancestor.get("role")
        if ancestor.get("ariaModal") == "true":
            return True
        if tag in {"dialog"}:
            return True
        if role in {"dialog", "alertdialog"}:
            return True
        identifier = _combine_identifier(ancestor)
        if any(keyword in identifier for keyword in _POPUP_KEYWORDS):
            return True
    return False


def _is_header(ancestors: List[Dict[str, Any]], rect: Dict[str, Any], viewport: Dict[str, Any]) -> bool:
    if _any_tag(ancestors, ["header", "nav"]):
        return True
    if _any_role(ancestors, ["banner"]):
        return True
    if _any_keyword(ancestors, _HEADER_KEYWORDS):
        return True
    return _is_near_top(rect, viewport)


def _is_footer(ancestors: List[Dict[str, Any]], rect: Dict[str, Any], viewport: Dict[str, Any]) -> bool:
    if _any_tag(ancestors, ["footer"]):
        return True
    if _any_role(ancestors, ["contentinfo"]):
        return True
    if _any_keyword(ancestors, _FOOTER_KEYWORDS):
        return True
    return _is_near_bottom(rect, viewport)


def _is_sidebar(ancestors: List[Dict[str, Any]], rect: Dict[str, Any], viewport: Dict[str, Any]) -> bool:
    if _any_tag(ancestors, ["aside"]):
        return True
    if _any_role(ancestors, ["complementary", "navigation"]):
        return True
    if _any_keyword(ancestors, _SIDEBAR_KEYWORDS):
        return True
    return _is_near_side(rect, viewport)


def _is_main(ancestors: List[Dict[str, Any]]) -> bool:
    if _any_tag(ancestors, ["main", "article", "section"]):
        return True
    if _any_role(ancestors, ["main"]):
        return True
    return _any_keyword(ancestors, _MAIN_KEYWORDS)


def classify_dom_region(element: ElementHandle) -> FormRegion:
    try:
        context = _gather_dom_context(element)
    except Exception:
        return DEFAULT_REGION

    ancestors = context.get("ancestors") or []
    rect = context.get("rect") or {}
    viewport = context.get("viewport") or {}

    if not ancestors:
        return DEFAULT_REGION

    if _is_popup(ancestors):
        return "popup"
    if _is_header(ancestors, rect, viewport):
        return "header"
    if _is_footer(ancestors, rect, viewport):
        return "footer"
    if _is_sidebar(ancestors, rect, viewport):
        return "sidebar"
    if _is_main(ancestors):
        return "main"
    return DEFAULT_REGION


__all__ = [
    "FormRegion",
    "DEFAULT_REGION",
    "classify_dom_region",
]
