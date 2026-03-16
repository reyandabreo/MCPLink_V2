import httpx
from typing import Dict, Any, Optional
import psutil, datetime, os

BASE_URL = "http://127.0.0.1:8000/api/v1"

class APIClient:
    """Async HTTP Client for interacting with the MCPLink_V2 backend API."""
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)
        return self._client

    async def create_session(self) -> str:
        response = await self.client.post("/sessions")
        response.raise_for_status()
        return response.json()["session_id"]
        
    async def get_session(self, session_id: str) -> Dict[str, Any]:
        response = await self.client.get(f"/sessions/{session_id}")
        response.raise_for_status()
        return response.json()
        
    async def get_tools(self) -> Dict[str, Any]:
        response = await self.client.get("/tools")
        response.raise_for_status()
        return response.json()
        
    async def create_plan(self, session_id: str, prompt: str, context: Optional[str] = None) -> Dict[str, Any]:
        response = await self.client.post(
            f"/sessions/{session_id}/plan",
            json={"prompt": prompt, "document_context": context}
        )
        response.raise_for_status()
        return response.json()
        
    async def get_plan(self, session_id: str, plan_id: str) -> Dict[str, Any]:
        response = await self.client.get(f"/sessions/{session_id}/plan/{plan_id}")
        response.raise_for_status()
        return response.json()
        
    async def execute_plan(self, session_id: str, plan_id: str, mode: str = "full") -> Dict[str, Any]:
        response = await self.client.post(
            f"/sessions/{session_id}/execute",
            json={"plan_id": plan_id, "mode": mode}
        )
        response.raise_for_status()
        return response.json()
        
    async def get_execution_status(self, session_id: str, job_id: str) -> Dict[str, Any]:
        response = await self.client.get(f"/sessions/{session_id}/execution-status/{job_id}")
        response.raise_for_status()
        return response.json()
        
    async def get_history(self, session_id: str) -> Dict[str, Any]:
        response = await self.client.get(f"/sessions/{session_id}/history")
        response.raise_for_status()
        return response.json()
        
    async def get_policy(self) -> Dict[str, Any]:
        response = await self.client.get("/policy")
        response.raise_for_status()
        return response.json()
        
    async def update_policy(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        response = await self.client.put("/policy", json=updates)
        response.raise_for_status()
        return response.json()

    async def delete_session(self, session_id: str) -> Dict[str, Any]:
        response = await self.client.delete(f"/sessions/{session_id}")
        response.raise_for_status()
        return response.json()

    async def upload_file(self, file_path: str) -> Dict[str, Any]:
        """Upload a local file to the backend sandbox."""
        import aiofiles
        filename = file_path.split("/")[-1].split("\\")[-1]
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()
        files = {"file": (filename, content)}
        response = await self.client.post("/files/upload", files=files)
        response.raise_for_status()
        return response.json()

    # ── System metrics (local, no backend call needed) ──────────
    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """Collect local CPU / memory stats without hitting the API."""
        try:
            cpu    = psutil.cpu_percent(interval=None)
            mem    = psutil.virtual_memory()
            mem_mb = mem.used // (1024 * 1024)
            return {"cpu": f"{cpu:.1f}%", "mem": f"{mem_mb}MB", "ok": True}
        except Exception:
            return {"cpu": "—", "mem": "—", "ok": False}

api = APIClient()
