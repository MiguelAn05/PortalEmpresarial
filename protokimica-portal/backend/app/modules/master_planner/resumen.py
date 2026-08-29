"""
Cálculo del resumen gerencial.

Todo se calcula en el servidor y se entrega ya digerido: el frontend no
debería tener que descargar todos los proyectos, todas las tareas y todo el
historial para sumar cifras. Además así el mismo número significa lo mismo
en pantalla, en un correo o en un reporte futuro.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.master_planner import Proyecto, Tarea, HistorialCambio
from app.models.user import User
from app.modules.master_planner.permisos import (
    aplicar_filtro_proyectos, puede_ver_presupuesto, condicion_area,
)

SIN_AREA = "Sin área"

# Un proyecto está "en riesgo" cuando su avance se queda por debajo del
# tiempo ya consumido. Estos son los márgenes de tolerancia en puntos
# porcentuales: hasta 10 puntos atrás se considera normal.
TOLERANCIA_VERDE = -10
TOLERANCIA_AMARILLO = -25


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _aware(f: datetime | None) -> datetime | None:
    """
    SQLite devuelve datetimes sin zona y Postgres con zona. Normalizamos a UTC
    para poder compararlos sin que reviente en uno de los dos motores.
    """
    if f is None:
        return None
    return f if f.tzinfo else f.replace(tzinfo=timezone.utc)


def _pct(parte: float, total: float) -> float:
    return round((parte / total) * 100, 1) if total else 0.0


def _plazo_consumido_pct(proyecto: Proyecto) -> float | None:
    """Qué porcentaje del tiempo planeado del proyecto ya transcurrió."""
    inicio, fin = _aware(proyecto.fecha_inicio), _aware(proyecto.fecha_fin_estimada)
    if not inicio or not fin or fin <= inicio:
        return None
    transcurrido = (_ahora() - inicio).total_seconds()
    total = (fin - inicio).total_seconds()
    return round(max(0.0, min(transcurrido / total, 2.0)) * 100, 1)


def _salud(proyecto: Proyecto, plazo_pct: float | None) -> str:
    """verde | amarillo | rojo | cerrado | sin_datos"""
    if proyecto.estado == "cerrado":
        return "cerrado"
    if plazo_pct is None:
        return "sin_datos"

    avance = proyecto.avance_pct or 0
    # Plazo vencido sin terminar es rojo sin importar el avance: la fecha
    # comprometida ya se incumplió.
    if plazo_pct >= 100 and avance < 100:
        return "rojo"

    desviacion = avance - plazo_pct
    if desviacion >= TOLERANCIA_VERDE:
        return "verde"
    if desviacion >= TOLERANCIA_AMARILLO:
        return "amarillo"
    return "rojo"


def _replanificaciones(db: Session, tenant_id: int, ids_visibles: list[int]) -> dict[int, dict]:
    """
    Cuántas veces se movió la fecha de entrega de cada proyecto y cuántos días
    se aplazó en total. Sale del historial: cada cambio de fecha_fin_estimada
    dejó registrados sus valores anterior y nuevo.
    """
    if not ids_visibles:
        return {}

    filas = (
        db.query(HistorialCambio)
        .join(Proyecto, HistorialCambio.proyecto_id == Proyecto.id)
        .filter(
            Proyecto.tenant_id == tenant_id,
            HistorialCambio.proyecto_id.in_(ids_visibles),
            HistorialCambio.entidad == "proyecto",
            HistorialCambio.campo == "fecha_fin_estimada",
        )
        .all()
    )

    resultado: dict[int, dict] = {}
    for fila in filas:
        acumulado = resultado.setdefault(fila.entidad_id, {"veces": 0, "dias": 0})
        acumulado["veces"] += 1
        # Solo cuenta como aplazamiento si había fecha antes y la nueva es
        # posterior; poner una fecha por primera vez no es replanificar, y
        # adelantarla no debe restarle días al acumulado de retraso.
        if fila.valor_anterior and fila.valor_nuevo:
            try:
                # _aware es imprescindible aquí: el historial puede tener
                # fechas con y sin zona mezcladas (Postgres las devuelve con
                # zona, SQLite sin ella), y restarlas directo revienta.
                antes = _aware(datetime.fromisoformat(fila.valor_anterior))
                despues = _aware(datetime.fromisoformat(fila.valor_nuevo))
            except ValueError:
                continue
            dias = (despues - antes).days
            if dias > 0:
                acumulado["dias"] += dias
    return resultado


def construir_resumen(
    db: Session, tenant_id: int, usuario: User, area: str | None = None,
) -> dict:
    """
    El resumen se calcula solo sobre los proyectos que `usuario` puede ver.
    Alguien de Calidad ve indicadores de Calidad; gerencia y admin, de todo.
    """
    proyectos_q = db.query(Proyecto).filter(
        Proyecto.tenant_id == tenant_id, Proyecto.archivado.is_(False),
    )
    proyectos_q = aplicar_filtro_proyectos(proyectos_q, usuario)
    if area:
        # Igual que en el listado: cuenta el área responsable y también
        # aquellas en las que el proyecto la tiene como participante.
        proyectos_q = proyectos_q.filter(condicion_area(area))
    proyectos = proyectos_q.all()
    ids_proyectos = [p.id for p in proyectos]

    tareas = []
    if ids_proyectos:
        tareas = (
            db.query(Tarea)
            .filter(Tarea.proyecto_id.in_(ids_proyectos), Tarea.parent_id.is_(None))
            .all()
        )

    ahora = _ahora()
    replan = _replanificaciones(db, tenant_id, ids_proyectos)

    # ── Tareas: abiertas, prioridad, vencidas, cumplimiento ──────
    abiertas = [t for t in tareas if t.estado != "completada"]
    alta_prioridad = [t for t in abiertas if t.prioridad in ("alta", "critica")]
    vencidas = [t for t in abiertas if _aware(t.fecha_fin) and _aware(t.fecha_fin) < ahora]

    # Cumplimiento: solo entran las tareas completadas que tenían fecha
    # comprometida y fecha real de cierre. Las cerradas antes de que
    # existiera el registro no cuentan, ni a favor ni en contra.
    medibles = [t for t in tareas
                if t.estado == "completada" and t.fecha_fin and t.fecha_completada]
    a_tiempo = [t for t in medibles if _aware(t.fecha_completada) <= _aware(t.fecha_fin)]

    # ── Presupuesto por área ─────────────────────────────────────
    # Solo entra la plata de los proyectos cuyo presupuesto el usuario tiene
    # permitido ver. Sin esto, alguien con una tarea asignada en un proyecto
    # de otra área vería aquí un total que el detalle le niega con un 403.
    presupuesto_visible = {p.id: puede_ver_presupuesto(p, usuario) for p in proyectos}
    proyectos_con_plata = [p for p in proyectos if presupuesto_visible[p.id]]

    por_area: dict[str, dict] = {}
    for p in proyectos_con_plata:
        clave = p.area or SIN_AREA
        acumulado = por_area.setdefault(clave, {
            "area": clave, "planeado": 0.0, "aprobado": 0.0,
            "ejecutado": 0.0, "pendiente": 0.0, "proyectos": 0,
        })
        acumulado["planeado"] += p.presupuesto_total
        acumulado["aprobado"] += p.presupuesto_aprobado
        acumulado["ejecutado"] += p.presupuesto_pagado
        acumulado["pendiente"] += p.presupuesto_pendiente
        acumulado["proyectos"] += 1

    total_planeado = sum(a["planeado"] for a in por_area.values())
    total_aprobado = sum(a["aprobado"] for a in por_area.values())
    total_ejecutado = sum(a["ejecutado"] for a in por_area.values())
    total_pendiente = sum(a["pendiente"] for a in por_area.values())

    presupuesto_por_area = sorted(
        (
            {
                **a,
                "disponible": a["planeado"] - a["ejecutado"],
                "ejecucion_pct": _pct(a["ejecutado"], a["planeado"]),
                # Pagado sobre lo APROBADO: es lo que de verdad se debe.
                # Lo planeado puede no aprobarse nunca.
                "pagado_pct": _pct(a["ejecutado"], a["aprobado"]),
                "participacion_pct": _pct(a["planeado"], total_planeado),
                "sobrepasado": a["ejecutado"] > a["planeado"],
            }
            for a in por_area.values()
        ),
        key=lambda a: a["planeado"], reverse=True,
    )

    # ── Estado de cada proyecto (semáforo + replanificaciones) ───
    tareas_por_proyecto: dict[int, list[Tarea]] = {}
    for t in tareas:
        tareas_por_proyecto.setdefault(t.proyecto_id, []).append(t)

    filas_proyectos = []
    for p in proyectos:
        plazo_pct = _plazo_consumido_pct(p)
        propias = tareas_por_proyecto.get(p.id, [])
        r = replan.get(p.id, {"veces": 0, "dias": 0})
        filas_proyectos.append({
            "id": p.id,
            "nombre": p.nombre,
            "area": p.area or SIN_AREA,
            "estado": p.estado,
            "lider_nombre": p.lider.nombre if p.lider else None,
            "avance_pct": p.avance_pct,
            "plazo_consumido_pct": plazo_pct,
            "salud": _salud(p, plazo_pct),
            "fecha_fin_estimada": p.fecha_fin_estimada,
            "total_tareas": len(propias),
            "tareas_vencidas": sum(
                1 for t in propias
                if t.estado != "completada" and _aware(t.fecha_fin) and _aware(t.fecha_fin) < ahora
            ),
            "replanificaciones": r["veces"],
            "dias_aplazados": r["dias"],
            # El presupuesto va en null, no en 0, cuando no se puede ver: un 0
            # se leería como "este proyecto no tiene plata asignada".
            "presupuesto_visible": presupuesto_visible[p.id],
            "planeado": p.presupuesto_total if presupuesto_visible[p.id] else None,
            "aprobado": p.presupuesto_aprobado if presupuesto_visible[p.id] else None,
            "pagado": p.presupuesto_pagado if presupuesto_visible[p.id] else None,
            "pendiente_pago": p.presupuesto_pendiente if presupuesto_visible[p.id] else None,
            "pagado_pct": p.pagado_pct if presupuesto_visible[p.id] else None,
            "items_por_aprobar": p.items_por_aprobar if presupuesto_visible[p.id] else None,
            "ejecutado": p.presupuesto_pagado if presupuesto_visible[p.id] else None,
            "ejecucion_pct": (
                _pct(p.presupuesto_pagado, p.presupuesto_total)
                if presupuesto_visible[p.id] else None
            ),
        })
    # Lo urgente primero: rojo, amarillo, y dentro de cada grupo el de peor avance.
    orden_salud = {"rojo": 0, "amarillo": 1, "sin_datos": 2, "verde": 3, "cerrado": 4}
    filas_proyectos.sort(key=lambda f: (orden_salud[f["salud"]], f["avance_pct"]))

    # ── Cumplimiento por área ────────────────────────────────────
    cumpl: dict[str, dict] = {}
    for t in tareas:
        clave = t.area or (t.proyecto.area if t.proyecto else None) or SIN_AREA
        fila = cumpl.setdefault(clave, {
            "area": clave, "a_tiempo": 0, "tarde": 0, "abiertas": 0, "vencidas": 0,
        })
        if t.estado == "completada":
            if t.fecha_fin and t.fecha_completada:
                if _aware(t.fecha_completada) <= _aware(t.fecha_fin):
                    fila["a_tiempo"] += 1
                else:
                    fila["tarde"] += 1
        else:
            fila["abiertas"] += 1
            if _aware(t.fecha_fin) and _aware(t.fecha_fin) < ahora:
                fila["vencidas"] += 1

    cumplimiento_por_area = sorted(
        (
            {**c, "cumplimiento_pct": _pct(c["a_tiempo"], c["a_tiempo"] + c["tarde"]),
             "medibles": c["a_tiempo"] + c["tarde"]}
            for c in cumpl.values()
        ),
        key=lambda c: c["abiertas"] + c["medibles"], reverse=True,
    )

    # ── Carga por responsable ────────────────────────────────────
    carga: dict[int, dict] = {}
    for t in abiertas:
        if not t.asignado_a:
            continue
        fila = carga.setdefault(t.asignado_a, {
            "usuario_id": t.asignado_a,
            "nombre": t.asignado.nombre if t.asignado else f"Usuario #{t.asignado_a}",
            "area": t.asignado.area if t.asignado else None,
            "activas": 0, "vencidas": 0, "por_vencer": 0, "alta_prioridad": 0,
        })
        fila["activas"] += 1
        fin = _aware(t.fecha_fin)
        if fin:
            dias = (fin - ahora).days
            if fin < ahora:
                fila["vencidas"] += 1
            elif dias <= 3:
                fila["por_vencer"] += 1
        if t.prioridad in ("alta", "critica"):
            fila["alta_prioridad"] += 1

    sin_asignar = sum(1 for t in abiertas if not t.asignado_a)
    carga_por_persona = sorted(carga.values(), key=lambda c: (-c["vencidas"], -c["activas"]))

    return {
        "kpis": {
            "proyectos_total": len(proyectos),
            "proyectos_en_ejecucion": sum(1 for p in proyectos if p.estado == "en_ejecucion"),
            "proyectos_en_riesgo": sum(1 for f in filas_proyectos if f["salud"] in ("rojo", "amarillo")),
            "tareas_total": len(tareas),
            "tareas_abiertas": len(abiertas),
            "tareas_alta_prioridad": len(alta_prioridad),
            "tareas_vencidas": len(vencidas),
            "tareas_sin_asignar": sin_asignar,
            "cumplimiento_pct": _pct(len(a_tiempo), len(medibles)),
            "tareas_medibles": len(medibles),
        },
        "presupuesto": {
            "planeado": total_planeado,
            "aprobado": total_aprobado,
            "ejecutado": total_ejecutado,      # = pagado, nombre conservado
            "pagado": total_ejecutado,
            "pendiente": total_pendiente,
            "disponible": total_planeado - total_ejecutado,
            "ejecucion_pct": _pct(total_ejecutado, total_planeado),
            "pagado_pct": _pct(total_ejecutado, total_aprobado),
            "por_aprobar": total_planeado - total_aprobado,
        },
        "presupuesto_por_area": presupuesto_por_area,
        "proyectos": filas_proyectos,
        "cumplimiento_por_area": cumplimiento_por_area,
        "carga_por_persona": carga_por_persona,
        # Sin aplicar el filtro de `area`: el desplegable tiene que seguir
        # ofreciendo todas las areas que el usuario puede ver, no solo la
        # que ya tiene seleccionada.
        "areas_disponibles": sorted({
            p.area
            for p in aplicar_filtro_proyectos(
                db.query(Proyecto).filter(
                    Proyecto.tenant_id == tenant_id, Proyecto.archivado.is_(False),
                ),
                usuario,
            ).all()
            if p.area
        }),
    }
