from typing import Any, Optional, Dict
import hashlib
import json

class CacheManager:
    """Stores cached LLM responses and token usage to optimize execution."""
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._token_stats: Dict[str, int] = {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
        }

    def _generate_key(self, prompt: str, context: Optional[str] = None) -> str:
        data = f"{prompt}_{context}"
        return hashlib.sha256(data.encode()).hexdigest()

    def get(self, prompt: str, context: Optional[str] = None) -> Optional[Any]:
        key = self._generate_key(prompt, context)
        return self._cache.get(key)
        
    def set(self, prompt: str, response: Any, context: Optional[str] = None) -> None:
        key = self._generate_key(prompt, context)
        self._cache[key] = response

    def add_tokens(self, prompt_tokens: int, completion_tokens: int):
        self._token_stats["total_prompt_tokens"] += prompt_tokens
        self._token_stats["total_completion_tokens"] += completion_tokens

    def get_stats(self) -> Dict[str, int]:
        return self._token_stats.copy()

# Global instance
cache_manager = CacheManager()
