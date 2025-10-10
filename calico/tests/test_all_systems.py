from __future__ import annotations

from io import BytesIO

import pytest

from PIL import Image

from calico.agent.actions import AIAction, ActionResult
from calico.agent.session import AISession
from calico.agent.llm import LLMPlan
from calico.applications import JobApplication, PersonalInformation, PositionDetails
from calico.workflow.config import Settings
from calico.vision.preprocess import PreprocessConfig, preprocess_image_bytes


class _DummyLLM:
    """Simple LLM stub that emits a single action followed by completion."""

    def __init__(self) -> None:
        self._calls = 0

    async def plan_actions(self, *, goal, context, state, error=None) -> LLMPlan:  # type: ignore[override]
        self._calls += 1
        if self._calls == 1:
            action = AIAction(type="click", target="#submit")
            return LLMPlan(actions=[action], reasoning="submit form", done=True)
        return LLMPlan(actions=[], reasoning="done", done=True)


class _DummyExecutor:
    """Executor stub that records actions without hitting Playwright."""

    def __init__(self) -> None:
        self.actions: list[AIAction] = []

    async def execute(self, action: AIAction) -> ActionResult:
        self.actions.append(action)
        return ActionResult(success=True, message="ok")


@pytest.mark.asyncio
async def test_agent_session_happy_path() -> None:
    llm = _DummyLLM()
    executor = _DummyExecutor()
    session = AISession(llm, executor, max_turns=2)

    state = await session.run("Submit the form", context={"url": "https://example.com"})

    assert state.completed is True
    assert state.failure_count == 0
    assert executor.actions and executor.actions[0].target == "#submit"


def _image_bytes(gray: int) -> bytes:
    image = Image.new("L", (8, 8), color=gray)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_preprocess_image_bytes_thresholding() -> None:
    raw = _image_bytes(200)
    config = PreprocessConfig(threshold=150, scale=1.0, denoise=False)

    processed = preprocess_image_bytes(raw, config=config)

    with Image.open(BytesIO(processed)) as converted:
        assert converted.mode == "L"
        assert set(converted.getdata()) == {255}


def test_job_application_payload_round_trip() -> None:
    application = JobApplication(
        personal_information=PersonalInformation(full_legal_name="Ada Lovelace", contact_email="ada@example.com"),
        position_details=PositionDetails(position_applied_for="Automation Engineer"),
    )
    application.profile_id = "principal-agent"

    payload = application.to_payload()

    assert payload["personal_information"]["full_legal_name"] == "Ada Lovelace"
    assert payload["position_details"]["position_applied_for"] == "Automation Engineer"
    assert payload["metadata"]["profile_id"] == "principal-agent"
    assert "created_at" in payload and payload["created_at"].endswith("+00:00")


def test_workflow_settings_resolves_sqlite(tmp_path, monkeypatch) -> None:
    sqlite_path = tmp_path / "calico.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SQLITE_PATH", str(sqlite_path))

    settings = Settings()
    resolved = settings.resolved_database_url()

    assert resolved.startswith("sqlite:///")
    assert resolved.endswith("calico.db")
    assert sqlite_path.parent.exists()
