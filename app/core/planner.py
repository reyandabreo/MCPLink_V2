import json
import re
from typing import Optional, Dict, Any
from app.config import settings
from app.core.intent_router import classify_intent
from app.llm.base import BaseLLM
from app.llm.openai_provider import OpenAIProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.schemas import ExecutionPlan, ToolCallStep
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
        # Deterministic path for news export prompts to avoid LLM tool-selection misses.
        deterministic_plan = self._build_deterministic_news_plan(prompt)
        if deterministic_plan is not None:
            return deterministic_plan

        # Hybrid classifier pass (non-breaking): apply only when confidence is high.
        intent = classify_intent(prompt)
        if intent.confidence >= float(settings.INTENT_ROUTER_MIN_CONFIDENCE):
            if intent.route == "web_search_file":
                hybrid_file_plan = self._build_deterministic_topic_file_plan(prompt)
                if hybrid_file_plan is not None:
                    return hybrid_file_plan
            if intent.route == "llm_knowledge_file":
                hybrid_file_plan = self._build_deterministic_topic_file_plan(prompt)
                if hybrid_file_plan is not None:
                    return hybrid_file_plan

        deterministic_generic_plan = self._build_deterministic_topic_file_plan(prompt)
        if deterministic_generic_plan is not None:
            return deterministic_generic_plan

        # Inject available tools dynamically into the prompt
        tools_schema = json.dumps(tool_registry.list_tools(), indent=2)
        plan_schema = json.dumps(ExecutionPlan.model_json_schema(), indent=2)
        system_instructions = (
            f"Available Tools:\n{tools_schema}\n\n"
            "Analyze the user request and generate a step-by-step ExecutionPlan using ONLY the available tools. "
            "Ensure arguments exactly match the tool parameters schema.\n\n"
            "When user asks for latest news in any file format (.xlsx, .txt, .docx, .md, .json, .csv), prefer create_latest_news_file in a single step. "
            "Use create_latest_news_xlsx only when the request is explicitly xlsx-specific and create_latest_news_file is unavailable. "
            "Do NOT use run_python for this workflow unless explicitly requested by the user. "
            "For alphabetical ordering, use sort_mode='headline_alphabetical'. "
            "Set limit to 10 when user asks top 10 and keep requested file path/extension exactly as requested when valid.\n\n"
            "You MUST output a JSON object exactly matching this schema:\n"
            f"{plan_schema}\n"
        )
        
        full_context = system_instructions
        full_context += (
            "\n\nRouting hint from hybrid classifier: "
            f"route={intent.route}, confidence={intent.confidence:.2f}, reason={intent.reason}"
        )
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

    def _build_deterministic_news_plan(self, prompt: str) -> Optional[ExecutionPlan]:
        low = (prompt or "").lower()
        if "news" not in low:
            return None

        path_matches = re.findall(
            r"([A-Za-z0-9_\-./]+\.(?:xlsx|txt|docx|md|json|csv))",
            prompt,
            flags=re.IGNORECASE,
        )
        if not path_matches:
            return None

        out_path = path_matches[-1].strip().strip("\"'")

        # Parse limit from expressions like "top 10" or "10 latest"
        limit = 10
        top_match = re.search(r"top\s+(\d{1,2})", low)
        if top_match:
            limit = int(top_match.group(1))
        else:
            latest_match = re.search(r"(\d{1,2})\s+latest", low)
            if latest_match:
                limit = int(latest_match.group(1))

        sort_mode = "headline_alphabetical" if "alphabetical" in low else "headline_alphabetical"

        # Try to extract topic from "related to ..." or "about ..."; otherwise fall back to "news".
        topic = "news"
        rel_match = re.search(r"related\s+to\s+(.+?)(?:\s+in\s+|\s+with\s+|$)", prompt, flags=re.IGNORECASE)
        if rel_match:
            topic = rel_match.group(1).strip(" .")
        else:
            about_match = re.search(r"about\s+(.+?)(?:\s+in\s+|\s+with\s+|$)", prompt, flags=re.IGNORECASE)
            if about_match:
                topic = about_match.group(1).strip(" .")
            else:
                # Handle phrases like "latest sports news" / "top 5 latest entertainment news".
                topical_match = re.search(
                    r"(?:top\s+\d{1,2}\s+)?(?:latest\s+)?([a-zA-Z][a-zA-Z\- ]{1,40})\s+news",
                    low,
                )
                if topical_match:
                    extracted = topical_match.group(1).strip()
                    if extracted and extracted not in {"latest", "top"}:
                        topic = extracted

        return ExecutionPlan(
            goal=f"Create {out_path} with top latest news",
            steps=[
                ToolCallStep(
                    tool_name="create_latest_news_file",
                    arguments={
                        "path": out_path,
                        "topic": topic,
                        "limit": max(1, min(limit, 50)),
                        "sort_mode": sort_mode,
                        "story_mode": "expanded",
                    },
                    explanation="Deterministic news-file workflow selected for reliability.",
                )
            ],
        )

    def _build_deterministic_topic_file_plan(self, prompt: str) -> Optional[ExecutionPlan]:
        low = (prompt or "").lower()
        if "news" in low:
            return None
        if "create" not in low:
            return None

        path_matches = re.findall(
            r"([A-Za-z0-9_\-./]+\.(?:xlsx|txt|docx|md|json|csv))",
            prompt,
            flags=re.IGNORECASE,
        )
        if not path_matches:
            return None

        out_path = path_matches[-1].strip().strip("\"'")

        topic = prompt.strip()
        with_match = re.search(r"with\s+(.+?)(?:\.|$)", prompt, flags=re.IGNORECASE)
        if with_match:
            topic = with_match.group(1).strip(" .")
        else:
            about_match = re.search(r"about\s+(.+?)(?:\.|$)", prompt, flags=re.IGNORECASE)
            if about_match:
                topic = about_match.group(1).strip(" .")

        return ExecutionPlan(
            goal=f"Create {out_path} with requested topic content",
            steps=[
                ToolCallStep(
                    tool_name="web_fetch_tool",
                    arguments={
                        "query": topic,
                        "output_path": out_path,
                    },
                    explanation="Deterministic generic topic-to-file workflow routed via web_fetch_tool.",
                )
            ],
        )
