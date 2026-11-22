from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import MACADDR
from sqlalchemy.orm import relationship

from app.db.session import Base


class Tutor(Base):
    """dono do pet -- quem se cadastra e faz login no app"""

    __tablename__ = "tutores"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    senha_hash = Column(String, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)

    pets = relationship("Pet", back_populates="tutor")


class Pet(Base):
    __tablename__ = "pets"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    tutor_id = Column(Integer, ForeignKey("tutores.id"), nullable=False, index=True)
    # filtro de persistencia dos alertas: leituras seguidas fora da zona
    leituras_fora_consecutivas = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # histerese: leituras seguidas dentro da zona (para fechar o alerta)
    leituras_dentro_consecutivas = Column(
        Integer, nullable=False, default=0, server_default="0"
    )

    tutor = relationship("Tutor", back_populates="pets")
    localizacoes = relationship("Localizacao", back_populates="pet")
    zonas_seguras = relationship("ZonaSegura", back_populates="pet")
    alertas = relationship("Alerta", back_populates="pet")


class Localizacao(Base):
    __tablename__ = "localizacoes"

    id = Column(Integer, primary_key=True, index=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    # hora da leitura: a que o dispositivo mandou, ou a do servidor se ele nao mandou
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    # hora (UTC) em que o SERVIDOR recebeu a leitura. sempre preenchida pelo
    # servidor, independe do relogio do dispositivo (nula em leituras antigas)
    recebido_em = Column(DateTime, nullable=True)
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)

    pet = relationship("Pet", back_populates="localizacoes")


class ZonaSegura(Base):
    __tablename__ = "zonas_seguras"

    id = Column(Integer, primary_key=True, index=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    abordagem = Column(String, nullable=False)
    geom = Column(Geometry(srid=4326), nullable=False)
    criada_em = Column(DateTime, default=datetime.utcnow, nullable=False)

    pet = relationship("Pet", back_populates="zonas_seguras")


class Alerta(Base):
    __tablename__ = "alertas"

    id = Column(Integer, primary_key=True, index=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    tipo = Column(String, nullable=False, default="fora_da_zona")
    mensagem = Column(String, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolvido = Column(Boolean, default=False, nullable=False)

    pet = relationship("Pet", back_populates="alertas")


# MACADDR no PostgreSQL; texto no SQLite dos testes (o valor já chega normalizado)
_MAC = MACADDR().with_variant(String(17), "sqlite")
# BIGINT IDENTITY no PostgreSQL; o SQLite só autoincrementa INTEGER PRIMARY KEY
_ID_GRANDE = BigInteger().with_variant(Integer, "sqlite")


class Antena(Base):
    """antena fixa (ESP) usada para estimar a posição da tag do pet por RSSI.

    Cada antena busca uma única vez, ao ligar, a própria posição e os parâmetros
    do modelo de propagação log-distância (GET /antena/{mac}).
    """

    __tablename__ = "antena"

    # MAC normalizado em minúsculas: aa:bb:cc:dd:ee:ff
    endereco_mac = Column(_MAC, primary_key=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    potencia_referencia_dbm = Column(REAL, nullable=False)
    expoente_perda_percurso = Column(REAL, nullable=False)
    desvio_sombreamento_db = Column(REAL, nullable=False)

    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_dentro_da_faixa"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_dentro_da_faixa"),
        CheckConstraint("NOT (latitude = 0 AND longitude = 0)", name="coordenada_nao_e_ilha_nula"),
        CheckConstraint(
            "potencia_referencia_dbm BETWEEN -100 AND 0", name="potencia_referencia_plausivel"
        ),
        CheckConstraint("expoente_perda_percurso BETWEEN 1.0 AND 6.0", name="expoente_plausivel"),
        CheckConstraint(
            "desvio_sombreamento_db > 0 AND desvio_sombreamento_db < 30",
            name="sombreamento_plausivel",
        ),
    )


class Medida(Base):
    """o que uma âncora observou de um pet (ou o silêncio) em um superquadro.

    pet_id nulo significa que a âncora estava viva, reportou, e não ouviu pet algum.
    pet_id é o identificador da tag (uint32), por isso não tem chave estrangeira.
    """

    __tablename__ = "medida"

    id = Column(_ID_GRANDE, Identity(always=True), primary_key=True)

    # quando e de quem
    numero_superquadro = Column(BigInteger, nullable=False)
    instante_superquadro = Column(DateTime(timezone=True), nullable=False)
    endereco_mac_ancora = Column(_MAC, ForeignKey("antena.endereco_mac"), nullable=False)

    # qual pet; nulo significa "ouviu silêncio"
    pet_id = Column(BigInteger)

    # observação de rádio, agregada na janela
    rssi_maximo_dbm = Column(SmallInteger)
    rssi_mediano_dbm = Column(REAL)
    rssi_medio_dbm = Column(REAL)
    amostras_total = Column(SmallInteger, nullable=False, server_default="0")
    amostras_canal_37 = Column(SmallInteger, nullable=False, server_default="0")
    amostras_canal_38 = Column(SmallInteger, nullable=False, server_default="0")
    amostras_canal_39 = Column(SmallInteger, nullable=False, server_default="0")
    sequencia_pet_primeira = Column(Integer)
    sequencia_pet_ultima = Column(Integer)
    bateria_pet = Column(SmallInteger)

    # telemetria da âncora naquele superquadro
    profundidade = Column(SmallInteger, nullable=False)
    endereco_mac_pai = Column(_MAC)
    rssi_espnow_pai_dbm = Column(SmallInteger)
    vizinhos_ativos = Column(SmallInteger, nullable=False)
    tempo_varredura_ms = Column(SmallInteger, nullable=False)
    desvio_sincronismo_us = Column(Integer, nullable=False)
    sequencia_espnow = Column(Integer, nullable=False)
    quadros_ambiente = Column(Integer, nullable=False, server_default="0")
    latencia_chegada_ms = Column(Integer)

    # configuração vigente, para o experimento de compromisso
    duracao_comunicacao_ms = Column(SmallInteger, nullable=False)

    # anotação de campanha, preenchida pelo modo de coleta
    ponto_id = Column(Text)
    sessao = Column(Text)

    __table_args__ = (
        CheckConstraint(
            "rssi_maximo_dbm IS NULL OR rssi_maximo_dbm BETWEEN -110 AND 0", name="rssi_plausivel"
        ),
        CheckConstraint(
            "rssi_maximo_dbm IS NULL OR rssi_medio_dbm IS NULL OR rssi_maximo_dbm >= rssi_medio_dbm",
            name="ordem_dos_agregados",
        ),
        CheckConstraint(
            "amostras_total = amostras_canal_37 + amostras_canal_38 + amostras_canal_39",
            name="amostras_somam_os_canais",
        ),
        CheckConstraint("(pet_id IS NULL) = (amostras_total = 0)", name="silencio_sem_pet"),
        CheckConstraint(
            "tempo_varredura_ms BETWEEN 0 AND 2000", name="varredura_dentro_do_superquadro"
        ),
        CheckConstraint("profundidade BETWEEN 1 AND 32", name="profundidade_valida"),
        UniqueConstraint(
            "numero_superquadro",
            "endereco_mac_ancora",
            "pet_id",
            name="medida_unica",
            postgresql_nulls_not_distinct=True,
        ),
    )
