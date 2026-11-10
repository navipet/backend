from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """configurações centrais da aplicação, lidas do .env"""

    database_url: str = "postgresql://geofencing:geofencing@localhost:5432/geofencing"
    environment: str = "development"

    raio_fixo_metros: float = 100.0

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # chave usada para assinar os tokens JWT de login. valor diferente em produção
    # (defina SECRET_KEY como variável de ambiente) -- nunca deixe o valor
    # padrão em um ambiente real
    secret_key: str = "troque-esta-chave-em-producao"

    # recalculo automatico da zona segura conforme o histórico cresce
    # cada campo pode ser sobrescrito por variável de ambiente (ex: ZONA_AUTO_HABILITADA=false desliga o recálculo automático).
    zona_auto_habilitada: bool = True
    zona_abordagem_padrao: str = "densidade"
    zona_min_pontos: int = 30
    zona_intervalo_recalculo: int = 50

    # filtro de persistencia: quantas leituras SEGUIDAS fora da zona sao
    # necessarias para abrir um alerta. com leituras a cada 2 s, 5 = ~10 s
    # de atraso. 1 = comportamento antigo (uma leitura fora ja abre)
    # (env: ALERTA_LEITURAS_CONSECUTIVAS)
    alerta_leituras_consecutivas: int = 5

    class Config:
        env_file = ".env"

    @property
    def lista_cors_origins(self) -> list[str]:
        return [origem.strip() for origem in self.cors_origins.split(",") if origem.strip()]


settings = Settings()