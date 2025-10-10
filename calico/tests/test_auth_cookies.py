"""Tests for the auth cookie utilities."""

import json

import pytest

from calico.utils.auth_cookies import AuthCookie, apply_cookies, load_cookies_from_path


@pytest.mark.parametrize(
    "payload",
    [
        {"cookies": [{"name": "demo", "value": "123", "domain": "example.com"}]},
        [{"name": "demo", "value": "123", "domain": "example.com"}],
    ],
)
def test_load_cookies_from_path(tmp_path, payload):
    path = tmp_path / "cookies.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    cookies = load_cookies_from_path(path)

    assert len(cookies) == 1
    cookie = cookies[0]
    assert cookie.name == "demo"
    assert cookie.value == "123"
    assert cookie.domain == "example.com"


@pytest.mark.only_browser("chromium")
def test_apply_cookies_sets_value(context, page):
    cookie = AuthCookie(
        name="demo-session",
        value="abc123",
        domain="httpbin.org",
        path="/",
        secure=True,
        same_site="Lax",
    )

    apply_cookies(context, [cookie])

    cookies = context.cookies(["https://httpbin.org"])
    assert any(entry["name"] == "demo-session" for entry in cookies)
    target = next(entry for entry in cookies if entry["name"] == "demo-session")
    assert target["value"] == "abc123"
    assert target["domain"].endswith("httpbin.org")
