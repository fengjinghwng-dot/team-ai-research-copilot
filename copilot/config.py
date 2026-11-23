from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: Literal["production", "test"] = "production"
    database_url: str = "postgresql+psycopg://copilot:copilot@localhost:5432/copilot"
    supabase_url: str = ""
    cors_origins: list[str] = []
    workspace_url: str = "http://localhost:3000"
    llm_enabled: bool = False
    llm_provider: Literal["openai", "deepseek"] = "openai"
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    daily_budget_cny: Decimal = Field(default=Decimal("20"), ge=Decimal("0.01"))
    cheap_model: str = "gpt-4.1-mini"
    deep_model: str = "gpt-4.1"
    embedding_model: str = "text-embedding-3-small"
    daily_token_limit: int = Field(default=1_000_000, ge=1)
    timezone: str = "Asia/Shanghai"
    semantic_scholar_api_key: str = ""
    arxiv_categories: list[str] = ["cs.AI", "cs.CL", "cs.LG", "cs.DC"]
    source_user_agent: str = "TeamResearchCopilot/0.1"
    enable_hf: bool = True
    http_cache_hours: int = 12
    use_cache_only: bool = False
    shortlist_size: int = Field(default=20, ge=5, le=25)
    deep_count: int = Field(default=5, ge=1, le=8)
    exploration_ratio: float = Field(default=0.2, ge=0.15, le=0.2)
    im_provider: Literal["", "feishu", "wecom", "slack"] = ""
    im_webhook_url: str = ""
    im_team_id: str = ""
    resend_api_key: str = ""
    email_from: str = ""

    @model_validator(mode="after")
    def validate_config(self):
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("PostgreSQL + psycopg is required; SQLite is unsupported")
        if self.llm_provider == "deepseek":
            if {self.cheap_model, self.deep_model} != {"deepseek-flash"}:
                raise ValueError("DeepSeek budget guard requires CHEAP_MODEL=DEEP_MODEL=deepseek-flash")
            if self.llm_enabled and not self.deepseek_api_key:
                raise ValueError("LLM_ENABLED requires DEEPSEEK_API_KEY for DeepSeek")
        elif self.llm_enabled and not self.openai_api_key:
            raise ValueError("LLM_ENABLED requires OPENAI_API_KEY for OpenAI")
        if self.supabase_url and not self.supabase_url.startswith("https://"):
            raise ValueError("SUPABASE_URL must use HTTPS")
        if self.deep_count > self.shortlist_size:
            raise ValueError("DEEP_COUNT must not exceed SHORTLIST_SIZE")
        return self

    @property
    def effective_daily_token_limit(self) -> int:
        if self.llm_provider == "deepseek":
            # Current Flash peak price: input <= 2, output <= 8 CNY / million tokens.
            # Charge every reserved token at the more expensive rate, including uncertain calls.
            # This conservative ceiling is shared by all teams, workers and API calls.
            monetary_limit = int(self.daily_budget_cny * 1_000_000 / Decimal("8"))
            return min(self.daily_token_limit, monetary_limit)
        return self.daily_token_limit


@lru_cache
def settings() -> Settings:
    return Settings()
