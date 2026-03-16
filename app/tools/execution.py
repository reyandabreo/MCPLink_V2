import subprocess
from pydantic import BaseModel, Field
from app.tools.registry import tool_registry
from app.sandbox.limits import resolve_sandbox_path
from app.config import settings
from app.core.exceptions import ToolExecutionError

class RunPythonArgs(BaseModel):
    script_path: str = Field(..., description="Path to the Python script to execute within the sandbox.")

@tool_registry.register(
    "run_python",
    "Executes a Python script within the sandbox directory.",
    RunPythonArgs
)
def run_python(args: RunPythonArgs) -> str:
    try:
        result = subprocess.run(
            ["python", args.script_path],
            capture_output=True,
            text=True,
            timeout=settings.EXECUTION_TIMEOUT_SECONDS,
            cwd=settings.SANDBOX_DIR
        )
        if result.returncode != 0:
            raise ToolExecutionError(f"Python script failed: {result.stderr}")
        return result.stdout
    except subprocess.TimeoutExpired:
        raise ToolExecutionError(f"Python execution timed out after {settings.EXECUTION_TIMEOUT_SECONDS}s")
    except Exception as e:
        raise ToolExecutionError(f"Failed to execute python: {str(e)}")

class RunShellArgs(BaseModel):
    command: str = Field(..., description="Shell command to execute")

@tool_registry.register(
    "run_shell",
    "Run a shell command inside the sandbox directory. WARNING: highly privileged.",
    RunShellArgs
)
def run_shell(args: RunShellArgs) -> str:
    # Very basic restriction, a real impl might trace syscalls or run in docker
    if any(forbidden in args.command for forbidden in ["rm -rf /", "sudo"]):
        return "Execution rejected: Forbidden command"
        
    try:
        result = subprocess.run(
            args.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=settings.EXECUTION_TIMEOUT_SECONDS,
            cwd=str(settings.SANDBOX_DIR)
        )
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return f"Execution failed: Timeout ({settings.EXECUTION_TIMEOUT_SECONDS}s)"
    except Exception as e:
        return f"Execution failed: {str(e)}"
