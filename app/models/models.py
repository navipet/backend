from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
)
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


class Antena(Base):
    """antena fixa (ESP) usada para estimar a posição da tag do pet por RSSI.

    Cada antena busca uma única vez, ao ligar, a própria posição e os parâmetros
    de cálculo de distância (GET /antena/{mac}).
    """

    __tablename__ = "antenas"

    # MAC normalizado em maiúsculas: AA:BB:CC:DD:EE:FF
    endereco_mac = Column(String(17), primary_key=True)
    codigo_epsg = Column(Integer, nullable=False)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altura_elipsoidal_m = Column(Float, nullable=False)

    # incerteza da posição da antena no plano local (leste/norte), em m²
    variancia_leste_m2 = Column(Float, nullable=False)
    variancia_norte_m2 = Column(Float, nullable=False)
    covariancia_leste_norte_m2 = Column(Float, nullable=False)

    # modelo de propagação (log-distância com sombreamento)
    potencia_referencia_1m_dbm = Column(Float, nullable=False)
    expoente_perda_percurso = Column(Float, nullable=False)
    desvio_sombreamento_los_db = Column(Float, nullable=False)
    fator_inflacao_dispersao = Column(Float, nullable=False)
    limiar_rssi_dbm = Column(SmallInteger, nullable=False)

    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_antenas_latitude_valida"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_antenas_longitude_valida"),
        CheckConstraint(
            "variancia_leste_m2 > 0 AND variancia_norte_m2 > 0",
            name="ck_antenas_variancias_positivas",
        ),
        CheckConstraint(
            "variancia_leste_m2 * variancia_norte_m2 >= "
            "covariancia_leste_norte_m2 * covariancia_leste_norte_m2",
            name="ck_antenas_covariancia_semidefinida_positiva",
        ),
        CheckConstraint(
            "expoente_perda_percurso BETWEEN 1.5 AND 6.0", name="ck_antenas_expoente_plausivel"
        ),
        CheckConstraint("desvio_sombreamento_los_db > 0", name="ck_antenas_desvio_positivo"),
        CheckConstraint("limiar_rssi_dbm < 0", name="ck_antenas_limiar_negativo"),
    )