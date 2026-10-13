"""add user management operation log

Revision ID: 20260806_0009
Revises: 20260805_0008
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260806_0009"
down_revision: str | None = "20260805_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_operation_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "operator_user_id",
            sa.Integer(),
            sa.ForeignKey("app_user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "target_user_id",
            sa.Integer(),
            sa.ForeignKey("app_user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("before_value", sa.String(40)),
        sa.Column("after_value", sa.String(40)),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_user_operation_log_operator", "user_operation_log", ["operator_user_id"]
    )
    op.create_index(
        "ix_user_operation_log_target", "user_operation_log", ["target_user_id"]
    )
    op.create_index(
        "ix_user_operation_log_create_time", "user_operation_log", ["create_time"]
    )


def downgrade() -> None:
    op.drop_index("ix_user_operation_log_create_time", table_name="user_operation_log")
    op.drop_index("ix_user_operation_log_target", table_name="user_operation_log")
    op.drop_index("ix_user_operation_log_operator", table_name="user_operation_log")
    op.drop_table("user_operation_log")
