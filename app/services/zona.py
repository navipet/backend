import logging

from geoalchemy2.shape import from_shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.algorithms.base import AbordagemGeofencing
from app.algorithms.convex_hull import ConvexHull
from app.algorithms.densidade import DensidadeDBSCAN
from app.algorithms.raio_fixo import RaioFixo
from app.core.config import settings
from app.models.models import Localizacao, ZonaSegura
from app.services.alertas import ha_alerta_aberto, obter_zona_atual
from app.services.regras_zona import deve_recalcular_zona

logger = logging.getLogger(__name__)

# se a abordagem escolhida falhar por falta de estrutura nos dados (ex:
# densidade sem nenhum cluster), o recalculo automatico cai para esta, que
# funciona com qualquer historico. assim o pet nunca fica sem zona
ABORDAGEM_FALLBACK = "raio_fixo"


class AbordagemDesconhecida(Exception):
    """a abordagem de zona pedida nao existe"""


def construir_algoritmo(abordagem: str) -> AbordagemGeofencing:
    if abordagem == "raio_fixo":
        return RaioFixo(raio_metros=settings.raio_fixo_metros)
    if abordagem == "convex_hull":
        return ConvexHull()
    if abordagem == "densidade":
        return DensidadeDBSCAN(
            eps_metros=settings.zona_dbscan_eps_metros,
            min_amostras=settings.zona_dbscan_min_amostras,
            max_pontos=settings.zona_max_pontos or None,
        )
    raise AbordagemDesconhecida(abordagem)


def recalcular_zona(
    db: Session, pet_id: int, abordagem: str, permitir_fallback: bool = False
) -> ZonaSegura | None:
    """
    calcula a zona segura do pet a partir de todo o histórico e a salva

    retorna a zona criada, ou None se o pet ainda não tem localizações
    levanta AbordagemDesconhecida se a abordagem não existe, e ValueError
    se a abordagem não conseguiu construir a zona com esse histórico
    (a menos que permitir_fallback esteja ligado
    """
    # só as duas colunas, em ordem cronológica (a subamostragem do DBSCAN
    # depende da ordem), sem carregar um objeto completo por leitura
    linhas = (
        db.query(Localizacao.latitude, Localizacao.longitude)
        .filter(Localizacao.pet_id == pet_id)
        .order_by(Localizacao.timestamp, Localizacao.id)
        .all()
    )
    if not linhas:
        return None

    pontos = [(lat, lon) for lat, lon in linhas]

    algoritmo = construir_algoritmo(abordagem)
    try:
        poligono = algoritmo.construir_zona(pontos)
    except ValueError:
        if not permitir_fallback or abordagem == ABORDAGEM_FALLBACK:
            raise
        logger.info(
            "Abordagem '%s' falhou para o pet %s; usando '%s'",
            abordagem,
            pet_id,
            ABORDAGEM_FALLBACK,
        )
        algoritmo = construir_algoritmo(ABORDAGEM_FALLBACK)
        poligono = algoritmo.construir_zona(pontos)

    zona = ZonaSegura(
        pet_id=pet_id,
        abordagem=algoritmo.nome,
        geom=from_shape(poligono, srid=4326),
    )
    db.add(zona)
    db.commit()
    db.refresh(zona)
    return zona


def recalcular_zona_se_necessario(db: Session, pet_id: int) -> bool:
    """
    recalculo automatico da zona (adaptacao pelo historico). chamado a
    cada localizacao recebida; so recalcula quando a regra manda

    nunca levanta excecao: a localizacao ja foi salva e uma falha aqui
    nao pode virar erro para o dispositivo que a enviou
    """
    if not settings.zona_auto_habilitada:
        return False

    try:
        total = (
            db.query(func.count(Localizacao.id))
            .filter(Localizacao.pet_id == pet_id)
            .scalar()
        )
        if not deve_recalcular_zona(
            total_pontos=total,
            tem_zona=obter_zona_atual(db, pet_id) is not None,
            ha_alerta_aberto=ha_alerta_aberto(db, pet_id),
            min_pontos=settings.zona_min_pontos,
            intervalo=settings.zona_intervalo_recalculo,
        ):
            return False

        zona = recalcular_zona(
            db, pet_id, settings.zona_abordagem_padrao, permitir_fallback=True
        )
        return zona is not None
    except Exception:
        db.rollback()
        logger.exception("Falha no recálculo automático da zona do pet %s", pet_id)
        return False