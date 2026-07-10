"""
Lógica de negocio de PQRS.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, UploadFile

from app.core.config import settings

SLA_DIAS_POR_TIPO = {
    "peticion":   15,
    "queja":       5,
    "reclamo":     8,
    "sugerencia": 10,
}

PRIORIDAD_POR_TIPO = {
    "peticion":   "media",
    "queja":      "alta",
    "reclamo":    "alta",
    "sugerencia": "baja",
}

UPLOAD_DIR = "/app/uploads"
EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".pdf", ".webp"}
MAX_TAMANIO_MB = 10


async def guardar_archivo(archivo: UploadFile, subfolder: str) -> str:
    """Guarda un archivo subido (público o interno) y retorna la ruta relativa."""
    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido. Usa: {', '.join(EXTENSIONES_PERMITIDAS)}"
        )

    contenido = await archivo.read()
    if len(contenido) > MAX_TAMANIO_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo no puede superar {MAX_TAMANIO_MB}MB."
        )

    carpeta = os.path.join(UPLOAD_DIR, subfolder)
    os.makedirs(carpeta, exist_ok=True)

    nombre_unico = f"{uuid.uuid4().hex}{ext}"
    ruta = os.path.join(carpeta, nombre_unico)

    with open(ruta, "wb") as f:
        f.write(contenido)

    return f"/uploads/{subfolder}/{nombre_unico}"


def calcular_fecha_limite_sla(tipo: str) -> datetime:
    dias = SLA_DIAS_POR_TIPO.get(tipo, 10)
    return datetime.now(timezone.utc) + timedelta(days=dias)


def calcular_prioridad(tipo: str) -> str:
    return PRIORIDAD_POR_TIPO.get(tipo, "media")


def generar_codigo_seguimiento(pqrs_id: int) -> str:
    """
    Genera el código de seguimiento a partir del ID real de la PQRS,
    para que el número que ve el cliente (PK-2026-0010) sea siempre
    el mismo caso que internamente se ve como "PQRS #10".
    Formato: PK-{año}-{id con 4 dígitos mínimo}.
    """
    año = datetime.now().year
    return f"PK-{año}-{pqrs_id:04d}"


def generar_radicado_calidad(db, tenant_id: int) -> str:
    """
    Genera un consecutivo independiente para el área de Calidad,
    distinto al número de radicado general del cliente.
    Formato: CAL-{año}-{consecutivo con 4 dígitos}.
    """
    from app.models.pqrs import PQRSSolicitud  # import local para evitar ciclos

    año = datetime.now().year
    prefijo = f"CAL-{año}-"
    total = (
        db.query(PQRSSolicitud)
        .filter(
            PQRSSolicitud.tenant_id == tenant_id,
            PQRSSolicitud.radicado_calidad.isnot(None),
            PQRSSolicitud.radicado_calidad.like(f"{prefijo}%"),
        )
        .count()
    )
    consecutivo = total + 1
    return f"{prefijo}{consecutivo:04d}"


def disparar_webhook_n8n(evento: str, payload: dict) -> None:
    """
    Notifica a n8n para automatizaciones: email, Teams, escalamiento, etc.
    Si n8n no está configurado, se ignora silenciosamente.
    """
    url = getattr(settings, "N8N_WEBHOOK_URL", None)
    if not url:
        return

    try:
        httpx.post(f"{url}/{evento}", json=payload, timeout=3.0)
    except httpx.HTTPError:
        pass