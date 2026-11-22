import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Antena
from app.models.schemas import AntenaBootOut, AntenaConfig, AntenaCreate, AntenaListaOut, AntenaOut
from app.utils.mac import normalizar_mac

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/antena", tags=["antenas"])


def _mac_ou_422(valor: str) -> str:
    try:
        return normalizar_mac(valor)
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro))


def _antena_ou_404(db: Session, endereco_mac: str) -> Antena:
    antena = db.get(Antena, _mac_ou_422(endereco_mac))
    if antena is None:
        raise HTTPException(status_code=404, detail="Antena não encontrada")
    return antena


def _gravar(db: Session) -> None:
    """commit com tratamento: qualquer falha no banco vira erro 500 com rollback"""
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("falha ao gravar antena no banco")
        raise HTTPException(status_code=500, detail="Erro ao gravar a antena no banco de dados")


@router.post("", response_model=AntenaOut, status_code=201)
def criar_antena(dados: AntenaCreate, db: Session = Depends(get_db)):
    """cadastra uma antena; 409 se já existir uma com o mesmo MAC"""
    if db.get(Antena, dados.endereco_mac) is not None:
        raise HTTPException(status_code=409, detail="Já existe uma antena com este endereço MAC")

    antena = Antena(**dados.model_dump())
    db.add(antena)
    try:
        db.commit()
    except IntegrityError:
        # duas requisições simultâneas com o mesmo MAC: a segunda cai aqui
        db.rollback()
        if db.get(Antena, dados.endereco_mac) is not None:
            raise HTTPException(status_code=409, detail="Já existe uma antena com este endereço MAC")
        logger.exception("violação de integridade ao criar antena")
        raise HTTPException(status_code=500, detail="Erro ao gravar a antena no banco de dados")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("falha ao criar antena")
        raise HTTPException(status_code=500, detail="Erro ao gravar a antena no banco de dados")

    db.refresh(antena)
    return antena


@router.get("", response_model=AntenaListaOut)
def listar_antenas(db: Session = Depends(get_db)):
    """lista todas as antenas cadastradas"""
    antenas = db.query(Antena).order_by(Antena.endereco_mac).all()
    return {"antenas": antenas}


@router.get("/{endereco_mac}", response_model=AntenaBootOut)
def obter_antena(endereco_mac: str, db: Session = Depends(get_db)):
    """devolve posição e parâmetros de uma antena (a antena chama isto uma vez, ao ligar).
    Inclui também rssi_referencia e expoente_perda (nomes antigos) por compatibilidade."""
    antena = _antena_ou_404(db, endereco_mac)
    dados = AntenaConfig.model_validate(antena).model_dump()
    dados["rssi_referencia"] = round(antena.potencia_referencia_dbm)
    dados["expoente_perda"] = antena.expoente_perda_percurso
    return dados


@router.put("/{endereco_mac}", response_model=AntenaOut)
def atualizar_antena(endereco_mac: str, dados: AntenaConfig, db: Session = Depends(get_db)):
    """atualiza posição e parâmetros; a antena só passa a usá-los na próxima vez que ligar"""
    antena = _antena_ou_404(db, endereco_mac)
    for campo, valor in dados.model_dump().items():
        setattr(antena, campo, valor)
    _gravar(db)
    db.refresh(antena)
    return antena


@router.delete("/{endereco_mac}")
def remover_antena(endereco_mac: str, db: Session = Depends(get_db)):
    """remove uma antena"""
    antena = _antena_ou_404(db, endereco_mac)
    db.delete(antena)
    _gravar(db)
    return {"mensagem": "Antena removida"}
