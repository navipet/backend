"""tabela antena no formato pedido pela infra e tabela medida nova

antenas -> antena: endereco_mac vira MACADDR, ficam só posição e os três
parâmetros do modelo de propagação. As antenas já cadastradas são mantidas
(potencia_referencia_1m_dbm -> potencia_referencia_dbm,
desvio_sombreamento_los_db -> desvio_sombreamento_db). Os campos de incerteza
de posição, EPSG, altura, fator de inflação e limiar são descartados.

Se alguma antena já cadastrada violar as faixas novas (potência fora de
-100..0 dBm, desvio >= 30 dB, expoente < 1, ou coordenada (0, 0)), o upgrade
falha ao criar a restrição: corrija a linha e rode de novo.

Cria a tabela medida (o que cada âncora ouviu em cada superquadro). Exige
PostgreSQL 15+ por causa do UNIQUE NULLS NOT DISTINCT.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-22

"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

CHECKS_ANTIGOS = {
    "ck_antenas_latitude_valida": "latitude BETWEEN -90 AND 90",
    "ck_antenas_longitude_valida": "longitude BETWEEN -180 AND 180",
    "ck_antenas_variancias_positivas": "variancia_leste_m2 > 0 AND variancia_norte_m2 > 0",
    "ck_antenas_covariancia_semidefinida_positiva": (
        "variancia_leste_m2 * variancia_norte_m2 >= "
        "covariancia_leste_norte_m2 * covariancia_leste_norte_m2"
    ),
    "ck_antenas_expoente_plausivel": "expoente_perda_percurso BETWEEN 1.5 AND 6.0",
    "ck_antenas_desvio_positivo": "desvio_sombreamento_los_db > 0",
    "ck_antenas_limiar_negativo": "limiar_rssi_dbm < 0",
}

# (coluna, tipo, valor provisório no downgrade) -- os mesmos provisórios da 0007
DESCARTADAS = [
    ("codigo_epsg", sa.Integer(), "31983"),
    ("altura_elipsoidal_m", sa.Float(), "0"),
    ("variancia_leste_m2", sa.Float(), "1"),
    ("variancia_norte_m2", sa.Float(), "1"),
    ("covariancia_leste_norte_m2", sa.Float(), "0"),
    ("fator_inflacao_dispersao", sa.Float(), "1"),
    ("limiar_rssi_dbm", sa.SmallInteger(), "-90"),
]

CHECKS_NOVOS = {
    "latitude_dentro_da_faixa": "latitude BETWEEN -90 AND 90",
    "longitude_dentro_da_faixa": "longitude BETWEEN -180 AND 180",
    "coordenada_nao_e_ilha_nula": "NOT (latitude = 0 AND longitude = 0)",
    "potencia_referencia_plausivel": "potencia_referencia_dbm BETWEEN -100 AND 0",
    "expoente_plausivel": "expoente_perda_percurso BETWEEN 1.0 AND 6.0",
    "sombreamento_plausivel": "desvio_sombreamento_db > 0 AND desvio_sombreamento_db < 30",
}

CRIAR_MEDIDA = """
CREATE TABLE medida (
    id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Quando e de quem
    numero_superquadro        BIGINT      NOT NULL,
    instante_superquadro      TIMESTAMPTZ NOT NULL,
    endereco_mac_ancora       MACADDR     NOT NULL REFERENCES antena (endereco_mac),

    -- Qual pet; nulo significa "ouviu silêncio"
    pet_id                    BIGINT,

    -- Observação de rádio, agregada na janela
    rssi_maximo_dbm           SMALLINT,
    rssi_mediano_dbm          REAL,
    rssi_medio_dbm            REAL,
    amostras_total            SMALLINT    NOT NULL DEFAULT 0,
    amostras_canal_37         SMALLINT    NOT NULL DEFAULT 0,
    amostras_canal_38         SMALLINT    NOT NULL DEFAULT 0,
    amostras_canal_39         SMALLINT    NOT NULL DEFAULT 0,
    sequencia_pet_primeira    INTEGER,
    sequencia_pet_ultima      INTEGER,
    bateria_pet               SMALLINT,

    -- Telemetria da âncora naquele superquadro
    profundidade              SMALLINT    NOT NULL,
    endereco_mac_pai          MACADDR,
    rssi_espnow_pai_dbm       SMALLINT,
    vizinhos_ativos           SMALLINT    NOT NULL,
    tempo_varredura_ms        SMALLINT    NOT NULL,
    desvio_sincronismo_us     INTEGER     NOT NULL,
    sequencia_espnow          INTEGER     NOT NULL,
    quadros_ambiente          INTEGER     NOT NULL DEFAULT 0,
    latencia_chegada_ms       INTEGER,

    -- Configuração vigente, para o experimento de compromisso
    duracao_comunicacao_ms    SMALLINT    NOT NULL,

    -- Anotação de campanha, preenchida pelo modo de coleta
    ponto_id                  TEXT,
    sessao                    TEXT,

    CONSTRAINT rssi_plausivel
        CHECK (rssi_maximo_dbm IS NULL OR rssi_maximo_dbm BETWEEN -110 AND 0),
    CONSTRAINT ordem_dos_agregados
        CHECK (rssi_maximo_dbm IS NULL OR rssi_medio_dbm IS NULL
               OR rssi_maximo_dbm >= rssi_medio_dbm),
    CONSTRAINT amostras_somam_os_canais
        CHECK (amostras_total = amostras_canal_37 + amostras_canal_38 + amostras_canal_39),
    CONSTRAINT silencio_sem_pet
        CHECK ((pet_id IS NULL) = (amostras_total = 0)),
    CONSTRAINT varredura_dentro_do_superquadro
        CHECK (tempo_varredura_ms BETWEEN 0 AND 2000),
    CONSTRAINT profundidade_valida
        CHECK (profundidade BETWEEN 1 AND 32),

    CONSTRAINT medida_unica
        UNIQUE NULLS NOT DISTINCT (numero_superquadro, endereco_mac_ancora, pet_id)
)
"""


def upgrade() -> None:
    for nome in CHECKS_ANTIGOS:
        op.drop_constraint(nome, "antenas", type_="check")
    for nome, _, _ in DESCARTADAS:
        op.drop_column("antenas", nome)

    op.alter_column("antenas", "potencia_referencia_1m_dbm", new_column_name="potencia_referencia_dbm")
    op.alter_column("antenas", "desvio_sombreamento_los_db", new_column_name="desvio_sombreamento_db")
    for coluna in ("potencia_referencia_dbm", "expoente_perda_percurso", "desvio_sombreamento_db"):
        op.alter_column("antenas", coluna, type_=sa.REAL(), postgresql_using=f"{coluna}::real")
    op.execute("ALTER TABLE antenas ALTER COLUMN endereco_mac TYPE macaddr USING endereco_mac::macaddr")

    op.rename_table("antenas", "antena")
    op.execute("ALTER TABLE antena RENAME CONSTRAINT antenas_pkey TO antena_pkey")

    for nome, condicao in CHECKS_NOVOS.items():
        op.create_check_constraint(nome, "antena", condicao)

    op.execute(CRIAR_MEDIDA)


def downgrade() -> None:
    op.drop_table("medida")

    for nome in CHECKS_NOVOS:
        op.drop_constraint(nome, "antena", type_="check")

    op.execute("ALTER TABLE antena RENAME CONSTRAINT antena_pkey TO antenas_pkey")
    op.rename_table("antena", "antenas")

    # volta ao formato da 0007: texto em maiúsculas
    op.execute(
        "ALTER TABLE antenas ALTER COLUMN endereco_mac TYPE varchar(17) "
        "USING upper(endereco_mac::text)"
    )
    for coluna in ("potencia_referencia_dbm", "expoente_perda_percurso", "desvio_sombreamento_db"):
        op.alter_column("antenas", coluna, type_=sa.Float(), postgresql_using=f"{coluna}::double precision")
    op.alter_column("antenas", "desvio_sombreamento_db", new_column_name="desvio_sombreamento_los_db")
    op.alter_column("antenas", "potencia_referencia_dbm", new_column_name="potencia_referencia_1m_dbm")

    for nome, tipo, provisorio in DESCARTADAS:
        op.add_column("antenas", sa.Column(nome, tipo, nullable=False, server_default=provisorio))
        op.alter_column("antenas", nome, server_default=None)

    # o expoente aceito na 0007 começa em 1.5; abaixo disso vira 1.5 para a restrição passar
    op.execute("UPDATE antenas SET expoente_perda_percurso = 1.5 WHERE expoente_perda_percurso < 1.5")
    for nome, condicao in CHECKS_ANTIGOS.items():
        op.create_check_constraint(nome, "antenas", condicao)
