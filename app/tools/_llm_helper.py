"""Shared LLM helper for tool-level text generation.

Reads settings.LLM_PROVIDER at call time so switching provider in the
Policy screen takes effect immediately without restarting the server.
"""
from app.config import settings


def call_llm(prompt: str, *, plain_text: bool = True) -> str:
    """
    Send *prompt* to whichever LLM provider is currently configured
    (``settings.LLM_PROVIDER`` — either ``"gemini"`` or ``"openai"``).

    Returns the model's response as a stripped string.
    Raises on API / network errors so callers can wrap in try/except.
    """
    provider = settings.LLM_PROVIDER.lower()

    if provider == "gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        mime = "text/plain" if plain_text else "application/json"
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type=mime),
        )
        return (response.text or "").strip()

    elif provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[{"role": "user", "content": prompt}],
            # JSON mode only when caller asks for it
            **({"response_format": {"type": "json_object"}} if not plain_text else {}),
        )
        return (response.choices[0].message.content or "").strip()

    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{settings.LLM_PROVIDER}'. "
            "Must be 'gemini' or 'openai'."
        )
