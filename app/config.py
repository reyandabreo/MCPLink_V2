import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Config
    APP_NAME: str = "MCPLink v2 Backend"
    API_V1_STR: str = "/api/v1"
    
    # LLM Config
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    LLM_PROVIDER: str = "openai"  # "gemini" or "openai"
    
    # Sandbox Limits
    SANDBOX_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "sandbox", "workspace")
    MAX_FILE_SIZE_MB: int = 10
    EXECUTION_TIMEOUT_SECONDS: int = 30

    # News/RSS Tooling
    NEWS_REQUEST_TIMEOUT_SECONDS: int = 10
    NEWS_MAX_ITEMS_PER_REQUEST: int = 20
    NEWS_CANONICAL_TOPIC: str = "U.S.-Israel conflict with Iran"
    ALLOWED_FETCH_DOMAINS: List[str] = [
        "feeds.reuters.com",
        "rss.cnn.com",
        "feeds.bbci.co.uk",
        "www.aljazeera.com",
        "www.npr.org",
        "www.theguardian.com",
    ]
    NEWS_RSS_FEEDS: List[str] = [
        "https://feeds.reuters.com/reuters/worldNews",
        "http://rss.cnn.com/rss/cnn_world.rss",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.aljazeera.com/xml/rss/all.xml",
    ]
    
    # Web Fetch Config
    WEB_FETCH_TIMEOUT_SECONDS: int = 10
    WEB_FETCH_MAX_ROWS: int = 1000
    TAVILY_API_KEY: str = ""
    TAVILY_MAX_RESULTS: int = 5
    INTENT_ROUTER_MODE: str = "hybrid"  # hybrid, deterministic, llm
    INTENT_ROUTER_MIN_CONFIDENCE: float = 0.55
    ALLOWED_WEB_SOURCES: List[str] = [
        "wikipedia_search",
        "tavily_search",
    ]
    
    # Memory Limits
    TOKEN_LIMIT: int = 8192
    
    # Logging Config
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "logs")

    class Config:
        env_file = ".env"

    def update_policy(self, updates: dict):
        """Update active setting attributes from a dictionary."""
        for key, value in updates.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @property
    def active_provider(self) -> str:
        return self.LLM_PROVIDER.lower()

settings = Settings()
