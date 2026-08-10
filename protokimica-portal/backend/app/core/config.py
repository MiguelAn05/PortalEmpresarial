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

    # URL pública del frontend, para armar links (ej. en correos de n8n)
    FRONTEND_URL: str = "http://localhost:5173"

    # Llave secreta para poder usar POST /auth/register (crear el primer
    # admin de un tenant nuevo). Sin esta llave, el endpoint queda cerrado.
    # Nunca se usa desde el frontend — solo se llama manualmente (ej. con
    # curl/Postman) la única vez que se crea una empresa nueva.
    REGISTER_SETUP_KEY: str = ""

    # Opcional: URL base de n8n para disparar automatizaciones. Vacío = se ignora.
    N8N_WEBHOOK_URL: str = ""

    # ── Microsoft 365 (calendario de Outlook / Teams) ────────────────────
    # Credenciales de la app registrada en Entra ID. Con los tres vacíos la
    # integración queda apagada y el portal funciona igual que siempre: es
    # un extra, nunca un requisito para operar.
    MS_TENANT_ID: str = ""
    MS_CLIENT_ID: str = ""
    MS_CLIENT_SECRET: str = ""

    # Zona horaria con la que se crean los eventos en Outlook.
    MS_ZONA_HORARIA: str = "America/Bogota"

    # Dominios de correo con los que se puede crear un usuario, separados por
    # coma. El portal es interno: si alguien entra con un correo personal no
    # tiene buzón corporativo, y de ahí en adelante nada que dependa de la
    # cuenta de la empresa (calendario, notificaciones) le funciona.
    # Vacío = se acepta cualquier dominio.
    DOMINIOS_EMAIL_PERMITIDOS: str = "protokimica.com"


    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def dominios_email_list(self) -> list[str]:
        """Los dominios ya normalizados: en minúscula y sin la arroba."""
        return [
            d.strip().lower().lstrip("@")
            for d in self.DOMINIOS_EMAIL_PERMITIDOS.split(",")
            if d.strip()
        ]


settings = Settings()
