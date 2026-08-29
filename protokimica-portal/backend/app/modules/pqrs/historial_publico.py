"""
El historial que ve el cliente cuando consulta su PQRS.

Regla única de este archivo: **el cliente ve el movimiento, no la
conversación interna.** Antes se le mandaba el `comentario` del seguimiento,
que es donde el área escribe sus notas de trabajo ("falta que bodega
confirme", "el cliente insiste"). Eso no le corresponde y además se lee mal.

Aquí el texto se REDACTA a partir del estado, así que siempre dice lo mismo,
en el mismo tono, sin importar quién ni cómo escribió por dentro.
"""

# Qué se le dice al cliente en cada estado. Redactado desde su lado: le
# importa qué pasó con SU solicitud, no cómo se llama el estado por dentro.
MOVIMIENTOS = {
    "recibido":   "Recibimos tu solicitud",
    "asignado":   "Tu solicitud fue asignada al área encargada",
    "en_proceso": "Estamos trabajando en tu solicitud",
    "resuelto":   "Tu solicitud fue resuelta",
    "cerrado":    "Tu solicitud fue cerrada",
}

# Rótulo para los seguimientos viejos, anteriores a que se guardara el estado.
# Es preferible a inventarse el movimiento leyendo el texto libre.
SIN_ESTADO = "Actualización de tu solicitud"

# Eventos que sí le importan al cliente. El resto de la bitácora —notas
# internas, reasignaciones, correcciones de clasificación— se queda adentro.
EVENTOS_VISIBLES = {"cambio_estado", "autorizacion_respondida"}


def texto_del_movimiento(seguimiento) -> str:
    if seguimiento.tipo_evento == "autorizacion_respondida":
        return "Se registró una autorización interna sobre tu solicitud"
    return MOVIMIENTOS.get(seguimiento.estado_nuevo or "", SIN_ESTADO)


def construir(seguimientos) -> list[dict]:
    """
    Los movimientos visibles, del más antiguo al más reciente.

    Nunca incluye `comentario` ni `adjunto_evidencia`: si algún día alguien
    los agrega aquí, vuelve el problema. Lo que el cliente debe saber se le
    escribe en el correo de cierre, no en la bitácora de trabajo.
    """
    visibles = [s for s in seguimientos if s.tipo_evento in EVENTOS_VISIBLES]
    visibles.sort(key=lambda s: (s.fecha is None, s.fecha))
    return [
        {"movimiento": texto_del_movimiento(s), "fecha": s.fecha}
        for s in visibles
    ]
