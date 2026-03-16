import os
import uuid
import shutil
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from app.core.agent import AgentOrchestrator
from app.memory.session_store import session_store
from app.memory.history import history_manager
from app.tools.registry import tool_registry
from app.config import settings

router = APIRouter()
orchestrator = AgentOrchestrator()  # reads settings.LLM_PROVIDER

class PlanRequest(BaseModel):
    prompt: str
    document_context: Optional[str] = None

class ExecuteRequest(BaseModel):
    plan_id: str
    mode: str = "full" # "full" or "step"

class SessionResponse(BaseModel):
    session_id: str
    status: str

@router.post("/sessions", response_model=SessionResponse, tags=["Sessions"])
def create_session():
    """Create a new session."""
    session_id = orchestrator.create_session()
    return SessionResponse(session_id=session_id, status="INITIALIZED")

@router.get("/sessions/{session_id}", tags=["Sessions"])
def get_session(session_id: str) -> Dict[str, Any]:
    """Get status of an existing session."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.delete("/sessions/{session_id}", tags=["Sessions"])
def delete_session(session_id: str):
    """Delete a session."""
    if session_store.delete_session(session_id):
        return {"result": "Session deleted"}
    raise HTTPException(status_code=404, detail="Session not found")

@router.post("/sessions/{session_id}/plan", tags=["Planning"])
def create_plan(session_id: str, request: PlanRequest) -> Dict[str, Any]:
    """Generates an execution plan without running it."""
    try:
        return orchestrator.plan_task(session_id, request.prompt, request.document_context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/plan/{plan_id}", tags=["Planning"])
def get_plan(session_id: str, plan_id: str) -> Dict[str, Any]:
    """Preview an existing plan before execution."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    plan = session.get("plans", {}).get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    return plan

@router.post("/sessions/{session_id}/execute", tags=["Execution"])
def execute_plan_endpoint(session_id: str, request: ExecuteRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Executes a previously generated plan."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    plan = session.get("plans", {}).get(request.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    try:
        # If full mode, queue it and return job id
        if request.mode == "full":
            job_id = str(uuid.uuid4())
            session["execution_jobs"][job_id] = {
                "job_id": job_id,
                "plan_id": request.plan_id,
                "status": "queued",
                "progress": "0%",
                "mode": "full"
            }
            background_tasks.add_task(orchestrator.execute_task_async, session_id, request.plan_id, job_id)
            return {"job_id": job_id, "status": "queued", "message": "Execution started in background."}
            
        # If step mode, run it synchronously
        else:
            result = orchestrator.execute_task(session_id, request.plan_id, "step")
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/execution-status/{job_id}", tags=["Execution"])
def get_execution_status(session_id: str, job_id: str) -> Dict[str, Any]:
    """Poll for the status of an async execution job."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    job = session.get("execution_jobs", {}).get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Execution job not found")
        
    return job

@router.get("/sessions/{session_id}/history", tags=["Logs"])
def get_history(session_id: str) -> Dict[str, Any]:
    """Retrieve execution history for a session."""
    return {
        "prompts": history_manager.get_prompts(session_id),
        "executions": history_manager.get_execution_records(session_id)
    }

@router.get("/tools", tags=["Tools"])
def list_tools() -> Dict[str, dict]:
    """Retrieve available tools and schemas."""
    return tool_registry.list_tools()


@router.post("/files/upload", tags=["Files"])
async def upload_file(file: UploadFile = File(...)) -> Dict[str, str]:
    """Upload a file securely into the sandbox."""
    # 1. Validate Extension
    allowed_extensions = {".txt", ".docx", ".pdf", ".csv", ".json", ".md"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Extension {ext} not allowed.")
        
    # 2. Normalize filename and prevent traversal
    safe_filename = os.path.basename(file.filename)
    if ".." in safe_filename or safe_filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid filename.")
        
    # 3. Create sandbox path
    os.makedirs(settings.SANDBOX_DIR, exist_ok=True)
    destination_path = os.path.join(settings.SANDBOX_DIR, safe_filename)
    
    # 4. Save and enforce file size logic iteratively 
    size = 0
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    
    with open(destination_path, "wb") as buffer:
        while chunk := await file.read(8192):
            size += len(chunk)
            if size > max_bytes:
                os.remove(destination_path)
                raise HTTPException(status_code=413, detail=f"File exceeds max size of {settings.MAX_FILE_SIZE_MB}MB")
            buffer.write(chunk)
            
    return {"message": "File uploaded securely", "path": safe_filename}


class PolicyUpdate(BaseModel):
    max_file_size_mb: Optional[int] = None
    execution_timeout_seconds: Optional[int] = None
    log_level: Optional[str] = None
    llm_provider: Optional[str] = None

@router.get("/policy", tags=["Policy"])
def get_policy() -> Dict[str, Any]:
    """Get the current dynamic execution policy."""
    return {
        "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
        "execution_timeout_seconds": settings.EXECUTION_TIMEOUT_SECONDS,
        "log_level": settings.LOG_LEVEL,
        "llm_provider": settings.LLM_PROVIDER,
    }

@router.put("/policy", tags=["Policy"])
def update_policy(request: PolicyUpdate) -> Dict[str, Any]:
    """Updates runtime security policies."""
    updates = request.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided.")

    # Validate provider before applying
    if "llm_provider" in updates:
        val = updates["llm_provider"].lower()
        if val not in ("gemini", "openai"):
            raise HTTPException(status_code=400, detail="llm_provider must be 'gemini' or 'openai'.")
        updates["llm_provider"] = val

    mapped_updates = {k.upper(): v for k, v in updates.items()}
    settings.update_policy(mapped_updates)

    # Keep the live orchestrator in sync
    if "llm_provider" in updates:
        orchestrator.provider = updates["llm_provider"]

    return {"message": "Policy updated dynamically", "new_policy": get_policy()}
