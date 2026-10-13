"""add multi-block and attachment risk locations

Revision ID: 20260805_0007
Revises: 20260805_0006
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_0007"
down_revision: str | None = "20260805_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "review_task",
        sa.Column("document_files", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "review_risk",
        sa.Column("location_spans", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "review_risk",
        sa.Column("location_hint", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("review_risk", "location_hint")
    op.drop_column("review_risk", "location_spans")
    op.drop_column("review_task", "document_files")
