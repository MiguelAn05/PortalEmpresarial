"""
La encuesta de satisfacción de PQRS, como origen de respuestas para el
módulo de Encuestas. Ver `core/origenes_encuesta.py`.
"""
from sqlalchemy.orm import Session

from app.core.origenes_encuesta import ItemVista, RespuestaVista
from app.models.pqrs import PQRSEncuesta, PQRSSolicitud


def _respuestas_de_pqrs(db: Session, tenant_id: int) -> list[RespuestaVista]:
    """
    Lee `pqrs_encuestas` tal como está. Solo las respondidas: las que se
    crean al cerrar una PQRS y nadie contestó no son datos, son pendientes.
    """
    filas = (
        db.query(PQRSEncuesta, PQRSSolicitud)
        .join(PQRSSolicitud, PQRSEncuesta.pqrs_id == PQRSSolicitud.id)
        .filter(
            PQRSSolicitud.tenant_id == tenant_id,
            PQRSEncuesta.respondida_en.isnot(None),
        )
        .all()
    )

    vistas = []
    for encuesta, solicitud in filas:
        items = [
            ItemVista("¿Quedó solucionada?", encuesta.solucionada),
            ItemVista("Calificación de la atención",
                      str(encuesta.calificacion) if encuesta.calificacion else None,
                      float(encuesta.calificacion) if encuesta.calificacion else None),
            ItemVista("Tiempo de respuesta", encuesta.calificacion_tiempo_respuesta),
            ItemVista("¿Nos recomendaría?",
                      None if encuesta.recomendaria is None else ("Sí" if encuesta.recomendaria else "No")),
        ]
        vistas.append(RespuestaVista(
            id=f"pqrs-{encuesta.id}",
            origen="pqrs",
            origen_nombre="Satisfacción PQRS",
            respondida_en=encuesta.respondida_en,
            calificacion=float(encuesta.calificacion) if encuesta.calificacion else None,
            comentario=encuesta.comentario,
            sujeto=solicitud.area_responsable,
            referencia=solicitud.codigo_seguimiento or solicitud.radicado_calidad,
            items=[i for i in items if i.valor is not None],
        ))
    return vistas


ORIGENES = {
    "pqrs": {
        "nombre": "Satisfacción PQRS",
        "descripcion": "La que responde el cliente cuando se cierra su PQRS.",
        "fn": _respuestas_de_pqrs,
    },
}
