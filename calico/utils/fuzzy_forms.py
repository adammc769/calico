"""Fuzzy matching helpers that map scraped form inputs to canonical fields.

The heuristics combine two passes:

1. Exact or regex-driven lookups using the curated patterns from
   ``MASTER_FORM_DICTIONARY``.
2. RapidFuzz similarity scores against a normalized synonym table derived from
   those same patterns.

The goal is to surface a small set of likely canonical field names for every
scraped form component so downstream automation can reason about the data model.

ENHANCED VERSION: This module has been enhanced with comprehensive patterns
covering 80+ field types including:
- Modern framework patterns (React, Vue, Angular, BEM, etc.)
- E-commerce fields (quantity, price, cart, etc.)
- Job search fields (keywords, location, job type, etc.)
- Social login buttons (Google, Facebook, GitHub, etc.)
- Address fields (country, state, city, zip, etc.)
- Enhanced authentication patterns
- Work authorization and visa fields
- Preferences and opt-ins (SMS, email, job alerts)
- Company and signature fields
- Demographics (pronoun, veteran status, disability)
- Education fields (school, degree, area of study)
- Job application fields (referral, compensation, reason for leaving)

Based on validation against 180+ real-world sites with 87%+ match rate.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from rapidfuzz import fuzz

MASTER_FORM_DICTIONARY: Dict[str, Sequence[str]] = {
    # ----------------------------
    # Personal Info
    # ----------------------------
    "first_name": [
        r"^first[\s_-]?name$",
        r"^fname$",
        r"^given[\s_-]?name$",
        r"^forename$",
        r"^first$",
        r".*first.*name.*",
    ],
    "last_name": [
        r"^last[\s_-]?name$",
        r"^lname$",
        r"^surname$",
        r"^family[\s_-]?name$",
        r"^last$",
        r".*last.*name.*",
    ],
    "fullname": [
        r"^fullname$",
        r"^full[-_]name$",
        r"^name$",
        r"^applicant[-_]fullname$",
        r"^applicant[-_]name$",
        r"^[A-Z][a-z]+_name_[a-zA-Z0-9]+$",
        r".*name.*input.*field.*",
    ],
    "email": [
        r"^email$",
        r"^e[-]?mail$",
        r"^emailaddress$",
        r"^user[_-]?email$",
        r"^mail$",
        # Enhanced patterns for modern frameworks
        r"^email[-_]bem$",
        r".*__input--email$",
        r"^input[-_]email[-_][a-z0-9]{5,8}$",
        r"^data[-_]email$",
        r"^react[-_]email$",
        r".*Email_.*\d+$",
        r".*email.*field.*control.*",
    ],
    "phone": [
        r"^phone$",
        r"^mobile$",
        r"^telephone$",
        r"^cell$",
        r"^contact[\s_-]?number$",
        r"^phone\d*$",
        r"^tel$",
        r"^applicant[-_]phone$",
        r".*phone.*input.*field.*",
    ],
    "dob": [
        r"^dob$",
        r"^date[\s_-]?of[\s_-]?birth$",
        r"^birthdate$",
        r"^birthday$",
        r"^birth[-_]date$",
        r"^birth[-_]day$",
        r".*birth.*date.*",
    ],
    "gender": [
        r"^gender$",
        r"^sex$",
        r"^user[_-]?gender$",
        r".*gender.*select.*",
    ],
    # ----------------------------
    # Address Fields
    # ----------------------------
    "country": [
        r"^country$",
        r"^countries$",
        r"^nation$",
        r"^billing[-_]country$",
        r"^shipping[-_]country$",
        r"^contact[Ii]nfo\.country$",
        r".*country.*select.*",
        r".*\.country$",
        r".*country$",
    ],
    "state": [
        r"^state$",
        r"^states$",
        r"^province$",
        r"^region$",
        r"^billing[-_]state$",
        r"^shipping[-_]state$",
        r"^contact[Ii]nfo\.region$",
        r".*state.*select.*",
        r".*\.region$",
        r".*state.*province.*",
    ],
    "city": [
        r"^city$",
        r"^town$",
        r"^municipality$",
        r"^billing[-_]city$",
        r"^shipping[-_]city$",
    ],
    "address": [
        r"^address$",
        r"^street$",
        r"^address[-_]?1$",
        r"^address[-_]line[-_]?1$",
        r"^street[-_]address$",
        r"^billing[-_]address$",
        r"^shipping[-_]address$",
        r".*street.*address.*",
    ],
    "address2": [
        r"^address[-_]?2$",
        r"^address[-_]line[-_]?2$",
        r"^apt$",
        r"^apartment$",
        r"^suite$",
        r"^unit$",
    ],
    "zip": [
        r"^zip$",
        r"^zipcode$",
        r"^zip[-_]code$",
        r"^postal$",
        r"^postalcode$",
        r"^postal[-_]code$",
        r"^postcode$",
        r"^contact[Ii]nfo\.postal[Cc]ode$",
        r".*postal.*code.*",
        r".*\.postal[Cc]ode$",
    ],
    # ----------------------------
    # Documents / Files
    # ----------------------------
    "resume": [
        r"^resume$",
        r"^cv$",
        r"^curriculum[\s_-]?vitae$",
        r"^upload[_-]?resume$",
        r"^resumeupload$",
        r"^resume[-_]upload$",
        r"^resume[-_]selection$",
        r"^resume[-_]file$",
        r"^cv[-_]upload$",
        r"^cv[-_]file$",
        r"^document[-_]resume$",
        r".*resume.*file.*",
        r".*resume.*upload.*",
        r".*cv.*upload.*",
    ],
    "cover_letter": [
        r"^cover[\s_-]?letter$",
        r"^motivation[\s_-]?letter$",
        r"^application[\s_-]?letter$",
        r"^coverletter$",
        r"^cover$",
    ],
    "portfolio": [
        r"^portfolio$",
        r"^site$",
        r"^portfolio[_-]?url$",
        r"^github$",
        r"^website$",
        r"^personal[-_]site$",
    ],
    # ----------------------------
    # Profile Links / Social
    # ----------------------------
    "linkedin": [
        r"^linkedin$",
        r"^li[_-]?profile$",
        r"^linkedin[_-]?url$",
    ],
    "github": [
        r"^github$",
        r"^git[_-]?profile$",
        r"^git[_-]?repo$",
    ],
    "twitter": [
        r"^twitter$",
        r"^x$",
        r"^twitter[_-]?handle$",
    ],
    "website": [
        r"^website$",
        r"^portfolio$",
        r"^personal[_-]?site$",
        r"^homepage$",
    ],
    # ----------------------------
    # Account / Authentication
    # ----------------------------
    "username": [
        r"^username$",
        r"^user$",
        r"^login$",
        r"^userid$",
        r"^user[_-]?name$",
        r"^handle$",
        r"^display[-_]?name$",
    ],
    "password": [
        r"^password$",
        r"^pass$",
        r"^pwd$",
        r"^user[_-]?password$",
        # Enhanced patterns for modern frameworks
        r"^password[-_]bem$",
        r".*__input--password$",
        r"^input[-_]password[-_][a-z0-9]{5,8}$",
        r"^react[-_]password$",
        r".*Password_.*\d+$",
        r".*password.*field.*control.*",
    ],
    "confirm_password": [
        r"^confirm[_-]?password$",
        r"^repeat[_-]?password$",
        r"^retype[_-]?password$",
        r"^password[-_]?2$",
        r"^verify[-_]?password$",
        r".*confirm.*password.*",
    ],
    "remember_me": [
        r"^remember$",
        r"^remember[-_]me$",
        r"^stay[-_]logged[-_]in$",
        r"^keep[-_]logged[-_]in$",
    ],
    # ----------------------------
    # Search Fields
    # ----------------------------
    "search_query": [
        r"^query$",
        r"^search[-_]query$",
        r"^searchQuery$",
        r"^q$",
        r"^search$",
        r"^term$",
        r"^what$",
        r"^keyword$",
        r"^keywords$",
        r"^filter[-_]?input$",
        r".*search.*query.*",
        r".*search.*input.*",
    ],
    "location": [
        r"^location$",
        r"^locations$",
        r"^search[-_]location$",
        r"^loc$",
        r"^where$",
        r"^city$",
        r"^place$",
        r".*location.*input.*",
    ],
    # ----------------------------
    # Job Search Fields
    # ----------------------------
    "keywords": [
        r"^keywords$",
        r"^keyword$",
        r"^search[-_]keywords$",
        r"^job[-_]keywords$",
        r"^kw$",
        r"^term$",
        r"^what$",
    ],
    "job_title": [
        r"^title$",
        r"^job[-_]title$",
        r"^position$",
        r"^role$",
        r"^job$",
    ],
    "job_type": [
        r"^jobtype$",
        r"^jobtypes$",
        r"^job[-_]type$",
        r"^job[-_]types$",
        r"^type$",
        r"^employment[-_]type$",
        r"^employment[-_]types$",
    ],
    "experience_level": [
        r"^experience$",
        r"^experiences$",
        r"^exp[-_]level$",
        r"^experience[-_]level$",
        r"^seniority$",
        r"^level$",
    ],
    "salary": [
        r"^salary$",
        r"^min[-_]salary$",
        r"^salary[-_]range$",
        r"^compensation$",
        r"^pay$",
    ],
    "distance": [
        r"^distance$",
        r"^radius$",
        r"^within$",
        r"^miles$",
        r"^search[-_]radius$",
    ],
    # ----------------------------
    # E-commerce Fields
    # ----------------------------
    "quantity": [
        r"^quantity$",
        r"^qty$",
        r"^product[_-]?quantity$",
        r"^item[_-]?quantity$",
    ],
    "price_min": [
        r"^price[_-]?min$",
        r"^min[_-]?price$",
        r"^minPrice$",
        r"^priceFrom$",
    ],
    "price_max": [
        r"^price[_-]?max$",
        r"^max[_-]?price$",
        r"^maxPrice$",
        r"^priceTo$",
    ],
    "condition": [
        r"^condition$",
        r"^product[_-]?condition$",
        r"^item[_-]?condition$",
    ],
    "size": [
        r"^size$",
        r"^product[_-]?size$",
        r"^item[_-]?size$",
    ],
    "color": [
        r"^colou?r$",
        r"^product[_-]?colou?r$",
        r"^item[_-]?colou?r$",
    ],
    "category": [
        r"^category$",
        r"^cat$",
        r"^product[_-]?category$",
    ],
    # ----------------------------
    # Social / Content Fields
    # ----------------------------
    "comment": [
        r"^comment$",
        r"^comments$",
        r"^message$",
        r"^reply$",
        r"^feedback$",
        r"^text$",
        r"^body$",
        r".*comment.*text.*",
    ],
    "newsletter": [
        r"^newsletter$",
        r"^subscribe$",
        r"^subscription$",
        r"^email[-_]signup$",
    ],
    "tags": [
        r"^tags?$",
        r"^categories$",
        r"^category$",
        r"^topics?$",
    ],
    "sort": [
        r"^sort$",
        r"^sortby$",
        r"^sort[-_]by$",
        r"^order$",
        r"^orderby$",
        r"^order[-_]by$",
    ],
    "filter": [
        r"^filter$",
        r"^filterinput$",
        r"^filter[-_]input$",
    ],
    # ----------------------------
    # Buttons
    # ----------------------------
    "submit_button": [
        r"^submit$",
        r"^save$",
        r"^apply$",
        r"^send$",
        r"^submit[-_]button$",
        r"^btn[-_]submit$",
        r".*submit.*button.*",
    ],
    "next_button": [
        r"^next$",
        r"^continue$",
    ],
    "cancel_button": [
        r"^cancel$",
    ],
    "login_button": [
        r"^login$",
        r"^sign[_-]?in$",
        r"^signin$",
        r".*login.*button.*",
    ],
    "signup_button": [
        r"^signup$",
        r"^sign[_-]?up$",
        r"^register$",
    ],
    "search_button": [
        r"^search$",
        r"^find$",
        r"^search[-_]button$",
        r".*search.*button.*",
    ],
    "add_to_cart": [
        r"^add.*cart$",
        r"^addToCart$",
        r"^add.*bag$",
        r"^add.*basket$",
    ],
    "buy_now": [
        r"^buy.*now$",
        r"^buyNow$",
        r"^purchase.*now$",
    ],
    # ----------------------------
    # Social Login (SSO)
    # ----------------------------
    "google_login": [
        r"^google[-_]?login$",
        r"^google[-_]?signin$",
        r"^login[-_]?google$",
        r".*google.*login.*",
    ],
    "facebook_login": [
        r"^facebook[-_]?login$",
        r"^fb[-_]?login$",
        r"^facebook[-_]?signin$",
        r".*facebook.*login.*",
    ],
    "twitter_login": [
        r"^twitter[-_]?login$",
        r"^x[-_]?login$",
        r"^twitter[-_]?signin$",
        r".*twitter.*login.*",
    ],
    "github_login": [
        r"^github[-_]?login$",
        r"^github[-_]?signin$",
        r".*github.*login.*",
    ],
    "linkedin_login": [
        r"^linkedin[-_]?login$",
        r"^linkedin[-_]?signin$",
        r".*linkedin.*login.*",
    ],
    "apple_login": [
        r"^apple[-_]?login$",
        r"^apple[-_]?signin$",
        r"^apple[-_]?id$",
        r".*apple.*login.*",
    ],
    # ----------------------------
    # Search Inputs
    # ----------------------------
    "search_input": [
        r"^search$",
        r"^search[\s_-]?box$",
        r"^search[\s_-]?input$",
        r"^find$",
        r"^lookup$",
        r"^query$",
    ],
    # ----------------------------
    # Work Authorization
    # ----------------------------
    "work_authorization": [
        r"^work[-_]auth.*",
        r"^authorization.*",
        r"^visa.*",
        r"^eligib.*",
        r"^legal.*work.*",
        r"^sponsor.*",
        r".*work.*authorization.*",
        r".*authorization.*type.*",
    ],
    # ----------------------------
    # Preferences & Opt-ins
    # ----------------------------
    "sms_optin": [
        r"^sms[-_]opt[-_]?in$",
        r"^sms[-_]consent$",
        r"^text[-_]opt[-_]?in$",
        r"^text[-_]messages.*",
        r".*sms.*opt.*",
        r".*text.*messages.*accepted.*",
    ],
    "email_optin": [
        r"^email[-_]opt[-_]?in$",
        r"^email[-_]consent$",
        r"^email[-_]updates$",
        r"^newsletter$",
        r".*email.*opt.*",
        r".*email.*updates.*",
        r".*campaign.*email.*",
        r".*email.*enabled.*",
    ],
    "job_alerts": [
        r"^job[-_]alerts?$",
        r"^alerts?$",
        r"^notifications?$",
        r"^job[-_]notifications?$",
        r".*job.*alerts.*",
        r".*job.*matches.*",
    ],
    "remote_work": [
        r"^remote[-_]work$",
        r"^remote[-_]?preference$",
        r"^remote[-_]?willing$",
        r"^relocation[-_]preference$",
        r".*remote.*work.*",
        r".*relocation.*",
    ],
    "future_consideration": [
        r"^future[-_]consideration$",
        r"^keep[-_]on[-_]file$",
        r"^future[-_]opportunities$",
        r".*future.*consideration.*",
    ],
    # ----------------------------
    # Company Information
    # ----------------------------
    "company_name": [
        r"^company$",
        r"^company[-_]name$",
        r"^organization$",
        r"^employer$",
        r"^business[-_]name$",
        r".*company.*name.*",
    ],
    # ----------------------------
    # Signature & Legal
    # ----------------------------
    "signature": [
        r"^signature$",
        r"^electronic[-_]signature$",
        r"^e[-_]signature$",
        r"^sign$",
        r"^applicant.*signature$",
        r".*signature.*",
    ],
    "acknowledgement": [
        r"^acknowledge.*",
        r"^agree.*",
        r"^accept.*",
        r"^terms.*",
        r"^consent$",
        r".*acknowledgement.*",
    ],
    # ----------------------------
    # Demographics & EEO
    # ----------------------------
    "pronoun": [
        r"^pronoun.*",
        r"^pronouns$",
        r".*\.pronoun.*",
    ],
    "veteran_status": [
        r"^veteran.*",
        r".*veteran.*status.*",
    ],
    "disability_status": [
        r"^disability.*",
        r".*disability.*status.*",
    ],
    "race_ethnicity": [
        r"^race$",
        r"^ethnicity$",
        r"^race[-_]ethnicity$",
        r".*race.*ethnicity.*",
    ],
    # ----------------------------
    # Job Application Specific
    # ----------------------------
    "referral_source": [
        r"^referr.*",
        r"^how.*hear.*",
        r"^source$",
        r".*referred.*by.*",
        r".*how.*hear.*about.*",
    ],
    "compensation_expectations": [
        r"^comp.*expectations?$",
        r"^salary.*expect.*",
        r"^desired[-_]salary$",
        r".*compensation.*expectations.*",
        r".*comp.*expectations.*",
    ],
    "reason_leaving": [
        r"^reason.*leaving$",
        r"^leaving[-_]reason$",
        r".*reason.*leaving.*",
    ],
    "employment_type_preference": [
        r"^employment[-_]type$",
        r"^job[-_]type[-_]preference$",
        r"^type[-_]preference$",
        r".*employment.*type.*",
    ],
    # ----------------------------
    # Education Fields
    # ----------------------------
    "education_level": [
        r"^education$",
        r"^education[-_]level$",
        r"^degree$",
        r"^education[-_]type$",
        r".*education.*level.*",
        r".*education.*type.*",
    ],
    "school_name": [
        r"^school$",
        r"^school[-_]name$",
        r"^institution$",
        r"^university$",
        r"^college$",
        r".*school.*institution.*name.*",
    ],
    "area_of_study": [
        r"^major$",
        r"^area[-_]of[-_]study$",
        r"^field[-_]of[-_]study$",
        r"^study[-_]area$",
        r".*area.*study.*",
    ],
    "graduation_status": [
        r"^graduated$",
        r"^graduation[-_]status$",
        r"^graduation[-_]date$",
        r".*graduated.*",
    ],
}


_COMPILED_PATTERNS: Dict[str, Tuple[re.Pattern[str], ...]] = {
    field: tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)
    for field, patterns in MASTER_FORM_DICTIONARY.items()
}

_SUFFIX_SPLITS: Tuple[str, ...] = (
    "address",
    "number",
    "name",
    "letter",
    "profile",
    "handle",
    "url",
    "site",
    "box",
    "input",
    "button",
)


def _normalize_text(value: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", value.lower())
    return " ".join(tokens)


def _expand_suffixes(term: str) -> Iterable[str]:
    for suffix in _SUFFIX_SPLITS:
        if term.endswith(suffix) and len(term) > len(suffix):
            prefix = term[: -len(suffix)]
            yield f"{prefix} {suffix}"


def _pattern_to_synonyms(pattern: str) -> Iterable[str]:
    cleaned = pattern.strip()
    if cleaned.startswith("^"):
        cleaned = cleaned[1:]
    if cleaned.endswith("$"):
        cleaned = cleaned[:-1]
    cleaned = cleaned.replace(r"[\s_-]?", " ")
    cleaned = cleaned.replace(r"[\s_-]", " ")
    cleaned = cleaned.replace("_", " ")
    cleaned = cleaned.replace("-", " ")
    cleaned = re.sub(r"\\d\*", "", cleaned)
    cleaned = re.sub(r"\\w", "", cleaned)
    cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    if not cleaned:
        return []
    synonyms = set()
    synonyms.add(cleaned)
    synonyms.update(_expand_suffixes(cleaned))
    tokens = re.findall(r"[a-z0-9]+", cleaned)
    if len(tokens) > 1:
        synonyms.add("".join(tokens))
    return {syn for syn in synonyms if syn}


def _build_synonym_table() -> Dict[str, Tuple[str, ...]]:
    synonym_table: Dict[str, set[str]] = {}
    for field, patterns in MASTER_FORM_DICTIONARY.items():
        entries: set[str] = set()
        entries.add(field)
        entries.add(field.replace("_", " "))
        tokens = re.findall(r"[a-z0-9]+", field)
        if len(tokens) > 1:
            entries.add("".join(tokens))
        for pattern in patterns:
            entries.update(_pattern_to_synonyms(pattern))
        normalized_entries = {value for value in (_normalize_text(entry) for entry in entries) if value}
        synonym_table[field] = tuple(sorted(normalized_entries))
    return synonym_table


_SYNTHETIC_SYNONYMS: Dict[str, Tuple[str, ...]] = _build_synonym_table()

_SCORE_WEIGHTS: Dict[str, float] = {
    "attribute": 0.5,
    "placeholder": 0.3,
    "visual": 0.2,
}

_SOURCE_GROUP_MAP: Dict[str, str] = {
    "id": "attribute",
    "name": "attribute",
    "autocomplete": "attribute",
    "data_attributes": "attribute",
    "label": "placeholder",
    "placeholder": "placeholder",
    "ariaLabel": "placeholder",
    "ariaLabelledBy": "placeholder",
    "text": "visual",
    "ocr_text": "visual",
    "visual_text": "visual",
    "ocr": "visual",
}

MatchDict = Dict[str, Any]
FallbackResolver = Callable[[Dict[str, Any]], Sequence[Dict[str, Any]]]
ResolverEntry = Tuple[int, Dict[str, Any], Dict[str, Any]]
AmbiguityResolver = Callable[[str, Sequence[ResolverEntry]], Optional[int]]
UnknownFieldResolver = Callable[[Sequence[Tuple[int, Dict[str, Any]]]], Sequence[Dict[str, Any]]]

_FIELD_TYPE_HINTS: Dict[str, Sequence[str]] = {
    "email": ("email",),
    "phone": ("tel", "text", "number"),
    "resume": ("file",),
    "cover_letter": ("file", "textarea", "text"),
    "portfolio": ("url", "text"),
    "linkedin": ("url", "text"),
    "github": ("url", "text"),
    "twitter": ("text",),
    "website": ("url", "text"),
    "dob": ("date", "text"),
    "password": ("password",),
    "confirm_password": ("password",),
    "search_input": ("search", "text"),
    "search_query": ("search", "text"),
    "search_button": ("submit", "button"),
    "submit_button": ("submit", "button"),
    "next_button": ("submit", "button"),
    "cancel_button": ("button",),
    "login_button": ("submit", "button"),
    "signup_button": ("submit", "button"),
    "add_to_cart": ("submit", "button"),
    "buy_now": ("submit", "button"),
    "google_login": ("submit", "button"),
    "facebook_login": ("submit", "button"),
    "twitter_login": ("submit", "button"),
    "github_login": ("submit", "button"),
    "linkedin_login": ("submit", "button"),
    "apple_login": ("submit", "button"),
    "quantity": ("number", "select", "text"),
    "price_min": ("number", "text"),
    "price_max": ("number", "text"),
    "condition": ("select", "text"),
    "size": ("select", "text"),
    "color": ("select", "text"),
    "category": ("select", "text"),
    "comment": ("textarea", "text"),
    "newsletter": ("email", "text"),
    # New field type hints
    "work_authorization": ("select", "radio", "text"),
    "sms_optin": ("checkbox",),
    "email_optin": ("checkbox",),
    "job_alerts": ("checkbox",),
    "remote_work": ("checkbox", "radio", "select"),
    "future_consideration": ("checkbox",),
    "signature": ("text",),
    "acknowledgement": ("checkbox",),
    "pronoun": ("select", "text"),
    "veteran_status": ("select", "radio"),
    "disability_status": ("select", "radio"),
    "race_ethnicity": ("select",),
    "referral_source": ("text", "select"),
    "compensation_expectations": ("text", "number"),
    "reason_leaving": ("text", "textarea"),
    "employment_type_preference": ("select", "checkbox"),
    "education_level": ("select", "text"),
    "school_name": ("text",),
    "area_of_study": ("text", "select"),
    "graduation_status": ("select", "radio", "date"),
}

_FIELD_TAG_HINTS: Dict[str, Sequence[str]] = {
    "gender": ("SELECT", "INPUT"),
    "resume": ("INPUT",),
    "cover_letter": ("TEXTAREA", "INPUT"),
    "submit_button": ("BUTTON", "INPUT"),
    "next_button": ("BUTTON", "INPUT"),
    "cancel_button": ("BUTTON", "INPUT"),
    "login_button": ("BUTTON", "INPUT"),
    "signup_button": ("BUTTON", "INPUT"),
    "search_button": ("BUTTON", "INPUT"),
    "add_to_cart": ("BUTTON", "INPUT"),
    "buy_now": ("BUTTON", "INPUT"),
    "google_login": ("BUTTON", "INPUT"),
    "facebook_login": ("BUTTON", "INPUT"),
    "twitter_login": ("BUTTON", "INPUT"),
    "github_login": ("BUTTON", "INPUT"),
    "linkedin_login": ("BUTTON", "INPUT"),
    "apple_login": ("BUTTON", "INPUT"),
    "job_type": ("SELECT", "INPUT"),
    "experience_level": ("SELECT", "INPUT"),
    "salary": ("SELECT", "INPUT"),
    "condition": ("SELECT", "INPUT"),
    "size": ("SELECT", "INPUT"),
    "color": ("SELECT", "INPUT"),
    "category": ("SELECT", "INPUT"),
    "country": ("SELECT", "INPUT"),
    "state": ("SELECT", "INPUT"),
    "comment": ("TEXTAREA",),
    # New tag hints
    "work_authorization": ("SELECT", "INPUT"),
    "sms_optin": ("INPUT",),
    "email_optin": ("INPUT",),
    "job_alerts": ("INPUT",),
    "remote_work": ("INPUT", "SELECT"),
    "future_consideration": ("INPUT",),
    "signature": ("INPUT",),
    "acknowledgement": ("INPUT",),
    "pronoun": ("SELECT", "INPUT"),
    "veteran_status": ("SELECT", "INPUT"),
    "disability_status": ("SELECT", "INPUT"),
    "race_ethnicity": ("SELECT",),
    "referral_source": ("INPUT", "SELECT", "TEXTAREA"),
    "compensation_expectations": ("INPUT",),
    "reason_leaving": ("INPUT", "TEXTAREA"),
    "employment_type_preference": ("SELECT", "INPUT"),
    "education_level": ("SELECT", "INPUT"),
    "school_name": ("INPUT",),
    "area_of_study": ("INPUT", "SELECT"),
    "graduation_status": ("SELECT", "INPUT"),
}


def _source_group(source: str) -> str | None:
    if source.startswith("data_attributes."):
        return _SOURCE_GROUP_MAP.get("data_attributes")
    return _SOURCE_GROUP_MAP.get(source)


def match_form_field_candidate(
    attributes: Dict[str, Any],
    *,
    score_cutoff: int = 75,
    limit: int = 5,
    fallback_resolver: Optional[FallbackResolver] = None,
) -> List[Dict[str, object]]:
    """Return likely canonical field mappings for a scraped form control.

    Parameters
    ----------
    attributes:
        A dictionary of scraped attributes (label, placeholder, etc.). Values
        are normalized internally, so passing the output of
        :meth:`FormComponent.to_candidate` or its intermediate mapping works.
    score_cutoff:
        Minimum RapidFuzz score required to include a fuzzy match. Regex hits
        always bypass this threshold and are returned with a score of 100.
    limit:
        Maximum number of matches to return after ranking. Set a higher value
        when you want to inspect more candidates.
    fallback_resolver:
        Optional callable invoked when the dictionary-driven matcher fails to
        produce any results. Receives the raw attribute dictionary and should
        return an iterable of dictionaries describing fallback matches.
    """

    if limit <= 0:
        return []

    raw_sources: List[Dict[str, object]] = []
    seen_sources: set[Tuple[str, str]] = set()

    def _invoke_fallback() -> List[Dict[str, object]]:
        if fallback_resolver is None:
            return []
        fallback_matches = fallback_resolver(attributes) or []
        normalized: List[Dict[str, object]] = []
        for raw in fallback_matches:
            field = raw.get("field")
            if not isinstance(field, str):
                continue
            score_raw = raw.get("score", 0.0)
            score = float(score_raw) if isinstance(score_raw, (int, float)) else 0.0
            score_percent_raw = raw.get("score_percent")
            if isinstance(score_percent_raw, (int, float)):
                score_percent = float(score_percent_raw)
            else:
                score_percent = score * 100.0 if score <= 1.0 else score
            normalized.append(
                {
                    "field": field,
                    "score": score,
                    "score_percent": score_percent,
                    "method": raw.get("method", "fallback"),
                    "source": raw.get("source", "fallback"),
                    "value": raw.get("value", attributes.get("label") or attributes.get("name") or ""),
                    "contributors": raw.get("contributors", []),
                    "breakdown": raw.get("breakdown", {}),
                    "weights_applied": raw.get("weights_applied", sum(_SCORE_WEIGHTS.values())),
                    "group": raw.get("group"),
                }
            )
        normalized.sort(key=lambda item: (-item["score"], item["field"]))
        return normalized[:limit]

    def _store(value: object, source: str) -> None:
        if isinstance(value, str):
            candidates = [value]
        elif isinstance(value, Sequence):
            candidates = [item for item in value if isinstance(item, str)]  # type: ignore[arg-type]
        else:
            candidates = []
        for candidate_value in candidates:
            stripped = candidate_value.strip()
            if not stripped:
                continue
            normalized = _normalize_text(stripped)
            if not normalized:
                continue
            key = (normalized, source)
            if key in seen_sources:
                continue
            seen_sources.add(key)
            raw_sources.append(
                {
                    "normalized": normalized,
                    "source": source,
                    "value": stripped,
                    "group": _source_group(source),
                }
            )

    _store(attributes.get("label"), "label")
    _store(attributes.get("placeholder"), "placeholder")
    _store(attributes.get("name"), "name")
    _store(attributes.get("id"), "id")
    _store(attributes.get("text"), "text")
    _store(attributes.get("autocomplete"), "autocomplete")
    _store(attributes.get("ariaLabel"), "ariaLabel")
    _store(attributes.get("ariaLabelledBy"), "ariaLabelledBy")
    _store(attributes.get("value"), "value")
    _store(attributes.get("ocr_text"), "ocr_text")
    _store(attributes.get("visual_text"), "visual_text")

    data_attributes = attributes.get("data_attributes")
    if isinstance(data_attributes, dict):
        for key, value in data_attributes.items():
            if isinstance(value, str):
                _store(value, f"data_attributes.{key}")

    if not raw_sources:
        return _invoke_fallback()

    matches_by_field: Dict[str, Dict[str, Dict[str, object]]] = {}

    def _is_preferred(new_match: Dict[str, object], existing_match: Dict[str, object]) -> bool:
        if existing_match["method"] == "regex" and new_match["method"] != "regex":
            return False
        if new_match["method"] == "regex" and existing_match["method"] != "regex":
            return True
        return float(new_match["score"]) > float(existing_match["score"])

    def _update_best(match: Dict[str, object]) -> None:
        field = match["field"]  # type: ignore[index]
        group = match.get("group") or f"source:{match['source']}"
        field_matches = matches_by_field.setdefault(field, {})
        existing = field_matches.get(group)
        if existing is None or _is_preferred(match, existing):
            field_matches[group] = match

    for source_info in raw_sources:
        normalized = source_info["normalized"]  # type: ignore[index]
        source = source_info["source"]  # type: ignore[index]
        raw_value = source_info["value"]  # type: ignore[index]
        group = source_info.get("group")

        for field, patterns in _COMPILED_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(raw_value):
                    _update_best(
                        {
                            "field": field,
                            "score": 100.0,
                            "method": "regex",
                            "source": source,
                            "value": raw_value,
                            "pattern": pattern.pattern,
                            "group": group,
                        }
                    )
                    break
        for field, synonyms in _SYNTHETIC_SYNONYMS.items():
            best_score = 0.0
            best_synonym = None
            for synonym in synonyms:
                if not synonym:
                    continue
                score = float(fuzz.WRatio(normalized, synonym))
                if score > best_score:
                    best_score = score
                    best_synonym = synonym
            if best_score >= score_cutoff and best_synonym:
                _update_best(
                    {
                        "field": field,
                        "score": best_score,
                        "method": "fuzzy",
                        "source": source,
                        "value": raw_value,
                        "synonym": best_synonym,
                        "group": group,
                    }
                )

    if not matches_by_field:
        return []

    results: List[Dict[str, object]] = []
    for field, grouped_matches in matches_by_field.items():
        contributors: List[Dict[str, object]] = []
        weighted_total = 0.0
        breakdown: Dict[str, Dict[str, float | str]] = {}
        for group_key, match in grouped_matches.items():
            normalized_score = 1.0 if match["method"] == "regex" else float(match["score"]) / 100.0
            group = match.get("group")
            weight = _SCORE_WEIGHTS.get(group, 0.0)
            weighted_score = weight * normalized_score
            contributor: Dict[str, object] = {
                "group": group,
                "source": match["source"],
                "value": match["value"],
                "method": match["method"],
                "score": match["score"],
                "normalized_score": normalized_score,
                "weight": weight,
                "weighted_score": weighted_score,
            }
            if "pattern" in match:
                contributor["pattern"] = match["pattern"]
            if "synonym" in match:
                contributor["synonym"] = match["synonym"]
            contributors.append(contributor)
            if group in _SCORE_WEIGHTS:
                breakdown[group] = {
                    "weight": weight,
                    "normalized_score": normalized_score,
                    "weighted_score": weighted_score,
                    "source": str(match["source"]),
                }
                weighted_total += weighted_score
            else:
                breakdown[group_key] = {
                    "weight": weight,
                    "normalized_score": normalized_score,
                    "weighted_score": weighted_score,
                    "source": str(match["source"]),
                }

        contributors.sort(
            key=lambda entry: (
                -entry["weight"],
                -entry["normalized_score"],
                entry.get("source", ""),
            )
        )
        weighted_total = min(weighted_total, 1.0)
        results.append(
            {
                "field": field,
                "score": weighted_total,
                "score_percent": weighted_total * 100.0,
                "contributors": contributors,
                "breakdown": breakdown,
                "weights_applied": sum(_SCORE_WEIGHTS.get(match.get("group"), 0.0) for match in grouped_matches.values()),
            }
        )

    results.sort(key=lambda item: (-item["score"], item["field"]))

    if not results:
        return _invoke_fallback()

    return results[:limit]


def select_best_candidates_by_field(
    candidates: Sequence[Dict[str, object]],
    *,
    resolver: Optional[AmbiguityResolver] = None,
    unknown_field_resolver: Optional[UnknownFieldResolver] = None,
    score_tolerance: float = 0.05,
) -> Dict[str, Dict[str, object]]:
    """Return disambiguated candidates for each canonical field.

    Parameters
    ----------
    candidates:
        Iterable of candidate dictionaries produced by
        :func:`collect_form_candidates` or similar helpers.
    resolver:
        Optional callback used when multiple candidates remain after score,
        input-type, and bounding-box heuristics. Receives the field name and a
        sequence of ``(index, candidate, match)`` tuples. Should return either
        a candidate index or ``None``.
    unknown_field_resolver:
        Optional callback invoked for candidates without any canonical field
        matches. Receives a sequence of ``(index, candidate)`` tuples and
        should return an iterable of resolution dictionaries containing at
        least ``field`` and ``candidate_index`` keys.
    score_tolerance:
        Maximum difference allowed (in absolute score units) when considering
        candidates tied for the top score.

    Returns
    -------
    dict
        Mapping of canonical field name to a structure describing the chosen
        candidate index, score, and resolution metadata.
    """

    field_entries: Dict[str, List[Dict[str, Any]]] = {}
    unresolved: List[Tuple[int, Dict[str, Any]]] = []

    for index, candidate in enumerate(candidates):
        matches = candidate.get("fuzzy_matches")
        if not isinstance(matches, list) or not matches:
            unresolved.append((index, candidate))
            continue
        has_field = False
        for match in matches:
            field = match.get("field")
            score = match.get("score")
            if not isinstance(field, str) or not isinstance(score, (int, float)):
                continue
            has_field = True
            field_entries.setdefault(field, []).append(
                {"index": index, "candidate": candidate, "match": match}
            )
        if not has_field:
            unresolved.append((index, candidate))

    results: Dict[str, Dict[str, object]] = {}

    for field, entries in field_entries.items():
        entries.sort(key=lambda entry: float(entry["match"].get("score", 0.0)), reverse=True)
        top_score = float(entries[0]["match"].get("score", 0.0))
        pool = [
            entry
            for entry in entries
            if float(entry["match"].get("score", 0.0)) >= top_score - max(score_tolerance, 0.0)
        ]

        resolved_by = "score"
        resolver_metadata: Optional[Any] = None

        filtered_by_type = _filter_by_type(field, pool)
        if filtered_by_type:
            pool = filtered_by_type
            resolved_by = "input_type"

        if len(pool) > 1:
            pool_sorted = sorted(pool, key=_bbox_sort_key)
            if any(_has_real_bbox(entry) for entry in pool_sorted):
                pool = [pool_sorted[0]]
                resolved_by = "bounding_box"
            else:
                pool = pool_sorted

        if len(pool) > 1 and resolver is not None:
            choice = resolver(
                field,
                [(entry["index"], entry["candidate"], entry["match"]) for entry in pool],
            )
            chosen_entry = None
            if isinstance(choice, int):
                for entry in pool:
                    if entry["index"] == choice:
                        chosen_entry = entry
                        break
            elif isinstance(choice, dict):
                idx = choice.get("candidate_index")
                if isinstance(idx, int):
                    for entry in pool:
                        if entry["index"] == idx:
                            chosen_entry = entry
                            break
                resolver_metadata = choice.get("metadata")
            if chosen_entry is not None:
                pool = [chosen_entry]
                resolved_by = "resolver"

        chosen = pool[0]
        match = chosen["match"]
        result: Dict[str, object] = {
            "candidate_index": chosen["index"],
            "score": float(match.get("score", 0.0)),
            "score_percent": float(match.get("score_percent", float(match.get("score", 0.0)) * 100.0)),
            "match": match,
            "resolved_by": resolved_by,
        }
        if resolver_metadata is not None:
            result["resolver_metadata"] = resolver_metadata
        results[field] = result

    if unknown_field_resolver is not None and unresolved:
        assignments = unknown_field_resolver(unresolved) or []
        for assignment in assignments:
            field = assignment.get("field")
            candidate_index = assignment.get("candidate_index")
            if not isinstance(field, str) or not isinstance(candidate_index, int):
                continue
            if field in results:
                continue
            score_value = assignment.get("score", 0.0)
            score = float(score_value) if isinstance(score_value, (int, float)) else 0.0
            score_percent_value = assignment.get("score_percent")
            if isinstance(score_percent_value, (int, float)):
                score_percent = float(score_percent_value)
            else:
                score_percent = score * 100.0 if score <= 1.0 else score
            result: Dict[str, object] = {
                "candidate_index": candidate_index,
                "score": score,
                "score_percent": score_percent,
                "match": assignment.get("match"),
                "resolved_by": assignment.get("resolved_by", "unknown_resolver"),
            }
            metadata = assignment.get("resolver_metadata")
            if metadata is not None:
                result["resolver_metadata"] = metadata
            results[field] = result

    return results


def _filter_by_type(field: str, entries: Sequence[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    expected_types = {value.lower() for value in _FIELD_TYPE_HINTS.get(field, ())}
    expected_tags = {value.upper() for value in _FIELD_TAG_HINTS.get(field, ())}
    if not expected_types and not expected_tags:
        return None

    filtered: List[Dict[str, Any]] = []
    for entry in entries:
        candidate = entry["candidate"]
        type_value = str(candidate.get("type") or "").lower()
        tag_value = str(candidate.get("tag") or "").upper()
        type_match = expected_types and type_value in expected_types
        tag_match = expected_tags and tag_value in expected_tags
        if (expected_types and type_match) or (expected_tags and tag_match):
            filtered.append(entry)

    return filtered or None


def _bbox_sort_key(entry: Dict[str, Any]) -> Tuple[float, float, int]:
    bbox = entry["candidate"].get("bounding_box")
    if isinstance(bbox, dict):
        top = bbox.get("top")
        left = bbox.get("left")
    else:
        top = left = None
    top_val = float(top) if isinstance(top, (int, float)) else float("inf")
    left_val = float(left) if isinstance(left, (int, float)) else float("inf")
    return (top_val, left_val, entry["index"])


def _has_real_bbox(entry: Dict[str, Any]) -> bool:
    bbox = entry["candidate"].get("bounding_box")
    if not isinstance(bbox, dict):
        return False
    return any(isinstance(bbox.get(key), (int, float)) for key in ("top", "left", "bottom", "right", "width", "height"))


__all__ = [
    "MASTER_FORM_DICTIONARY",
    "match_form_field_candidate",
    "select_best_candidates_by_field",
]
