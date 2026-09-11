from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    mode: str = "demo"
    database_url: str = "sqlite:///./data/autoagent.db"
    redis_url: str = ""
    storage_root: Path = Path("data/files")
    auth_secret: str = ""
    auth_issuer: str = "autoagent"
    auth_audience: str = "autoagent-api"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_reasoning_effort: Literal["", "low", "medium", "high"] = ""
    search_api_key: str = ""
    search_provider: Literal["tavily", "brave"] = "tavily"
    tavily_api_key: str = ""
    sandbox_url: str = "http://sandbox:8001"
    sandbox_secret: str = ""
    max_upload_bytes: int = 10_000_000
    max_steps: int = 16
    max_tokens: int = 30000
    max_seconds: int = 600
    max_cost: float = 1.0
    token_price_per_million: float = 10.0
    max_tool_bytes: int = 24000
    lease_seconds: int = 30
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    def validate_runtime(self):
        if self.mode not in {"demo", "live"}:
            raise ValueError("MODE must be demo or live")
        if self.mode == "live" and (len(self.auth_secret) < 32 or not self.llm_api_key or not self.llm_model or len(self.sandbox_secret) < 32):
            raise ValueError("Live mode requires AUTH_SECRET, LLM_API_KEY, LLM_MODEL and SANDBOX_SECRET")


@lru_cache
def settings():
    return Settings()
