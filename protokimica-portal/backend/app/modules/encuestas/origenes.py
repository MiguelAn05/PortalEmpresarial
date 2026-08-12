"""
De dónde salen las respuestas que muestra el módulo.

Mismo patrón que `indicadores/fuentes.py`: cada origen se registra aquí y el
resto del módulo no sabe de qué tabla vino cada respuesta. Eso es lo que
permite mostrar en una sola lista la encuesta de PQRS —que vive en su propia
tabla desde antes de que este módulo existiera— junto a las plantillas
nuevas, sin migrar nada ni tocar el flujo de PQRS.

Para agregar un origen: escribir la función que devuelve `RespuestaVista` y
registrarla en ORIGENES. Nada más del módulo cambia.
"""
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.encuestas import Plantilla, Respuesta
from app.models.pqrs import PQRSEncuesta, PQRSSolicitud

# Escala común de calificación. La encuesta de PQRS ya venía de 1 a 5, y
# forzar todo a la misma escala es lo que permite comparar y promediar entre
# encuestas distintas sin normalizar en cada consulta.
ESCALA_MAX = 5


@dataclass
class ItemVista:
    pregunta: str
    valor: str | None
    numero: float | None = None


@dataclass
class RespuestaVista:
    """Una respuesta, venga de donde venga, en la forma que el módulo pinta."""
    id: str                       # "pqrs-12" / "enc-45": único entre orígenes
    origen: str                   # clave del origen
    origen_nombre: str
    respondida_en: datetime | None
    calificacion: float | None    # 1..5, o None si esa encuesta no califica
    comentario: str | None = None
    sujeto: str | None = None     # a quién o qué califica
    referencia: str | None = None # de dónde salió (radicado, punto de venta)
    items: list[ItemVista] = field(default_factory=list)


# ── Origen: la encuesta de satisfacción de PQRS ──────────────────────────

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


# ── Origen: las plantillas del propio módulo ─────────────────────────────

def calificacion_principal(respuesta: Respuesta) -> float | None:
    """
    La nota que representa a toda la respuesta.

    Es el promedio de sus preguntas de escala. Una encuesta puede tener
    varias (atención, limpieza, tiempo de espera) y quedarse solo con la
    primera daría un número que no representa lo que la persona contestó.
    """
    numeros = [
        float(i.valor_numero) for i in respuesta.items
        if i.valor_numero is not None and i.pregunta.tipo == "escala"
    ]
    if not numeros:
        return None
    return round(sum(numeros) / len(numeros), 2)


def _comentario_principal(respuesta: Respuesta) -> str | None:
    for item in respuesta.items:
        if item.pregunta.tipo == "texto" and item.valor_texto:
            return item.valor_texto
    return None


def _respuestas_de_plantillas(db: Session, tenant_id: int) -> list[RespuestaVista]:
    respuestas = (
        db.query(Respuesta)
        .join(Plantilla, Respuesta.plantilla_id == Plantilla.id)
        .filter(Respuesta.tenant_id == tenant_id)
        .all()
    )

    vistas = []
    for r in respuestas:
        vistas.append(RespuestaVista(
            id=f"enc-{r.id}",
            origen=r.plantilla.slug,
            origen_nombre=r.plantilla.nombre,
            respondida_en=r.respondida_en,
            calificacion=calificacion_principal(r),
            comentario=_comentario_principal(r),
            sujeto=r.sujeto_nombre,
            referencia=r.sujeto_ref,
            items=[
                ItemVista(
                    pregunta=i.pregunta.texto,
                    valor=i.valor_texto if i.valor_texto is not None else (
                        str(i.valor_numero) if i.valor_numero is not None else None
                    ),
                    numero=float(i.valor_numero) if i.valor_numero is not None else None,
                )
                for i in sorted(r.items, key=lambda i: i.pregunta.orden)
            ],
        ))
    return vistas


# Los orígenes disponibles. PQRS está fijo porque es código; las plantillas
# aportan uno por cada encuesta que exista en la base.
ORIGENES = {
    "pqrs": {
        "nombre": "Satisfacción PQRS",
        "descripcion": "La que responde el cliente cuando se cierra su PQRS.",
        "fn": _respuestas_de_pqrs,
    },
    "plantillas": {
        "nombre": "Encuestas del portal",
        "descripcion": "Las creadas en este módulo.",
        "fn": _respuestas_de_plantillas,
    },
}


def todas_las_respuestas(db: Session, tenant_id: int) -> list[RespuestaVista]:
    """Todo junto, de la más reciente a la más vieja."""
    reunidas: list[RespuestaVista] = []
    for origen in ORIGENES.values():
        reunidas.extend(origen["fn"](db, tenant_id))

    # Las que no tienen fecha van al final en vez de reventar la comparación.
    return sorted(
        reunidas,
        key=lambda r: (r.respondida_en is not None, r.respondida_en),
        reverse=True,
    )
