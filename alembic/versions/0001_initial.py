"""initial

Revision ID: 0001
Revises:
Create Date: 2026-08-19

"""
import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "pets",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("tutor_id", sa.Integer(), nullable=False, index=True),
    )

    op.create_table(
        "localizacoes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "pet_id", sa.Integer(), sa.ForeignKey("pets.id"), nullable=False, index=True
        ),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.Geometry(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
    )

    op.create_table(
        "zonas_seguras",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "pet_id", sa.Integer(), sa.ForeignKey("pets.id"), nullable=False, index=True
        ),
        sa.Column("abordagem", sa.String(), nullable=False),
        sa.Column("geom", geoalchemy2.Geometry(srid=4326), nullable=False),
        sa.Column("criada_em", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "alertas",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "pet_id", sa.Integer(), sa.ForeignKey("pets.id"), nullable=False, index=True
        ),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("mensagem", sa.String(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column(
            "resolvido", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_table("alertas")
    op.drop_table("zonas_seguras")
    op.drop_table("localizacoes")
    op.drop_table("pets")