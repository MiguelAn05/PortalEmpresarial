import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles

from app.core.config import settings

# Logging global: sin esto, logger.info()/.error() de los módulos
# (ej. notificaciones a n8n) no aparecen en `docker logs` con formato
# útil. Nivel INFO en desarrollo, WARNING en producción para no llenar
# los logs de ruido — los errores (n8n caído, SMTP fallando, etc.)
# siempre se ven en ambos casos porque ERROR > WARNING.
logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT != "production" else logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# Excepción: el logger de n8n queremos verlo en INFO también en
# producción — es la única forma de confirmar que un correo SÍ salió,
# no solo cuando falla.
logging.getLogger("pqrs.n8n").setLevel(logging.INFO)
from app.modules.auth.router import router as auth_router
from app.modules.pqrs.router import router as pqrs_router
from app.modules.pqrs.router_public import router as pqrs_public_router
from app.modules.autorizaciones.router import router as autorizaciones_router
from app.modules.master_planner.router import router as master_planner_router
from app.modules.indicadores.router import router as indicadores_router
from app.models import tenant, user, pqrs, autorizacion, master_planner, indicadores  # noqa: F401

app = FastAPI(
    title=settings.APP_NAME,
    description="API del Portal de Gestión Empresarial — Protokimica",
    version="0.1.0",
    # En producción se ocultan /docs, /redoc y el esquema OpenAPI —
    # no hace falta que estén visibles para cualquiera en internet.
    # Se activan solo si ENVIRONMENT=development (o cualquier valor
    # distinto de "production") en el backend/.env.
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    for path in schema.get("paths", {}).values():
        for method in path.values():
            if "security" in method:
                method["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir archivos subidos
os.makedirs("/app/uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="/app/uploads"), name="uploads")


@app.get("/health", tags=["Sistema"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}


# ─── Módulos ───────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(pqrs_router)
app.include_router(pqrs_public_router)
app.include_router(autorizaciones_router)
app.include_router(master_planner_router)
app.include_router(indicadores_router)