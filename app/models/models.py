from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class Pet(Base):
    __tablename__ = "pets"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    tutor_id = Column(Integer, nullable=False, index=True)

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
    """
    Alerta disparado quando o pet é detectado fora da zona segura
    (Seção 5.1, item iv do escopo: "mecanismo de disparo de alertas").

    O disparo em si (notificação push/e-mail/WebSocket) é responsabilidade
    da camada de infraestrutura/frontend (Tabela 1); este backend só
    detecta a condição e registra o alerta, disponibilizando via API.
    """

    __tablename__ = "alertas"

    id = Column(Integer, primary_key=True, index=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    tipo = Column(String, nullable=False, default="fora_da_zona")
    mensagem = Column(String, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolvido = Column(Boolean, default=False, nullable=False)

    pet = relationship("Pet", back_populates="alertas")