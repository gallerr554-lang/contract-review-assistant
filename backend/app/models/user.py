from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.core.time import utc_now


class User(Base):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_login_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    __tablename__ = "user_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuthCaptcha(Base):
    __tablename__ = "auth_captcha"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class UserOperationLog(Base):
    __tablename__ = "user_operation_log"
    __table_args__ = (
        Index("ix_user_operation_log_operator", "operator_user_id"),
        Index("ix_user_operation_log_target", "target_user_id"),
        Index("ix_user_operation_log_create_time", "create_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operator_user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False
    )
    target_user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    before_value: Mapped[str | None] = mapped_column(String(40))
    after_value: Mapped[str | None] = mapped_column(String(40))
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
