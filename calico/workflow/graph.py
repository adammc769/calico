"""Neo4j graph helpers for workflow orchestration."""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict

from .config import get_settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency guard
    from neo4j import GraphDatabase, basic_auth
except Exception:  # pragma: no cover - dependency missing at runtime
    GraphDatabase = None  # type: ignore
    basic_auth = None  # type: ignore


@dataclass(slots=True)
class GraphSettings:
    uri: str
    user: str
    password: str
    database: str


class GraphService:
    """Thin wrapper around the Neo4j Python driver."""

    def __init__(self, settings: GraphSettings) -> None:
        if GraphDatabase is None or basic_auth is None:
            raise ImportError("neo4j driver is not installed; cannot create GraphService")
        self._settings = settings
        self._driver = GraphDatabase.driver(
            settings.uri,
            auth=basic_auth(settings.user, settings.password),
        )

    def close(self) -> None:
        if getattr(self, "_driver", None):
            self._driver.close()

    @contextmanager
    def _session(self):
        session = self._driver.session(database=self._settings.database)
        try:
            yield session
        finally:
            session.close()

    def upsert_agent_run(self, *, run_id: int, agent_name: str, goal: str, status: str) -> None:
        query = """
        MERGE (r:AgentRun {id: $run_id})
          ON CREATE SET r.goal = $goal, r.agent_name = $agent_name, r.status = $status, r.created_at = datetime()
          ON MATCH SET r.goal = $goal, r.agent_name = $agent_name, r.status = $status, r.updated_at = datetime()
        MERGE (a:Agent {name: $agent_name})
        MERGE (a)-[:EXECUTED]->(r)
        """
        self._execute_write(query, run_id=run_id, agent_name=agent_name, goal=goal, status=status)

    def append_event(self, *, run_id: int, step: int, phase: str, success: bool, message: str | None, data: Dict[str, Any] | None) -> None:
        query = """
        MATCH (r:AgentRun {id: $run_id})
        CREATE (e:AgentEvent {
            id: apoc.create.uuid(),
            step: $step,
            phase: $phase,
            success: $success,
            message: $message,
            data: $data,
            created_at: datetime()
        })
        MERGE (r)-[:EMITTED]->(e)
        """
        payload = data or {}
        self._execute_write(query, run_id=run_id, step=step, phase=phase, success=success, message=message, data=json.dumps(payload))

    def upsert_error(self, *, run_id: int, error: str) -> None:
        query = """
        MATCH (r:AgentRun {id: $run_id})
        SET r.error = $error, r.status = COALESCE(r.status, 'failed'), r.finished_at = datetime()
        MERGE (err:AgentError {message: $error})
        MERGE (r)-[:RAISED]->(err)
        """
        self._execute_write(query, run_id=run_id, error=error)

    def complete_run(self, *, run_id: int) -> None:
        query = """
        MATCH (r:AgentRun {id: $run_id})
        SET r.status = 'completed', r.finished_at = datetime()
        """
        self._execute_write(query, run_id=run_id)

    def start_workflow(self, *, workflow_id: str, goal: str) -> None:
        query = """
        MERGE (w:Workflow {id: $workflow_id})
          ON CREATE SET w.goal = $goal, w.created_at = datetime(), w.status = 'running'
          ON MATCH SET w.goal = $goal, w.updated_at = datetime(), w.status = 'running'
        """
        self._execute_write(query, workflow_id=workflow_id, goal=goal)

    def link_workflow_run(self, *, workflow_id: str, run_id: int) -> None:
        query = """
        MATCH (w:Workflow {id: $workflow_id})
        MATCH (r:AgentRun {id: $run_id})
        MERGE (w)-[:INCLUDES]->(r)
        """
        self._execute_write(query, workflow_id=workflow_id, run_id=run_id)

    def complete_workflow(self, *, workflow_id: str, status: str) -> None:
        query = """
        MATCH (w:Workflow {id: $workflow_id})
        SET w.status = $status, w.finished_at = datetime()
        """
        self._execute_write(query, workflow_id=workflow_id, status=status)

    def _execute_write(self, query: str, **params: Any) -> None:
        with self._session() as session:
            session.execute_write(lambda tx: tx.run(query, **params))


class NullGraphService:
    """No-op implementation used when Neo4j is not configured."""

    def close(self) -> None:  # pragma: no cover - trivial
        return

    def upsert_agent_run(self, **kwargs: Any) -> None:
        logger.debug("Neo4j disabled; skipping upsert_agent_run", extra={"kwargs": kwargs})

    def append_event(self, **kwargs: Any) -> None:
        logger.debug("Neo4j disabled; skipping append_event", extra={"kwargs": kwargs})

    def upsert_error(self, **kwargs: Any) -> None:
        logger.debug("Neo4j disabled; skipping upsert_error", extra={"kwargs": kwargs})

    def complete_run(self, **kwargs: Any) -> None:
        logger.debug("Neo4j disabled; skipping complete_run", extra={"kwargs": kwargs})

    def start_workflow(self, **kwargs: Any) -> None:
        logger.debug("Neo4j disabled; skipping start_workflow", extra={"kwargs": kwargs})

    def link_workflow_run(self, **kwargs: Any) -> None:
        logger.debug("Neo4j disabled; skipping link_workflow_run", extra={"kwargs": kwargs})

    def complete_workflow(self, **kwargs: Any) -> None:
        logger.debug("Neo4j disabled; skipping complete_workflow", extra={"kwargs": kwargs})


def get_graph_service() -> GraphService | NullGraphService:
    settings = get_settings()
    if not settings.neo4j_enabled:
        return NullGraphService()
    try:
        graph_settings = GraphSettings(
            uri=settings.neo4j_uri or "",
            user=settings.neo4j_user or "",
            password=settings.neo4j_password or "",
            database=settings.neo4j_database,
        )
        return GraphService(graph_settings)
    except Exception as exc:  # pragma: no cover - fallback when driver missing
        logger.warning("Failed to initialise Neo4j driver; falling back to no-op service", exc_info=exc)
        return NullGraphService()