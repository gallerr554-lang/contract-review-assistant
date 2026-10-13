"""add review records, feedback and model configuration

Revision ID: 20260804_0003
Revises: 20260804_0002
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_0003"
down_revision: str | None = "20260804_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "review_task",
        sa.Column(
            "model_snapshot",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.create_index("ix_review_task_status", "review_task", ["status"])
    op.create_index("ix_review_task_create_time", "review_task", ["create_time"])
    op.create_index("ix_review_task_contract_name", "review_task", ["contract_name"])
    op.create_index(
        "ix_review_risk_task_level", "review_risk", ["task_id", "risk_level"]
    )

    op.add_column("model_config", sa.Column("api_key_encrypted", sa.Text()))
    op.add_column(
        "model_config",
        sa.Column(
            "create_time",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "model_config",
        sa.Column(
            "update_time",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.drop_column("model_config", "api_key")
    op.create_index("ix_model_config_status", "model_config", ["status"])

    op.create_table(
        "review_risk_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("review_task.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "risk_id",
            sa.Integer(),
            sa.ForeignKey("review_risk.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("content", sa.String(500), nullable=False),
        sa.Column(
            "create_time",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "task_id", "risk_id", name="uq_review_risk_feedback_task_risk"
        ),
    )
    op.create_index(
        "ix_review_risk_feedback_task_id", "review_risk_feedback", ["task_id"]
    )
    op.create_index(
        "ix_review_risk_feedback_risk_id", "review_risk_feedback", ["risk_id"]
    )

    connection = op.get_bind()
    model_table = sa.table(
        "model_config",
        sa.column("provider", sa.String),
        sa.column("model_name", sa.String),
        sa.column("api_base", sa.String),
        sa.column("api_key_encrypted", sa.Text),
        sa.column("temperature", sa.Float),
        sa.column("max_tokens", sa.Integer),
        sa.column("status", sa.Boolean),
    )
    model_count = connection.scalar(
        sa.select(sa.func.count()).select_from(model_table)
    )
    if not model_count:
        op.bulk_insert(
            model_table,
            [
                {
                    "provider": "deepseek",
                    "model_name": "deepseek-chat",
                    "api_base": "https://api.deepseek.com",
                    "api_key_encrypted": None,
                    "temperature": 0.2,
                    "max_tokens": 4096,
                    "status": True,
                }
            ],
        )


def downgrade() -> None:
    op.drop_index("ix_review_risk_feedback_risk_id", table_name="review_risk_feedback")
    op.drop_index("ix_review_risk_feedback_task_id", table_name="review_risk_feedback")
    op.drop_table("review_risk_feedback")

    op.drop_index("ix_model_config_status", table_name="model_config")
    op.add_column("model_config", sa.Column("api_key", sa.String(255)))
    op.drop_column("model_config", "update_time")
    op.drop_column("model_config", "create_time")
    op.drop_column("model_config", "api_key_encrypted")

    op.drop_index("ix_review_risk_task_level", table_name="review_risk")
    op.drop_index("ix_review_task_contract_name", table_name="review_task")
    op.drop_index("ix_review_task_create_time", table_name="review_task")
    op.drop_index("ix_review_task_status", table_name="review_task")
    op.drop_column("review_task", "model_snapshot")
