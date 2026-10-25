"""add optional student mapping and token version to users

Revision ID: a92e75f65f10
Revises: 564597f82c24
Create Date: 2026-10-25 10:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a92e75f65f10"
down_revision: str | None = "564597f82c24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("student_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("token_version", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.create_foreign_key(
            "fk_users_student_id_students",
            "students",
            ["student_id"],
            ["id"],
        )
        batch_op.create_unique_constraint("uq_users_student_id", ["student_id"])


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_student_id", type_="unique")
        batch_op.drop_constraint("fk_users_student_id_students", type_="foreignkey")
        batch_op.drop_column("token_version")
        batch_op.drop_column("student_id")
