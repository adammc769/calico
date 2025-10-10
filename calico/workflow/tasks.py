"""Celery tasks for orchestrating DOM unit workflows."""
from __future__ import annotations

import json
import logging
from typing import Optional

from celery import shared_task
from playwright.sync_api import sync_playwright

from calico.utils.dom_units import collect_dom_units
from calico.workflow.orchestrator import AgentRunError, orchestrate_workflow, run_agent_session

from .config import get_settings
from .db import ScrapeRun, get_session, init_db

logger = logging.getLogger(__name__)


def _launch_browser(playwright_browser: str):
    """Launch a Playwright browser based on configured browser name."""

    with sync_playwright() as playwright:
        browser_type = getattr(playwright, playwright_browser, None)
        if browser_type is None:
            raise ValueError(f"Unsupported Playwright browser '{playwright_browser}'")
        browser = browser_type.launch(headless=True)
        page = browser.new_page()
        try:
            yield page
        finally:
            page.close()
            browser.close()


@shared_task(bind=True, name="calico.workflow.tasks.collect_dom_units")
def collect_dom_units_task(self, url: str, limit: Optional[int] = None) -> dict:
    """Scrape logical DOM units from the provided URL and persist the result."""

    settings = get_settings()
    init_db()

    with get_session() as session:
        run = ScrapeRun(url=url, status="running")
        session.add(run)
        session.flush()
        run_id = run.id

    logger.info("Starting DOM unit collection", extra={"url": url, "run_id": run_id})

    try:
        with sync_playwright() as playwright:
            browser_type = getattr(playwright, settings.playwright_browser, None)
            if browser_type is None:
                raise ValueError(
                    f"Unsupported Playwright browser '{settings.playwright_browser}'"
                )
            browser = browser_type.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            try:
                page.goto(url, wait_until="networkidle")
                units = collect_dom_units(page, limit=limit)
            finally:
                context.close()
                browser.close()

        payload = [unit.to_dict() for unit in units]

        with get_session() as session:
            run = session.get(ScrapeRun, run_id)
            if run is not None:
                run.status = "completed"
                run.unit_count = len(payload)
                run.payload = json.dumps(payload)
        logger.info(
            "Completed DOM unit collection",
            extra={"url": url, "run_id": run_id, "unit_count": len(payload)},
        )
        return {"run_id": run_id, "unit_count": len(payload)}
    except Exception as exc:  # pragma: no cover - integration behavior
        logger.exception(
            "DOM unit collection failed",
            extra={"url": url, "run_id": run_id},
        )
        with get_session() as session:
            run = session.get(ScrapeRun, run_id)
            if run is not None:
                run.status = "failed"
                run.payload = json.dumps({"error": str(exc)})
        raise


@shared_task(bind=True, name="calico.workflow.tasks.run_agent_session")
def run_agent_session_task(
    self,
    *,
    agent_name: str,
    goal: str,
    context: Optional[dict] = None,
    workflow_id: Optional[str] = None,
    llm_config: Optional[dict] = None,
) -> dict:
    """Execute an agent session with retry-aware error handling."""

    settings = get_settings()
    try:
        result = run_agent_session(
            agent_name=agent_name,
            goal=goal,
            context=context or {},
            workflow_id=workflow_id,
            llm_config=llm_config,
            raise_on_failure=True,
        )
        return result.to_dict()
    except AgentRunError as exc:
        retries = getattr(self.request, "retries", 0)
        if retries < settings.agent_max_retries:
            countdown = int(settings.agent_retry_backoff_seconds * (retries + 1))
            raise self.retry(exc=exc, countdown=countdown)
        logger.error(
            "Agent %s exceeded retry budget; returning failure payload", agent_name, exc_info=exc
        )
        return exc.result.to_dict()


@shared_task(bind=True, name="calico.workflow.tasks.orchestrate_workflow")
def orchestrate_workflow_task(
    self,
    *,
    goal: str,
    agents: list[dict],
    context: Optional[dict] = None,
    workflow_id: Optional[str] = None,
    llm_config: Optional[dict] = None,
) -> dict:
    """Coordinate multiple agent sessions and return a workflow summary."""

    if not isinstance(agents, list) or not agents:
        raise ValueError("'agents' must be a non-empty list of agent specifications")

    result = orchestrate_workflow(
        goal=goal,
        agents=agents,
        context=context,
        workflow_id=workflow_id,
        llm_config=llm_config,
    )
    return result


def enqueue_dom_unit_collection(url: str, limit: Optional[int] = None):
    """Convenience helper for scheduling the DOM unit collection task."""

    return collect_dom_units_task.delay(url=url, limit=limit)
