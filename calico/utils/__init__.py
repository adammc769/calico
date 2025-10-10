"""Helper modules for higher-level Playwright workflows."""

from .auth_cookies import AuthCookie, apply_cookies, load_cookies_from_path, save_cookies
from .dom_regions import DEFAULT_REGION, FormRegion, classify_dom_region
from .form_components import collect_form_candidates, collect_form_components, print_form_components
from .fuzzy_forms import MASTER_FORM_DICTIONARY, match_form_field_candidate, select_best_candidates_by_field
from .dom_units import DomUnit, collect_dom_units
from .page_text import collect_page_text, collect_page_text_dicts, print_page_text
from .mcp_planning import submit_plan
from .mcp_profiles import get_profile as mcp_get_profile, list_profiles as mcp_list_profiles, upsert_profile as mcp_upsert_profile
from .session_storage import SessionStorage

__all__ = [
    "AuthCookie",
    "apply_cookies",
    "load_cookies_from_path",
    "save_cookies",
    "DEFAULT_REGION",
    "FormRegion",
    "classify_dom_region",
    "collect_form_candidates",
    "collect_form_components",
    "print_form_components",
    "MASTER_FORM_DICTIONARY",
    "match_form_field_candidate",
    "select_best_candidates_by_field",
    "collect_dom_units",
    "DomUnit",
    "collect_page_text",
    "collect_page_text_dicts",
    "print_page_text",
    "submit_plan",
    "mcp_list_profiles",
    "mcp_get_profile",
    "mcp_upsert_profile",
    "SessionStorage",
]
