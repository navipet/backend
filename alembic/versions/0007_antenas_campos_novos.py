"""antenas: campos de incerteza de posição e modelo de propagação (pedido do João)

Renomeia rssi_referencia -> potencia_referencia_1m_dbm e expoente_perda ->
expoente_perda_percurso (os valores das antenas já cadastradas são mantidos) e
adiciona os campos novos. As antenas que já existem recebem VALORES PROVISÓRIOS
nos campos novos (EPSG 31983, altura 0, variâncias 1 m², covariância 0, desvio 4 dB,
fator 1, limiar -90 dBm); o João deve confirmá-los com PUT /antena/{mac}.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-21

"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# (coluna, tipo, valor provisório para as linhas já existentes)
NOVAS = [
    ("codigo_epsg", sa.Integer(), "31983"),
    ("altura_elipsoidal_m", sa.Float(), "0"),
    ("variancia_leste_m2", sa.Float(), "1"),
    ("variancia_norte_m2", sa.Float(), "1"),
    ("covariancia_leste_norte_m2", sa.Float(), "0"),
    ("desvio_sombreamento_los_db", sa.Float(), "4"),
    ("fator_inflacao_dispersao", sa.Float(), "1"),
    ("limiar_rssi_dbm", sa.SmallInteger(), "-90"),
]

CHECKS_NOVOS = {
    "ck_antenas_variancias_positivas": "variancia_leste_m2 > 0 AND variancia_norte_m2 > 0",
    "ck_antenas_covariancia_semidefinida_positiva": (
        "variancia_leste_m2 * variancia_norte_m2 >= "
        "covariancia_leste_norte_m2 * covariancia_leste_norte_m2"
    ),
    "ck_antenas_expoente_plausivel": "expoente_perda_percurso BETWEEN 1.5 AND 6.0",
    "ck_antenas_desvio_positivo": "desvio_sombreamento_los_db > 0",
    "ck_antenas_limiar_negativo": "limiar_rssi_dbm < 0",
}


def upgrade() -> None:
    op.drop_constraint("ck_antenas_rssi_valido", "antenas", type_="check")
    op.drop_constraint("ck_antenas_expoente_positivo", "antenas", type_="check")

    op.alter_column("antenas", "rssi_referencia", new_column_name="potencia_referencia_1m_dbm")
    op.alter_column("antenas", "expoente_perda", new_column_name="expoente_perda_percurso")
    for coluna in ("potencia_referencia_1m_dbm", "expoente_perda_percurso", "latitude", "longitude"):
        op.alter_column("antenas", coluna, type_=sa.Float(), postgresql_using=f"{coluna}::double precision")

    for nome, tipo, provisorio in NOVAS:
        op.add_column("antenas", sa.Column(nome, tipo, nullable=False, server_default=provisorio))
        op.alter_column("antenas", nome, server_default=None)

    for nome, condicao in CHECKS_NOVOS.items():
        op.create_check_constraint(nome, "antenas", condicao)


def downgrade() -> None:
    for nome in CHECKS_NOVOS:
        op.drop_constraint(nome, "antenas", type_="check")
    for nome, _, _ in NOVAS:
        op.drop_column("antenas", nome)

    op.alter_column("antenas", "potencia_referencia_1m_dbm", new_column_name="rssi_referencia")
    op.alter_column("antenas", "expoente_perda_percurso", new_column_name="expoente_perda")
    op.alter_column("antenas", "rssi_referencia", type_=sa.SmallInteger(),
                    postgresql_using="round(rssi_referencia)::smallint")
    op.alter_column("antenas", "expoente_perda", type_=sa.Numeric(4, 2),
                    postgresql_using="expoente_perda::numeric(4,2)")
    op.alter_column("antenas", "latitude", type_=sa.Numeric(11, 8), postgresql_using="latitude::numeric(11,8)")
    op.alter_column("antenas", "longitude", type_=sa.Numeric(11, 8), postgresql_using="longitude::numeric(11,8)")

    op.create_check_constraint("ck_antenas_rssi_valido", "antenas", "rssi_referencia BETWEEN -127 AND 0")
    op.create_check_constraint("ck_antenas_expoente_positivo", "antenas", "expoente_perda > 0")
