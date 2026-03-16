from abc import ABC, abstractmethod
from typing import Optional
from app.llm.schemas import ExecutionPlan

class BaseLLM(ABC):
    """Abstract interface for LLM providers."""
    
    @abstractmethod
    def generate_plan(self, prompt: str, context: Optional[str] = None) -> ExecutionPlan:
        """
        Takes a prompt and optional context, and generates a structured Plan.
        Should return an ExecutionPlan parsed from JSON.
        """
        pass
