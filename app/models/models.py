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
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    latitude = Column(Numeric(11, 8, asdecimal=False), nullable=False)
    longitude = Column(Numeric(11, 8, asdecimal=False), nullable=False)
    # RSSI (dBm) medido a 1 metro da tag
    rssi_referencia = Column(SmallInteger, nullable=False)
    # expoente de perda de percurso do ambiente (~2 em espaço aberto, 3 a 4 com obstáculos)
    expoente_perda = Column(Numeric(4, 2, asdecimal=False), nullable=False)

    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_antenas_latitude_valida"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_antenas_longitude_valida"),
        CheckConstraint("rssi_referencia BETWEEN -127 AND 0", name="ck_antenas_rssi_valido"),
        CheckConstraint("expoente_perda > 0", name="ck_antenas_expoente_positivo"),
    )
