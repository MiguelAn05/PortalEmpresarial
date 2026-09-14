"""
Gestionar una PQRS en un solo movimiento: mover el área, cambiar el estado,
dejar el comentario y adjuntar la evidencia.

Antes eran tres tarjetas separadas en pantalla y tres llamadas distintas a la
API. El precio lo pagaba quien atiende: para pasarle un caso a Calidad
explicando por qué, había que escribir el motivo al asignar el área y volver
a escribirlo al cambiar el estado. El historial terminaba con el mismo texto
dos veces y con dos eventos para un solo movimiento real.

**Cuando el estado cambia, el evento se sigue llamando `cambio_estado`.** De
ahí sale el historial que ve el cliente (`historial_publico.EVENTOS_VISIBLES`)
y de ahí se redacta su movimiento a partir de `estado_nuevo`. Un tipo de
evento nuevo dejaría al cliente sin ver los movimientos de su solicitud, y no
fallaría nada: simplemente no aparecerían.

Un comentario suelto, sin cambiar nada más, también es una gestión válida.
Antes había que mover el estado para poder escribir, que es como un registro
de seguimiento termina lleno de cambios de estado que nadie necesitaba.
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.areas import AREAS
from app.models.autorizacion import AutorizacionPQRS
from app.models.pqrs import (
    PQRSAdjuntoSolucion, PQRSSolicitud, PQRSSeguimiento, PQRSEncuesta,
)
from app.models.user import User
from app.modules.pqrs.permisos import (
    es_servicio_al_cliente, obtener_visible, puede_cambiar_area,
)
from app.modules.pqrs.notificaciones import (
    avisos_reasignacion, avisos_cierre, avisos_resuelta,
)
from app.modules.pqrs.service import generar_radicado_calidad

ESTADOS_VALIDOS = ("recibido", "asignado", "en_proceso", "resuelto", "cerrado")

# Cómo se nombra cada estado dentro del comentario del historial. El historial
# interno lo leen personas, no el código: "en proceso" y no "en_proceso".
ESTADO_LEGIBLE = {
    "recibido": "recibido",
    "asignado": "asignado",
    "en_proceso": "en proceso",
    "resuelto": "resuelto",
    "cerrado": "cerrado",
}


def _validar(db: Session, solicitud: PQRSSolicitud, usuario: User,
             area: str | None, estado: str | None, solucion: str | None) -> None:
    """
    Todo lo que puede impedir el guardado, ANTES de tocar la solicitud.

    Va junto y va primero a propósito: si una validación corriera después de
    haber movido el área, un rechazo por el estado dejaría la PQRS a medio
    camino, con el área ya cambiada y el estado sin cambiar.
    """
    if area is not None:
        if not puede_cambiar_area(usuario):
            raise HTTPException(
                status_code=403,
                detail=(
                    "El área la asigna Servicio al Cliente, que es quien "
                    "reparte los casos. Si este no es de tu área, escríbelo "
                    "en el comentario y ellos lo mueven."
                ),
            )
        if area not in AREAS:
            raise HTTPException(
                status_code=400,
                detail=f"'{area}' no es un área del portal. Elige una de la lista.",
            )
        if solicitud.estado == "cerrado":
            raise HTTPException(
                status_code=400,
                detail=(
                    "No se puede mover de área una PQRS cerrada. Si hay que "
                    "retomarla, cámbiale primero el estado."
                ),
            )

    if estado is None:
        return

    if estado not in ESTADOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Usa uno de: {', '.join(ESTADOS_VALIDOS)}.",
        )

    # Marcarla "resuelto" sin decir QUÉ se solucionó es la mitad del trabajo:
    # el cliente nunca se enteraba de nada más que "ya quedó", y el correo de
    # cierre solo traía la encuesta. Ahora la solución viaja con el estado, en
    # el mismo movimiento — igual que el análisis obligatorio de Indicadores.
    if estado == "resuelto" and not (solucion or "").strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "Escribe qué se le solucionó al cliente: es lo que se le va a "
                "enviar por correo pidiéndole que confirme."
            ),
        )

    if estado != "cerrado":
        return

    # Cerrar es la única transición restringida: dispara la encuesta al
    # cliente y congela la PQRS para los indicadores.
    if not es_servicio_al_cliente(usuario):
        raise HTTPException(
            status_code=403,
            detail=(
                "Solo el área de Servicio al Cliente puede cerrar una PQRS. "
                "Márcala como 'resuelto' y ellos la revisan y la cierran."
            ),
        )

    hay_pendiente = (
        db.query(AutorizacionPQRS)
        .filter(
            AutorizacionPQRS.pqrs_id == solicitud.id,
            AutorizacionPQRS.estado == "pendiente",
        )
        .first()
    )
    if hay_pendiente:
        raise HTTPException(
            status_code=400,
            detail=(
                "No se puede cerrar la PQRS: hay una autorización pendiente "
                "de respuesta."
            ),
        )

    # El cliente escribió el producto porque no lo encontró en el buscador.
    # Se corrige ANTES de cerrar, igual que el tipo: después ya no se puede,
    # y un nombre suelto vuelve inservible el informe por producto — que es
    # justo el que dice cuál da más problemas.
    if solicitud.producto_por_confirmar:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Falta confirmar el producto. El cliente escribió "
                f"«{solicitud.producto_nombre}» porque no lo encontró en el "
                "buscador. Búscalo en el catálogo y confírmalo antes de cerrar: "
                "después ya no se puede corregir y el informe por producto "
                "quedaría mal."
            ),
        )


def aplicar_gestion(
    db: Session,
    tenant_id: int,
    pqrs_id: int,
    usuario: User,
    *,
    area: str | None = None,
    estado: str | None = None,
    comentario: str | None = None,
    ruta_evidencia: str | None = None,
    solucion: str | None = None,
    rutas_adjuntos_solucion: list[str] | None = None,
) -> tuple[PQRSSolicitud, list]:
    """
    Aplica el movimiento y deja UN evento en el historial.

    Devuelve la solicitud ya guardada y los avisos que hay que mandar. Los
    avisos se ARMAN aquí —necesitan la sesión de base de datos— y se MANDAN
    después de responder, desde el router: notificar no puede tumbar la
    petición de algo que ya quedó guardado.
    """
    area = (area or "").strip() or None
    estado = (estado or "").strip() or None
    comentario = (comentario or "").strip() or None

    if not any((area, estado, comentario, ruta_evidencia)):
        raise HTTPException(
            status_code=400,
            detail=(
                "No hay nada que guardar. Cambia el área o el estado, escribe "
                "un comentario, o adjunta una evidencia."
            ),
        )

    solicitud = obtener_visible(db, tenant_id, pqrs_id, usuario)

    _validar(db, solicitud, usuario, area, estado, solucion)

    area_anterior = solicitud.area_responsable
    estado_anterior = solicitud.estado

    # Lo que de verdad cambió. Reasignar al área que ya la tenía, o repetir el
    # estado en el que ya está, no es un movimiento: si se registrara como tal,
    # el historial contaría movimientos que nunca ocurrieron.
    cambio_area = bool(area) and area != area_anterior
    cambio_estado = bool(estado) and estado != estado_anterior

    partes = []

    if cambio_area:
        solicitud.area_responsable = area
        partes.append(f"Área: {area_anterior or 'sin asignar'} -> {area}.")

        # Calidad lleva su propio consecutivo interno, distinto del código de
        # seguimiento que consulta el cliente.
        if area.strip().lower() == "calidad" and not solicitud.radicado_calidad:
            solicitud.radicado_calidad = generar_radicado_calidad(db, tenant_id)
            partes.append(f"Radicado de Calidad: {solicitud.radicado_calidad}.")

    if cambio_estado:
        solicitud.estado = estado
        partes.append(
            f"Estado: {ESTADO_LEGIBLE[estado_anterior]} -> {ESTADO_LEGIBLE[estado]}."
        )
        if estado == "cerrado":
            solicitud.fecha_cierre = datetime.now(timezone.utc)
            # La encuesta nace pendiente de respuesta; el cliente la contesta
            # desde el enlace que le llega en el correo de cierre.
            if not solicitud.encuesta:
                db.add(PQRSEncuesta(pqrs_id=solicitud.id))
        elif estado == "resuelto":
            solicitud.solucion = solucion.strip()
            solicitud.fecha_resuelto = datetime.now(timezone.utc)
            for ruta in (rutas_adjuntos_solucion or []):
                db.add(PQRSAdjuntoSolucion(pqrs_id=solicitud.id, ruta=ruta))
        elif estado_anterior == "resuelto":
            # Se reabre. El reloj de los 3 días hábiles se borra: si no, una
            # PQRS reabierta y resuelta de nuevo más tarde se cerraría sola
            # con el plazo de la primera vez, antes de que el cliente
            # llegara siquiera a ver la solución nueva.
            solicitud.fecha_resuelto = None

    # El comentario de quien gestiona va UNA vez y al final. Lo de arriba lo
    # redacta el servidor a partir de lo que cambió, así que no hay que
    # escribir "la paso a Calidad" en un campo y repetirlo en el otro.
    if comentario:
        partes.append(comentario)

    if cambio_estado:
        tipo_evento = "cambio_estado"
    elif cambio_area:
        tipo_evento = "asignacion_area"
    else:
        tipo_evento = "comentario"

    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id,
        usuario_id=usuario.id,
        tipo_evento=tipo_evento,
        comentario=" ".join(partes) or "Sin comentario.",
        adjunto_evidencia=ruta_evidencia,
        # El estado va aparte del comentario: es lo que permite redactarle al
        # cliente el movimiento sin mostrarle las notas internas.
        estado_nuevo=solicitud.estado if cambio_estado else None,
    ))
    db.commit()
    db.refresh(solicitud)

    avisos = []
    if cambio_area:
        avisos.append(avisos_reasignacion(db, tenant_id, solicitud, area))
    if cambio_estado and estado == "cerrado":
        avisos.append(avisos_cierre(solicitud))
    if cambio_estado and estado == "resuelto":
        avisos.append(avisos_resuelta(solicitud))

    return solicitud, avisos
