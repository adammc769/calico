"""Async client for the Playwright MCP JSON-RPC service."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Dict, Optional

import websockets
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

logger = logging.getLogger(__name__)

NotificationHandler = Callable[[str, Dict[str, Any]], Awaitable[None] | None]


@dataclass(slots=True)
class MCPError(Exception):
    """Represents an error returned by the MCP backend."""

    code: int
    message: str
    data: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"MCP error {self.code}: {self.message}"


class MCPClient:
    """Lightweight JSON-RPC client for the Playwright MCP backend."""

    def __init__(
        self,
        url: str,
        *,
        request_timeout: float = 30.0,
        notification_handler: NotificationHandler | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._url = url
        self._request_timeout = request_timeout
        self._notification_handler = notification_handler
        self._loop = loop or asyncio.get_event_loop()

        self._socket: WebSocketClientProtocol | None = None
        self._receiver_task: asyncio.Task[None] | None = None
        self._pending: dict[str, asyncio.Future[Any]] = {}
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._socket is not None and not self._socket.closed

    async def connect(self) -> None:
        async with self._lock:
            if self.connected:
                return
            logger.debug("Connecting to MCP backend", extra={"url": self._url})
            self._socket = await websockets.connect(self._url, ping_interval=20, ping_timeout=20)
            self._receiver_task = self._loop.create_task(self._receiver())

    async def close(self) -> None:
        async with self._lock:
            if self._receiver_task and not self._receiver_task.done():
                self._receiver_task.cancel()
                try:
                    await self._receiver_task
                except asyncio.CancelledError:
                    pass
            self._receiver_task = None

            if self._socket and not self._socket.closed:
                await self._socket.close()
            self._socket = None

            # fail any pending requests
            while self._pending:
                _, fut = self._pending.popitem()
                if not fut.done():
                    fut.set_exception(ConnectionClosedError(0, "connection closed"))

    async def __aenter__(self) -> "MCPClient":  # pragma: no cover - convenience
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - convenience
        await self.close()

    async def call(self, method: str, params: Dict[str, Any] | None = None, *, timeout: float | None = None) -> Any:
        await self._ensure_connection()
        assert self._socket is not None

        request_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }

        future: asyncio.Future[Any] = self._loop.create_future()
        self._pending[request_id] = future

        message = json.dumps(payload)
        logger.debug("Sending MCP request", extra={"method": method, "id": request_id})
        await self._socket.send(message)

        try:
            result = await asyncio.wait_for(future, timeout or self._request_timeout)
        finally:
            self._pending.pop(request_id, None)
        return result

    async def notify(self, method: str, params: Dict[str, Any] | None = None) -> None:
        await self._ensure_connection()
        assert self._socket is not None
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        await self._socket.send(json.dumps(payload))

    async def _ensure_connection(self) -> None:
        if not self.connected:
            await self.connect()

    async def _receiver(self) -> None:
        assert self._socket is not None
        try:
            async for raw in self._socket:
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON from MCP backend")
                    continue

                if isinstance(message, dict) and "id" in message:
                    await self._handle_response(message)
                elif isinstance(message, dict) and "method" in message:
                    await self._handle_notification(message)
                else:
                    logger.debug("Ignoring unrecognized MCP message", extra={"message": message})
        except (ConnectionClosedOK, ConnectionClosedError) as exc:
            logger.info("MCP connection closed", extra={"reason": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Unexpected MCP receiver error", exc_info=exc)
        finally:
            # ensure pending futures are failed if receiver exits unexpectedly
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionClosedError(0, "connection closed"))
            self._pending.clear()
            if self._socket and not self._socket.closed:
                await self._socket.close()
            self._socket = None

    async def _handle_response(self, message: Dict[str, Any]) -> None:
        request_id = str(message.get("id"))
        future = self._pending.get(request_id)
        if not future:
            logger.debug("No pending request for MCP response", extra={"id": request_id})
            return
        if future.done():
            return

        if "error" in message:
            error = message["error"] or {}
            fut_error = MCPError(int(error.get("code", -32000)), str(error.get("message", "unknown error")), error.get("data"))
            future.set_exception(fut_error)
        else:
            future.set_result(message.get("result"))

    async def _handle_notification(self, message: Dict[str, Any]) -> None:
        handler = self._notification_handler
        if not handler:
            return
        method = str(message.get("method"))
        params: Dict[str, Any] = message.get("params") if isinstance(message.get("params"), dict) else {}
        try:
            maybe_awaitable = handler(method, params)
            if asyncio.iscoroutine(maybe_awaitable):
                await maybe_awaitable
        except Exception:  # pragma: no cover - defensive
            logger.exception("Notification handler raised", extra={"method": method})