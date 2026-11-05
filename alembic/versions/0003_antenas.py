"""adiciona tabela antenas (posicionamento por RSSI)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-04

"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "antenas",
        sa.Column("endereco_mac", sa.String(17), primary_key=True),
        sa.Column("latitude", sa.Numeric(11, 8), nullable=False),
        sa.Column("longitude", sa.Numeric(11, 8), nullable=False),
        sa.Column("rssi_referencia", sa.SmallInteger(), nullable=False),
        sa.Column("expoente_perda", sa.Numeric(4, 2), nullable=False),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_antenas_latitude_valida"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_antenas_longitude_valida"),
        sa.CheckConstraint("rssi_referencia BETWEEN -127 AND 0", name="ck_antenas_rssi_valido"),
        sa.CheckConstraint("expoente_perda > 0", name="ck_antenas_expoente_positivo"),
    )


def downgrade() -> None:
    op.drop_table("antenas")
