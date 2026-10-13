"""add stable document risk location anchors

Revision ID: 20260805_0006
Revises: 20260804_0005
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_0006"
down_revision: str | None = "20260804_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("review_risk", sa.Column("source_file_id", sa.String(80)))
    op.add_column("review_risk", sa.Column("block_id", sa.String(80)))
    op.add_column("review_risk", sa.Column("start_offset", sa.Integer()))
    op.add_column("review_risk", sa.Column("end_offset", sa.Integer()))
    op.add_column("review_risk", sa.Column("anchor_text", sa.Text()))
    op.add_column("review_risk", sa.Column("anchor_hash", sa.String(64)))


def downgrade() -> None:
    op.drop_column("review_risk", "anchor_hash")
    op.drop_column("review_risk", "anchor_text")
    op.drop_column("review_risk", "end_offset")
    op.drop_column("review_risk", "start_offset")
    op.drop_column("review_risk", "block_id")
    op.drop_column("review_risk", "source_file_id")
