import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Antena, Medida
from app.models.schemas import MedidaCreate, MedidaListaOut, MedidaLoteOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/medida", tags=["medidas"])

# teto por requisição, para um lote gigante não segurar o servidor (e a transação)
MAX_MEDIDAS_POR_LOTE = 5000
LIMITE_PADRAO_LISTAGEM = 1000
LIMITE_MAXIMO_LISTAGEM = 5000

_INSERT_POR_DIALETO = {"postgresql": postgresql.insert, "sqlite": sqlite.insert}


@router.post("", response_model=MedidaLoteOut, status_code=201)
def registrar_medidas(
    medidas: list[MedidaCreate] = Body(..., min_length=1, max_length=MAX_MEDIDAS_POR_LOTE),
    db: Session = Depends(get_db),
):
    """grava um lote de medidas de uma vez (tudo ou nada).

    Reenviar uma medida que já existe (mesmo superquadro, âncora e pet) não é erro:
    ela é ignorada e contada em "duplicadas", para o gateway poder repetir um lote
    sem medo de duplicar dados.
    """
    macs = {m.endereco_mac_ancora for m in medidas}
    conhecidas = {
        mac for (mac,) in db.query(Antena.endereco_mac).filter(Antena.endereco_mac.in_(macs))
    }
    desconhecidas = sorted(macs - conhecidas)
    if desconhecidas:
        raise HTTPException(
            status_code=422,
            detail={"mensagem": "Âncora(s) não cadastrada(s) em /antena", "enderecos_mac": desconhecidas},
        )

    insert = _INSERT_POR_DIALETO[db.get_bind().dialect.name]
    comando = insert(Medida).on_conflict_do_nothing().returning(Medida.id)
    try:
        inseridas = len(db.execute(comando, [m.model_dump() for m in medidas]).all())
        db.commit()
    except IntegrityError:
        # ex: a âncora foi removida entre a verificação acima e o insert
        db.rollback()
        logger.exception("violação de integridade ao gravar medidas")
        raise HTTPException(status_code=422, detail="Medidas violam uma restrição do banco de dados")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("falha ao gravar medidas")
        raise HTTPException(status_code=500, detail="Erro ao gravar as medidas no banco de dados")

    return {"recebidas": len(medidas), "inseridas": inseridas, "duplicadas": len(medidas) - inseridas}


@router.get("", response_model=MedidaListaOut)
def listar_medidas(
    cursor: int | None = Query(
        None, ge=0, description="devolve medidas com id maior que este (use o proximo_cursor da página anterior)"
    ),
    limite: int = Query(LIMITE_PADRAO_LISTAGEM, ge=1, le=LIMITE_MAXIMO_LISTAGEM),
    db: Session = Depends(get_db),
):
    """lista medidas em ordem de id, paginadas por cursor"""
    consulta = db.query(Medida).order_by(Medida.id)
    if cursor is not None:
        consulta = consulta.filter(Medida.id > cursor)
    # busca uma a mais só para saber se existe próxima página
    linhas = consulta.limit(limite + 1).all()
    tem_mais = len(linhas) > limite
    medidas = linhas[:limite]

    return {
        "medidas": medidas,
        "paginacao": {
            "retornadas": len(medidas),
            "proximo_cursor": medidas[-1].id if tem_mais else None,
            "tem_mais": tem_mais,
        },
    }
