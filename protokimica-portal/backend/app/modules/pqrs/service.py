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
from app.core.dias_habiles import limite_en_habiles

logger = logging.getLogger("pqrs.n8n")

# Dias HABILES (lunes a viernes, sin festivos), no calendario.
# Ver app/core/dias_habiles.py.
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


def calcular_fecha_limite_sla(tipo: str, desde: datetime | None = None) -> datetime:
    """
    Fecha limite del SLA, en DIAS HABILES.

    Los 15 dias de una peticion salen de la Ley 1755 de 2015, que habla de
    dias habiles. Contarlos corridos hacia que el sistema declarara vencido
    algo que legalmente no lo estaba, y el indicador de oportunidad media
    contra un plazo equivocado.

    `desde` permite recalcular el plazo de una PQRS ya radicada tomando su
    fecha original, no la de hoy: si se reclasifica el tipo, el plazo que
    aplicaba fue siempre el del tipo correcto.
    """
    dias = SLA_DIAS_POR_TIPO.get(tipo, 10)
    return limite_en_habiles(desde or datetime.now(timezone.utc), dias)


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

    **Se busca el consecutivo MÁS ALTO, no cuántos hay.** Contar da el
    número equivocado en cuanto falta uno del medio: con VI0001 y VI0003
    en la tabla (porque alguien borró la VI0002), contar da 2 y el
    siguiente saldría VI0003 — que ya existe. Eso reventaba el `commit`
    con UniqueViolation *después* de haber guardado la solicitud, así que
    la PQRS quedaba radicada sin código y el cliente veía un error 500.
    """
    from app.models.pqrs import PQRSSolicitud  # import local para evitar ciclos

    prefijo_especial = PREFIJOS_POR_CANAL.get((canal_atencion or "").strip())
    prefijo = prefijo_especial or f"PK-{datetime.now().year}-"

    codigos = (
        db.query(PQRSSolicitud.codigo_seguimiento)
        .filter(
            PQRSSolicitud.tenant_id == tenant_id,
            PQRSSolicitud.codigo_seguimiento.isnot(None),
            PQRSSolicitud.codigo_seguimiento.like(f"{prefijo}%"),
        )
        .all()
    )

    # El máximo se calcula sobre el número, no sobre el texto: al pasar de
    # 9999 el orden alfabético pondría "10000" antes que "9999".
    mayor = 0
    for (codigo,) in codigos:
        sufijo = (codigo or "")[len(prefijo):]
        if sufijo.isdigit():
            mayor = max(mayor, int(sufijo))

    return f"{prefijo}{mayor + 1:04d}"


def asignar_codigo_seguimiento(db, solicitud, tenant_id: int, canal_atencion: str | None) -> str:
    """
    Le pone el código a una solicitud que ya está guardada, reintentando si
    otro la ganó por milímetros.

    Aunque el consecutivo se calcule bien, dos personas radicando a la vez
    leen el mismo número y la segunda choca contra el índice único. Es raro,
    pero pasa justo cuando más se usa el portal. Reintentar es la forma
    barata de resolverlo: al recalcular ya ve el código de la otra.

    Es importante que la solicitud YA esté guardada antes de llamar aquí: el
    `rollback` de un intento fallido deshace solo el UPDATE del código, no
    la radicación.
    """
    from sqlalchemy.exc import IntegrityError

    for intento in range(1, INTENTOS_CODIGO + 1):
        solicitud.codigo_seguimiento = generar_codigo_seguimiento(db, tenant_id, canal_atencion)
        try:
            db.commit()
            db.refresh(solicitud)
            return solicitud.codigo_seguimiento
        except IntegrityError:
            db.rollback()
            db.refresh(solicitud)
            logger.warning(
                "El código %s ya estaba tomado (intento %s de %s); se recalcula.",
                solicitud.codigo_seguimiento, intento, INTENTOS_CODIGO,
            )

    # Con cinco intentos fallidos no es una carrera: algo más está mal.
    logger.error(
        "No se pudo asignar código de seguimiento a la PQRS %s tras %s intentos.",
        solicitud.id, INTENTOS_CODIGO,
    )
    raise HTTPException(
        status_code=500,
        detail=(
            "La solicitud quedó registrada pero no se le pudo asignar el código "
            "de seguimiento. Avísale a un administrador con la fecha y tu nombre "
            "para que te lo entregue; no vuelvas a enviar el formulario."
        ),
    )


# Cinco intentos: si dos personas radican en el mismo milisegundo basta con
# uno más, y si fallan los cinco el problema no es la concurrencia.
INTENTOS_CODIGO = 5


def generar_radicado_calidad(db, tenant_id: int) -> str:
    """
    Genera un consecutivo independiente para el área de Calidad,
    distinto al número de radicado general del cliente.
    Formato: CAL-{año}-{consecutivo con 4 dígitos}.

    **Sale del MÁXIMO, no de un count()** — el mismo error que ya costó
    caro en `generar_codigo_seguimiento`: con CAL-2026-0001 y CAL-2026-0003
    en la tabla (alguien borró la del medio), contar da 2 y el siguiente
    saldría CAL-2026-0003, que ya existe. Como la columna es única, eso
    revienta el commit DESPUÉS de guardar la solicitud, y la PQRS queda
    radicada sin número.
    """
    from app.models.pqrs import PQRSSolicitud  # import local para evitar ciclos

    año = datetime.now().year
    prefijo = f"CAL-{año}-"
    radicados = (
        db.query(PQRSSolicitud.radicado_calidad)
        .filter(
            PQRSSolicitud.tenant_id == tenant_id,
            PQRSSolicitud.radicado_calidad.isnot(None),
            PQRSSolicitud.radicado_calidad.like(f"{prefijo}%"),
        )
        .all()
    )

    # El máximo se calcula sobre el número y no sobre el texto: al pasar de
    # 9999, el orden alfabético pondría "10000" antes que "9999".
    mayor = 0
    for (radicado,) in radicados:
        sufijo = (radicado or "")[len(prefijo):]
        if sufijo.isdigit():
            mayor = max(mayor, int(sufijo))

    return f"{prefijo}{mayor + 1:04d}"


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

    Ese "nunca lanza" hay que sostenerlo con `except Exception` y no con
    `except httpx.HTTPError`: `httpx.InvalidURL` NO hereda de HTTPError, así
    que un `N8N_WEBHOOK_URL` con un salto de línea o un tabulador invisible
    —cosa de un `.env` mal pegado— se escapaba y tumbaba la petición DESPUÉS
    del commit. El cliente veía "error 500" y la PQRS quedaba radicada igual:
    el peor de los dos mundos, porque volvía a enviarla y quedaba duplicada.
    """
    # Se limpia lo que trae un `.env` escrito a mano: espacios, un salto de
    # línea al final, una barra de más. Con la barra de más la URL quedaba
    # `.../webhook//evento` y n8n contesta 404 — otro "no llega el correo"
    # sin causa aparente.
    url = (getattr(settings, "N8N_WEBHOOK_URL", None) or "").strip().rstrip("/")
    if not url:
        # Sin URL no hay correo. Se dice una vez y en WARNING: el silencio
        # total es lo que hace que "no llegó el correo" tarde días en
        # diagnosticarse.
        global _aviso_n8n_sin_configurar
        if not _aviso_n8n_sin_configurar:
            _aviso_n8n_sin_configurar = True
            logger.warning(
                "N8N_WEBHOOK_URL está vacío: NO se enviará ninguna notificación "
                "por correo (evento '%s' y los siguientes). Configúralo en el .env "
                "y recrea el contenedor con `up -d` (un restart no relee el .env).",
                evento,
            )
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
    except Exception as exc:
        logger.error(
            "Fallo al llamar webhook de n8n '%s' (%s): %s: %s",
            evento, webhook_url, type(exc).__name__, exc,
        )


# Se avisa una sola vez por proceso; si no, cada PQRS ensucia el log con tres
# líneas iguales.
_aviso_n8n_sin_configurar = False