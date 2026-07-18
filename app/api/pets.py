from datetime import datetime
from app.algorithms.densidade import DensidadeDBSCAN
from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point, mapping
from sqlalchemy.orm import Session

from app.algorithms.convex_hull import ConvexHull
from app.algorithms.raio_fixo import RaioFixo
from app.core.config import settings
from app.db.session import get_db
from app.models.models import Localizacao, ZonaSegura
from app.models.schemas import (
    LocalizacaoCreate,
    LocalizacaoOut,
    StatusOut,
    ZonaSeguraOut,
)

router = APIRouter(prefix="/pets", tags=["pets"])


@router.post("/{pet_id}/localizacoes", response_model=LocalizacaoOut)
def registrar_localizacao(
    pet_id: int, dados: LocalizacaoCreate, db: Session = Depends(get_db)
):
    """Recebe uma coordenada GPS do dispositivo/simulador e a armazena."""
    ponto = Point(dados.longitude, dados.latitude)

    localizacao = Localizacao(
        pet_id=pet_id,
        latitude=dados.latitude,
        longitude=dados.longitude,
        timestamp=dados.timestamp or datetime.utcnow(),
        geom=from_shape(ponto, srid=4326),
    )
    db.add(localizacao)
    db.commit()
    db.refresh(localizacao)
    return localizacao


@router.post("/{pet_id}/zona-segura/calcular", response_model=ZonaSeguraOut)
def calcular_zona_segura(
    pet_id: int, abordagem: str = "raio_fixo", db: Session = Depends(get_db)
):
    """
    Recalcula a zona segura do pet a partir do histórico de localizações,
    usando a abordagem indicada (raio_fixo, convex_hull; densidade entra
    na próxima etapa do roadmap).
    """
    localizacoes = db.query(Localizacao).filter(Localizacao.pet_id == pet_id).all()
    if not localizacoes:
        raise HTTPException(404, "Nenhuma localização encontrada para este pet")

    pontos = [(loc.latitude, loc.longitude) for loc in localizacoes]

    if abordagem == "raio_fixo":
        algoritmo = RaioFixo(raio_metros=settings.raio_fixo_metros)
    elif abordagem == "convex_hull":
        algoritmo = ConvexHull()
    elif abordagem == "densidade":
        algoritmo = DensidadeDBSCAN()
    else:
        raise HTTPException(400, f"Abordagem '{abordagem}' ainda não implementada")

    poligono = algoritmo.construir_zona(pontos)

    zona = ZonaSegura(
        pet_id=pet_id,
        abordagem=algoritmo.nome,
        geom=from_shape(poligono, srid=4326),
    )
    db.add(zona)
    db.commit()
    db.refresh(zona)

    return ZonaSeguraOut(
        id=zona.id,
        pet_id=zona.pet_id,
        abordagem=zona.abordagem,
        geometria=mapping(poligono),
        criada_em=zona.criada_em,
    )


@router.get("/{pet_id}/status", response_model=StatusOut)
def verificar_status(pet_id: int, db: Session = Depends(get_db)):
    """Verifica se a última localização do pet está dentro da zona segura."""
    ultima_localizacao = (
        db.query(Localizacao)
        .filter(Localizacao.pet_id == pet_id)
        .order_by(Localizacao.timestamp.desc())
        .first()
    )
    if not ultima_localizacao:
        raise HTTPException(404, "Nenhuma localização encontrada para este pet")

    zona = (
        db.query(ZonaSegura)
        .filter(ZonaSegura.pet_id == pet_id)
        .order_by(ZonaSegura.criada_em.desc())
        .first()
    )
    if not zona:
        raise HTTPException(404, "Nenhuma zona segura calculada para este pet")

    poligono_zona = to_shape(zona.geom)
    ponto_atual = Point(ultima_localizacao.longitude, ultima_localizacao.latitude)
    dentro = poligono_zona.covers(ponto_atual)

    return StatusOut(
        pet_id=pet_id,
        dentro_da_zona=dentro,
        abordagem_utilizada=zona.abordagem,
    )