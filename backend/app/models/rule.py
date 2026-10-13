from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.core.time import utc_now


class ReviewRule(Base):
    __tablename__ = "review_rule"
    __table_args__ = (Index("ix_review_rule_rule_id", "rule_id", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    rule_name: Mapped[str] = mapped_column(String(40), nullable=False)
    business_type: Mapped[str] = mapped_column(String(40), default="合同审查")
    rule_type: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    review_requirement: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
