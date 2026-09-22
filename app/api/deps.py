import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decodificar_token
from app.db.session import get_db
from app.models.models import Tutor

bearer_scheme = HTTPBearer()


def get_tutor_atual(
    credenciais: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Tutor:
    """
    extrai e valida o tutor autenticado a partir do header
    'Authorization: Bearer <token>'. usar como Depends() em qualquer rota
    que deva exigir login.
    """
    try:
        tutor_id = decodificar_token(credenciais.credentials)
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido ou expirado")

    tutor = db.query(Tutor).filter(Tutor.id == tutor_id).first()
    if not tutor:
        raise HTTPException(401, "Tutor não encontrado")
    return tutor