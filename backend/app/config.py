"""
Pydantic Settings — centralised environment variable loading.

All settings are loaded from environment variables (or .env file).
FastAPI's dependency injection system never touches these directly —
import `settings` directly where needed.

Week 2 additions:
  - GITHUB_TOKEN
  - EMBEDDING_PROVIDER
  - OLLAMA_BASE_URL
  - MAX_FILES_PER_REPO
  - MAX_FILE_SIZE_KB
"""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Supabase ----------------------------------------------------------
    supabase_url: str
    supabase_service_key: str     # service role key (not anon key)

    # ---- API keys ----------------------------------------------------------
    groq_api_key: str = ""
    github_token: str = ""       # GitHub personal access token (repo:read)

    # ---- Embeddings --------------------------------------------------------
    embedding_provider: str = "ollama"   # "ollama" | "noop"
    ollama_base_url: str = "http://localhost:11434"

    # ---- Ingestion limits --------------------------------------------------
    max_files_per_repo: int = 500
    max_file_size_kb: int = 200

    # ---- CORS / security ---------------------------------------------------
    frontend_url: str = "http://localhost:5173"
    allowed_origins: list[str] = []

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def set_allowed_origins(cls, v, info):
        # If allowed_origins not set, default to frontend_url
        if not v:
            frontend_url = info.data.get("frontend_url", "http://localhost:5173")
            return [frontend_url]
        return v

    # ---- Rate limiting -----------------------------------------------------
    rate_limit_ingest: str = "5/hour"
    rate_limit_chat: str = "30/minute"
    rate_limit_default: str = "60/minute"

    # ---- Environment -------------------------------------------------------
    environment: str = "development"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"
    @property
    def rate_chat(self):
        return self.rate_limit_chat

    @property
    def rate_ingest(self):
        return self.rate_limit_ingest

    @property
    def rate_impact(self):
        return self.rate_limit_default

    @property
    def rate_heatmap(self):
        return self.rate_limit_default

    @property
    def rate_walkthrough(self):
        return self.rate_limit_default

settings = Settings()



