"""adiciona contador de leituras seguidas dentro da zona (histerese do alerta)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-11

"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pets",
        sa.Column(
            "leituras_dentro_consecutivas",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("pets", "leituras_dentro_consecutivas")