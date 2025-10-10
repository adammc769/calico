"""Typed JSON-RPC payload contracts used by the Playwright MCP bridge.

The Playwright MCP service communicates with Calico over JSON-RPC 2.0.
This module centralises the request/response payload shapes so both sides
of the bridge have a single source of truth.  The data structures defined
here are intentionally minimal – they capture the values Calico relies on
while leaving room for the MCP service to attach additional metadata.
"""
from __future__ import annotations

from typing import Dict, List, Literal, NotRequired, TypedDict, Union

__all__ = [
    "JSONScalar",
    "JSONValue",
    "ClipRegion",
    "ViewportMetrics",
    "ScreenshotRequestParams",
    "ScreenshotResult",
    "DomSnapshotRequestParams",
    "DomSnapshotNode",
    "DomSnapshotResult",
    "LogNotificationParams",
    "PlannedCommandPayload",
    "PlanStep",
    "PlanSubmissionParams",
    "PlanSubmissionResult",
    "TelemetryEventPayload",
    "TelemetryNotificationParams",
    "OCRTelemetryPayload",
    "HuggingFaceScoreEntry",
    "HuggingFaceTelemetryPayload",
    "ReasoningTraceEntry",
    "AllowlistFlagsPayload",
    "ProfileCredentialsPayload",
    "ProfileFieldPolicyPayload",
    "ProfileSummaryPayload",
    "ProfileDetailPayload",
    "ProfileUpsertPayload",
    "ProfilesListResult",
    "ProfileGetParams",
    "ProfileGetResult",
    "ProfileUpsertParams",
    "ProfileUpsertResult",
]

JSONScalar = Union[str, int, float, bool, None]
JSONValue = Union[JSONScalar, "JSONArray", "JSONObject"]
JSONArray = List[JSONValue]
JSONObject = Dict[str, JSONValue]


class ClipRegion(TypedDict, total=True):
    """Pixel-space clip rectangle used for screenshot capture."""

    x: float
    """Left coordinate of the clip region."""

    y: float
    """Top coordinate of the clip region."""

    width: float
    """Width of the clip region in pixels."""

    height: float
    """Height of the clip region in pixels."""


class ViewportMetrics(TypedDict, total=False):
    """Viewport metadata accompanying DOM snapshots."""

    width: int
    height: int
    devicePixelRatio: float


class ScreenshotRequestParams(TypedDict, total=False):
    """Parameters accepted by the ``captureScreenshot`` JSON-RPC method."""

    sessionId: str
    """Active MCP session identifier."""

    selector: str
    """CSS selector to focus before taking the screenshot (optional)."""

    clip: ClipRegion
    """Explicit clip rectangle; overrides ``selector`` when supplied."""

    fullPage: bool
    """Capture the entire page when ``True`` (default ``False``)."""

    omitBackground: bool
    """Hide the default browser background before capture."""

    scale: Literal["device", "css"]
    """Screenshot scale policy mirroring Playwright's API."""

    format: Literal["png", "jpeg"]
    """Image encoding format."""

    quality: int
    """JPEG quality (1–100) when ``format`` is ``"jpeg"``."""


class ScreenshotResult(TypedDict, total=False):
    """Result payload returned by ``captureScreenshot``."""

    data: str
    """Base64-encoded image bytes."""

    mimeType: str
    """MIME type describing the image (e.g. ``"image/png"``)."""

    width: int
    height: int
    """Pixel dimensions of the captured image."""

    encoding: Literal["base64"]
    """Encoding flag; currently always ``"base64"``."""

    timestamp: str
    """ISO-8601 timestamp assigned by MCP when the image was captured."""

    clip: NotRequired[ClipRegion]
    """Clip rectangle applied when the screenshot was captured."""

    metadata: NotRequired[Dict[str, JSONValue]]
    """Optional MCP-specific metadata."""


class DomSnapshotRequestParams(TypedDict, total=False):
    """Parameters accepted by the ``getDomSnapshot`` JSON-RPC method."""

    sessionId: str
    """Active MCP session identifier."""

    selector: str
    """Limit the snapshot to a particular subtree."""

    includeHtml: bool
    """When true, include the outer HTML string in the response."""

    includeAccessibilityTree: bool
    """Request the computed accessibility tree in ``nodes`` metadata."""

    maxElements: int
    """Maximum number of DOM nodes to serialise (MCP may truncate)."""


class DomSnapshotNode(TypedDict, total=False):
    """Single node entry within a DOM snapshot result."""

    selector: str
    outerHTML: str
    innerText: str
    attributes: Dict[str, str]
    boundingBox: Dict[str, float]
    accessibility: Dict[str, JSONValue]


class DomSnapshotResult(TypedDict, total=False):
    """Payload returned by the ``getDomSnapshot`` JSON-RPC method."""

    url: str
    title: str
    timestamp: str
    html: str
    nodes: List[DomSnapshotNode]
    viewport: ViewportMetrics


class LogNotificationParams(TypedDict, total=False):
    """Payload emitted via the ``log`` JSON-RPC notification."""

    level: Literal["debug", "info", "warn", "error"]
    message: str
    details: Dict[str, JSONValue]
    sessionId: str
    timestamp: str


class PlanStep(TypedDict, total=False):
    """Structured representation of a single autonomous plan step."""

    id: str
    description: str
    status: Literal["pending", "running", "completed", "failed"]
    target: NotRequired[str]
    command: NotRequired["PlannedCommandPayload"]
    metadata: NotRequired[Dict[str, JSONValue]]


class PlannedCommandPayload(TypedDict, total=False):
    """Minimal representation of a command to execute."""

    command: str
    params: NotRequired[Dict[str, JSONValue]]


class PlanSubmissionParams(TypedDict, total=False):
    """Payload accepted by the optional ``submitPlan`` JSON-RPC method."""

    sessionId: str
    goal: str
    summary: NotRequired[str]
    steps: List[PlanStep]
    rationale: NotRequired[str]
    note: NotRequired[str]
    commands: NotRequired[List[PlannedCommandPayload]]
    profileId: str
    domCandidates: NotRequired[List[Dict[str, JSONValue]]]


class PlanSubmissionResult(TypedDict, total=False):
    """Acknowledgement returned by ``submitPlan``."""

    accepted: bool
    message: NotRequired[str]
    executedCommands: int
    plannerNote: NotRequired[str]
    reason: NotRequired[str]


class OCRTelemetryPayload(TypedDict, total=False):
    """OCR-specific telemetry payload forwarded to the extension."""

    text: str
    """Full OCR text produced for the current context."""

    chunks: NotRequired[List[str]]
    """Optional list of smaller OCR snippets or regions."""

    language: NotRequired[str]
    """BCP-47 language tag detected by OCR."""

    confidence: NotRequired[float]
    """Overall OCR confidence score in the range ``[0, 1]``."""


class HuggingFaceScoreEntry(TypedDict, total=False):
    """Single DOM candidate score emitted by the Hugging Face integration."""

    selector: str
    score: float
    label: NotRequired[str]
    textPreview: NotRequired[str]
    contextSnippet: NotRequired[str]


class HuggingFaceTelemetryPayload(TypedDict, total=False):
    """Structured telemetry describing Hugging Face candidate scoring."""

    model: NotRequired[str]
    latencyMs: NotRequired[float]
    scoredSelectors: List[HuggingFaceScoreEntry]


class ReasoningTraceEntry(TypedDict, total=False):
    """Represents a single planner reasoning step."""

    thought: str
    """Primary reasoning sentence."""

    evidence: NotRequired[str]
    """Supporting evidence or DOM snippet."""

    confidence: NotRequired[float]
    """Planner-assigned confidence in the reasoning step (0-1)."""

    action: NotRequired[str]
    """Planned follow-up action, if any."""


class TelemetryEventPayload(TypedDict, total=False):
    """Telemetry events forwarded from Python to the extension via MCP."""

    sessionId: str
    kind: Literal[
        "reasoning",
        "action",
        "observation",
        "ocr",
        "error",
        "custom",
    ]
    message: str
    data: NotRequired[Dict[str, JSONValue]]
    timestamp: str
    ocr: NotRequired[OCRTelemetryPayload]
    huggingFace: NotRequired[HuggingFaceTelemetryPayload]
    reasoningTrace: NotRequired[List[ReasoningTraceEntry]]


class TelemetryNotificationParams(TypedDict, total=False):
    """Parameters for the ``telemetry.emit`` JSON-RPC notification."""

    event: TelemetryEventPayload
    audience: NotRequired[Literal["extension", "all"]]


class AllowlistFlagsPayload(TypedDict, total=False):
    """Allowlist capabilities associated with a profile."""

    allowCredentialAutomation: bool
    allowSocialAutomation: bool
    allowFinancialAutomation: bool


class ProfileCredentialsPayload(TypedDict, total=False):
    """Credential alias configuration bundled with a profile."""

    usernameField: NotRequired[str]
    usernameAlias: NotRequired[str]
    passwordAlias: NotRequired[str]


class ProfileFieldPolicyPayload(TypedDict, total=False):
    """Field policy metadata describing profile-assisted automation."""

    fieldType: str
    description: NotRequired[str]
    allowGenerate: bool
    profileKey: NotRequired[str]
    sampleValues: NotRequired[List[str]]


class ProfileSummaryPayload(TypedDict, total=False):
    """Lightweight profile summary returned by ``profiles.list``."""

    id: str
    displayName: str
    persona: str
    source: Literal["built-in", "file"]
    hasStoredCredentials: bool


class ProfileDetailPayload(ProfileSummaryPayload, total=False):
    """Full profile representation returned by ``profiles.get`` and ``profiles.upsert``."""

    allowlist: AllowlistFlagsPayload
    credentials: NotRequired[ProfileCredentialsPayload]
    metadata: NotRequired[JSONObject]
    data: NotRequired[Dict[str, str]]
    fieldPolicies: NotRequired[List[ProfileFieldPolicyPayload]]
    automationContext: NotRequired[JSONObject]
    automationContextSource: NotRequired[JSONObject]


class ProfileUpsertPayload(TypedDict, total=False):
    """Profile fields accepted by the ``profiles.upsert`` method."""

    id: NotRequired[str]
    displayName: NotRequired[str]
    persona: NotRequired[str]
    allowlist: NotRequired[AllowlistFlagsPayload]
    credentials: NotRequired[ProfileCredentialsPayload]
    metadata: NotRequired[JSONObject]
    data: NotRequired[JSONObject]
    fieldPolicies: NotRequired[List[ProfileFieldPolicyPayload]]
    automationContext: NotRequired[JSONObject]


class ProfilesListResult(TypedDict, total=False):
    """Result payload produced by ``profiles.list``."""

    profiles: List[ProfileSummaryPayload]


class ProfileGetParams(TypedDict, total=False):
    """Parameters accepted by ``profiles.get``."""

    profileId: NotRequired[str]


class ProfileGetResult(TypedDict, total=False):
    """Result payload returned by ``profiles.get``."""

    profile: ProfileDetailPayload


class ProfileUpsertParams(TypedDict, total=False):
    """Parameters accepted by ``profiles.upsert``."""

    profileId: NotRequired[str]
    profile: ProfileUpsertPayload


class ProfileUpsertResult(TypedDict, total=False):
    """Result payload returned by ``profiles.upsert``."""

    profile: ProfileDetailPayload