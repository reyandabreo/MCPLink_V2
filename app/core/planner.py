import json
from typing import Optional, Dict, Any
from app.llm.base import BaseLLM
from app.llm.openai_provider import OpenAIProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.schemas import ExecutionPlan
from app.core.exceptions import PlanValidationError
from app.tools.registry import tool_registry

class Planner:
    """Handles interaction with LLM for structured plan generation."""
    
    def __init__(self, provider: str = None):
        from app.config import settings as _settings
        provider = (provider or _settings.LLM_PROVIDER).lower()
        if provider == "openai":
            self.llm: BaseLLM = OpenAIProvider()
        elif provider == "gemini":
            self.llm: BaseLLM = GeminiProvider()
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    def generate_plan(self, prompt: str, context: Optional[str] = None) -> ExecutionPlan:
        """
        Accept prompt + context, send structured instruction to LLM,
        and return a validated ExecutionPlan.
        """
        # Inject available tools dynamically into the prompt
        tools_schema = json.dumps(tool_registry.list_tools(), indent=2)
        plan_schema = json.dumps(ExecutionPlan.model_json_schema(), indent=2)
        system_instructions = (
            f"Available Tools:\n{tools_schema}\n\n"
            "Analyze the user request and generate a step-by-step ExecutionPlan using ONLY the available tools. "
            "Ensure arguments exactly match the tool parameters schema.\n\n"
            "You MUST output a JSON object exactly matching this schema:\n"
            f"{plan_schema}\n"
        )
        
        full_context = system_instructions
        if context:
            full_context += f"\n\nAdditional Context:\n{context}"
            
        last_error = None
        for attempt in range(2):
            try:
                plan = self.llm.generate_plan(prompt, full_context)
                return plan
            except Exception as e:
                last_error = str(e)
                full_context += f"\n\nPrevious attempt failed with validation error: {last_error}\nPlease fix the JSON structure and try again."
        
        raise PlanValidationError(f"Failed to generate or validate plan after retries: {last_error}")
