"""
Lo que las Encuestas saben medir solas, para el módulo de Indicadores.

Indicadores las reúne de cada módulo instalado (ver `core/registro.py`).
"""
from sqlalchemy.orm import Session

from app.core.fechas import con_zona
from app.core.fuentes import FuentesDinamicas, Resultado, proporcion, rango_mes
from app.models.encuestas import Plantilla, Respuesta
from app.modules.encuestas.origenes import calificacion_principal

# ── Encuestas: fuentes que no se pueden escribir de antemano ─────────────
#
# Las fuentes de los otros módulos son fijas porque lo que miden es fijo. Las
# encuestas no: se crean desde la interfaz, y una fuente por encuesta escrita
# a mano significaría tocar el código y desplegar cada vez que Calidad
# arma una encuesta nueva. Por eso estas se generan leyendo las plantillas
# que existan.
#
# La clave lleva el slug dentro ("encuesta:vendedores:promedio") para que el
# indicador siga apuntando a la misma encuesta aunque le cambien el nombre.

PREFIJO_ENCUESTA = "encuesta"


def _respuestas_encuesta_del_mes(db: Session, tenant_id: int, slug: str,
                                 anio: int, mes: int) -> list:
    desde, hasta = rango_mes(anio, mes)
    respuestas = (
        db.query(Respuesta)
        .join(Plantilla, Respuesta.plantilla_id == Plantilla.id)
        .filter(Respuesta.tenant_id == tenant_id, Plantilla.slug == slug)
        .all()
    )
    return [
        r for r in respuestas
        if r.respondida_en and desde <= con_zona(r.respondida_en) <= hasta
    ]


def _notas_del_mes(db: Session, tenant_id: int, slug: str,
                   anio: int, mes: int) -> list[float]:
    """
    Las calificaciones del mes, usando la misma regla que el módulo de
    Encuestas: el promedio de las preguntas de escala de cada respuesta.
    Se importa en vez de recalcularse para que el indicador y el panel no
    puedan dar números distintos.
    """
    notas = [
        calificacion_principal(r)
        for r in _respuestas_encuesta_del_mes(db, tenant_id, slug, anio, mes)
    ]
    return [n for n in notas if n is not None]


def encuesta_promedio(db, tenant_id, anio, mes, slug) -> Resultado:
    notas = _notas_del_mes(db, tenant_id, slug, anio, mes)
    if not notas:
        return Resultado(valor=None, detalle="Sin respuestas en el periodo")
    return Resultado(
        valor=round(sum(notas) / len(notas), 2),
        detalle=f"Promedio de {len(notas)} respuesta(s)",
    )


def encuesta_detractores(db, tenant_id, anio, mes, slug) -> Resultado:
    notas = _notas_del_mes(db, tenant_id, slug, anio, mes)
    malas = [n for n in notas if n <= 2]
    return proporcion(len(malas), len(notas),
                       f"{len(malas)} de {len(notas)} calificaron 1 o 2")


def encuesta_respuestas(db, tenant_id, anio, mes, slug) -> Resultado:
    total = len(_respuestas_encuesta_del_mes(db, tenant_id, slug, anio, mes))
    return Resultado(valor=total, detalle=f"{total} respuesta(s) en el mes")


METRICAS_ENCUESTA = {
    "promedio": {
        "sufijo": "— calificación promedio",
        "descripcion": "Calificación promedio de la encuesta, de 1 a 5.",
        "formula": "Promedio de las calificaciones recibidas en el mes",
        "unidad": "razon", "direccion": "arriba", "fn": encuesta_promedio,
    },
    "detractores": {
        "sufijo": "— clientes insatisfechos",
        "descripcion": "Porcentaje de personas que calificaron 1 o 2 de 5.",
        "formula": "(Respuestas con nota ≤ 2 ÷ respuestas calificadas) × 100",
        "unidad": "porcentaje", "direccion": "abajo", "fn": encuesta_detractores,
    },
    "respuestas": {
        "sufijo": "— respuestas recibidas",
        "descripcion": "Cuántas personas respondieron la encuesta en el mes.",
        "formula": "Conteo de respuestas con fecha dentro del mes",
        "unidad": "cantidad", "direccion": "arriba", "fn": encuesta_respuestas,
    },
}


def _partir_clave(clave: str) -> tuple[str, str] | None:
    """'encuesta:vendedores:promedio' -> ('vendedores', 'promedio')"""
    partes = clave.split(":")
    if len(partes) != 3 or partes[0] != PREFIJO_ENCUESTA:
        return None
    return partes[1], partes[2]


def _calcular(clave: str, db: Session, tenant_id: int, anio: int, mes: int) -> Resultado:
    encuesta = _partir_clave(clave)
    if not encuesta:
        raise ValueError(f"No existe la fuente automática '{clave}'.")
    slug, metrica = encuesta
    cfg = METRICAS_ENCUESTA.get(metrica)
    if not cfg:
        raise ValueError(
            f"La métrica '{metrica}' no existe. "
            f"Usa una de: {', '.join(sorted(METRICAS_ENCUESTA))}."
        )
    return cfg["fn"](db, tenant_id, anio, mes, slug)


def _listar(db: Session, tenant_id: int) -> list[dict]:
    """Tres fuentes por cada encuesta activa: promedio, insatisfechos y volumen."""
    plantillas = db.query(Plantilla).filter(
        Plantilla.tenant_id == tenant_id, Plantilla.activa.is_(True),
    ).order_by(Plantilla.nombre).all()

    salida = []
    for p in plantillas:
        for metrica, cfg in METRICAS_ENCUESTA.items():
            salida.append({
                "clave": f"{PREFIJO_ENCUESTA}:{p.slug}:{metrica}",
                "nombre": f"{p.nombre} {cfg['sufijo']}",
                "modulo": "Encuestas",
                "descripcion": cfg["descripcion"],
                "formula": cfg["formula"],
                "unidad": cfg["unidad"],
                "direccion": cfg["direccion"],
            })
    return salida


def _existe(clave: str, db: Session, tenant_id: int) -> bool:
    encuesta = _partir_clave(clave)
    if not encuesta:
        return False
    slug, metrica = encuesta
    if metrica not in METRICAS_ENCUESTA:
        return False
    return db.query(Plantilla).filter(
        Plantilla.tenant_id == tenant_id, Plantilla.slug == slug,
    ).first() is not None


FUENTES: dict = {}

DINAMICAS = FuentesDinamicas(
    prefijo=PREFIJO_ENCUESTA, listar=_listar, calcular=_calcular, existe=_existe,
)
