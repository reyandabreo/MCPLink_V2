import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from app.core.planner import Planner
from app.core.executor import Executor
from app.core.context_manager import ContextManager
from app.memory.session_store import session_store
from app.memory.history import history_manager
from app.logs.logger import log_audit
from app.core.exceptions import MCPLinkError
import app.tools  # noqa: F401

from app.config import settings as _settings

class AgentOrchestrator:
    """Orchestrates planning and execution lifecycle for the MCPLink Backend."""
    
    def __init__(self, provider: str = None):
        self.provider = provider or _settings.LLM_PROVIDER
        
    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        session_store.create_session(session_id)
        log_audit(session_id, "SESSION_CREATED", {"provider": self.provider})
        return session_id
        
    def plan_task(self, session_id: str, prompt: str, document_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Receives request, invokes planner, stores the plan, and returns the plan_id.
        """
        if not session_store.get_session(session_id):
            raise MCPLinkError(f"Session {session_id} does not exist.")
            
        context_mgr = ContextManager(session_id)
        planner = Planner(provider=self.provider)
        
        # 1. Build Context
        context = context_mgr.build_context(document_context)
        history_manager.add_prompt(session_id, prompt)
        log_audit(session_id, "PLANNING_STARTED", {"prompt_length": len(prompt)})
        
        try:
            session_store.update_session(session_id, "execution_status", "PLANNING")
            
            # 2. Generate Plan
            plan = planner.generate_plan(prompt, context)
            plan_id = str(uuid.uuid4())
            
            # 3. Apply Pre-Validation / Annotation (Preview requirements)
            annotated_steps = []
            for step in plan.steps:
                try:
                    from app.core.policy import PolicyEnforcer
                    PolicyEnforcer.validate_execution_step(step.tool_name, step.arguments)
                    annotated_steps.append({
                        "tool_name": step.tool_name, 
                        "arguments": step.arguments,
                        "explanation": step.explanation,
                        "allowed": True,
                        "status": "pending"
                    })
                except Exception as e:
                    annotated_steps.append({
                        "tool_name": step.tool_name, 
                        "arguments": step.arguments,
                        "explanation": step.explanation,
                        "allowed": False,
                        "warning": str(e),
                        "status": "pending"
                    })
            
            # 4. Store Plan
            plan_record = {
                "plan_id": plan_id,
                "prompt": prompt,
                "goal": plan.goal,
                "steps": annotated_steps,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "created"
            }
            
            session = session_store.get_session(session_id)
            session["plans"][plan_id] = plan_record
            history_manager.add_plan(session_id, plan_record)
            
            log_audit(session_id, "PLAN_GENERATED", {"plan_id": plan_id, "steps_count": len(annotated_steps)})
            session_store.update_session(session_id, "execution_status", "PLAN_READY")
            
            return plan_record
            
        except Exception as e:
            session_store.update_session(session_id, "execution_status", "PLANNING_FAILED")
            log_audit(session_id, "PLANNING_ABORTED", {"error": str(e)})
            raise

    def execute_task(self, session_id: str, plan_id: str, mode: str = "full") -> Dict[str, Any]:
        if not session_store.get_session(session_id):
            raise MCPLinkError(f"Session {session_id} does not exist.")
            
        session_store.update_session(session_id, "execution_status", "EXECUTING")
        executor = Executor(session_id)
        
        try:
            result = executor.execute_task(plan_id, mode)
            
            # Log final telemetry
            final_status = result["plan_status"]
            session_store.update_session(session_id, "execution_status", final_status)
            
            log_audit(session_id, f"EXECUTION_{final_status}", {
                "plan_id": plan_id,
                "mode": mode,
                "results_count": len(result["results"])
            })
            
            return result
        except Exception as e:
            session_store.update_session(session_id, "execution_status", "FAILED")
            log_audit(session_id, "EXECUTION_ABORTED", {"error": str(e)})
            raise

    def execute_task_async(self, session_id: str, plan_id: str, job_id: str):
        """Background wrapper for full plan execution."""
        session = session_store.get_session(session_id)
        if not session:
            return
            
        job = session["execution_jobs"].get(job_id)
        if not job:
            return
            
        job["status"] = "running"
        try:
            result = self.execute_task(session_id, plan_id, "full")
            final_status = result.get("plan_status", "failed")
            job["status"] = "completed" if final_status == "completed" else "failed"
            job["progress"] = "100%"
            job["results"] = result["results"]
            if final_status != "completed":
                job["error"] = f"Plan finished with status: {final_status}"
        except Exception as e:
            job["status"] = "failed"
            job["error"] = str(e)
