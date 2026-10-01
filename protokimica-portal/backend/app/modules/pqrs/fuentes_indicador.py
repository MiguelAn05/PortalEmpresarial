"""
Lo que PQRS sabe medir solo, para el módulo de Indicadores.

Indicadores las reúne de cada módulo instalado (ver `core/registro.py`): si
PQRS no está, estas fuentes no aparecen y Indicadores sigue funcionando.
"""
from sqlalchemy.orm import Session

from app.core.fechas import con_zona
from app.core.fuentes import Resultado, proporcion, rango_mes
from app.models.pqrs import PQRSEncuesta, PQRSSolicitud


def _pqrs_del_mes(db: Session, tenant_id: int, anio: int, mes: int):
    desde, hasta = rango_mes(anio, mes)
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
    desde, hasta = rango_mes(anio, mes)
    cerradas = (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.tenant_id == tenant_id,
                PQRSSolicitud.fecha_cierre.isnot(None),
                PQRSSolicitud.fecha_cierre >= desde, PQRSSolicitud.fecha_cierre <= hasta)
        .all()
    )
    medibles = [p for p in cerradas if p.fecha_limite_sla]
    a_tiempo = [p for p in medibles if con_zona(p.fecha_cierre) <= con_zona(p.fecha_limite_sla)]
    return proporcion(
        len(a_tiempo), len(medibles),
        f"{len(a_tiempo)} de {len(medibles)} PQRS cerradas dentro del plazo",
    )


def pqrs_tiempo_cierre(db, tenant_id, anio, mes) -> Resultado:
    """Días promedio entre radicación y cierre, de lo cerrado en el mes."""
    desde, hasta = rango_mes(anio, mes)
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
        (con_zona(p.fecha_cierre) - con_zona(p.fecha_creacion)).total_seconds() / 86400
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
    desde, hasta = rango_mes(anio, mes)
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
    return proporcion(
        len(resueltas), len(respuestas),
        f"{len(resueltas)} de {len(respuestas)} clientes confirmaron solución",
    )


def pqrs_recomendaria(db, tenant_id, anio, mes) -> Resultado:
    respuestas = [e for e in _encuestas_del_mes(db, tenant_id, anio, mes)
                  if e.recomendaria is not None]
    positivas = [e for e in respuestas if e.recomendaria]
    return proporcion(
        len(positivas), len(respuestas),
        f"{len(positivas)} de {len(respuestas)} clientes nos recomendarían",
    )


FUENTES = {
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
    },}
