from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.utils.mac import normalizar_mac


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
    recebido_em: datetime | None = None

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


class AntenaConfig(BaseModel):
    """posição e parâmetros de uma antena (corpo do PUT)"""

    model_config = ConfigDict(from_attributes=True)

    codigo_epsg: int = Field(..., gt=0)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    altura_elipsoidal_m: float
    variancia_leste_m2: float = Field(..., gt=0)
    variancia_norte_m2: float = Field(..., gt=0)
    covariancia_leste_norte_m2: float
    potencia_referencia_1m_dbm: float
    expoente_perda_percurso: float = Field(..., ge=1.5, le=6.0)
    desvio_sombreamento_los_db: float = Field(..., gt=0)
    fator_inflacao_dispersao: float
    limiar_rssi_dbm: int = Field(..., lt=0)

    @model_validator(mode="after")
    def _covariancia_semidefinida_positiva(self):
        if self.variancia_leste_m2 * self.variancia_norte_m2 < self.covariancia_leste_norte_m2**2:
            raise ValueError(
                "covariância inválida: variancia_leste_m2 * variancia_norte_m2 "
                "deve ser >= covariancia_leste_norte_m2 ao quadrado"
            )
        return self


class AntenaCreate(AntenaConfig):
    endereco_mac: str

    @field_validator("endereco_mac")
    @classmethod
    def _normalizar_mac(cls, valor: str) -> str:
        return normalizar_mac(valor)


class AntenaOut(AntenaConfig):
    endereco_mac: str


class AntenaListaOut(BaseModel):
    antenas: list[AntenaOut]


class AntenaBootOut(AntenaConfig):
    """resposta de GET /antena/{mac}: os campos novos mais os nomes antigos
    (rssi_referencia e expoente_perda), para o firmware que já está gravado continuar lendo"""

    rssi_referencia: int
    expoente_perda: float
