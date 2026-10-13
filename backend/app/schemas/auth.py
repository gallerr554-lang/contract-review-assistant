from datetime import datetime
from typing import Literal

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CaptchaResponse(BaseModel):
    captcha_id: str
    image_data: str
    expires_at: datetime


class AuthCredentials(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    captcha_id: str = Field(min_length=36, max_length=36)
    captcha_code: str = Field(pattern=r"^\d{4}$")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("请输入有效的邮箱地址。")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("密码必须同时包含字母和数字。")
        return value


class UserResponse(BaseModel):
    id: int
    email: str
    role: Literal["user", "admin"]
    status: bool
    create_time: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserResponse
