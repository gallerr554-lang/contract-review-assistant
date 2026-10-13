"""add users, ownership and paged document metadata

Revision ID: 20260804_0004
Revises: 20260804_0003
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_0004"
down_revision: str | None = "20260804_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_time", sa.DateTime()),
    )
    op.create_index("ix_app_user_id", "app_user", ["id"])
    op.create_index("ix_app_user_email", "app_user", ["email"], unique=True)

    op.create_table(
        "user_session",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("app_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_session_user_id", "user_session", ["user_id"])
    op.create_index("ix_user_session_token_hash", "user_session", ["token_hash"], unique=True)
    op.create_index("ix_user_session_expires_at", "user_session", ["expires_at"])

    op.create_table(
        "auth_captcha",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_auth_captcha_expires_at", "auth_captcha", ["expires_at"])

    op.add_column("review_task", sa.Column("user_id", sa.Integer()))
    op.create_foreign_key(
        "fk_review_task_user_id", "review_task", "app_user", ["user_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_review_task_user_id", "review_task", ["user_id"])
    op.add_column(
        "review_task",
        sa.Column("document_pages", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "review_task",
        sa.Column("document_meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.drop_constraint("review_task_idempotency_key_key", "review_task", type_="unique")
    op.create_unique_constraint(
        "uq_review_task_user_idempotency", "review_task", ["user_id", "idempotency_key"]
    )

    op.add_column("review_risk", sa.Column("page_number", sa.Integer()))

    op.add_column("review_risk_feedback", sa.Column("user_id", sa.Integer()))
    op.create_foreign_key(
        "fk_review_risk_feedback_user_id",
        "review_risk_feedback",
        "app_user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_review_risk_feedback_user_id", "review_risk_feedback", ["user_id"])

    op.add_column("model_config", sa.Column("user_id", sa.Integer()))
    op.create_foreign_key(
        "fk_model_config_user_id", "model_config", "app_user", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_model_config_user_id", "model_config", ["user_id"])
    op.create_unique_constraint(
        "uq_model_config_user_provider_name_base",
        "model_config",
        ["user_id", "provider", "model_name", "api_base"],
    )
    op.create_index(
        "uq_model_config_user_active",
        "model_config",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IS TRUE AND user_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_model_config_user_active", table_name="model_config")
    op.drop_constraint("uq_model_config_user_provider_name_base", "model_config", type_="unique")
    op.drop_index("ix_model_config_user_id", table_name="model_config")
    op.drop_constraint("fk_model_config_user_id", "model_config", type_="foreignkey")
    op.drop_column("model_config", "user_id")

    op.drop_index("ix_review_risk_feedback_user_id", table_name="review_risk_feedback")
    op.drop_constraint("fk_review_risk_feedback_user_id", "review_risk_feedback", type_="foreignkey")
    op.drop_column("review_risk_feedback", "user_id")
    op.drop_column("review_risk", "page_number")

    op.drop_constraint("uq_review_task_user_idempotency", "review_task", type_="unique")
    op.create_unique_constraint("review_task_idempotency_key_key", "review_task", ["idempotency_key"])
    op.drop_column("review_task", "document_meta")
    op.drop_column("review_task", "document_pages")
    op.drop_index("ix_review_task_user_id", table_name="review_task")
    op.drop_constraint("fk_review_task_user_id", "review_task", type_="foreignkey")
    op.drop_column("review_task", "user_id")

    op.drop_index("ix_auth_captcha_expires_at", table_name="auth_captcha")
    op.drop_table("auth_captcha")
    op.drop_index("ix_user_session_expires_at", table_name="user_session")
    op.drop_index("ix_user_session_token_hash", table_name="user_session")
    op.drop_index("ix_user_session_user_id", table_name="user_session")
    op.drop_table("user_session")
    op.drop_index("ix_app_user_email", table_name="app_user")
    op.drop_index("ix_app_user_id", table_name="app_user")
    op.drop_table("app_user")
