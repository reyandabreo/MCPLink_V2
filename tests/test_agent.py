import pytest
from app.sandbox.limits import resolve_sandbox_path
from app.core.exceptions import PolicyViolationError
from app.core.agent import AgentOrchestrator
from app.tools.registry import tool_registry

# Setup dummy imports to register tools
import app.tools.filesystem 

def test_sandbox_path_normalization():
    """Test that path traversal is blocked."""
    with pytest.raises(PolicyViolationError):
        # Attempt to escape sandbox
        resolve_sandbox_path("../../../etc/passwd")

def test_sandbox_valid_path():
    """Test that valid relative paths are resolved inside sandbox."""
    path = resolve_sandbox_path("test_file.txt")
    assert "sandbox/workspace/test_file.txt" in str(path).replace("\\", "/")

def test_tool_registry():
    """Test tools are registered correctly."""
    tool = tool_registry.get_tool("create_file")
    assert tool.name == "create_file"
    assert "path" in tool.args_schema.model_fields
    assert "content" in tool.args_schema.model_fields

def test_create_session():
    """Test agent orchestrator session creation."""
    agent = AgentOrchestrator()
    session_id = agent.create_session()
    assert session_id is not None
    assert isinstance(session_id, str)
