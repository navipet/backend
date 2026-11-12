from geoalchemy2.shape import to_shape
from shapely.geometry import Point
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Alerta, Pet, ZonaSegura
from app.services.regras_alerta import (
    ABRIR,
    RESOLVER,
    atualizar_contador_dentro,
    atualizar_contador_fora,
    decidir_acao_alerta,
)

TIPO_FORA_DA_ZONA = "fora_da_zona"


def obter_zona_atual(db: Session, pet_id: int) -> ZonaSegura | None:
    """ultima zona segura calculada para o pet (ou None se ainda nao houver)"""
    return (
        db.query(ZonaSegura)
        .filter(ZonaSegura.pet_id == pet_id)
        .order_by(ZonaSegura.criada_em.desc())
        .first()
    )


def ha_alerta_aberto(db: Session, pet_id: int) -> bool:
    """True se o pet tem um alerta de 'fora da zona' ainda nao resolvido"""
    return (
        db.query(Alerta)
        .filter(
            Alerta.pet_id == pet_id,
            Alerta.tipo == TIPO_FORA_DA_ZONA,
            Alerta.resolvido.is_(False),
        )
        .first()
        is not None
    )


def avaliar_posicao(
    db: Session,
    pet_id: int,
    latitude: float,
    longitude: float,
    nova_leitura: bool = True,
) -> bool | None:
    """
    avalia se uma posicao esta dentro da zona segura atual do pet e
    atualiza os alertas de acordo: abre um alerta quando o pet fica fora
    por `settings.alerta_leituras_consecutivas` leituras seguidas (filtro
    de persistencia) e o resolve quando ele fica dentro por
    `settings.alerta_leituras_para_fechar` leituras seguidas (histerese)

    `nova_leitura=False` reavalia sem mexer no contador -- usado pelo
    endpoint de status, que reavalia sempre a mesma ultima leitura e nao
    pode conta-la de novo a cada chamada

    retorna True (dentro), False (fora) ou None (o pet ainda nao tem zona
    calculada, entao nao ha o que avaliar)
    """
    zona = obter_zona_atual(db, pet_id)
    if zona is None:
        return None

    dentro = bool(to_shape(zona.geom).covers(Point(longitude, latitude)))

    pet = db.get(Pet, pet_id)
    if nova_leitura:
        pet.leituras_fora_consecutivas = atualizar_contador_fora(
            dentro, pet.leituras_fora_consecutivas or 0
        )
        pet.leituras_dentro_consecutivas = atualizar_contador_dentro(
            dentro, pet.leituras_dentro_consecutivas or 0
        )

    alerta_aberto = (
        db.query(Alerta)
        .filter(
            Alerta.pet_id == pet_id,
            Alerta.tipo == TIPO_FORA_DA_ZONA,
            Alerta.resolvido.is_(False),
        )
        .first()
    )

    acao = decidir_acao_alerta(
        dentro,
        alerta_aberto is not None,
        leituras_fora_consecutivas=pet.leituras_fora_consecutivas,
        limiar=settings.alerta_leituras_consecutivas,
        leituras_dentro_consecutivas=pet.leituras_dentro_consecutivas or 0,
        limiar_fechar=settings.alerta_leituras_para_fechar,
    )
    if acao == ABRIR:
        db.add(
            Alerta(
                pet_id=pet_id,
                tipo=TIPO_FORA_DA_ZONA,
                mensagem=f"Pet saiu da zona segura (abordagem: {zona.abordagem})",
            )
        )
    elif acao == RESOLVER:
        alerta_aberto.resolvido = True
    db.commit()

    return dentro