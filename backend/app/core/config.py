from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TTRPG GM Engine"
    app_env: str = "development"
    secret_key: str = Field("change-me-in-production", alias="SECRET_KEY")
    database_url: str = Field("postgresql+psycopg://gm:gm@db:5432/gm", alias="DATABASE_URL")
    cors_origins: str = Field("http://localhost:3000", alias="CORS_ORIGINS")
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field("https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    anthropic_api_key: str | None = Field(None, alias="ANTHROPIC_API_KEY")
    demo_mode: bool = Field(True, alias="DEMO_MODE")
    default_llm_provider: str = Field("mock", alias="DEFAULT_LLM_PROVIDER")
    default_model: str = Field("mock-gm", alias="DEFAULT_MODEL")
    request_timeout_seconds: float = Field(60.0, alias="REQUEST_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

