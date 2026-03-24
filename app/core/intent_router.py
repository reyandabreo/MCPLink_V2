import json
import re
from dataclasses import dataclass

from app.config import settings
from app.tools._llm_helper import call_llm


@dataclass
class IntentDecision:
    route: str
    confidence: float
    reason: str


def _heuristic_classify(prompt: str) -> IntentDecision:
    low = (prompt or "").lower()
    has_file = bool(re.search(r"[a-zA-Z0-9_\-./]+\.(xlsx|txt|docx|md|json|csv)\b", low))

    web_tokens = (
        "web",
        "internet",
        "search",
        "browse",
        "find online",
        "latest",
        "news",
        "wikipedia",
        "tavily",
        "ratings",
        "reviews",
        "trends",
    )
    has_web_intent = any(tok in low for tok in web_tokens)

    if has_file and has_web_intent:
        return IntentDecision("web_search_file", 0.72, "heuristic: file + web tokens")
    if has_file:
        return IntentDecision("llm_knowledge_file", 0.70, "heuristic: file output without web tokens")
    if has_web_intent:
        return IntentDecision("web_search_answer", 0.68, "heuristic: web intent without file")
    return IntentDecision("llm_knowledge_answer", 0.66, "heuristic: direct knowledge answer")


def _llm_available() -> bool:
    provider = (settings.LLM_PROVIDER or "").lower()
    if provider == "gemini":
        return bool((settings.GEMINI_API_KEY or "").strip())
    if provider == "openai":
        return bool((settings.OPENAI_API_KEY or "").strip())
    return False


def _classify_with_llm(prompt: str) -> IntentDecision:
    schema = {
        "route": "web_search_file|web_search_answer|llm_knowledge_file|llm_knowledge_answer",
        "confidence": "float in [0,1]",
        "reason": "short string",
    }
    classifier_prompt = (
        "Classify user intent. Return JSON only with keys route, confidence, reason.\n"
        f"Allowed schema: {json.dumps(schema)}\n"
        "Rules:\n"
        "- If user asks to create/save/export a file and needs external/up-to-date facts, use web_search_file.\n"
        "- If user asks a direct question requiring external/up-to-date facts but no file, use web_search_answer.\n"
        "- If user asks to create/save/export a file and generic knowledge is enough, use llm_knowledge_file.\n"
        "- Otherwise use llm_knowledge_answer.\n"
        f"User prompt: {prompt}"
    )

    raw = call_llm(classifier_prompt, plain_text=False)
    data = json.loads(raw)

    route = str(data.get("route", "")).strip()
    confidence = float(data.get("confidence", 0.0))
    reason = str(data.get("reason", "")).strip() or "llm classified"

    allowed = {
        "web_search_file",
        "web_search_answer",
        "llm_knowledge_file",
        "llm_knowledge_answer",
    }
    if route not in allowed:
        raise ValueError(f"Invalid route: {route}")

    confidence = max(0.0, min(confidence, 1.0))
    return IntentDecision(route, confidence, reason)


def classify_intent(prompt: str) -> IntentDecision:
    mode = (settings.INTENT_ROUTER_MODE or "hybrid").strip().lower()

    if mode == "deterministic":
        return _heuristic_classify(prompt)

    if mode == "llm":
        if _llm_available():
            try:
                return _classify_with_llm(prompt)
            except Exception:
                return _heuristic_classify(prompt)
        return _heuristic_classify(prompt)

    if _llm_available():
        try:
            return _classify_with_llm(prompt)
        except Exception:
            return _heuristic_classify(prompt)

    return _heuristic_classify(prompt)
