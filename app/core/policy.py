import time
from typing import Dict, Any, Callable
from app.core.exceptions import PolicyViolationError
from app.tools.registry import tool_registry

class PolicyEnforcer:
    """Enforces boundaries and security constraints before and during execution."""
    
    @staticmethod
    def validate_tool_exists(tool_name: str) -> None:
        try:
            tool_registry.get_tool(tool_name)
        except Exception:
            raise PolicyViolationError(f"Tool {tool_name} is not whitelisted/registered or does not exist.")

    @staticmethod
    def enforce_timeout(func: Callable, args: Any, timeout: int) -> Any:
        # In a real async/multiprocessing setup, this would forcibly kill the execution.
        # For simplicity in this sync mockup, we rely on the tools themselves 
        # (like subprocess.run timeout) to respect the timeout.
        start = time.time()
        result = func(args)
        elapsed = time.time() - start
        
        if elapsed > timeout:
            raise PolicyViolationError(f"Execution exceeded allowed timeout of {timeout}s")
            
        return result
        
    @staticmethod
    def validate_execution_step(tool_name: str, args: Dict[str, Any]) -> None:
        """Central validation hub run before ANY tool execution"""
        PolicyEnforcer.validate_tool_exists(tool_name)
        
        # Tools will independently enforce path, size, and shell limits internally 
        # via the `app.sandbox.limits` module.
