from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: Literal["local", "test", "prod"] = "local"
    api_url: str = "http://localhost:8000"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    database_url: str = (
        "postgresql+asyncpg://slop:slop@localhost:5432/slop"
    )
    database_url_sync: str = (
        "postgresql+psycopg://slop:slop@localhost:5432/slop"
    )

    # LLM providers
    fake_llm: bool = False
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    xai_api_key: str = ""
    nigel_model: str = "claude-sonnet-4-6"
    elle_model: str = "gpt-4o"
    steve_model: str = "grok-4"
    image_model: str = "dall-e-3"

    # Image storage
    images_bucket: str = "daily-slop-v2-images-prod"
    images_local_dir: str = "/var/slop/images"
    images_public_base_url: str = "http://localhost:8000/images"

    # LangFuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"
    langfuse_enabled: bool = False

    # Scheduler / admin auth
    scheduler_sa_email: str = ""
    admin_dev_token: str = ""
    # Comma-separated additional OIDC audiences accepted on /admin/generate (e.g.
    # the Cloud Run service URL while the public domain isn't yet wired).
    extra_audiences: str = ""

    # Feature toggles
    steve_quota: float = 0.25  # share of stories assigned to Steve

    # Site / public URLs
    site_url: str = "https://dailyslop.co.uk"

    # LinkedIn
    linkedin_org_urn: str = ""
    gcp_project_id: str = ""
    linkedin_client_id_secret: str = "linkedin-client-id"
    linkedin_client_secret_secret: str = "linkedin-client-secret"
    linkedin_access_token_secret: str = "linkedin-access-token"
    linkedin_refresh_token_secret: str = "linkedin-refresh-token"
    linkedin_dry_run: bool = False
    linkedin_api_version: str = "202405"

    @property
    def is_local(self) -> bool:
        return self.env == "local"

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
