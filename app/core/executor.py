from typing import Dict, Any, List
from app.llm.schemas import ExecutionPlan, ToolCallStep
from app.memory.session_store import session_store
from app.core.exceptions import ToolExecutionError, PolicyViolationError
from app.core.policy import PolicyEnforcer
from app.tools.registry import tool_registry
from app.logs.logger import log_execution

class Executor:
    """Executes validated plan steps in the sandbox environment."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        
    def execute_task(self, plan_id: str, mode: str = "full") -> Dict[str, Any]:
        """Iterates through plan steps and executes them securely."""
        session = session_store.get_session(self.session_id)
        if not session or plan_id not in session.get("plans", {}):
            raise ValueError("Invalid session or plan_id")
            
        plan_record = session["plans"][plan_id]
        steps = plan_record["steps"]
        results = []
        
        for idx, step in enumerate(steps):
            if step["status"] != "pending":
                continue # Skip already executed
                
            # Convert dictionary back to ToolCallStep for execution logic
            step_obj = ToolCallStep(
                tool_name=step["tool_name"], 
                arguments=step["arguments"], 
                explanation=step["explanation"]
            )
            
            result = self._execute_step(step_obj, idx)
            results.append(result)
            
            # Update state
            step["status"] = result["status"]
            step["output"] = result.get("output", result.get("error"))
            
            # Stop execution on failure
            if result["status"] == "failed":
                plan_record["status"] = "failed"
                break
                
            if mode == "step":
                break # Only execute one pending step
                
        # Check if all steps are success
        if all(s["status"] == "success" for s in steps):
            plan_record["status"] = "completed"
            
        return {
            "mode": mode,
            "plan_status": plan_record["status"],
            "results": results,
            "plan_record": plan_record
        }
        
    def _execute_step(self, step: ToolCallStep, step_index: int) -> Dict[str, Any]:
        """Executes a single tool step and captures the output."""
        try:
            # 1. Validate Policy Before Execution
            PolicyEnforcer.validate_execution_step(step.tool_name, step.arguments)
            
            # 2. Extract Tool
            tool = tool_registry.get_tool(step.tool_name)
            
            # 3. Validate Arguments against schema (Pydantic does this)
            validated_args = tool.args_schema(**step.arguments)
            
            # 4. Execute (In sync mode, we assume the tool limits timeout. In real-world, wrap in asyncio.wait_for)
            tool_output = tool.callable(validated_args)
            
            record = {
                "step_index": step_index,
                "tool": step.tool_name,
                "status": "success",
                "output": str(tool_output),
                "explanation": step.explanation
            }
            
            log_execution(self.session_id, step.tool_name, "SUCCESS", "Execution completed successfully")
            return record
            
        except PolicyViolationError as e:
            error_msg = f"Policy Violation: {str(e)}"
            log_execution(self.session_id, step.tool_name, "POLICY_VIOLATION", error_msg)
            return self._build_error_record(step_index, step, error_msg)
            
        except Exception as e:
            error_msg = f"Execution Error: {str(e)}"
            log_execution(self.session_id, step.tool_name, "FAILURE", error_msg)
            return self._build_error_record(step_index, step, error_msg)
            
    def _build_error_record(self, step_index: int, step: ToolCallStep, error_msg: str) -> Dict[str, Any]:
        return {
            "step_index": step_index,
            "tool": step.tool_name if hasattr(step, "tool_name") else "unknown",
            "status": "failed",
            "error": error_msg,
            "explanation": step.explanation if hasattr(step, "explanation") else "unknown"
        }
