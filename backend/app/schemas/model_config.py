from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ProviderName = Literal["openai", "deepseek", "qwen"]


class ModelConfigCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    provider: ProviderName
    model_name: str = Field(min_length=1, max_length=120)
    api_base: str = Field(min_length=8, max_length=255)
    api_key: str = Field(min_length=1, max_length=500)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=1, le=128_000)
    status: bool = False

    @field_validator("api_base")
    @classmethod
    def validate_api_base(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("API Base 必须使用 http:// 或 https://。")
        return value.rstrip("/")


class ModelConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    provider: ProviderName
    model_name: str = Field(min_length=1, max_length=120)
    api_base: str = Field(min_length=8, max_length=255)
    api_key: str | None = Field(default=None, min_length=1, max_length=500)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=1, le=128_000)
    status: bool

    @field_validator("api_base")
    @classmethod
    def validate_api_base(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("API Base 必须使用 http:// 或 https://。")
        return value.rstrip("/")


class ModelConfigResponse(BaseModel):
    id: int
    provider: str
    model_name: str
    api_base: str | None
    api_key_masked: str
    api_key_configured: bool
    api_key_source: Literal["encrypted", "environment", "missing"]
    temperature: float
    max_tokens: int
    status: bool
    create_time: datetime
    update_time: datetime


class ModelConnectionTestResponse(BaseModel):
    provider: str
    model_name: str
    api_base: str
    success: bool
    http_status: int | None = None
    message: str
