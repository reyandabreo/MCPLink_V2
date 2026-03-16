from typing import Optional
import json
from google import genai
from google.genai import types

from app.llm.base import BaseLLM
from app.llm.schemas import ExecutionPlan
from app.config import settings

class GeminiProvider(BaseLLM):
    """Google Gemini implementation of the LLM provider."""
    
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = 'gemini-2.5-flash'
        
    def generate_plan(self, prompt: str, context: Optional[str] = None) -> ExecutionPlan:
        system_prompt = (
            "You are an AI Agent Planner. Your job is to create a structured execution plan based on the user's request.\n"
            "You must respond ONLY with valid JSON matching the ExecutionPlan schema.\n"
            "Do not include markdown code blocks like ```json ... ```, just pure JSON."
        )
        
        full_prompt = system_prompt + "\n\nUser Request:\n" + prompt
        if context:
            full_prompt += "\n\nContext:\n" + context
            
        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        
        content = response.text
        if not content:
            raise ValueError("Empty response from Gemini")
            
        # Parse JSON and validate against schema
        plan_dict = json.loads(content)
        return ExecutionPlan(**plan_dict)
