"""adiciona contador de leituras seguidas fora da zona (filtro de persistencia)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-09

"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pets",
        sa.Column(
            "leituras_fora_consecutivas",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("pets", "leituras_fora_consecutivas")
