"""
Lógica de negocio de PQRS.
"""
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, UploadFile

from app.core.config import settings

logger = logging.getLogger("pqrs.n8n")

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


def generar_codigo_seguimiento(db, tenant_id: int, canal_atencion: str | None = None) -> str:
    """
    Genera el código de seguimiento con un consecutivo INDEPENDIENTE
    por prefijo (punto de venta / canal), no un ID global compartido.

    Antes se usaba el ID autoincremental de toda la tabla, por lo que
    dos canales distintos "se robaban" números entre sí (ej: la
    primera PQRS de todo el sistema entraba por PVG y salía PVG0001,
    la segunda entraba por PVI y salía PVI0002 — saltándose PVI0001).
    Ahora cada prefijo lleva su propio consecutivo desde 0001, lo cual
    además es necesario para que los indicadores/reportes por punto de
    venta tengan sentido.

    - Canal = punto de venta específico o venta institucional:
      prefijo propio sin año, ej: PVG0010 (Guayabal), VI0010.
    - Cualquier otro canal (o sin canal): PK-{año}-{consecutivo}.

    Nota: los códigos ya asignados a PQRS existentes NO se recalculan
    ni se tocan — este cambio solo afecta a los que se creen de aquí
    en adelante.
    """
    from app.models.pqrs import PQRSSolicitud  # import local para evitar ciclos

    prefijo_especial = PREFIJOS_POR_CANAL.get((canal_atencion or "").strip())
    prefijo = prefijo_especial or f"PK-{datetime.now().year}-"

    total = (
        db.query(PQRSSolicitud)
        .filter(
            PQRSSolicitud.tenant_id == tenant_id,
            PQRSSolicitud.codigo_seguimiento.isnot(None),
            PQRSSolicitud.codigo_seguimiento.like(f"{prefijo}%"),
        )
        .count()
    )
    consecutivo = total + 1
    return f"{prefijo}{consecutivo:04d}"


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

    Si n8n no está configurado (N8N_WEBHOOK_URL vacío), se ignora
    silenciosamente a propósito (ej. en desarrollo sin n8n levantado).

    Cualquier otro fallo (timeout, conexión rechazada, respuesta de
    error de n8n) SE LOGUEA siempre — nunca debe fallar en silencio,
    porque el único síntoma visible es "no llegó el correo" y sin log
    no hay forma de saber por qué. Nunca lanza excepción hacia arriba:
    un fallo notificando a n8n no debe tumbar la creación/cierre de la
    PQRS, que ya se guardó en la base de datos.
    """
    url = getattr(settings, "N8N_WEBHOOK_URL", None)
    if not url:
        return

    webhook_url = f"{url}/{evento}"
    try:
        resp = httpx.post(webhook_url, json=payload, timeout=10.0)
        if resp.status_code >= 400:
            logger.error(
                "n8n respondió error en '%s' (HTTP %s): %s",
                evento, resp.status_code, resp.text[:500],
            )
        else:
            logger.info("n8n webhook '%s' disparado OK (HTTP %s)", evento, resp.status_code)
    except httpx.HTTPError as exc:
        logger.error("Fallo al llamar webhook de n8n '%s' (%s): %s", evento, webhook_url, exc)