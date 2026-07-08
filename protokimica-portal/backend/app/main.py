from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.modules.auth.router import router as auth_router
from app.modules.pqrs.router import router as pqrs_router
from app.modules.pqrs.router_public import router as pqrs_public_router
from app.modules.autorizaciones.router import router as autorizaciones_router
from app.models import tenant, user, pqrs, autorizacion  # noqa: F401

app = FastAPI(
    title=settings.APP_NAME,
    description="API del Portal de Gestión Empresarial — Protokimica",
    version="0.1.0",
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