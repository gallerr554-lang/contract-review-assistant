from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


UserRole = Literal["user", "admin"]


class ManagedUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: UserRole
    status: bool
    create_time: datetime
    last_login_time: datetime | None
    task_count: int


class ManagedUserListResponse(BaseModel):
    items: list[ManagedUserResponse]
    total: int
    page: int
    page_size: int


class UserStatusUpdateRequest(BaseModel):
    status: bool
    confirmed: Literal[True]


class UserRoleUpdateRequest(BaseModel):
    role: UserRole
    confirmed: Literal[True]


class UserPasswordResetRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    new_password: str = Field(min_length=8, max_length=128)
    confirmed: Literal[True]

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(
            char.isdigit() for char in value
        ):
            raise ValueError("密码必须同时包含字母和数字。")
        return value
