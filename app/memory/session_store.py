from typing import Dict, Any, Optional

class SessionStore:
    """In-memory store for active sessions. 
       In production, replace with Redis or a database.
    """
    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, session_id: str) -> None:
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "id": session_id,
                "plans": {},            # map of plan_id -> plan dict
                "execution_jobs": {},   # map of execution_id -> job dict
                "execution_status": "INITIALIZED"
            }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._sessions.get(session_id)
        
    def update_session(self, session_id: str, key: str, value: Any) -> None:
        if session_id in self._sessions:
            self._sessions[session_id][key] = value

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

# Global instance
session_store = SessionStore()
