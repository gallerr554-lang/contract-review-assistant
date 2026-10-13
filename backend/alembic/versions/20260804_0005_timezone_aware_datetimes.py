"""convert application datetimes to timezone-aware UTC

Revision ID: 20260804_0005
Revises: 20260804_0004
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_0005"
down_revision: str | None = "20260804_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TIME_COLUMNS = (
    ("review_rule", "update_time", False),
    ("review_scene", "update_time", False),
    ("review_task", "create_time", False),
    ("review_task", "complete_time", True),
    ("model_config", "create_time", False),
    ("model_config", "update_time", False),
    ("review_risk_feedback", "create_time", False),
    ("app_user", "create_time", False),
    ("app_user", "last_login_time", True),
    ("user_session", "expires_at", False),
    ("user_session", "create_time", False),
    ("auth_captcha", "expires_at", False),
    ("auth_captcha", "create_time", False),
)


def upgrade() -> None:
    for table_name, column_name, nullable in TIME_COLUMNS:
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=nullable,
            postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    for table_name, column_name, nullable in reversed(TIME_COLUMNS):
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=nullable,
            postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
        )
