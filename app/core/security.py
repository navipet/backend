from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings

ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha, senha_hash)


def criar_token_acesso(tutor_id: int, expira_em_minutos: int = 60 * 24) -> str:
    """Gera um JWT válido por 24h (padrão) contendo o id do tutor."""
    expira = datetime.now(timezone.utc) + timedelta(minutes=expira_em_minutos)
    payload = {"sub": str(tutor_id), "exp": expira}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decodificar_token(token: str) -> int:
    """Retorna o tutor_id contido no token. Levanta jwt.InvalidTokenError se inválido/expirado."""
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    return int(payload["sub"])