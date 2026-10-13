from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.core.time import utc_now


class ReviewScene(Base):
    __tablename__ = "review_scene"
    __table_args__ = (
        UniqueConstraint("scene_name", "business_type", name="uq_scene_name_business"),
        Index("ix_review_scene_available", "status", "display_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scene_name: Mapped[str] = mapped_column(String(40), nullable=False)
    business_type: Mapped[str] = mapped_column(String(40), default="合同审查")
    description: Mapped[str | None] = mapped_column(String(200))
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=1)
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SceneRuleRelation(Base):
    __tablename__ = "scene_rule_relation"
    __table_args__ = (Index("ix_scene_rule_relation_rule_id", "rule_id"),)

    scene_id: Mapped[int] = mapped_column(ForeignKey("review_scene.id"), primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("review_rule.id"), primary_key=True)
