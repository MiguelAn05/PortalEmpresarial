"""
De dónde salen las respuestas que muestra el módulo.

Mismo patrón que `indicadores/fuentes.py`: cada módulo declara sus orígenes
en su `origen_encuesta.py` (ver `core/origenes_encuesta.py`), aquí se reúnen
con el de las plantillas propias, y el resto del módulo no sabe de qué tabla
vino cada respuesta. Eso es lo que permite mostrar en una sola lista la
encuesta de PQRS —que vive en su propia tabla desde antes de que este módulo
existiera— junto a las plantillas nuevas, sin migrar nada ni tocar el flujo
de PQRS.

Para agregar un origen: escribir en el módulo dueño de los datos la función
que devuelve `RespuestaVista` y declararla en su `ORIGENES`. Nada de este
módulo cambia.
"""
from sqlalchemy.orm import Session

from app.core import registro
from app.core.modulos import paquete_contratado
from app.models.tenant import Tenant
from app.core.origenes_encuesta import ItemVista, RespuestaVista
from app.models.encuestas import Plantilla, Respuesta


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


# El origen de las plantillas propias. Va aparte porque aporta uno por cada
# encuesta que exista en la base, no uno solo.
CLAVE_PLANTILLAS = "plantillas"


def _reunir() -> dict:
    """Los orígenes que declaran los otros módulos, y al final el propio."""
    origenes = {}
    for pieza in registro.piezas("origen_encuesta"):
        for clave, cfg in getattr(pieza, "ORIGENES", {}).items():
            assert clave not in origenes, f"El origen '{clave}' está declarado dos veces."
            origenes[clave] = {**cfg, "paquete": registro.paquete_de(pieza)}
    origenes[CLAVE_PLANTILLAS] = {
        "nombre": "Encuestas del portal",
        "descripcion": "Las creadas en este módulo.",
        "fn": _respuestas_de_plantillas,
    }
    return origenes


ORIGENES = _reunir()


def origenes_de(db: Session, tenant_id: int) -> dict:
    """Los orígenes de los módulos que esta empresa tiene contratados."""
    tenant = db.get(Tenant, tenant_id)
    return {
        clave: cfg for clave, cfg in ORIGENES.items()
        if "paquete" not in cfg or paquete_contratado(tenant, cfg["paquete"])
    }


def todas_las_respuestas(db: Session, tenant_id: int) -> list[RespuestaVista]:
    """Todo junto, de la más reciente a la más vieja."""
    reunidas: list[RespuestaVista] = []
    for origen in origenes_de(db, tenant_id).values():
        reunidas.extend(origen["fn"](db, tenant_id))

    # Las que no tienen fecha van al final en vez de reventar la comparación.
    return sorted(
        reunidas,
        key=lambda r: (r.respondida_en is not None, r.respondida_en),
        reverse=True,
    )
