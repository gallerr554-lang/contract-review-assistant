"""make model configuration global

Revision ID: 20260805_0008
Revises: 20260805_0007
Create Date: 2026-08-05
"""

from collections.abc import Mapping, Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_0008"
down_revision: str | None = "20260805_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _consolidate_configs(connection: sa.Connection) -> None:
    model = sa.table(
        "model_config",
        sa.column("id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("provider", sa.String),
        sa.column("model_name", sa.String),
        sa.column("api_base", sa.String),
        sa.column("api_key_encrypted", sa.Text),
        sa.column("temperature", sa.Float),
        sa.column("max_tokens", sa.Integer),
        sa.column("status", sa.Boolean),
    )
    user = sa.table(
        "app_user",
        sa.column("id", sa.Integer),
        sa.column("role", sa.String),
    )
    rows = list(
        connection.execute(
            sa.select(
                model.c.id,
                model.c.provider,
                model.c.model_name,
                model.c.api_base,
                model.c.status,
                user.c.role,
            ).select_from(model.outerjoin(user, model.c.user_id == user.c.id))
        ).mappings()
    )
    if not rows:
        connection.execute(
            model.insert().values(
                provider="deepseek",
                model_name="deepseek-chat",
                api_base="https://api.deepseek.com",
                api_key_encrypted=None,
                temperature=0.2,
                max_tokens=4096,
                status=True,
            )
        )
        return

    def priority(row: Mapping[str, object]) -> tuple[int, int]:
        if row["status"] and row["role"] == "admin":
            rank = 0
        elif row["status"]:
            rank = 1
        elif row["role"] == "admin":
            rank = 2
        else:
            rank = 3
        return rank, int(row["id"])

    ordered = sorted(rows, key=priority)
    survivor_ids: list[int] = []
    seen: set[tuple[str, str, str | None]] = set()
    for row in ordered:
        identity = (row["provider"], row["model_name"], row["api_base"])
        if identity in seen:
            continue
        seen.add(identity)
        survivor_ids.append(int(row["id"]))

    connection.execute(sa.delete(model).where(model.c.id.not_in(survivor_ids)))
    connection.execute(sa.update(model).values(status=False))
    connection.execute(
        sa.update(model).where(model.c.id == survivor_ids[0]).values(status=True)
    )


def _scrub_task_snapshots(connection: sa.Connection) -> None:
    task = sa.table(
        "review_task",
        sa.column("id", sa.Integer),
        sa.column("model_snapshot", sa.JSON),
    )
    rows = connection.execute(sa.select(task.c.id, task.c.model_snapshot)).mappings()
    for row in rows:
        snapshot = dict(row["model_snapshot"] or {})
        changed = False
        for field in ("user_id", "api_key_encrypted"):
            if field in snapshot:
                snapshot.pop(field)
                changed = True
        if changed:
            connection.execute(
                sa.update(task)
                .where(task.c.id == row["id"])
                .values(model_snapshot=snapshot)
            )


def upgrade() -> None:
    connection = op.get_bind()
    _consolidate_configs(connection)
    _scrub_task_snapshots(connection)

    op.drop_index("uq_model_config_user_active", table_name="model_config")
    op.drop_constraint(
        "uq_model_config_user_provider_name_base", "model_config", type_="unique"
    )
    op.drop_index("ix_model_config_user_id", table_name="model_config")
    op.drop_constraint("fk_model_config_user_id", "model_config", type_="foreignkey")
    op.drop_column("model_config", "user_id")

    op.create_unique_constraint(
        "uq_model_config_provider_name_base",
        "model_config",
        ["provider", "model_name", "api_base"],
    )
    op.create_index(
        "uq_model_config_active",
        "model_config",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status IS TRUE"),
        sqlite_where=sa.text("status IS TRUE"),
    )


def downgrade() -> None:
    op.drop_index("uq_model_config_active", table_name="model_config")
    op.drop_constraint(
        "uq_model_config_provider_name_base", "model_config", type_="unique"
    )

    op.add_column("model_config", sa.Column("user_id", sa.Integer()))
    op.create_foreign_key(
        "fk_model_config_user_id",
        "model_config",
        "app_user",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
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
        sqlite_where=sa.text("status IS TRUE AND user_id IS NOT NULL"),
    )
