"""add source event link for manual corrections

Revision ID: b62f3ac91d7e
Revises: a92e75f65f10
Create Date: 2026-10-25 10:50:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b62f3ac91d7e"
down_revision: str | None = "a92e75f65f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("presence_events") as batch_op:
        batch_op.add_column(
            sa.Column("correction_of_event_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("correction_event_type", sa.String(length=32), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_presence_events_correction_of_event_id_presence_events",
            "presence_events",
            ["correction_of_event_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_presence_events_correction_of_event_id",
            ["correction_of_event_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("presence_events") as batch_op:
        batch_op.drop_index("ix_presence_events_correction_of_event_id")
        batch_op.drop_constraint(
            "fk_presence_events_correction_of_event_id_presence_events",
            type_="foreignkey",
        )
        batch_op.drop_column("correction_of_event_id")
        batch_op.drop_column("correction_event_type")
