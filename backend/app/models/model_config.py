from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.core.time import utc_now


class ModelConfig(Base):
    __tablename__ = "model_config"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "model_name",
            "api_base",
            name="uq_model_config_provider_name_base",
        ),
        Index(
            "uq_model_config_active",
            "status",
            unique=True,
            postgresql_where=text("status IS TRUE"),
            sqlite_where=text("status IS TRUE"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    api_base: Mapped[str | None] = mapped_column(String(255))
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    temperature: Mapped[float] = mapped_column(Float, default=0.2)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    status: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
