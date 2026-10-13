from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.core.time import utc_now


class ReviewTask(Base):
    __tablename__ = "review_task"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_review_task_user_idempotency"),
        Index("ix_review_task_task_no", "task_no", unique=True),
        Index("ix_review_task_status", "status"),
        Index("ix_review_task_create_time", "create_time"),
        Index("ix_review_task_contract_name", "contract_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True, index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    upload_id: Mapped[str] = mapped_column(String(36), nullable=False)
    contract_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_text: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_names: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    attachment_texts: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    scene_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scene_name: Mapped[str] = mapped_column(String(80), nullable=False)
    scene_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    model_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    document_pages: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    document_meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    document_files: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    scale: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")
    position: Mapped[str] = mapped_column(String(20), nullable=False, default="party_a")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PROCESSING")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_message: Mapped[str] = mapped_column(String(200), nullable=False, default="任务已创建")
    error_message: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    complete_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewRisk(Base):
    __tablename__ = "review_risk"
    __table_args__ = (Index("ix_review_risk_task_level", "task_id", "risk_level"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("review_task.id"), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_name: Mapped[str] = mapped_column(String(120), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    original_text: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(255))
    locatable: Mapped[bool] = mapped_column(nullable=False, default=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    source_file_id: Mapped[str | None] = mapped_column(String(80))
    block_id: Mapped[str | None] = mapped_column(String(80))
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    anchor_text: Mapped[str | None] = mapped_column(Text)
    anchor_hash: Mapped[str | None] = mapped_column(String(64))
    location_spans: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    location_hint: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ReviewRiskFeedback(Base):
    __tablename__ = "review_risk_feedback"
    __table_args__ = (
        UniqueConstraint("task_id", "risk_id", name="uq_review_risk_feedback_task_risk"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("review_task.id", ondelete="CASCADE"), nullable=False, index=True
    )
    risk_id: Mapped[int] = mapped_column(
        ForeignKey("review_risk.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(String(500), nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
