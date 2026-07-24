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

# Videos: no validamos duración en el servidor (requeriría ffmpeg/procesamiento
# adicional), así que controlamos el peso del archivo. 20MB es suficiente para
# un clip corto (~20-30 seg) en buena calidad sin dejar que la carpeta de
# uploads crezca sin control. El límite de tiempo real se sugiere en el
# frontend al momento de grabar/seleccionar el video.
EXTENSIONES_VIDEO_PERMITIDAS = {".mp4", ".mov", ".webm"}
MAX_TAMANIO_VIDEO_MB = 20


async def guardar_archivo(
    archivo: UploadFile,
    subfolder: str,
    extensiones_permitidas: set[str] | None = None,
    max_mb: int | None = None,
) -> str:
    """Guarda un archivo subido (público o interno) y retorna la ruta relativa.
    Por defecto valida como imagen/documento; pasa extensiones_permitidas y
    max_mb para validar otro tipo de archivo (ej. video)."""
    extensiones = extensiones_permitidas or EXTENSIONES_PERMITIDAS
    limite_mb = max_mb or MAX_TAMANIO_MB

    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in extensiones:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido. Usa: {', '.join(extensiones)}"
        )

    contenido = await archivo.read()
    if len(contenido) > limite_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo no puede superar {limite_mb}MB."
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


# Prefijos especiales cuando la PQRS viene de un punto de venta específico
# o de venta institucional. Para cualquier otro canal (línea telefónica,
# página web, distribuidor autorizado, etc.) se sigue usando el radicado
# general "PK-{año}-####".
PREFIJOS_POR_CANAL = {
    "Punto de venta Centro":      "PVC",
    "Punto de venta Belén":       "PVB",
    "Punto de venta Guayabal":    "PVG",
    "Punto de venta La 65":       "PV65",
    "Punto de venta Cristo Rey":  "PVCR",
    "Punto de venta Itagüí":      "PVI",
    "Venta institucional":        "VI",
}


def generar_codigo_seguimiento(pqrs_id: int, canal_atencion: str | None = None) -> str:
    """
    Genera el código de seguimiento a partir del ID real de la PQRS,
    para que el número que ve el cliente sea siempre el mismo caso que
    internamente se ve como "PQRS #<id>" — sin importar el prefijo.

    - Canal = punto de venta específico o venta institucional:
      prefijo propio sin año, ej: PVG0010 (Guayabal), VI0010.
    - Cualquier otro canal (o sin canal): PK-{año}-{id}, como siempre.
    """
    prefijo_especial = PREFIJOS_POR_CANAL.get((canal_atencion or "").strip())
    if prefijo_especial:
        return f"{prefijo_especial}{pqrs_id:04d}"

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