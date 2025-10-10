"""Test orchestrator backend integration."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import os

from calico.workflow.orchestrator import (
    _determine_backend_mode, 
    _create_backend_executor_factory,
    _legacy_default_executor_factory
)
from calico.workflow.config import get_settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.backend_mode = "mcp"
    settings.use_mcp_backend = True
    settings.mcp_ws_url = "ws://test:7001"
    settings.mcp_request_timeout_seconds = 30.0
    settings.agent_max_retries = 3
    settings.mcp_session_prefix = "test"
    return settings


def test_determine_backend_mode_with_backend_mode():
    """Test backend mode determination with BACKEND_MODE set."""
    settings = MagicMock()
    settings.backend_mode = "custom"
    settings.use_mcp_backend = True
    
    result = _determine_backend_mode(settings)
    assert result == "custom"


def test_determine_backend_mode_with_use_mcp_backend():
    """Test backend mode determination with legacy USE_MCP_BACKEND."""
    settings = MagicMock()
    settings.backend_mode = ""  # Empty string
    settings.use_mcp_backend = True
    
    result = _determine_backend_mode(settings)
    assert result == "mcp"
    
    settings.use_mcp_backend = False
    result = _determine_backend_mode(settings)
    assert result == "default"


def test_determine_backend_mode_default():
    """Test backend mode determination with defaults."""
    settings = MagicMock()
    # Remove the attributes to test default behavior
    del settings.backend_mode
    del settings.use_mcp_backend
    
    result = _determine_backend_mode(settings)
    assert result == "mcp"


@patch('calico.workflow.orchestrator.get_backend_registry')
def test_create_backend_executor_factory_mcp(mock_get_registry, mock_settings):
    """Test MCP backend factory creation."""
    mock_registry = MagicMock()
    mock_factory = AsyncMock()
    mock_registry.create_executor_factory.return_value = mock_factory
    mock_get_registry.return_value = mock_registry
    
    notification_handler = AsyncMock()
    result = _create_backend_executor_factory(
        backend_mode="mcp",
        session_identifier="test-session",
        settings=mock_settings,
        notification_handler=notification_handler
    )
    
    assert result == mock_factory
    # Check the call was made with correct parameters
    call_args = mock_registry.create_executor_factory.call_args
    assert call_args[1]['backend_name'] == "mcp"
    assert call_args[1]['session_id'] == "test-session"
    assert call_args[1]['url'] == mock_settings.mcp_ws_url
    assert call_args[1]['notification_handler'] == notification_handler


@patch('calico.workflow.orchestrator.get_backend_registry')
def test_create_backend_executor_factory_custom(mock_get_registry):
    """Test custom backend factory creation."""
    mock_registry = MagicMock()
    mock_factory = AsyncMock()
    mock_registry.create_executor_factory.return_value = mock_factory
    mock_get_registry.return_value = mock_registry
    
    settings = MagicMock()
    notification_handler = AsyncMock()
    
    result = _create_backend_executor_factory(
        backend_mode="custom",
        session_identifier="test-session",
        settings=settings,
        notification_handler=notification_handler
    )
    
    assert result == mock_factory
    # Check the call was made with correct parameters
    call_args = mock_registry.create_executor_factory.call_args
    assert call_args[1]['backend_name'] == "custom"
    assert call_args[1]['session_id'] == "test-session"
    assert call_args[1]['notification_handler'] == notification_handler


@patch('calico.workflow.orchestrator.get_backend_registry')
def test_create_backend_executor_factory_error(mock_get_registry):
    """Test error handling in backend factory creation."""
    mock_registry = MagicMock()
    mock_registry.create_executor_factory.side_effect = ValueError("Backend not found")
    mock_get_registry.return_value = mock_registry
    
    settings = MagicMock()
    
    with pytest.raises(ValueError, match="Backend 'unknown' is not available"):
        _create_backend_executor_factory(
            backend_mode="unknown",
            session_identifier="test-session",
            settings=settings
        )


@pytest.mark.asyncio
async def test_legacy_default_executor_factory():
    """Test that legacy default executor factory raises helpful error."""
    with pytest.raises(RuntimeError) as exc_info:
        await _legacy_default_executor_factory()
    
    error_msg = str(exc_info.value)
    assert "Direct Playwright executor is no longer supported" in error_msg
    assert "MCP backend" in error_msg
    assert "BACKEND_MODE=mcp" in error_msg
    assert "USE_MCP_BACKEND=true" in error_msg


def test_environment_variable_integration():
    """Test that environment variables are properly read."""
    # Test with current environment
    settings = get_settings()
    
    # Should have backend_mode attribute
    assert hasattr(settings, 'backend_mode')
    assert hasattr(settings, 'use_mcp_backend')
    
    # Test backend mode determination
    backend_mode = _determine_backend_mode(settings)
    assert backend_mode in ["mcp", "default"]  # Should be one of the valid options


@patch.dict(os.environ, {'BACKEND_MODE': 'test_backend'}, clear=False)
@patch('calico.workflow.config.get_settings')
def test_backend_mode_environment_override(mock_get_settings):
    """Test that BACKEND_MODE environment variable is respected."""
    mock_settings = MagicMock()
    mock_settings.backend_mode = "test_backend"
    mock_settings.use_mcp_backend = True
    mock_get_settings.return_value = mock_settings
    
    backend_mode = _determine_backend_mode(mock_settings)
    assert backend_mode == "test_backend"


@patch.dict(os.environ, {'USE_MCP_BACKEND': 'false', 'BACKEND_MODE': ''}, clear=False)
@patch('calico.workflow.config.get_settings')
def test_legacy_flag_precedence(mock_get_settings):
    """Test that legacy USE_MCP_BACKEND works when BACKEND_MODE is empty."""
    mock_settings = MagicMock()
    mock_settings.backend_mode = ""  # Empty string
    mock_settings.use_mcp_backend = False
    mock_get_settings.return_value = mock_settings
    
    backend_mode = _determine_backend_mode(mock_settings)
    assert backend_mode == "default"


def test_notification_handler_integration(mock_settings):
    """Test that notification handler is properly integrated."""
    
    def mock_handler(method: str, params: dict):
        # Mock notification handler
        pass
    
    with patch('calico.workflow.orchestrator.get_backend_registry') as mock_get_registry:
        mock_registry = MagicMock()
        mock_factory = AsyncMock()
        mock_registry.create_executor_factory.return_value = mock_factory
        mock_get_registry.return_value = mock_registry
        
        result = _create_backend_executor_factory(
            backend_mode="mcp",
            session_identifier="test-session",
            settings=mock_settings,
            notification_handler=mock_handler
        )
        
        # Check that notification handler was passed
        call_args = mock_registry.create_executor_factory.call_args
        assert call_args[1]['notification_handler'] is not None