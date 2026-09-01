from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações centrais da aplicação, lidas do .env"""

    database_url: str = "postgresql://geofencing:geofencing@localhost:5432/geofencing"
    environment: str = "development"

    raio_fixo_metros: float = 100.0

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Chave usada para assinar os tokens JWT de login. MUDE isso em produção
    # (defina SECRET_KEY como variável de ambiente) -- nunca deixe o valor
    # padrão em um ambiente real.
    secret_key: str = "troque-esta-chave-em-producao"

    class Config:
        env_file = ".env"

    @property
    def lista_cors_origins(self) -> list[str]:
        return [origem.strip() for origem in self.cors_origins.split(",") if origem.strip()]


settings = Settings()