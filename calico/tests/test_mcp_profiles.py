from __future__ import annotations

import pytest

from calico.utils.mcp_profiles import get_profile, list_profiles, upsert_profile


class MCPClientStub:
    def __init__(self, responses: dict[str, object]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict]] = []

    async def call(self, method: str, params: dict) -> object:
        self.calls.append((method, params))
        return self._responses.get(method, {})


@pytest.mark.asyncio
async def test_list_profiles_returns_summaries() -> None:
    client = MCPClientStub(
        {
            "profiles.list": {
                "profiles": [
                    {
                        "id": "default",
                        "displayName": "Default Persona",
                        "persona": "Demo persona",
                        "source": "built-in",
                        "hasStoredCredentials": True,
                    }
                ]
            }
        }
    )

    summaries = await list_profiles(client)

    assert summaries and summaries[0]["id"] == "default"
    assert client.calls and client.calls[0][0] == "profiles.list"
    assert client.calls[0][1] == {}


@pytest.mark.asyncio
async def test_get_profile_passes_identifier() -> None:
    client = MCPClientStub(
        {
            "profiles.get": {
                "profile": {
                    "id": "default",
                    "displayName": "Default Persona",
                    "persona": "Demo persona",
                    "allowlist": {
                        "allowCredentialAutomation": True,
                        "allowSocialAutomation": True,
                        "allowFinancialAutomation": False,
                    },
                }
            }
        }
    )

    profile = await get_profile(client, profile_id="default")

    assert profile["id"] == "default"
    assert client.calls and client.calls[0] == ("profiles.get", {"profileId": "default"})


@pytest.mark.asyncio
async def test_upsert_profile_allows_profile_id_override() -> None:
    client = MCPClientStub(
        {
            "profiles.upsert": {
                "profile": {
                    "id": "new-profile",
                    "displayName": "New Profile",
                    "persona": "Fresh persona",
                    "allowlist": {
                        "allowCredentialAutomation": True,
                        "allowSocialAutomation": True,
                        "allowFinancialAutomation": False,
                    },
                }
            }
        }
    )

    payload = {"displayName": "New Profile", "persona": "Fresh persona"}
    profile = await upsert_profile(client, payload, profile_id="new-profile")

    assert profile["id"] == "new-profile"
    assert client.calls
    method, params = client.calls[0]
    assert method == "profiles.upsert"
    assert params["profileId"] == "new-profile"
    assert params["profile"]["displayName"] == "New Profile"
