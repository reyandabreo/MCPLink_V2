import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Config
    APP_NAME: str = "MCPLink v2 Backend"
    API_V1_STR: str = "/api/v1"
    
    # LLM Config
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    LLM_PROVIDER: str = "gemini"  # "gemini" or "openai"
    
    # Sandbox Limits
    SANDBOX_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "sandbox", "workspace")
    MAX_FILE_SIZE_MB: int = 10
    EXECUTION_TIMEOUT_SECONDS: int = 30
    
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
