from typing import Optional
import json
from openai import OpenAI
from app.llm.base import BaseLLM
from app.llm.schemas import ExecutionPlan
from app.config import settings

class OpenAIProvider(BaseLLM):
    """OpenAI implementation of the LLM provider."""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4-turbo-preview" # Or configured model
        
    def generate_plan(self, prompt: str, context: Optional[str] = None) -> ExecutionPlan:
        system_prompt = (
            "You are an AI Agent Planner. Your job is to create a structured execution plan based on the user's request.\n"
            "You must respond ONLY with valid JSON matching the ExecutionPlan schema.\n"
        )
        if context:
            system_prompt += f"\nContext:\n{context}\n"
            
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from OpenAI")
            
        # Parse JSON and validate against schema
        plan_dict = json.loads(content)
        return ExecutionPlan(**plan_dict)
