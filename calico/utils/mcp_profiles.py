"""Helpers for interacting with MCP profile management endpoints."""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping, cast

from calico.utils.mcp_client import MCPClient
from calico.utils.mcp_contracts import (
    ProfileDetailPayload,
    ProfileGetParams,
    ProfileGetResult,
    ProfileSummaryPayload,
    ProfileUpsertParams,
    ProfileUpsertPayload,
    ProfileUpsertResult,
    ProfilesListResult,
)

__all__ = [
    "list_profiles",
    "get_profile",
    "upsert_profile",
]


def _coerce_mapping(value: Mapping[str, Any]) -> MutableMapping[str, Any]:
    return dict(value)


async def list_profiles(client: MCPClient) -> list[ProfileSummaryPayload]:
    """Return available profiles exposed by the MCP backend."""

    raw_result = await client.call("profiles.list", {})
    if not isinstance(raw_result, Mapping):
        raise ValueError("profiles.list returned a non-object payload")

    result = cast(ProfilesListResult, raw_result)
    profiles_value = result.get("profiles", [])
    if not isinstance(profiles_value, list):
        raise ValueError("profiles.list did not return an array in 'profiles'")

    summaries: list[ProfileSummaryPayload] = []
    for entry in profiles_value:
        if isinstance(entry, Mapping):
            summaries.append(cast(ProfileSummaryPayload, dict(entry)))
    return summaries


async def get_profile(client: MCPClient, profile_id: str | None = None) -> ProfileDetailPayload:
    """Fetch a detailed profile representation by identifier (defaults to 'default')."""

    params: ProfileGetParams = {}
    if profile_id:
        params["profileId"] = profile_id

    raw_result = await client.call("profiles.get", params)
    if not isinstance(raw_result, Mapping):
        raise ValueError("profiles.get returned a non-object payload")

    result = cast(ProfileGetResult, raw_result)
    profile_value = result.get("profile")
    if not isinstance(profile_value, Mapping):
        raise ValueError("profiles.get response was missing 'profile'")

    return cast(ProfileDetailPayload, dict(profile_value))


async def upsert_profile(
    client: MCPClient,
    profile: Mapping[str, Any],
    *,
    profile_id: str | None = None,
) -> ProfileDetailPayload:
    """Create or update an MCP profile and return the persisted representation."""

    if not isinstance(profile, Mapping):
        raise TypeError("profile must be a mapping of fields")

    payload_profile = cast(ProfileUpsertPayload, _coerce_mapping(profile))
    params: ProfileUpsertParams = {"profile": payload_profile}
    if profile_id and "id" not in payload_profile:
        params["profileId"] = profile_id

    raw_result = await client.call("profiles.upsert", params)
    if not isinstance(raw_result, Mapping):
        raise ValueError("profiles.upsert returned a non-object payload")

    result = cast(ProfileUpsertResult, raw_result)
    profile_value = result.get("profile")
    if not isinstance(profile_value, Mapping):
        raise ValueError("profiles.upsert response missing 'profile'")

    return cast(ProfileDetailPayload, dict(profile_value))
