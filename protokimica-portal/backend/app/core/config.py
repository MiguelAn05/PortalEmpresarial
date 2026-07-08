"""
Configuración central de la aplicación.
Lee variables de entorno desde el archivo .env.
Cualquier módulo nuevo (indicadores, proyectos, etc.) reutiliza este mismo settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Protokimica Portal API"
    ENVIRONMENT: str = "development"

    DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379/0"

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    CORS_ORIGINS: str = "http://localhost:5173"

    # Opcional: URL base de n8n para disparar automatizaciones. Vacío = se ignora.
    N8N_WEBHOOK_URL: str = ""


    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


settings = Settings()
