from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_tutor_atual
from app.core.security import criar_token_acesso, hash_senha, verificar_senha
from app.db.session import get_db
from app.models.models import Tutor
from app.models.schemas import TokenOut, TutorCreate, TutorLogin, TutorOut

router = APIRouter(prefix="/tutores", tags=["tutores"])


@router.post("", response_model=TutorOut, status_code=201)
def criar_tutor(dados: TutorCreate, db: Session = Depends(get_db)):
    """Cadastra um novo tutor -- é ele quem faz login e usa o app."""
    existente = db.query(Tutor).filter(Tutor.email == dados.email).first()
    if existente:
        raise HTTPException(400, "Já existe um tutor cadastrado com esse e-mail")

    tutor = Tutor(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
    )
    db.add(tutor)
    db.commit()
    db.refresh(tutor)
    return tutor


@router.post("/login", response_model=TokenOut)
def login(dados: TutorLogin, db: Session = Depends(get_db)):
    """Autentica o tutor e retorna um token de acesso (JWT, válido por 24h)."""
    tutor = db.query(Tutor).filter(Tutor.email == dados.email).first()
    if not tutor or not verificar_senha(dados.senha, tutor.senha_hash):
        raise HTTPException(401, "E-mail ou senha incorretos")

    token = criar_token_acesso(tutor.id)
    return TokenOut(access_token=token)


@router.get("/me", response_model=TutorOut)
def obter_tutor_logado(tutor: Tutor = Depends(get_tutor_atual)):
    """
    Retorna os dados do tutor autenticado -- útil pro frontend confirmar
    a sessão (ex: ao recarregar a página, chama isso pra saber se o token
    salvo ainda é válido e quem está logado).
    """
    return tutor