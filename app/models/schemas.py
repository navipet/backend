from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class TutorCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str = Field(..., min_length=6)


class TutorOut(BaseModel):
    id: int
    nome: str
    email: str

    class Config:
        from_attributes = True


class TutorLogin(BaseModel):
    email: EmailStr
    senha: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PetCreate(BaseModel):
    nome: str
    tutor_id: int


class PetOut(BaseModel):
    id: int
    nome: str
    tutor_id: int

    class Config:
        from_attributes = True


class LocalizacaoCreate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timestamp: datetime | None = None


class LocalizacaoOut(BaseModel):
    id: int
    pet_id: int
    latitude: float
    longitude: float
    timestamp: datetime

    class Config:
        from_attributes = True


class ZonaSeguraOut(BaseModel):
    id: int
    pet_id: int
    abordagem: str
    geometria: dict
    criada_em: datetime

    class Config:
        from_attributes = True


class StatusOut(BaseModel):
    pet_id: int
    dentro_da_zona: bool
    abordagem_utilizada: str
    distancia_da_borda_metros: float | None = None


class AlertaOut(BaseModel):
    id: int
    pet_id: int
    tipo: str
    mensagem: str
    criado_em: datetime
    resolvido: bool

    class Config:
        from_attributes = True