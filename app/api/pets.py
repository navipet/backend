from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point, mapping
from sqlalchemy.orm import Session

from app.algorithms.convex_hull import ConvexHull
from app.algorithms.densidade import DensidadeDBSCAN
from app.algorithms.raio_fixo import RaioFixo
from app.core.config import settings
from app.db.session import get_db
from app.models.models import Alerta, Localizacao, Pet, ZonaSegura
from app.models.schemas import (
    AlertaOut,
    LocalizacaoCreate,
    LocalizacaoOut,
    PetCreate,
    PetOut,
    StatusOut,
    ZonaSeguraOut,
)

router = APIRouter(prefix="/pets", tags=["pets"])


@router.post("", response_model=PetOut, status_code=201)
def criar_pet(dados: PetCreate, db: Session = Depends(get_db)):
    """Cadastra um novo pet vinculado a um tutor."""
    pet = Pet(nome=dados.nome, tutor_id=dados.tutor_id)
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


@router.get("", response_model=list[PetOut])
def listar_pets(tutor_id: int | None = None, db: Session = Depends(get_db)):
    """Lista pets, opcionalmente filtrando por tutor (?tutor_id=123)."""
    query = db.query(Pet)
    if tutor_id is not None:
        query = query.filter(Pet.tutor_id == tutor_id)
    return query.all()


@router.get("/{pet_id}", response_model=PetOut)
def obter_pet(pet_id: int, db: Session = Depends(get_db)):
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet:
        raise HTTPException(404, "Pet não encontrado")
    return pet


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


@router.get("/{pet_id}/historico", response_model=list[LocalizacaoOut])
def obter_historico(pet_id: int, limite: int = 500, db: Session = Depends(get_db)):
    """
    Retorna o histórico de localizações em ordem cronológica -- usado
    pelo frontend para desenhar o mapa/heatmap de trajetórias.
    """
    localizacoes = (
        db.query(Localizacao)
        .filter(Localizacao.pet_id == pet_id)
        .order_by(Localizacao.timestamp.desc())
        .limit(limite)
        .all()
    )
    return list(reversed(localizacoes))


@router.post("/{pet_id}/zona-segura/calcular", response_model=ZonaSeguraOut)
def calcular_zona_segura(
    pet_id: int, abordagem: str = "raio_fixo", db: Session = Depends(get_db)
):
    """
    Recalcula a zona segura do pet a partir do histórico de localizações,
    usando a abordagem indicada (raio_fixo, convex_hull, densidade).
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


@router.get("/{pet_id}/zona-segura", response_model=ZonaSeguraOut)
def obter_zona_segura(pet_id: int, db: Session = Depends(get_db)):
    """
    Retorna a última zona segura já calculada, sem recalcular -- usado
    pelo frontend para desenhar a zona sobre o mapa.
    """
    zona = (
        db.query(ZonaSegura)
        .filter(ZonaSegura.pet_id == pet_id)
        .order_by(ZonaSegura.criada_em.desc())
        .first()
    )
    if not zona:
        raise HTTPException(404, "Nenhuma zona segura calculada para este pet")

    poligono = to_shape(zona.geom)
    return ZonaSeguraOut(
        id=zona.id,
        pet_id=zona.pet_id,
        abordagem=zona.abordagem,
        geometria=mapping(poligono),
        criada_em=zona.criada_em,
    )


@router.get("/{pet_id}/status", response_model=StatusOut)
def verificar_status(pet_id: int, db: Session = Depends(get_db)):
    """
    Verifica se a última localização do pet está dentro da zona segura.

    Efeito colateral (mecanismo de alertas, Seção 5.1-iv do escopo): se o
    pet está fora da zona e não existe um alerta em aberto, cria um. Se
    ele está dentro e havia um alerta em aberto, marca como resolvido
    automaticamente (o pet "voltou" para a zona segura).
    """
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

    alerta_aberto = (
        db.query(Alerta)
        .filter(
            Alerta.pet_id == pet_id,
            Alerta.tipo == "fora_da_zona",
            Alerta.resolvido.is_(False),
        )
        .first()
    )

    if not dentro and not alerta_aberto:
        novo_alerta = Alerta(
            pet_id=pet_id,
            tipo="fora_da_zona",
            mensagem=f"Pet saiu da zona segura (abordagem: {zona.abordagem})",
        )
        db.add(novo_alerta)
        db.commit()
    elif dentro and alerta_aberto:
        alerta_aberto.resolvido = True
        db.commit()

    return StatusOut(
        pet_id=pet_id,
        dentro_da_zona=dentro,
        abordagem_utilizada=zona.abordagem,
    )


@router.get("/{pet_id}/alertas", response_model=list[AlertaOut])
def listar_alertas(
    pet_id: int, apenas_nao_resolvidos: bool = False, db: Session = Depends(get_db)
):
    """Lista o histórico de alertas do pet (mais recentes primeiro)."""
    query = db.query(Alerta).filter(Alerta.pet_id == pet_id)
    if apenas_nao_resolvidos:
        query = query.filter(Alerta.resolvido.is_(False))
    return query.order_by(Alerta.criado_em.desc()).all()