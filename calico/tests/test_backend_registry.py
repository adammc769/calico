"""Test backend registry system."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from calico.workflow.backends import (
    BackendRegistry, 
    get_backend_registry, 
    register_backend,
    create_executor_factory
)
from calico.agent.actions import ActionResult
from calico.agent import AIAction


class MockExecutor:
    """Mock executor for testing."""
    
    async def execute(self, action: AIAction) -> ActionResult:
        return ActionResult(success=True, message="mock execution")


@pytest.fixture
def registry():
    """Create a fresh registry for testing."""
    return BackendRegistry()


def test_backend_registry_initialization(registry):
    """Test that registry initializes with MCP backend."""
    backends = registry.list_backends()
    
    assert "mcp" in backends
    assert backends["mcp"].name == "mcp"
    assert backends["mcp"].is_available
    assert "MCP" in backends["mcp"].description
    
    # MCP should be the default
    assert registry.get_default_backend() == "mcp"


def test_register_custom_backend(registry):
    """Test registering a custom backend."""
    
    def mock_factory(**kwargs):
        async def factory():
            return MockExecutor(), AsyncMock()
        return factory
    
    registry.register_backend(
        name="test_backend",
        description="Test backend for testing",
        factory_func=mock_factory,
        requirements=["test_requirement"],
        is_available=True
    )
    
    backends = registry.list_backends()
    assert "test_backend" in backends
    assert backends["test_backend"].description == "Test backend for testing"
    assert backends["test_backend"].requirements == ["test_requirement"]


def test_unavailable_backend(registry):
    """Test that unavailable backends raise errors."""
    
    def mock_factory(**kwargs):
        async def factory():
            return MockExecutor(), AsyncMock()
        return factory
    
    registry.register_backend(
        name="unavailable_backend",
        description="Unavailable backend",
        factory_func=mock_factory,
        is_available=False
    )
    
    with pytest.raises(RuntimeError, match="not available"):
        registry.get_backend("unavailable_backend")


def test_nonexistent_backend(registry):
    """Test that requesting nonexistent backend raises error."""
    
    with pytest.raises(ValueError, match="Backend 'nonexistent' not found"):
        registry.get_backend("nonexistent")


def test_available_backends_filter(registry):
    """Test that get_available_backends filters correctly."""
    
    def mock_factory(**kwargs):
        async def factory():
            return MockExecutor(), AsyncMock()
        return factory
    
    registry.register_backend("available", "Available", mock_factory, is_available=True)
    registry.register_backend("unavailable", "Unavailable", mock_factory, is_available=False)
    
    available = registry.get_available_backends()
    assert "available" in available
    assert "unavailable" not in available
    assert "mcp" in available  # Built-in MCP backend


@patch('calico.workflow.backends.create_mcp_executor')
@patch('calico.workflow.backends.get_settings')
def test_mcp_factory_creation(mock_get_settings, mock_create_mcp, registry):
    """Test MCP factory creation with proper parameters."""
    
    # Mock settings
    mock_settings = MagicMock()
    mock_settings.mcp_ws_url = "ws://test:7001"
    mock_settings.mcp_request_timeout_seconds = 45.0
    mock_settings.agent_max_retries = 5
    mock_get_settings.return_value = mock_settings
    
    # Mock MCP executor creation
    mock_executor = MockExecutor()
    mock_cleanup = AsyncMock()
    mock_create_mcp.return_value = (mock_executor, mock_cleanup)
    
    # Create factory
    factory = registry.create_executor_factory(
        backend_name="mcp",
        session_id="test-session",
        notification_handler=AsyncMock()
    )
    
    # Factory should be callable
    assert callable(factory)


def test_global_registry_functions():
    """Test global registry convenience functions."""
    
    def mock_factory(**kwargs):
        async def factory():
            return MockExecutor(), AsyncMock()
        return factory
    
    # Test global register function
    register_backend(
        name="global_test",
        description="Global test backend",
        factory_func=mock_factory
    )
    
    # Should be in global registry
    global_registry = get_backend_registry()
    assert "global_test" in global_registry.list_backends()


def test_backend_error_handling(registry):
    """Test error handling in backend creation."""
    
    def failing_factory(**kwargs):
        raise RuntimeError("Factory failed")
    
    registry.register_backend(
        name="failing_backend",
        description="Backend that fails",
        factory_func=failing_factory
    )
    
    with pytest.raises(RuntimeError, match="Failed to create executor factory"):
        registry.create_executor_factory(backend_name="failing_backend")


def test_mcp_parameter_validation(registry):
    """Test that MCP backend requires session_id."""
    
    with pytest.raises(RuntimeError, match="Failed to create executor factory.*requires 'session_id'"):
        registry.create_executor_factory(backend_name="mcp")


def test_backend_mode_validation(registry):
    """Test validation of backend modes."""
    
    # Should provide helpful error for unknown backend
    with pytest.raises(ValueError) as exc_info:
        registry.create_executor_factory(backend_name="unknown_backend")
    
    error_msg = str(exc_info.value)
    assert "not available" in error_msg
    assert "Available backends:" in error_msg
    assert "mcp" in error_msg
    assert "Only 'mcp' backend is provided with Calico" in error_msg