"""Utilities for seeding Playwright contexts with authentication cookies.

The helpers in this module make it straightforward to reuse login sessions that
were harvested from browser developer tools or a prior Playwright run.  They are
small building blocks that play nicely with AI workflows that need to reason
about browser state without performing an interactive sign-in.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from playwright.sync_api import BrowserContext

__all__ = [
    "AuthCookie",
    "apply_cookies",
    "load_cookies_from_path",
    "save_cookies",
]


_VALID_SAME_SITE = {None, "Strict", "Lax", "None"}


@dataclass(frozen=True, slots=True)
class AuthCookie:
    """Typed container for authentication cookie metadata.

    Parameters
    ----------
    name:
        Name of the cookie.
    value:
        Raw string value.
    domain:
        Domain scope for the cookie (e.g. ``"example.com"``).
    path:
        Path scope. Defaults to ``"/"``.
    secure:
        Whether the cookie should only be sent over HTTPS.
    http_only:
        If true, JavaScript cannot read the cookie.
    same_site:
        Optional SameSite flag (``"Strict"``, ``"Lax"``, or ``"None"``).
    expires:
        Unix epoch timestamp (seconds) for the expiry time. ``None`` means a
        session cookie.
    """

    name: str
    value: str
    domain: str
    path: str = "/"
    secure: bool = False
    http_only: bool = False
    same_site: Optional[str] = None
    expires: Optional[int] = None

    def __post_init__(self) -> None:  # type: ignore[override]
        if not self.name:
            raise ValueError("Cookie name cannot be empty")
        if not self.domain:
            raise ValueError("Cookie domain cannot be empty")
        if self.same_site not in _VALID_SAME_SITE:
            raise ValueError(
                f"same_site must be one of {_VALID_SAME_SITE - {None}} or None; got {self.same_site!r}"
            )

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AuthCookie":
        """Create an :class:`AuthCookie` from loosely typed JSON data."""

        same_site = payload.get("sameSite") or payload.get("same_site")
        expires = payload.get("expires")

        if isinstance(expires, str) and expires:
            # Accept ISO-8601 timestamps for convenience.
            try:
                expires = int(datetime.fromisoformat(expires).timestamp())
            except ValueError:
                try:
                    expires = int(expires)
                except ValueError as exc:  # pragma: no cover - defensive programming
                    raise ValueError(f"Invalid expires value: {expires!r}") from exc

        return cls(
            name=payload["name"],
            value=payload.get("value", ""),
            domain=payload["domain"],
            path=payload.get("path", "/"),
            secure=bool(payload.get("secure", False)),
            http_only=bool(payload.get("httpOnly") or payload.get("http_only", False)),
            same_site=same_site,
            expires=expires,
        )

    def to_playwright_dict(self) -> Dict[str, Any]:
        """Convert this cookie to the dict structure Playwright expects."""

        payload: Dict[str, Any] = {
            "name": self.name,
            "value": self.value,
            "domain": self.domain,
            "path": self.path,
            "secure": self.secure,
            "httpOnly": self.http_only,
        }

        if self.same_site is not None:
            payload["sameSite"] = self.same_site
        if self.expires is not None:
            payload["expires"] = self.expires

        return payload

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable representation."""

        data = asdict(self)
        if data["same_site"] is None:
            data["same_site"] = None
        return data


CookieInput = Union[AuthCookie, Dict[str, Any]]


def _normalise_cookie(cookie: CookieInput) -> AuthCookie:
    if isinstance(cookie, AuthCookie):
        return cookie
    if not isinstance(cookie, dict):
        raise TypeError(f"Unsupported cookie type: {type(cookie)!r}")
    return AuthCookie.from_dict(cookie)


def apply_cookies(
    context: BrowserContext,
    cookies: Iterable[CookieInput],
) -> None:
    """Add the given cookies to a Playwright browser context.

    This is a convenience wrapper around :meth:`BrowserContext.add_cookies` that
    accepts either :class:`AuthCookie` instances or dictionaries with the same
    schema Playwright expects.  Cookie validation is performed automatically.
    """

    normalised = [_normalise_cookie(cookie).to_playwright_dict() for cookie in cookies]
    if not normalised:
        return
    context.add_cookies(normalised)


def load_cookies_from_path(path: Union[str, Path]) -> List[AuthCookie]:
    """Load cookies from a JSON file.

    The JSON can be either a plain list of cookie objects or a dictionary with a
    ``"cookies"`` key. This mirrors Playwright's ``storageState`` format.
    """

    resolved = Path(path)
    with resolved.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if isinstance(data, dict):
        data = data.get("cookies", [])
    if not isinstance(data, Sequence):
        raise ValueError("Cookie payload must be a list or a dict with a 'cookies' key")

    return [AuthCookie.from_dict(item) for item in data]


def save_cookies(context: BrowserContext, path: Union[str, Path]) -> None:
    """Persist the active context's cookies to a JSON file."""

    payload = context.cookies()
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as fh:
        json.dump({"cookies": payload}, fh, indent=2, sort_keys=True)