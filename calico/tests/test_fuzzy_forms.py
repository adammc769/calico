from calico.utils.dom_regions import DEFAULT_REGION
from calico.utils.form_components import FormComponent
from calico.utils.fuzzy_forms import match_form_field_candidate, select_best_candidates_by_field


def test_match_form_field_candidate_prefers_regex():
    candidate = {
        "label": "First Name",
        "data_attributes": {},
    }

    matches = match_form_field_candidate(candidate)

    assert matches, "Expected at least one fuzzy match"
    target = next(match for match in matches if match["field"] == "first_name")
    assert target["score"] >= 0.29, "Label-only match should contribute placeholder weight"
    assert any(contributor["method"] == "regex" for contributor in target["contributors"])


def test_match_form_field_candidate_handles_fuzzy_synonyms():
    candidate = {
        "placeholder": "E-mail address",
        "data_attributes": {},
    }

    matches = match_form_field_candidate(candidate, score_cutoff=60)

    email_match = next((match for match in matches if match["field"] == "email"), None)
    assert email_match, "Expected a fuzzy match for email"
    assert email_match["score"] > 0.0
    assert any(contributor["method"] == "fuzzy" for contributor in email_match["contributors"])


def test_match_form_field_candidate_uses_fallback_when_no_matches():
    def fallback(attributes):
        assert attributes == {}
        return [
            {
                "field": "custom_field",
                "score": 0.6,
                "method": "ai",
            }
        ]

    matches = match_form_field_candidate({}, fallback_resolver=fallback)

    assert matches
    assert matches[0]["field"] == "custom_field"
    assert matches[0]["method"] == "ai"


def test_form_component_candidate_includes_fuzzy_matches():
    component = FormComponent(
        tag="input",
        type="text",
        name="lastName",
        element_id="last-name",
        placeholder="Last Name",
        text="",
        label="Last Name",
        autocomplete=None,
        value=None,
        data_attributes={},
        aria_label=None,
        aria_labelledby=None,
        role=None,
        region=DEFAULT_REGION,
        bounding_box={"top": 10.0, "left": 15.0},
    )

    candidate = component.to_candidate()

    assert "fuzzy_matches" in candidate
    assert candidate.get("canonical_field") == "last_name"
    assert candidate.get("score", 0) >= 0.5
    assert any(match["field"] == "last_name" for match in candidate["fuzzy_matches"])
    assert any(contributor["group"] == "attribute" for contributor in candidate.get("score_contributors", []))
    assert candidate.get("bounding_box") == {"top": 10.0, "left": 15.0}


def test_select_best_candidates_by_field_picks_highest_score():
    first_component = FormComponent(
        tag="input",
        type="text",
        name="firstname",
        element_id="first-name",
        placeholder="First Name",
        text="",
        label="First Name",
        autocomplete=None,
        value=None,
        data_attributes={"data-field": "primary_first"},
        aria_label=None,
        aria_labelledby=None,
        role=None,
        region=DEFAULT_REGION,
    )

    last_component = FormComponent(
        tag="input",
        type="text",
        name="lastname",
        element_id="last-name",
        placeholder="Last Name",
        text="",
        label="Last Name",
        autocomplete=None,
        value=None,
        data_attributes={"data-field": "primary_last"},
        aria_label=None,
        aria_labelledby=None,
        role=None,
        region=DEFAULT_REGION,
    )

    candidates = [first_component.to_candidate(), last_component.to_candidate()]
    rankings = select_best_candidates_by_field(candidates)

    assert "first_name" in rankings
    assert "last_name" in rankings
    assert rankings["first_name"]["candidate_index"] == 0
    assert rankings["last_name"]["candidate_index"] == 1


def test_select_best_candidates_by_field_prefers_input_type():
    candidates = [
        {
            "tag": "INPUT",
            "type": "text",
            "bounding_box": {"top": 50.0, "left": 10.0},
            "fuzzy_matches": [
                {
                    "field": "email",
                    "score": 0.9,
                    "score_percent": 90.0,
                    "method": "fuzzy",
                }
            ],
        },
        {
            "tag": "INPUT",
            "type": "email",
            "bounding_box": {"top": 100.0, "left": 10.0},
            "fuzzy_matches": [
                {
                    "field": "email",
                    "score": 0.9,
                    "score_percent": 90.0,
                    "method": "fuzzy",
                }
            ],
        },
    ]

    rankings = select_best_candidates_by_field(candidates)

    assert rankings["email"]["candidate_index"] == 1
    assert rankings["email"]["resolved_by"] == "input_type"


def test_select_best_candidates_by_field_uses_bounding_box_for_ties():
    candidates = [
        {
            "tag": "INPUT",
            "type": "text",
            "bounding_box": {"top": 200.0, "left": 20.0},
            "fuzzy_matches": [
                {
                    "field": "phone",
                    "score": 0.8,
                    "score_percent": 80.0,
                    "method": "fuzzy",
                }
            ],
        },
        {
            "tag": "INPUT",
            "type": "text",
            "bounding_box": {"top": 80.0, "left": 15.0},
            "fuzzy_matches": [
                {
                    "field": "phone",
                    "score": 0.8,
                    "score_percent": 80.0,
                    "method": "fuzzy",
                }
            ],
        },
    ]

    rankings = select_best_candidates_by_field(candidates)

    assert rankings["phone"]["candidate_index"] == 1
    assert rankings["phone"]["resolved_by"] == "bounding_box"


def test_select_best_candidates_by_field_uses_resolver_when_needed():
    candidates = [
        {
            "tag": "INPUT",
            "type": "text",
            "bounding_box": None,
            "fuzzy_matches": [
                {
                    "field": "username",
                    "score": 0.75,
                    "score_percent": 75.0,
                    "method": "fuzzy",
                }
            ],
        },
        {
            "tag": "INPUT",
            "type": "text",
            "bounding_box": None,
            "fuzzy_matches": [
                {
                    "field": "username",
                    "score": 0.75,
                    "score_percent": 75.0,
                    "method": "fuzzy",
                }
            ],
        },
    ]

    def resolver(field, entries):
        assert field == "username"
        # pick the second candidate explicitly
        return entries[1][0]

    rankings = select_best_candidates_by_field(candidates, resolver=resolver)

    assert rankings["username"]["candidate_index"] == 1
    assert rankings["username"]["resolved_by"] == "resolver"


def test_select_best_candidates_by_field_handles_unknown_resolver():
    candidates = [
        {
            "tag": "INPUT",
            "type": "text",
            "bounding_box": {"top": 20.0, "left": 5.0},
            "fuzzy_matches": [],
        }
    ]

    def unknown(entries):
        assert entries[0][0] == 0
        return [
            {
                "field": "custom_field",
                "candidate_index": 0,
                "score": 0.42,
                "resolved_by": "unknown_resolver",
            }
        ]

    rankings = select_best_candidates_by_field(candidates, unknown_field_resolver=unknown)

    assert "custom_field" in rankings
    assert rankings["custom_field"]["candidate_index"] == 0
    assert rankings["custom_field"]["resolved_by"] == "unknown_resolver"
