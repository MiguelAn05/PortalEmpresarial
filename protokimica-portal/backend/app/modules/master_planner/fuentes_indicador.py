"""
Lo que el Master Planner sabe medir solo, para el módulo de Indicadores.

Indicadores las reúne de cada módulo instalado (ver `core/registro.py`).
"""
from sqlalchemy import and_, or_

from app.core.dias_habiles import contar_habiles, hoy as hoy_local
from app.core.fechas import con_zona
from app.core.fuentes import Resultado, proporcion, rango_mes
from app.core.periodos import dia_local
from app.models.master_planner import ActividadDiaria, DocumentoVersion, Proyecto, Tarea
from app.modules.master_planner import actividades as act
from app.modules.master_planner.permisos import condicion_area

# **Todas se acotan al área del indicador** (`acepta_area`). Un indicador
# de TICS que mide «avance de proyectos» tiene que medir los de TICS: antes
# promediaba los de toda la empresa, así que cinco indicadores de cinco áreas
# distintas mostraban exactamente el mismo número y ninguna área podía
# responder por el suyo. Sin área se sigue midiendo toda la empresa, que es lo
# que quiere un indicador de gerencia.
#
# Cómo se acota depende de lo que mide, y la diferencia importa:
#
# - **Lo que se PROMEDIA o se divide** (avance, cumplimiento de fechas) usa
#   `condicion_area`: los proyectos que el área lidera **y** aquellos en los
#   que participa. Es lo que espera quien filtra — si Mercadeo entró a un
#   proyecto de TICS, ese proyecto es también trabajo de Mercadeo.
# - **Lo que se SUMA o se cuenta** (presupuesto, proyectos cerrados) se
#   atribuye solo al área responsable. Repartir un proyecto de 10 millones
#   entre sus tres áreas haría que la empresa sumara 30. Es la misma regla que
#   ya sigue el resumen del Master Planner.


def _proyectos_del_area(query, area: str | None, incluir_participantes: bool):
    """Acota una consulta de proyectos al área, si hay área que aplicar."""
    if not area:
        return query
    if incluir_participantes:
        return query.filter(condicion_area(area))
    return query.filter(Proyecto.area == area)


def _tareas_del_area(query, area: str | None):
    """
    Acota una consulta de tareas (con `Proyecto` en outer join) al área: las
    de los proyectos donde participa, y las sin proyecto que son de esa área
    —su área es lo único que las ubica—.
    """
    if not area:
        return query
    return query.filter(or_(
        and_(Tarea.proyecto_id.isnot(None), condicion_area(area)),
        and_(Tarea.proyecto_id.is_(None), Tarea.area == area),
    ))


def mp_cumplimiento_fechas(db, tenant_id, anio, mes, area=None) -> Resultado:
    """
    % de tareas entregadas a tiempo, sobre las completadas en el mes. Solo
    cuentan las que tenían fecha comprometida: sin fecha no hay incumplimiento
    posible.
    """
    desde, hasta = rango_mes(anio, mes)
    query = (
        db.query(Tarea)
        .outerjoin(Proyecto, Tarea.proyecto_id == Proyecto.id)
        .filter(Tarea.tenant_id == tenant_id,
                Tarea.parent_id.is_(None),
                Tarea.fecha_completada.isnot(None),
                Tarea.fecha_completada >= desde, Tarea.fecha_completada <= hasta)
    )
    completadas = _tareas_del_area(query, area).all()
    medibles = [t for t in completadas if t.fecha_fin]
    a_tiempo = [t for t in medibles if con_zona(t.fecha_completada) <= con_zona(t.fecha_fin)]
    return proporcion(
        len(a_tiempo), len(medibles),
        f"{len(a_tiempo)} de {len(medibles)} tareas entregadas a tiempo",
    )


def mp_ejecucion_presupuestal(db, tenant_id, anio, mes, area=None) -> Resultado:
    """
    Ejecutado sobre planeado, de los proyectos activos. Es una foto del estado
    actual, no del movimiento del mes: el presupuesto no guarda en qué mes se
    ejecutó cada peso.

    Por área cuenta solo los proyectos que ESA área lidera: la plata se
    atribuye al responsable, nunca se reparte entre las participantes.
    """
    query = (
        db.query(Proyecto)
        .filter(Proyecto.tenant_id == tenant_id, Proyecto.archivado.is_(False))
    )
    proyectos = _proyectos_del_area(query, area, incluir_participantes=False).all()
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


def mp_avance_proyectos(db, tenant_id, anio, mes, area=None) -> Resultado:
    """
    Avance promedio de los proyectos en curso del área: los que lidera y
    aquellos en los que participa. Sin área, los de toda la empresa.
    """
    query = (
        db.query(Proyecto)
        .filter(Proyecto.tenant_id == tenant_id, Proyecto.archivado.is_(False),
                Proyecto.estado != "cerrado")
    )
    proyectos = _proyectos_del_area(query, area, incluir_participantes=True).all()
    if not proyectos:
        de_quien = f"de {area}" if area else "activos"
        return Resultado(valor=None, detalle=f"No hay proyectos {de_quien}")
    total = sum(p.avance_pct for p in proyectos)
    return Resultado(
        valor=round(total / len(proyectos), 2),
        numerador=total, denominador=len(proyectos),
        detalle=(f"Promedio de {len(proyectos)} proyectos en curso"
                 + (f" de {area}" if area else "")),
    )


def mp_actividades_diarias(db, tenant_id, anio, mes, area=None) -> Resultado:
    """
    % de veces que se registró lo que tocaba hacer.

    Lo que se espera de cada día NO está guardado: sale de la frecuencia de
    cada actividad (ver `master_planner/actividades.py`), y contra eso se
    cuentan los registros. Por eso el numerador y el denominador se guardan
    los dos — el acumulado del trimestre suma veces, no promedia porcentajes.

    **El mes en curso se mide hasta ayer.** Lo de hoy todavía se puede hacer;
    contarlo como incumplido pondría el indicador en rojo cada mañana.
    """
    query = db.query(ActividadDiaria).filter(ActividadDiaria.tenant_id == tenant_id)
    if area:
        query = query.filter(ActividadDiaria.area == area)

    # El «hoy» de la empresa, no el de UTC: el corte del mes en curso es
    # «hasta ayer», y con la fecha de UTC ese ayer cambia a las 7 p. m.
    desde, hasta = act.corte_del_mes(anio, mes, hoy_local())

    esperados = cumplidos = 0
    for actividad in query.all():
        conteo = act.cumplimiento(db, actividad, desde, hasta)
        esperados += conteo["esperados"]
        cumplidos += conteo["cumplidos"]

    if not esperados:
        # Sin nada que hacer no hay incumplimiento: un 0% diría que nadie
        # cumplió, y lo cierto es que no había qué cumplir.
        return Resultado(
            valor=None, numerador=0, denominador=0,
            detalle="No había actividades programadas en el periodo",
        )

    return proporcion(
        cumplidos, esperados,
        f"{cumplidos} de {esperados} veces registradas"
        + (f" en {area}" if area else ""),
    )


def mp_proyectos_cerrados(db, tenant_id, anio, mes, area=None) -> Resultado:
    desde, hasta = rango_mes(anio, mes)
    query = (
        db.query(Proyecto)
        .filter(Proyecto.tenant_id == tenant_id,
                Proyecto.fecha_fin_real.isnot(None),
                Proyecto.fecha_fin_real >= desde, Proyecto.fecha_fin_real <= hasta)
    )
    # Se cuenta al área responsable: si un proyecto contara para cada área
    # participante, sumar las áreas daría más proyectos de los que se cerraron.
    cerrados = _proyectos_del_area(query, area, incluir_participantes=False).count()
    return Resultado(valor=cerrados, detalle=f"{cerrados} proyectos cerrados en el periodo")


def _aprobaciones_del_mes(db, tenant_id, anio, mes, area) -> list[dict]:
    """
    Cada documento que recibió su última firma en el mes, con su VUELTA: las
    versiones desde la aprobación anterior de la misma tarea (si se reabrió)
    hasta esta. Las devoluciones y los días se miden sobre la vuelta, no sobre
    la vida entera de la tarea.

    Lo que se promedia o se divide incluye los proyectos donde el área
    participa, como `mp_cumplimiento_fechas`.
    """
    desde, hasta = rango_mes(anio, mes)
    query = (
        db.query(DocumentoVersion)
        .join(Tarea, DocumentoVersion.tarea_id == Tarea.id)
        .outerjoin(Proyecto, Tarea.proyecto_id == Proyecto.id)
        .filter(Tarea.tenant_id == tenant_id,
                DocumentoVersion.estado == "aprobada",
                DocumentoVersion.cerrado_en >= desde, DocumentoVersion.cerrado_en <= hasta)
    )
    aprobaciones = []
    for aprobada in _tareas_del_area(query, area).all():
        anteriores = [v.numero for v in aprobada.tarea.versiones
                      if v.estado == "aprobada" and v.numero < aprobada.numero]
        piso = max(anteriores, default=0)
        vuelta = [v for v in aprobada.tarea.versiones if piso < v.numero <= aprobada.numero]
        enviada = min((v.enviado_en for v in vuelta if v.enviado_en), default=None)
        aprobaciones.append({
            "devoluciones": sum(1 for v in vuelta for e in v.eventos if e.accion == "devuelto"),
            "dias": (contar_habiles(dia_local(con_zona(enviada)), dia_local(con_zona(aprobada.cerrado_en)))
                     if enviada else None),
        })
    return aprobaciones


def mp_documentos_sin_devolucion(db, tenant_id, anio, mes, area=None) -> Resultado:
    """
    % de los documentos aprobados en el mes que pasaron TODAS las firmas a la
    primera. Cada devolución es una vuelta más de trabajo para quien lo
    prepara y para quien ya lo había revisado.
    """
    aprobaciones = _aprobaciones_del_mes(db, tenant_id, anio, mes, area)
    if not aprobaciones:
        return Resultado(valor=None, numerador=0, denominador=0,
                         detalle="Ningún documento se aprobó en el periodo")
    limpios = sum(1 for a in aprobaciones if a["devoluciones"] == 0)
    return proporcion(
        limpios, len(aprobaciones),
        f"{limpios} de {len(aprobaciones)} documentos aprobados sin devolverse",
    )


def mp_dias_en_revision(db, tenant_id, anio, mes, area=None) -> Resultado:
    """
    Días hábiles promedio entre el primer envío a revisión y la última firma,
    de los documentos aprobados en el mes. Incluye el tiempo de corregir lo
    devuelto: es lo que de verdad tardó el documento en quedar firmado.
    """
    medidos = [a["dias"] for a in _aprobaciones_del_mes(db, tenant_id, anio, mes, area)
               if a["dias"] is not None]
    if not medidos:
        return Resultado(valor=None, numerador=0, denominador=0,
                         detalle="Ningún documento se aprobó en el periodo")
    total = sum(medidos)
    return Resultado(
        valor=round(total / len(medidos), 2),
        numerador=total, denominador=len(medidos),
        detalle=f"Promedio de {len(medidos)} documentos aprobados · días hábiles",
    )


FUENTES = {
    "mp_cumplimiento_fechas": {
        "nombre": "Cumplimiento de fechas en proyectos",
        "modulo": "Master Planner",
        "descripcion": "Tareas entregadas dentro de la fecha comprometida.",
        "formula": "(Tareas completadas a tiempo ÷ tareas completadas con fecha) × 100",
        "unidad": "porcentaje", "direccion": "arriba", "fn": mp_cumplimiento_fechas,
        "acepta_area": True,
    },
    "mp_ejecucion_presupuestal": {
        "nombre": "Ejecución presupuestal de proyectos",
        "modulo": "Master Planner",
        "descripcion": "Cuánto del presupuesto planeado se ha ejecutado.",
        "formula": "(Presupuesto ejecutado ÷ presupuesto planeado) × 100",
        "unidad": "porcentaje", "direccion": "arriba", "fn": mp_ejecucion_presupuestal,
        "acepta_area": True,
    },
    "mp_avance_proyectos": {
        "nombre": "Avance promedio de proyectos",
        "modulo": "Master Planner",
        "descripcion": "Avance promedio de los proyectos que siguen en curso.",
        "formula": "Promedio del % de avance de los proyectos activos",
        "unidad": "porcentaje", "direccion": "arriba", "fn": mp_avance_proyectos,
        "acepta_area": True,
    },
    "mp_proyectos_cerrados": {
        "nombre": "Proyectos cerrados",
        "modulo": "Master Planner",
        "descripcion": "Proyectos que se dieron por terminados en el periodo.",
        "formula": "Conteo de proyectos con fecha de cierre real dentro del mes",
        "unidad": "cantidad", "direccion": "arriba", "fn": mp_proyectos_cerrados,
        "acepta_area": True,
    },
    "mp_actividades_diarias": {
        "nombre": "Cumplimiento de actividades diarias",
        "modulo": "Master Planner",
        "descripcion": (
            "Qué tanto se registra lo que se repite: la ronda, el informe "
            "diario, la revisión semanal."
        ),
        "formula": "(Veces registradas ÷ veces que tocaba) × 100",
        "unidad": "porcentaje", "direccion": "arriba", "fn": mp_actividades_diarias,
        # Con área mide las de esa área; sin ella, las de toda la empresa.
        "acepta_area": True,
    },
    "mp_documentos_sin_devolucion": {
        "nombre": "Documentos aprobados sin devolución",
        "modulo": "Master Planner",
        "descripcion": "Documentos que pasaron todas sus firmas a la primera.",
        "formula": "(Documentos aprobados sin ninguna devolución ÷ documentos aprobados) × 100",
        "unidad": "porcentaje", "direccion": "arriba", "fn": mp_documentos_sin_devolucion,
        "acepta_area": True,
    },
    "mp_dias_en_revision": {
        "nombre": "Días en revisión de documentos",
        "modulo": "Master Planner",
        "descripcion": "Cuánto tarda un documento desde que se envía hasta su última firma.",
        "formula": "Promedio de días hábiles entre el primer envío y la aprobación final",
        "unidad": "dias", "direccion": "abajo", "fn": mp_dias_en_revision,
        "acepta_area": True,
    },
}
