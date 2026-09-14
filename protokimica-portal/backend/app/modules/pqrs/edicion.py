"""
Corregir los datos de una PQRS ya radicada: los del cliente, los de la
factura y los archivos que adjuntó.

El cliente escribe con prisa y desde el celular: el correo con una letra de
más, el teléfono con un dígito cambiado, la foto de la factura equivocada.
Hasta ahora nada de eso se podía arreglar, y un correo mal escrito no es un
detalle — es el cliente que nunca recibe la solución ni la encuesta.

**Qué se corrige aquí y qué no.** Cada dato que ya tiene su propio camino se
queda en él, porque ese camino existe por algo:

- El **tipo** se reclasifica (`PATCH /tipo`): recalcula el plazo y exige motivo.
- El **producto** se confirma contra el catálogo (`PATCH /producto`): escrito a
  mano volvería a ensuciar el informe por producto.
- El **canal** no se toca: de él salió el prefijo del radicado, y cambiarlo
  dejaría un `PVG0010` diciendo que entró por Belén.
- La **descripción** tampoco: es lo que el cliente dijo, con sus palabras, y es
  lo que se audita. Una aclaración va como comentario en la gestión.

**Todo queda en el historial**, con el valor anterior y el nuevo. Corregir un
dato no puede ser una forma silenciosa de cambiar lo que el cliente radicó.

Nada de esto se permite con la PQRS cerrada: ya entró a los indicadores y a la
encuesta, igual que con el tipo y el producto.
"""
from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.pqrs import PQRSSeguimiento, PQRSSolicitud
from app.models.user import User

# Los datos que se pueden corregir, con cómo se nombran en el historial.
# El orden es el de la pantalla, así el comentario se lee en el mismo orden.
CAMPOS_EDITABLES = {
    "empresa": "Empresa / persona",
    "nit_cedula": "NIT / cédula",
    "cliente_nombre": "Contacto",
    "cliente_email": "Correo",
    "cliente_telefono": "Teléfono",
    "ciudad": "Ciudad",
    "departamento": "Departamento",
    "presentacion": "Presentación",
    "cantidad_presentacion": "Cantidad de la presentación",
    "lote": "Lote",
    "factura_numero": "N.° de factura",
    "cantidad_factura": "Cantidad en factura",
    "cantidad_reclamo": "Cantidad en reclamo",
}

# Los tres archivos que adjunta el cliente al radicar: columna, cómo se
# nombra, carpeta y si es video (que tiene sus propios límites).
ADJUNTOS = {
    "producto": {"columna": "adjunto_producto", "nombre": "Foto del producto",
                 "carpeta": "productos", "video": False},
    "factura":  {"columna": "adjunto_factura", "nombre": "Factura",
                 "carpeta": "facturas", "video": False},
    "video":    {"columna": "adjunto_video", "nombre": "Video de evidencia",
                 "carpeta": "videos", "video": True},
}


def _no_cerrada(solicitud: PQRSSolicitud) -> None:
    if solicitud.estado == "cerrado":
        raise HTTPException(
            status_code=400,
            detail=(
                "No se pueden corregir los datos de una PQRS cerrada: ya entró "
                "a los indicadores. Si de verdad hay que corregirla, reábrela "
                "primero cambiando su estado."
            ),
        )


def _limpio(valor):
    """Un texto de puros espacios es un campo vacío, no un dato."""
    if valor is None:
        return None
    valor = str(valor).strip()
    return valor or None


def _mostrar(valor) -> str:
    return f"«{valor}»" if valor else "(vacío)"


def editar_datos(db: Session, solicitud: PQRSSolicitud, usuario: User,
                 cambios: dict) -> PQRSSolicitud:
    """
    Aplica solo los campos que llegaron y que de verdad cambiaron.

    `cambios` trae únicamente lo que la pantalla mandó: un campo ausente es
    «no lo toques», y un campo vacío es «bórralo».
    """
    _no_cerrada(solicitud)

    nuevos = {
        campo: _limpio(valor)
        for campo, valor in cambios.items()
        if campo in CAMPOS_EDITABLES
    }

    if "cliente_nombre" in nuevos and not nuevos["cliente_nombre"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "El nombre del contacto no puede quedar vacío: es a quien se "
                "le escribe. Si no lo sabes, deja el que estaba."
            ),
        )

    if nuevos.get("cliente_email"):
        try:
            nuevos["cliente_email"] = validate_email(
                nuevos["cliente_email"], check_deliverability=False,
            ).normalized
        except EmailNotValidError:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"«{nuevos['cliente_email']}» no es un correo válido. "
                    "Revísalo: a ese correo le llegan la solución y la encuesta."
                ),
            )

    diferencias = [
        (campo, getattr(solicitud, campo), valor)
        for campo, valor in nuevos.items()
        if (getattr(solicitud, campo) or None) != valor
    ]
    if not diferencias:
        raise HTTPException(
            status_code=400,
            detail="No cambiaste ningún dato. Modifica al menos un campo antes de guardar.",
        )

    for campo, _anterior, valor in diferencias:
        setattr(solicitud, campo, valor)

    # El orden de CAMPOS_EDITABLES, no el de llegada: así dos correcciones
    # iguales se leen igual en el historial.
    orden = list(CAMPOS_EDITABLES)
    diferencias.sort(key=lambda d: orden.index(d[0]))
    detalle = "; ".join(
        f"{CAMPOS_EDITABLES[campo]}: {_mostrar(anterior)} → {_mostrar(valor)}"
        for campo, anterior, valor in diferencias
    )
    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id,
        usuario_id=usuario.id,
        tipo_evento="edicion_datos",
        comentario=f"Datos corregidos. {detalle}.",
    ))
    db.commit()
    db.refresh(solicitud)
    return solicitud


def validar_adjunto(solicitud: PQRSSolicitud, campo: str) -> dict:
    """
    Todo lo que puede rechazar el cambio de un archivo, ANTES de guardarlo en
    disco: si se validara después, un rechazo dejaría un archivo huérfano en
    `/uploads` que nadie referencia.
    """
    if campo not in ADJUNTOS:
        raise HTTPException(
            status_code=404,
            detail=f"No existe el adjunto «{campo}». Usa uno de: {', '.join(ADJUNTOS)}.",
        )
    _no_cerrada(solicitud)
    return ADJUNTOS[campo]


def cambiar_adjunto(db: Session, solicitud: PQRSSolicitud, usuario: User,
                    campo: str, ruta_nueva: str | None) -> PQRSSolicitud:
    """
    Reemplaza el archivo (`ruta_nueva`) o lo quita (`None`).

    **El archivo anterior NO se borra del servidor.** Se desvincula de la
    PQRS y su ruta queda escrita en el historial. Quien lo quitó puede haberse
    equivocado de fila, y una evidencia de un reclamo borrada de verdad no se
    recupera. Lo que se intentó y no servía se descarta, no se destruye — la
    misma regla que ya siguen las OMP.
    """
    config = validar_adjunto(solicitud, campo)
    anterior = getattr(solicitud, config["columna"])

    if anterior is None and ruta_nueva is None:
        raise HTTPException(
            status_code=400,
            detail=f"La PQRS no tiene {config['nombre'].lower()} que quitar.",
        )

    setattr(solicitud, config["columna"], ruta_nueva)

    if ruta_nueva is None:
        comentario = f"Se quitó el adjunto «{config['nombre']}»."
    elif anterior is None:
        comentario = f"Se adjuntó «{config['nombre']}»."
    else:
        comentario = f"Se reemplazó el adjunto «{config['nombre']}»."
    if anterior:
        comentario += f" El archivo anterior se conserva en el servidor: {anterior}"

    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id,
        usuario_id=usuario.id,
        tipo_evento="cambio_adjunto",
        comentario=comentario,
        # El nuevo sí se enlaza: es lo que quedó vigente y se puede abrir
        # desde el historial.
        adjunto_evidencia=ruta_nueva,
    ))
    db.commit()
    db.refresh(solicitud)
    return solicitud
