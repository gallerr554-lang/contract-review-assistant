"""create contract review core tables

Revision ID: 20260803_0001
Revises:
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model_name", sa.String(120), nullable=False),
        sa.Column("api_base", sa.String(255)),
        sa.Column("api_key", sa.String(255)),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="4096"),
        sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "review_rule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_id", sa.String(64), nullable=False, unique=True),
        sa.Column("rule_name", sa.String(40), nullable=False),
        sa.Column("business_type", sa.String(40), nullable=False, server_default="合同审查"),
        sa.Column("rule_type", sa.String(40), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("review_requirement", sa.Text(), nullable=False),
        sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("update_time", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_review_rule_rule_id", "review_rule", ["rule_id"], unique=True)
    op.create_table(
        "review_scene",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scene_name", sa.String(40), nullable=False),
        sa.Column("business_type", sa.String(40), nullable=False, server_default="合同审查"),
        sa.Column("description", sa.String(200)),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("update_time", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("scene_name", "business_type", name="uq_scene_name_business"),
    )
    op.create_table(
        "scene_rule_relation",
        sa.Column("scene_id", sa.Integer(), sa.ForeignKey("review_scene.id"), primary_key=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("review_rule.id"), primary_key=True),
    )
    op.create_table(
        "review_task",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_no", sa.String(32), nullable=False, unique=True),
        sa.Column("idempotency_key", sa.String(64), unique=True),
        sa.Column("upload_id", sa.String(36), nullable=False),
        sa.Column("contract_name", sa.String(255), nullable=False),
        sa.Column("contract_text", sa.Text(), nullable=False),
        sa.Column("attachment_names", sa.JSON(), nullable=False),
        sa.Column("attachment_texts", sa.JSON(), nullable=False),
        sa.Column("scene_id", sa.Integer()),
        sa.Column("scene_name", sa.String(80), nullable=False),
        sa.Column("scene_snapshot", sa.JSON(), nullable=False),
        sa.Column("scale", sa.String(20), nullable=False),
        sa.Column("position", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("current_message", sa.String(200), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("summary", sa.Text()),
        sa.Column("create_time", sa.DateTime(), nullable=False),
        sa.Column("complete_time", sa.DateTime()),
    )
    op.create_index("ix_review_task_task_no", "review_task", ["task_no"], unique=True)
    op.create_table(
        "review_risk",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("review_task.id"), nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("risk_name", sa.String(120), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("original_text", sa.Text()),
        sa.Column("source", sa.String(255)),
        sa.Column("locatable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("review_risk")
    op.drop_index("ix_review_task_task_no", table_name="review_task")
    op.drop_table("review_task")
    op.drop_table("scene_rule_relation")
    op.drop_table("review_scene")
    op.drop_index("ix_review_rule_rule_id", table_name="review_rule")
    op.drop_table("review_rule")
    op.drop_table("model_config")
