"""Backend registry system for executor selection and management."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, Mapping, Tuple
from dataclasses import dataclass

from calico.agent.actions import ActionResult
from calico.agent import AIAction
from calico.agent.mcp_executor import create_mcp_executor
from calico.workflow.config import get_settings

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Protocol for action executors."""
    
    async def execute(self, action: AIAction) -> ActionResult:
        """Execute an action and return the result."""
        ...


ExecutorFactory = Callable[[], Awaitable[Tuple[ActionExecutor, Callable[[], Awaitable[None]]]]]


@dataclass
class BackendInfo:
    """Information about a registered backend."""
    
    name: str
    description: str
    factory_func: Callable[..., ExecutorFactory]
    requirements: list[str]
    is_available: bool


class BackendRegistry:
    """Registry for managing automation backends."""
    
    def __init__(self):
        self._backends: Dict[str, BackendInfo] = {}
        self._default_backend: str | None = None
        self._register_builtin_backends()
    
    def register_backend(
        self,
        name: str,
        description: str,
        factory_func: Callable[..., ExecutorFactory],
        requirements: list[str] | None = None,
        is_available: bool = True
    ) -> None:
        """Register a new backend."""
        self._backends[name] = BackendInfo(
            name=name,
            description=description,
            factory_func=factory_func,
            requirements=requirements or [],
            is_available=is_available
        )
        logger.debug(f"Registered backend: {name}")
    
    def get_backend(self, name: str) -> BackendInfo:
        """Get backend info by name."""
        if name not in self._backends:
            available = list(self._backends.keys())
            raise ValueError(
                f"Backend '{name}' not found. Available backends: {available}"
            )
        
        backend = self._backends[name]
        if not backend.is_available:
            raise RuntimeError(
                f"Backend '{name}' is registered but not available. "
                f"Requirements: {backend.requirements}"
            )
        
        return backend
    
    def list_backends(self) -> Dict[str, BackendInfo]:
        """List all registered backends."""
        return dict(self._backends)
    
    def get_available_backends(self) -> Dict[str, BackendInfo]:
        """Get only available backends."""
        return {
            name: info for name, info in self._backends.items()
            if info.is_available
        }
    
    def set_default_backend(self, name: str) -> None:
        """Set the default backend."""
        self.get_backend(name)  # Validate backend exists and is available
        self._default_backend = name
        logger.info(f"Set default backend to: {name}")
    
    def get_default_backend(self) -> str:
        """Get the default backend name."""
        if self._default_backend is None:
            available = list(self.get_available_backends().keys())
            if not available:
                raise RuntimeError("No backends are available")
            self._default_backend = available[0]
            logger.info(f"Auto-selected default backend: {self._default_backend}")
        
        return self._default_backend
    
    def create_executor_factory(
        self,
        backend_name: str | None = None,
        **kwargs
    ) -> ExecutorFactory:
        """Create an executor factory for the specified backend."""
        if backend_name is None:
            backend_name = self.get_default_backend()
        
        try:
            backend = self.get_backend(backend_name)
        except ValueError as exc:
            # Enhance error message for better user experience
            available = list(self.get_available_backends().keys())
            raise ValueError(
                f"Backend '{backend_name}' is not available. "
                f"Available backends: {available}. "
                f"Only 'mcp' backend is provided with Calico. "
                f"Other backends can be registered via the backend registry."
            ) from exc
        
        logger.info(f"Creating executor factory for backend: {backend_name}")
        
        try:
            return backend.factory_func(**kwargs)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to create executor factory for backend '{backend_name}': {exc}"
            ) from exc
    
    def _register_builtin_backends(self) -> None:
        """Register built-in backends."""
        # Register local Playwright backend (direct, no MCP)
        self.register_backend(
            name="local",
            description="Local Playwright backend (direct browser control, no MCP required)",
            factory_func=self._create_local_factory,
            requirements=["playwright"],
            is_available=True
        )
        
        # Register MCP backend
        self.register_backend(
            name="mcp",
            description="MCP (Model Context Protocol) backend via WebSocket JSON-RPC",
            factory_func=self._create_mcp_factory,
            requirements=["websockets", "playwright-mcp service"],
            is_available=True
        )
        
        # Set local as default for easier setup
        self.set_default_backend("local")
    
    def _create_local_factory(self, **kwargs) -> ExecutorFactory:
        """Create local Playwright executor factory."""
        from calico.workflow.local_backend import create_local_executor
        
        settings = get_settings()
        
        # Extract parameters
        session_id = kwargs.get("session_id")
        if not session_id:
            raise ValueError("Local backend requires 'session_id' parameter")
        
        notification_handler = kwargs.get("notification_handler")
        headless = kwargs.get("headless", settings.playwright_headless)
        stealth_mode = kwargs.get("stealth_mode", settings.playwright_stealth_mode)
        max_action_retries = kwargs.get("max_action_retries", settings.agent_max_retries)
        
        async def _local_factory() -> Tuple[ActionExecutor, Callable[[], Awaitable[None]]]:
            return await create_local_executor(
                session_id=session_id,
                headless=headless,
                stealth_mode=stealth_mode,
                max_action_retries=max_action_retries,
                notification_handler=notification_handler,
            )
        
        return _local_factory
    
    def _create_mcp_factory(self, **kwargs) -> ExecutorFactory:
        """Create MCP executor factory."""
        settings = get_settings()
        
        # Extract MCP-specific parameters
        session_id = kwargs.get("session_id")
        if not session_id:
            raise ValueError("MCP backend requires 'session_id' parameter")
        
        notification_handler = kwargs.get("notification_handler")
        
        # Use settings defaults with override capability
        url = kwargs.get("url", settings.mcp_ws_url)
        request_timeout = kwargs.get("request_timeout", settings.mcp_request_timeout_seconds)
        max_action_retries = kwargs.get("max_action_retries", settings.agent_max_retries)
        
        async def _mcp_factory() -> Tuple[ActionExecutor, Callable[[], Awaitable[None]]]:
            return await create_mcp_executor(
                url=url,
                session_id=session_id,
                request_timeout=request_timeout,
                max_action_retries=max_action_retries,
                notification_handler=notification_handler,
            )
        
        return _mcp_factory


# Global registry instance
_registry = BackendRegistry()


def get_backend_registry() -> BackendRegistry:
    """Get the global backend registry."""
    return _registry


def register_backend(
    name: str,
    description: str,
    factory_func: Callable[..., ExecutorFactory],
    requirements: list[str] | None = None,
    is_available: bool = True
) -> None:
    """Register a backend with the global registry."""
    _registry.register_backend(
        name=name,
        description=description,
        factory_func=factory_func,
        requirements=requirements,
        is_available=is_available
    )


def create_executor_factory(
    backend_name: str | None = None,
    **kwargs
) -> ExecutorFactory:
    """Create an executor factory using the global registry."""
    return _registry.create_executor_factory(backend_name=backend_name, **kwargs)