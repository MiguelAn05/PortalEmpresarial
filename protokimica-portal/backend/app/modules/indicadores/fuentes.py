"""
Indicadores que el portal calcula solo, sin que nadie digite nada.

Cada fuente devuelve numerador y denominador cuando el indicador es una
proporción. Eso es lo que permite que el acumulado trimestral y anual sea
correcto: se suman los numeradores y los denominadores, no se promedian los
porcentajes de cada mes.

Para agregar una fuente nueva basta con registrarla en CATALOGO: el resto del
módulo (crear indicador, calcular, tablero) no necesita cambios.
"""
from calendar import monthrange
from datetime import datetime, timezone
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.pqrs import PQRSSolicitud, PQRSEncuesta
from app.models.master_planner import Proyecto, Tarea


@dataclass
class Resultado:
    """
    Un cálculo automático. `denominador` en 0 significa que en ese mes no hubo
    nada que medir — no es lo mismo que un cero real, y el tablero lo muestra
    como "sin datos" en vez de como un incumplimiento.
    """
    valor: float | None
    numerador: float | None = None
    denominador: float | None = None
    detalle: str | None = None


def _rango_mes(anio: int, mes: int) -> tuple[datetime, datetime]:
    ultimo_dia = monthrange(anio, mes)[1]
    return (
        datetime(anio, mes, 1, tzinfo=timezone.utc),
        datetime(anio, mes, ultimo_dia, 23, 59, 59, tzinfo=timezone.utc),
    )


def _aware(f):
    """Postgres devuelve fechas con zona y SQLite sin ella; normalizamos."""
    if f is None:
        return None
    return f if f.tzinfo else f.replace(tzinfo=timezone.utc)


def _proporcion(numerador: int, denominador: int, detalle: str) -> Resultado:
    if not denominador:
        return Resultado(valor=None, numerador=0, denominador=0, detalle="Sin datos en el periodo")
    return Resultado(
        valor=round((numerador / denominador) * 100, 2),
        numerador=numerador, denominador=denominador, detalle=detalle,
    )


# ── PQRS ──────────────────────────────────────────────────────

def _pqrs_del_mes(db: Session, tenant_id: int, anio: int, mes: int):
    desde, hasta = _rango_mes(anio, mes)
    return (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.tenant_id == tenant_id,
                PQRSSolicitud.fecha_creacion >= desde, PQRSSolicitud.fecha_creacion <= hasta)
        .all()
    )


def pqrs_recibidas(db, tenant_id, anio, mes) -> Resultado:
    total = len(_pqrs_del_mes(db, tenant_id, anio, mes))
    return Resultado(valor=total, detalle=f"{total} PQRS radicadas en el periodo")


def pqrs_reclamos(db, tenant_id, anio, mes) -> Resultado:
    reclamos = [p for p in _pqrs_del_mes(db, tenant_id, anio, mes) if p.tipo == "reclamo"]
    return Resultado(valor=len(reclamos), detalle=f"{len(reclamos)} reclamos radicados")


def pqrs_oportunidad_sla(db, tenant_id, anio, mes) -> Resultado:
    """
    % de PQRS cerradas dentro del plazo. Se mide sobre las CERRADAS en el mes,
    no sobre las radicadas: una PQRS de junio cerrada en julio cuenta el
    cumplimiento de julio, que es cuando efectivamente se atendió.
    """
    desde, hasta = _rango_mes(anio, mes)
    cerradas = (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.tenant_id == tenant_id,
                PQRSSolicitud.fecha_cierre.isnot(None),
                PQRSSolicitud.fecha_cierre >= desde, PQRSSolicitud.fecha_cierre <= hasta)
        .all()
    )
    medibles = [p for p in cerradas if p.fecha_limite_sla]
    a_tiempo = [p for p in medibles if _aware(p.fecha_cierre) <= _aware(p.fecha_limite_sla)]
    return _proporcion(
        len(a_tiempo), len(medibles),
        f"{len(a_tiempo)} de {len(medibles)} PQRS cerradas dentro del plazo",
    )


def pqrs_tiempo_cierre(db, tenant_id, anio, mes) -> Resultado:
    """Días promedio entre radicación y cierre, de lo cerrado en el mes."""
    desde, hasta = _rango_mes(anio, mes)
    cerradas = (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.tenant_id == tenant_id,
                PQRSSolicitud.fecha_cierre.isnot(None),
                PQRSSolicitud.fecha_cierre >= desde, PQRSSolicitud.fecha_cierre <= hasta)
        .all()
    )
    if not cerradas:
        return Resultado(valor=None, detalle="No se cerró ninguna PQRS en el periodo")
    dias = [
        (_aware(p.fecha_cierre) - _aware(p.fecha_creacion)).total_seconds() / 86400
        for p in cerradas if p.fecha_creacion
    ]
    if not dias:
        return Resultado(valor=None, detalle="Sin fechas suficientes para calcular")
    return Resultado(
        valor=round(sum(dias) / len(dias), 2),
        numerador=round(sum(dias), 2), denominador=len(dias),
        detalle=f"Promedio sobre {len(dias)} PQRS cerradas",
    )


def _encuestas_del_mes(db, tenant_id, anio, mes):
    desde, hasta = _rango_mes(anio, mes)
    return (
        db.query(PQRSEncuesta)
        .join(PQRSSolicitud, PQRSEncuesta.pqrs_id == PQRSSolicitud.id)
        .filter(PQRSSolicitud.tenant_id == tenant_id,
                PQRSEncuesta.respondida_en.isnot(None),
                PQRSEncuesta.respondida_en >= desde,
                PQRSEncuesta.respondida_en <= hasta)
        .all()
    )


def pqrs_satisfaccion(db, tenant_id, anio, mes) -> Resultado:
    """Calificación promedio de la atención, de 1 a 5."""
    respuestas = [e for e in _encuestas_del_mes(db, tenant_id, anio, mes) if e.calificacion]
    if not respuestas:
        return Resultado(valor=None, detalle="Sin encuestas respondidas en el periodo")
    total = sum(e.calificacion for e in respuestas)
    return Resultado(
        valor=round(total / len(respuestas), 2),
        numerador=total, denominador=len(respuestas),
        detalle=f"Promedio de {len(respuestas)} encuestas respondidas",
    )


def pqrs_solucionadas(db, tenant_id, anio, mes) -> Resultado:
    """% de clientes que dijeron que su solicitud sí quedó resuelta."""
    respuestas = [e for e in _encuestas_del_mes(db, tenant_id, anio, mes) if e.solucionada]
    resueltas = [e for e in respuestas if e.solucionada == "si"]
    return _proporcion(
        len(resueltas), len(respuestas),
        f"{len(resueltas)} de {len(respuestas)} clientes confirmaron solución",
    )


def pqrs_recomendaria(db, tenant_id, anio, mes) -> Resultado:
    respuestas = [e for e in _encuestas_del_mes(db, tenant_id, anio, mes)
                  if e.recomendaria is not None]
    positivas = [e for e in respuestas if e.recomendaria]
    return _proporcion(
        len(positivas), len(respuestas),
        f"{len(positivas)} de {len(respuestas)} clientes nos recomendarían",
    )


# ── Master Planner ────────────────────────────────────────────

def mp_cumplimiento_fechas(db, tenant_id, anio, mes) -> Resultado:
    """
    % de tareas entregadas a tiempo, sobre las completadas en el mes. Solo
    cuentan las que tenían fecha comprometida: sin fecha no hay incumplimiento
    posible.
    """
    desde, hasta = _rango_mes(anio, mes)
    completadas = (
        db.query(Tarea)
        .join(Proyecto, Tarea.proyecto_id == Proyecto.id)
        .filter(Proyecto.tenant_id == tenant_id,
                Tarea.parent_id.is_(None),
                Tarea.fecha_completada.isnot(None),
                Tarea.fecha_completada >= desde, Tarea.fecha_completada <= hasta)
        .all()
    )
    medibles = [t for t in completadas if t.fecha_fin]
    a_tiempo = [t for t in medibles if _aware(t.fecha_completada) <= _aware(t.fecha_fin)]
    return _proporcion(
        len(a_tiempo), len(medibles),
        f"{len(a_tiempo)} de {len(medibles)} tareas entregadas a tiempo",
    )


def mp_ejecucion_presupuestal(db, tenant_id, anio, mes) -> Resultado:
    """
    Ejecutado sobre planeado, de los proyectos activos. Es una foto del estado
    actual, no del movimiento del mes: el presupuesto no guarda en qué mes se
    ejecutó cada peso.
    """
    proyectos = (
        db.query(Proyecto)
        .filter(Proyecto.tenant_id == tenant_id, Proyecto.archivado.is_(False))
        .all()
    )
    planeado = sum(p.presupuesto_total for p in proyectos)
    ejecutado = sum(p.presupuesto_pagado for p in proyectos)
    if not planeado:
        return Resultado(valor=None, numerador=0, denominador=0,
                         detalle="Ningún proyecto activo tiene presupuesto cargado")
    return Resultado(
        valor=round((ejecutado / planeado) * 100, 2),
        numerador=ejecutado, denominador=planeado,
        detalle=f"{len(proyectos)} proyectos activos · foto al cierre del periodo",
    )


def mp_avance_proyectos(db, tenant_id, anio, mes) -> Resultado:
    proyectos = (
        db.query(Proyecto)
        .filter(Proyecto.tenant_id == tenant_id, Proyecto.archivado.is_(False),
                Proyecto.estado != "cerrado")
        .all()
    )
    if not proyectos:
        return Resultado(valor=None, detalle="No hay proyectos activos")
    total = sum(p.avance_pct for p in proyectos)
    return Resultado(
        valor=round(total / len(proyectos), 2),
        numerador=total, denominador=len(proyectos),
        detalle=f"Promedio de {len(proyectos)} proyectos en curso",
    )


def mp_proyectos_cerrados(db, tenant_id, anio, mes) -> Resultado:
    desde, hasta = _rango_mes(anio, mes)
    cerrados = (
        db.query(Proyecto)
        .filter(Proyecto.tenant_id == tenant_id,
                Proyecto.fecha_fin_real.isnot(None),
                Proyecto.fecha_fin_real >= desde, Proyecto.fecha_fin_real <= hasta)
        .count()
    )
    return Resultado(valor=cerrados, detalle=f"{cerrados} proyectos cerrados en el periodo")


# ── Catálogo ──────────────────────────────────────────────────
# Lo que se ofrece en el desplegable al crear un indicador automático.
# `unidad` y `direccion` son los valores por defecto sugeridos; quien crea el
# indicador puede ajustarlos.

CATALOGO = {
    "pqrs_recibidas": {
        "nombre": "PQRS recibidas",
        "modulo": "PQRS",
        "descripcion": "Cantidad de solicitudes radicadas en el periodo.",
        "formula": "Conteo de PQRS con fecha de radicación dentro del mes",
        "unidad": "cantidad", "direccion": "abajo", "fn": pqrs_recibidas,
    },
    "pqrs_reclamos": {
        "nombre": "Reclamos recibidos",
        "modulo": "PQRS",
        "descripcion": "Cantidad de PQRS de tipo reclamo radicadas en el periodo.",
        "formula": "Conteo de PQRS tipo=reclamo dentro del mes",
        "unidad": "cantidad", "direccion": "abajo", "fn": pqrs_reclamos,
    },
    "pqrs_oportunidad_sla": {
        "nombre": "Oportunidad en la respuesta de PQRS",
        "modulo": "PQRS",
        "descripcion": "Qué tanto se cierran las PQRS dentro del plazo comprometido.",
        "formula": "(PQRS cerradas dentro del SLA ÷ PQRS cerradas con SLA) × 100",
        "unidad": "porcentaje", "direccion": "arriba", "fn": pqrs_oportunidad_sla,
    },
    "pqrs_tiempo_cierre": {
        "nombre": "Tiempo promedio de cierre de PQRS",
        "modulo": "PQRS",
        "descripcion": "Días que en promedio toma cerrar una solicitud.",
        "formula": "Promedio de (fecha de cierre − fecha de radicación) en días",
        "unidad": "dias", "direccion": "abajo", "fn": pqrs_tiempo_cierre,
    },
    "pqrs_satisfaccion": {
        "nombre": "Satisfacción del cliente",
        "modulo": "PQRS",
        "descripcion": "Calificación promedio de la atención, de 1 a 5.",
        "formula": "Promedio de las calificaciones de la encuesta",
        "unidad": "razon", "direccion": "arriba", "fn": pqrs_satisfaccion,
    },
    "pqrs_solucionadas": {
        "nombre": "Solicitudes efectivamente solucionadas",
        "modulo": "PQRS",
        "descripcion": "Porcentaje de clientes que confirman que su caso quedó resuelto.",
        "formula": "(Encuestas con 'sí quedó solucionada' ÷ encuestas respondidas) × 100",
        "unidad": "porcentaje", "direccion": "arriba", "fn": pqrs_solucionadas,
    },
    "pqrs_recomendaria": {
        "nombre": "Clientes que nos recomendarían",
        "modulo": "PQRS",
        "descripcion": "Porcentaje de clientes que recomendarían la empresa tras su PQRSSolicitud.",
        "formula": "(Encuestas con 'sí recomendaría' ÷ encuestas respondidas) × 100",
        "unidad": "porcentaje", "direccion": "arriba", "fn": pqrs_recomendaria,
    },
    "mp_cumplimiento_fechas": {
        "nombre": "Cumplimiento de fechas en proyectos",
        "modulo": "Master Planner",
        "descripcion": "Tareas entregadas dentro de la fecha comprometida.",
        "formula": "(Tareas completadas a tiempo ÷ tareas completadas con fecha) × 100",
        "unidad": "porcentaje", "direccion": "arriba", "fn": mp_cumplimiento_fechas,
    },
    "mp_ejecucion_presupuestal": {
        "nombre": "Ejecución presupuestal de proyectos",
        "modulo": "Master Planner",
        "descripcion": "Cuánto del presupuesto planeado se ha ejecutado.",
        "formula": "(Presupuesto ejecutado ÷ presupuesto planeado) × 100",
        "unidad": "porcentaje", "direccion": "arriba", "fn": mp_ejecucion_presupuestal,
    },
    "mp_avance_proyectos": {
        "nombre": "Avance promedio de proyectos",
        "modulo": "Master Planner",
        "descripcion": "Avance promedio de los proyectos que siguen en curso.",
        "formula": "Promedio del % de avance de los proyectos activos",
        "unidad": "porcentaje", "direccion": "arriba", "fn": mp_avance_proyectos,
    },
    "mp_proyectos_cerrados": {
        "nombre": "Proyectos cerrados",
        "modulo": "Master Planner",
        "descripcion": "Proyectos que se dieron por terminados en el periodo.",
        "formula": "Conteo de proyectos con fecha de cierre real dentro del mes",
        "unidad": "cantidad", "direccion": "arriba", "fn": mp_proyectos_cerrados,
    },
}


def calcular(clave: str, db: Session, tenant_id: int, anio: int, mes: int) -> Resultado:
    fuente = CATALOGO.get(clave)
    if not fuente:
        raise ValueError(f"No existe la fuente automática '{clave}'.")
    return fuente["fn"](db, tenant_id, anio, mes)


def catalogo_publico() -> list[dict]:
    """El catálogo sin las funciones, para exponerlo por la API."""
    return [
        {"clave": clave, **{k: v for k, v in cfg.items() if k != "fn"}}
        for clave, cfg in CATALOGO.items()
    ]
