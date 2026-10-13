from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "contract-review-assistant"
    app_env: str = "development"
    app_debug: bool = True

    database_url: str | None = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "contract_review"
    postgres_user: str = "contract_review"
    postgres_password: str = Field(default="contract_review", repr=False)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    storage_root: str = "../storage"
    max_file_size_mb: int = 20
    max_review_characters: int = 120_000
    document_page_characters: int = 3_000
    ocr_min_page_characters: int = 30
    ocr_language: str = "chi_sim+eng"
    ocr_timeout_seconds: int = 90

    auth_session_hours: int = 24
    captcha_expire_minutes: int = 5
    initial_admin_email: str | None = None
    initial_admin_password: str | None = Field(default=None, repr=False)

    model_provider: str = "deepseek"
    model_name: str = "deepseek-chat"
    model_api_base: str | None = None
    model_api_key: str | None = Field(default=None, repr=False)
    model_config_encryption_key: str | None = Field(default=None, repr=False)
    model_temperature: float = 0.2
    model_max_tokens: int = 4096
    model_request_timeout_seconds: int = 300

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if not self.database_url:
            user = quote_plus(self.postgres_user)
            password = quote_plus(self.postgres_password)
            database = quote_plus(self.postgres_db)
            self.database_url = (
                f"postgresql+psycopg://{user}:{password}@"
                f"{self.postgres_host}:{self.postgres_port}/{database}"
            )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
