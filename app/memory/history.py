from typing import List, Dict, Any

class HistoryManager:
    """Maintains conversation and execution history per session."""
    
    def __init__(self):
        self._prompt_history: Dict[str, List[str]] = {}
        self._plan_history: Dict[str, List[Dict[str, Any]]] = {}
        self._execution_records: Dict[str, List[Dict[str, Any]]] = {}

    def add_prompt(self, session_id: str, prompt: str):
        if session_id not in self._prompt_history:
            self._prompt_history[session_id] = []
        self._prompt_history[session_id].append(prompt)

    def get_prompts(self, session_id: str) -> List[str]:
        return self._prompt_history.get(session_id, [])

    def add_plan(self, session_id: str, plan: Dict[str, Any]):
        if session_id not in self._plan_history:
            self._plan_history[session_id] = []
        self._plan_history[session_id].append(plan)

    def get_plans(self, session_id: str) -> List[Dict[str, Any]]:
        return self._plan_history.get(session_id, [])

    def add_execution_record(self, session_id: str, record: Dict[str, Any]):
        if session_id not in self._execution_records:
            self._execution_records[session_id] = []
        self._execution_records[session_id].append(record)

    def get_execution_records(self, session_id: str) -> List[Dict[str, Any]]:
        return self._execution_records.get(session_id, [])

# Global instance
history_manager = HistoryManager()
