from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações centrais da aplicação, lidas do .env"""

    database_url: str = "postgresql://geofencing:geofencing@localhost:5432/geofencing"
    environment: str = "development"

    raio_fixo_metros: float = 100.0

    # Origens permitidas para CORS, separadas por vírgula. Em dev, o
    # frontend costuma rodar em portas tipo 5173 (Vite) ou 3000 (CRA).
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    class Config:
        env_file = ".env"

    @property
    def lista_cors_origins(self) -> list[str]:
        return [origem.strip() for origem in self.cors_origins.split(",") if origem.strip()]


settings = Settings()