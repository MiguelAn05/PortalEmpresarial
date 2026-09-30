"""
Lógica de negocio de PQRS.
"""
import logging
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core import canales
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

# Cómo se nombra cada campo en el mensaje de error: quien lo lee es quien
# llenó el formulario, no quien conoce la tabla.
NOMBRES_CAMPOS = {
    "tipo": "Tipo",
    "empresa": "Empresa / persona",
    "nit_cedula": "NIT / cédula",
    "cliente_nombre": "Nombre del contacto",
    "cliente_email": "Correo",
    "cliente_telefono": "Teléfono",
    "ciudad": "Ciudad",
    "departamento": "Departamento",
    "producto_codigo": "Código de producto",
    "producto_nombre": "Nombre del producto",
    "presentacion": "Presentación",
    "cantidad_presentacion": "Cantidad de la presentación",
    "canal_atencion": "Canal de atención",
    "lote": "Lote",
    "factura_numero": "N.° de factura",
    "cantidad_factura": "Cantidad en factura",
    "cantidad_reclamo": "Cantidad en reclamo",
    "area_responsable": "Área responsable",
}


def validar_largos(campos: dict, modelo=None, prefijo: str = "") -> None:
    """
    Rechaza con un mensaje claro lo que no cabe en su columna.

    Sin esto, un texto más largo que la columna llegaba hasta el `commit` y
    Postgres respondía `value too long for type character varying(20)`: un
    500 que la pantalla mostraba como «Error al crear la PQRS», sin decir
    qué campo. Escribir «5 galones de 20 litros» en la cantidad bastaba para
    no poder radicar. Las pruebas no lo veían porque SQLite no aplica el
    largo de un VARCHAR.

    El tope se lee de la COLUMNA del modelo, no de una lista aparte: así no
    hay un segundo número que se quede atrás el día que la columna crezca.
    Va antes de guardar los adjuntos, o cada rechazo dejaría archivos
    huérfanos en /uploads.

    `modelo` es la tabla contra la que se mide (por defecto la solicitud; los
    productos pasan `PQRSProducto`), y `prefijo` antepone al mensaje de qué
    fila se trata: «Producto 2: …».
    """
    # Import local: el modelo importa de `app.core`, y este módulo lo usan
    # los routers; así no se crea un ciclo al arrancar.
    from app.models.pqrs import PQRSSolicitud

    columnas = (modelo or PQRSSolicitud).__table__.columns
    for campo, valor in campos.items():
        if not isinstance(valor, str) or campo not in columnas:
            continue
        tope = getattr(columnas[campo].type, "length", None)
        if tope and len(valor) > tope:
            nombre = NOMBRES_CAMPOS.get(campo, campo)
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{prefijo}«{nombre}» admite máximo {tope} caracteres y tiene "
                    f"{len(valor)}. Acórtalo; si necesitas explicar más, "
                    "escríbelo en la descripción."
                ),
            )


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


# Los canales y sus prefijos viven en `core/canales.py`, que es la fuente
# única y tiene su gemelo en el frontend. Aquí solo se reexporta para no
# romper lo que ya lo importaba desde este módulo.
PREFIJOS_POR_CANAL = canales.PREFIJOS_POR_CANAL


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
            "de seguimiento. Informa a un administrador con la fecha y tu nombre "
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
