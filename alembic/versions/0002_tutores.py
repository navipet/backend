"""adiciona tabela tutores e FK real em pets.tutor_id

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-30

"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tutores",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("senha_hash", sa.String(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
    )

    op.create_foreign_key(
        "fk_pets_tutor_id_tutores",
        "pets",
        "tutores",
        ["tutor_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_pets_tutor_id_tutores", "pets", type_="foreignkey")
    op.drop_table("tutores")