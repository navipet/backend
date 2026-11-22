from datetime import datetime, timezone

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

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

    @field_validator("timestamp")
    @classmethod
    def _para_utc_sem_fuso(cls, valor: datetime | None) -> datetime | None:
        # a coluna é "timestamp without time zone" em UTC (igual a recebido_em).
        # sem isto, "...T15:43:36-03:00" seria gravado como 15:43, perdendo o fuso
        if valor is None or valor.tzinfo is None:
            return valor
        return valor.astimezone(timezone.utc).replace(tzinfo=None)


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

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    potencia_referencia_dbm: float = Field(..., ge=-100, le=0)
    expoente_perda_percurso: float = Field(..., ge=1.0, le=6.0)
    desvio_sombreamento_db: float = Field(..., gt=0, lt=30)

    @model_validator(mode="after")
    def _nao_e_ilha_nula(self):
        # (0, 0) quase sempre é GPS sem fix ou campo esquecido, não uma antena no Atlântico
        if self.latitude == 0 and self.longitude == 0:
            raise ValueError("coordenada (0, 0) não é aceita: latitude e longitude zeradas")
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


# --- medidas -----------------------------------------------------------------

_INT32_MAX = 2**31 - 1
_INT16_MAX = 2**15 - 1
_INT64_MAX = 2**63 - 1
_UINT32_MAX = 2**32 - 1

# preenchidos só quando a âncora ouviu um pet; nulos no silêncio
_CAMPOS_DE_ESCUTA = (
    "rssi_maximo_dbm",
    "rssi_mediano_dbm",
    "rssi_medio_dbm",
    "sequencia_pet_primeira",
    "sequencia_pet_ultima",
)


class MedidaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # quando e de quem
    numero_superquadro: int = Field(..., ge=0, le=_INT64_MAX)
    instante_superquadro: AwareDatetime
    endereco_mac_ancora: str

    # obrigatório, mas pode ser nulo (silêncio)
    pet_id: int | None = Field(..., ge=0, le=_UINT32_MAX)

    # observação de rádio
    rssi_maximo_dbm: int | None = Field(None, ge=-110, le=0)
    rssi_mediano_dbm: float | None = Field(None, ge=-110, le=0)
    rssi_medio_dbm: float | None = Field(None, ge=-110, le=0)
    amostras_total: int = Field(..., ge=0, le=_INT16_MAX)
    amostras_canal_37: int = Field(..., ge=0, le=_INT16_MAX)
    amostras_canal_38: int = Field(..., ge=0, le=_INT16_MAX)
    amostras_canal_39: int = Field(..., ge=0, le=_INT16_MAX)
    sequencia_pet_primeira: int | None = Field(None, ge=0, le=65535)
    sequencia_pet_ultima: int | None = Field(None, ge=0, le=65535)
    bateria_pet: int | None = Field(None, ge=0, le=100)

    # telemetria da âncora
    profundidade: int = Field(..., ge=1, le=32)
    endereco_mac_pai: str | None = None
    rssi_espnow_pai_dbm: int | None = Field(None, ge=-110, le=0)
    vizinhos_ativos: int = Field(..., ge=0, le=_INT16_MAX)
    tempo_varredura_ms: int = Field(..., ge=0, le=2000)
    desvio_sincronismo_us: int = Field(..., ge=-1_000_000, le=1_000_000)
    sequencia_espnow: int = Field(..., ge=0, le=_INT32_MAX)
    quadros_ambiente: int = Field(..., ge=0, le=_INT32_MAX)
    latencia_chegada_ms: int | None = Field(None, ge=0, le=_INT32_MAX)

    # configuração vigente
    duracao_comunicacao_ms: int = Field(..., ge=1, le=1000)

    # anotação de campanha
    ponto_id: str | None = Field(None, max_length=64)
    sessao: str | None = Field(None, max_length=64)


class MedidaCreate(MedidaBase):
    @field_validator("endereco_mac_ancora", "endereco_mac_pai")
    @classmethod
    def _normalizar_mac(cls, valor: str | None) -> str | None:
        return None if valor is None else normalizar_mac(valor)

    @model_validator(mode="after")
    def _coerencia(self):
        canais = self.amostras_canal_37 + self.amostras_canal_38 + self.amostras_canal_39
        if self.amostras_total != canais:
            raise ValueError(
                f"amostras_total ({self.amostras_total}) deve ser a soma dos canais 37, 38 e 39 ({canais})"
            )

        silencio = self.pet_id is None
        if silencio != (self.amostras_total == 0):
            raise ValueError("pet_id deve ser nulo se e somente se amostras_total for 0 (silêncio)")

        preenchidos = [c for c in _CAMPOS_DE_ESCUTA if getattr(self, c) is not None]
        if silencio and preenchidos:
            raise ValueError(f"no silêncio (pet_id nulo) estes campos devem ser nulos: {preenchidos}")
        if not silencio and len(preenchidos) < len(_CAMPOS_DE_ESCUTA):
            faltando = [c for c in _CAMPOS_DE_ESCUTA if c not in preenchidos]
            raise ValueError(f"com pet_id preenchido estes campos são obrigatórios: {faltando}")

        for agregado in ("rssi_medio_dbm", "rssi_mediano_dbm"):
            valor = getattr(self, agregado)
            if self.rssi_maximo_dbm is not None and valor is not None and self.rssi_maximo_dbm < valor:
                raise ValueError(f"rssi_maximo_dbm não pode ser menor que {agregado}")
        return self


class MedidaOut(MedidaBase):
    id: int
    # o banco sempre devolve com fuso (TIMESTAMPTZ); datetime aqui só para não
    # recusar a saída de bancos sem fuso, como o SQLite dos testes
    instante_superquadro: datetime


class PaginacaoOut(BaseModel):
    retornadas: int
    proximo_cursor: int | None
    tem_mais: bool


class MedidaListaOut(BaseModel):
    medidas: list[MedidaOut]
    paginacao: PaginacaoOut


class MedidaLoteOut(BaseModel):
    recebidas: int
    inseridas: int
    duplicadas: int
