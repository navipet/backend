from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class Tutor(Base):
    """Dono do pet -- quem se cadastra e faz login no app."""

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