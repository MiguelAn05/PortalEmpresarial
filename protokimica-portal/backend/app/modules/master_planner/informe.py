"""
El informe gerencial de Master Planner de un periodo: qué se comprometió y
qué se cumplió, qué se movió de fecha, qué se cerró, cuánta plata salió, y
cómo está cada área y cada proyecto.

**Es UN informe de empresa con el área como filtro, no un informe por
área.** Los proyectos cruzan áreas: uno de TICS donde trabaja Mercadeo
saldría en dos informes o se perdería en uno. Con un solo informe la tabla
«Por área» compara a todas en la misma hoja, que es lo que pide gerencia.
Las reglas de atribución son las de siempre (ver `fuentes_indicador.py`):

- **Lo que se promedia o se juzga** (avance, riesgo, cumplimiento) cuenta
  para el área responsable Y para las participantes (`condicion_area`).
- **Lo que se suma** (plata, proyectos cerrados) cuenta solo para el área
  responsable; repartirlo inflaría los totales.

**Hay dos clases de cifras y el informe las separa.** PQRS mide lo que
ENTRÓ en un periodo; aquí además hay un estado que cambia —el avance de un
proyecto no se guarda mes a mes—, así que:

- Lo que **pasó en el periodo** sale de datos con fecha: tareas que vencían,
  entregas, aplazamientos del historial, actas de cierre, pagos, registros
  de actividades. Se compara contra el periodo anterior del mismo largo.
- Lo que es **foto de hoy** (salud, avance, lo pendiente de pago, la carga
  abierta) se rotula así. No se inventa el avance de un mes ya pasado.

**Los compromisos del periodo** son las tareas cuya fecha de entrega cae en
él. Se juzgan las que ya se pueden juzgar: entregada a tiempo, entregada
tarde, o vencida sin entregar. Las que vencen más adelante en el mismo
periodo van aparte como pendientes: el día 10 no se le cobra a nadie lo que
vence el 25. Es distinto del indicador «Cumplimiento de fechas» —ese mide
solo lo ENTREGADO en el mes, y por eso una tarea que nunca se entrega no le
baja el número—; el informe trae los dos y dice cuál es cuál.

**Cada quien ve el informe de lo que puede ver** (`aplicar_filtro_proyectos`
y `aplicar_filtro_actividades`). La tabla por persona la ve quien ve toda la
empresa, y un líder la de su gente; el presupuesto, quien ya lo ve en el
proyecto (`puede_ver_presupuesto`), y el informe dice cuántos quedaron por
fuera para que el total no se lea como el de la empresa.

Solo cuentan las tareas de primer nivel, como en el resumen y en los
indicadores: una subtarea es parte de su tarea, no otro compromiso.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core import supervision
from app.core.areas import clave_alfabetica
from app.core.dias_habiles import hoy
from app.core.fechas import con_zona
from app.core.periodos import (
    MESES, describir, dia_local, limites, periodo_anterior, resolver_periodo, serie,
)
from app.models.master_planner import (
    ESTADOS_TERMINALES, ActividadDiaria, HistorialCambio, ItemPresupuesto, Proyecto,
    Tarea, TareaActualizacion,
)
from app.models.user import User
from app.modules.master_planner import actividades as act
from app.modules.master_planner.cierre import CANCELADO, FINALIZADO
from app.modules.master_planner.permisos import (
    aplicar_filtro_actividades, aplicar_filtro_proyectos, condicion_area,
    puede_ver_presupuesto, ve_todo,
)
from app.modules.master_planner.resumen import (
    SIN_AREA, _plazo_consumido_pct, _salud,
)

SALUD = {
    "rojo": "En riesgo alto",
    "amarillo": "Atención",
    "verde": "En curso normal",
    "sin_datos": "Sin fechas para medir",
}
ESTADOS_PROYECTO = {
    "planeacion": "Planeación",
    "en_ejecucion": "En ejecución",
    "pausado": "Pausado",
}
TOP_ACTIVIDADES = 8
TOP_APLAZADOS = 8


def _pct(n: float, total: float) -> float | None:
    return round(n * 100 / total, 1) if total else None


def _variacion(actual: float | None, anterior: float | None) -> float | None:
    """La diferencia ya hecha, para que la pantalla no reste dos números."""
    if actual is None or anterior is None:
        return None
    return round(actual - anterior, 1)


def _fecha_texto(momento: datetime | date) -> str:
    d = dia_local(momento) if isinstance(momento, datetime) else momento
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _en(momento: datetime | None, ini: datetime, fin: datetime) -> bool:
    m = con_zona(momento)
    return m is not None and ini <= m < fin


def _activo(p: Proyecto) -> bool:
    return p.estado not in ESTADOS_TERMINALES and not p.archivado


def _area_de_tarea(t: Tarea) -> str:
    """La de la tarea, o la del proyecto si la tarea no dice. Igual que el resumen."""
    return t.area or (t.proyecto.area if t.proyecto else None) or SIN_AREA


# ── Compromisos: las tareas que vencían en el periodo ────────────────

def _clasificar(t: Tarea, ahora: datetime) -> str:
    """
    a_tiempo | tarde | vencida | pendiente | sin_medir

    `sin_medir` es una completada sin fecha de entrega real: se cerró antes
    de que existiera ese registro y no cuenta ni a favor ni en contra.
    """
    limite = con_zona(t.fecha_fin)
    if t.estado == "completada":
        entrega = con_zona(t.fecha_completada)
        if not entrega:
            return "sin_medir"
        return "a_tiempo" if entrega <= limite else "tarde"
    return "vencida" if limite < ahora else "pendiente"


def _contar(tareas: list[Tarea], ahora: datetime) -> dict:
    conteo = Counter(_clasificar(t, ahora) for t in tareas)
    juzgadas = conteo["a_tiempo"] + conteo["tarde"] + conteo["vencida"]
    return {
        "total": len(tareas),
        "a_tiempo": conteo["a_tiempo"],
        "tarde": conteo["tarde"],
        "vencidas": conteo["vencida"],
        "pendientes": conteo["pendiente"],
        "sin_medir": conteo["sin_medir"],
        "juzgadas": juzgadas,
        # Sobre lo que YA se puede juzgar: las que vencen más adelante en el
        # periodo no bajan el porcentaje antes de tiempo.
        "pct": _pct(conteo["a_tiempo"], juzgadas),
        # De esas, cuántas se movieron de fecha alguna vez: el cumplimiento se
        # mide contra la fecha vigente, y esto dice cuánto costó llegar a ella.
        "aplazadas": sum(1 for t in tareas if t.veces_aplazada),
    }


def _del_periodo(tareas: list[Tarea], ini: datetime, fin: datetime) -> list[Tarea]:
    return [t for t in tareas if _en(t.fecha_fin, ini, fin)]


def _entregas(tareas: list[Tarea], ini: datetime, fin: datetime) -> dict:
    """
    Lo entregado en el periodo, a tiempo o no. Es la MISMA cuenta del
    indicador `mp_cumplimiento_fechas`, para que los dos digan lo mismo.
    """
    entregadas = [t for t in tareas if t.estado == "completada" and _en(t.fecha_completada, ini, fin)]
    con_fecha = [t for t in entregadas if t.fecha_fin]
    a_tiempo = [t for t in con_fecha if con_zona(t.fecha_completada) <= con_zona(t.fecha_fin)]
    return {
        "total": len(entregadas),
        "con_fecha": len(con_fecha),
        "a_tiempo": len(a_tiempo),
        "pct": _pct(len(a_tiempo), len(con_fecha)),
    }


# ── Aplazamientos (salen del historial, no de un contador) ───────────

def _dias_movidos(fila: HistorialCambio) -> int:
    """Cuántos días se corrió la fecha hacia adelante. Adelantarla no resta."""
    try:
        antes = con_zona(datetime.fromisoformat(fila.valor_anterior))
        despues = con_zona(datetime.fromisoformat(fila.valor_nuevo))
    except (TypeError, ValueError):
        return 0
    return max(0, (despues - antes).days)


def _aplazamientos(db: Session, ids: list[int], desde_utc: datetime) -> list[HistorialCambio]:
    """
    Los movimientos de fecha de proyectos y tareas desde `desde_utc`. Solo los
    de verdad: poner una fecha por primera vez no es aplazar nada (misma regla
    que `Tarea.veces_aplazada`).
    """
    if not ids:
        return []
    return (
        db.query(HistorialCambio)
        .filter(
            HistorialCambio.proyecto_id.in_(ids),
            HistorialCambio.fecha >= desde_utc,
            HistorialCambio.valor_anterior.isnot(None),
            (
                ((HistorialCambio.entidad == "tarea") & (HistorialCambio.campo == "fecha_fin"))
                | ((HistorialCambio.entidad == "proyecto") & (HistorialCambio.campo == "fecha_fin_estimada"))
            ),
        )
        .all()
    )


# ── Movimiento: qué proyectos tuvieron vida en el periodo ────────────

# Corregir la frase de un avance no es mover el proyecto: si contara, un
# proyecto quieto saldría «con movimiento» por arreglar una tilde.
EVENTOS_SIN_MOVIMIENTO = ("avance_corregido", "respuesta_corregida")


def _con_movimiento(db: Session, ids: list[int], tareas: list[Tarea],
                    ini: datetime, fin: datetime) -> set[int]:
    """
    Proyectos con algo registrado en el periodo: un cambio en el historial,
    un avance escrito, una tarea creada o entregada.
    """
    if not ids:
        return set()
    movidos = {
        pid for (pid, fecha) in db.query(HistorialCambio.proyecto_id, HistorialCambio.fecha)
        .filter(HistorialCambio.proyecto_id.in_(ids), HistorialCambio.fecha >= ini,
                HistorialCambio.campo.notin_(EVENTOS_SIN_MOVIMIENTO))
        if _en(fecha, ini, fin)
    }
    movidos |= {
        pid for (pid, fecha) in db.query(Tarea.proyecto_id, TareaActualizacion.fecha)
        .join(Tarea, TareaActualizacion.tarea_id == Tarea.id)
        .filter(Tarea.proyecto_id.in_(ids), TareaActualizacion.fecha >= ini)
        if _en(fecha, ini, fin)
    }
    movidos |= {
        t.proyecto_id for t in tareas
        if _en(t.creado_en, ini, fin) or _en(t.fecha_completada, ini, fin)
    }
    return movidos


def _ultimo_movimiento(db: Session, ids: list[int], tareas: list[Tarea],
                       proyectos: list[Proyecto]) -> dict[int, datetime]:
    """La fecha del último registro de cada proyecto, para decir cuánto lleva quieto."""
    ultimo: dict[int, datetime] = {}

    def _subir(pid: int, momento) -> None:
        m = con_zona(momento)
        if m and (pid not in ultimo or m > ultimo[pid]):
            ultimo[pid] = m

    if ids:
        for pid, fecha in (db.query(HistorialCambio.proyecto_id, func.max(HistorialCambio.fecha))
                           .filter(HistorialCambio.proyecto_id.in_(ids),
                                   HistorialCambio.campo.notin_(EVENTOS_SIN_MOVIMIENTO))
                           .group_by(HistorialCambio.proyecto_id)):
            _subir(pid, fecha)
        for pid, fecha in (db.query(Tarea.proyecto_id, func.max(TareaActualizacion.fecha))
                           .join(Tarea, TareaActualizacion.tarea_id == Tarea.id)
                           .filter(Tarea.proyecto_id.in_(ids))
                           .group_by(Tarea.proyecto_id)):
            _subir(pid, fecha)
    for t in tareas:
        _subir(t.proyecto_id, t.creado_en)
        _subir(t.proyecto_id, t.fecha_completada)
    for p in proyectos:
        _subir(p.id, p.creado_en)
    return ultimo


# ── Cierres ──────────────────────────────────────────────────────────

def _cierre_en(p: Proyecto, ini: datetime, fin: datetime) -> dict | None:
    """
    El cierre del proyecto si cayó en el periodo. Manda el acta vigente; los
    cerrados antes de que existiera el acta se leen por su estado y su
    `fecha_fin_real`, que es lo único que dejaron.
    """
    acta = p.cierre_vigente
    if acta is not None:
        if not _en(acta.cerrado_en, ini, fin):
            return None
        return {
            "tipo": acta.tipo, "fecha": con_zona(acta.cerrado_en),
            "texto": acta.entregables if acta.tipo == FINALIZADO else acta.motivo,
            "dias_de_duracion": acta.dias_de_duracion,
            "tareas_total": acta.tareas_total, "tareas_completadas": acta.tareas_completadas,
        }
    if p.estado in ESTADOS_TERMINALES and _en(p.fecha_fin_real, ini, fin):
        return {
            "tipo": FINALIZADO if p.estado == "cerrado" else CANCELADO,
            "fecha": con_zona(p.fecha_fin_real), "texto": None, "dias_de_duracion": None,
            "tareas_total": p.total_tareas, "tareas_completadas": p.tareas_completadas,
        }
    return None


def _cierres(proyectos: list[Proyecto], ini: datetime, fin: datetime) -> list[dict]:
    filas = []
    for p in proyectos:
        c = _cierre_en(p, ini, fin)
        if not c:
            continue
        estimada = con_zona(p.fecha_fin_estimada)
        filas.append({
            "id": p.id, "nombre": p.nombre, "area": p.area or SIN_AREA,
            "lider_nombre": p.lider_nombre,
            "tipo": c["tipo"],
            "fecha": c["fecha"].isoformat(),
            "texto": c["texto"],
            "dias_de_duracion": c["dias_de_duracion"],
            "tareas_total": c["tareas_total"],
            "tareas_completadas": c["tareas_completadas"],
            # Solo un proyecto finalizado se entrega «en plazo» o no; uno
            # cancelado no entregó nada.
            "en_plazo": (c["fecha"] <= estimada) if (c["tipo"] == FINALIZADO and estimada) else None,
        })
    filas.sort(key=lambda f: f["fecha"])
    return filas


def _resumen_cierres(filas: list[dict]) -> dict:
    finalizados = [f for f in filas if f["tipo"] == FINALIZADO]
    medibles = [f for f in finalizados if f["en_plazo"] is not None]
    return {
        "finalizados": len(finalizados),
        "cancelados": sum(1 for f in filas if f["tipo"] == CANCELADO),
        "finalizados_en_plazo": sum(1 for f in medibles if f["en_plazo"]),
        "finalizados_medibles": len(medibles),
        "pct_en_plazo": _pct(sum(1 for f in medibles if f["en_plazo"]), len(medibles)),
    }


# ── Actividades diarias ──────────────────────────────────────────────

def _actividades(db: Session, usuario: User, area: str | None,
                 desde: date, hasta: date, ant_desde: date, ant_hasta: date) -> dict:
    """
    Cuánto se registró de lo que tocaba. Como el indicador, **hasta AYER**:
    lo de hoy todavía se puede hacer.
    """
    ayer = hoy() - timedelta(days=1)
    query = db.query(ActividadDiaria).filter(ActividadDiaria.tenant_id == usuario.tenant_id)
    query = aplicar_filtro_actividades(query, usuario)
    if area:
        query = query.filter(ActividadDiaria.area == area)

    por_area: dict[str, dict] = {}
    filas, esperados, cumplidos, ant_esp, ant_cum = [], 0, 0, 0, 0
    for a in query.all():
        c = act.cumplimiento(db, a, desde, min(hasta, ayer))
        antes = act.cumplimiento(db, a, ant_desde, min(ant_hasta, ayer))
        esperados += c["esperados"]
        cumplidos += c["cumplidos"]
        ant_esp += antes["esperados"]
        ant_cum += antes["cumplidos"]
        clave = a.area or SIN_AREA
        fila_area = por_area.setdefault(clave, {"area": clave, "esperados": 0, "cumplidos": 0})
        fila_area["esperados"] += c["esperados"]
        fila_area["cumplidos"] += c["cumplidos"]
        if c["esperados"]:
            filas.append({
                "id": a.id, "titulo": a.titulo, "area": clave,
                "asignado_nombre": a.asignado_nombre,
                "frecuencia": act.descripcion_frecuencia(a),
                "esperados": c["esperados"], "cumplidos": c["cumplidos"], "pct": c["pct"],
            })

    pct = _pct(cumplidos, esperados)
    pct_anterior = _pct(ant_cum, ant_esp)
    filas.sort(key=lambda f: (f["pct"], -f["esperados"], f["titulo"]))
    return {
        "esperados": esperados,
        "cumplidos": cumplidos,
        "pct": pct,
        "pct_anterior": pct_anterior,
        "variacion_puntos": _variacion(pct, pct_anterior),
        "por_area": {k: {**v, "pct": _pct(v["cumplidos"], v["esperados"])} for k, v in por_area.items()},
        # Las que menos se registraron primero: es la lista que se lee.
        "menos_cumplidas": [f for f in filas if f["pct"] is not None and f["pct"] < 100][:TOP_ACTIVIDADES],
    }


# ── Presupuesto ──────────────────────────────────────────────────────

def _presupuesto(proyectos: list[Proyecto], usuario: User,
                 ini: datetime, fin: datetime, ant_ini: datetime, ant_fin: datetime) -> dict | None:
    con_plata = [p for p in proyectos if puede_ver_presupuesto(p, usuario)]
    sin_acceso = len(proyectos) - len(con_plata)
    if not con_plata:
        return None

    vivos = [p for p in con_plata if not p.archivado]
    por_area: dict[str, dict] = {}

    def _fila(area: str) -> dict:
        return por_area.setdefault(area, {
            "area": area, "planeado": 0.0, "aprobado": 0.0, "pagado": 0.0, "pendiente": 0.0,
            "aprobado_periodo": 0.0, "pagado_periodo": 0.0,
        })

    # Foto de hoy: la plata de los proyectos que siguen vivos.
    for p in vivos:
        fila = _fila(p.area or SIN_AREA)
        fila["planeado"] += p.presupuesto_total
        fila["aprobado"] += p.presupuesto_aprobado
        fila["pagado"] += p.presupuesto_pagado
        fila["pendiente"] += p.presupuesto_pendiente

    # Lo que pasó en el periodo: también de los ya cerrados, porque un pago
    # de septiembre de un proyecto cerrado en octubre sí salió en septiembre.
    aprobado_periodo = pagado_periodo = pagado_anterior = 0.0
    pagos_periodo = 0
    for p in con_plata:
        for item in p.items_presupuesto:
            if item.valor_aprobado is not None and _en(item.aprobado_en, ini, fin):
                aprobado_periodo += float(item.valor_aprobado)
                _fila(p.area or SIN_AREA)["aprobado_periodo"] += float(item.valor_aprobado)
            for pago in item.pagos:
                if _en(pago.fecha, ini, fin):
                    pagado_periodo += float(pago.valor)
                    pagos_periodo += 1
                    _fila(p.area or SIN_AREA)["pagado_periodo"] += float(pago.valor)
                elif _en(pago.fecha, ant_ini, ant_fin):
                    pagado_anterior += float(pago.valor)

    planeado = sum(f["planeado"] for f in por_area.values())
    aprobado = sum(f["aprobado"] for f in por_area.values())
    pagado = sum(f["pagado"] for f in por_area.values())
    filas = sorted(
        ({**f, "pagado_pct": _pct(f["pagado"], f["aprobado"])} for f in por_area.values()),
        key=lambda f: (-f["planeado"], -f["pagado_periodo"], clave_alfabetica(f["area"])),
    )
    return {
        "proyectos": len(con_plata),
        # Cuántos proyectos del informe NO entran en estas cifras porque su
        # plata no la ve esta persona: sin decirlo, el total se leería como
        # el de la empresa.
        "proyectos_sin_acceso": sin_acceso,
        "planeado": planeado,
        "aprobado": aprobado,
        "pagado": pagado,
        "pendiente_pago": sum(f["pendiente"] for f in por_area.values()),
        "por_aprobar": max(0.0, planeado - aprobado),
        "items_por_aprobar": sum(p.items_por_aprobar for p in vivos),
        # Pagado sobre lo APROBADO: es lo que de verdad se debe.
        "pagado_pct": _pct(pagado, aprobado),
        "aprobado_periodo": aprobado_periodo,
        "pagado_periodo": pagado_periodo,
        "pagos_periodo": pagos_periodo,
        "pagado_anterior": pagado_anterior,
        "por_area": filas,
    }


# ── Personas ─────────────────────────────────────────────────────────

def _quienes_ve(db: Session, usuario: User) -> set[int] | None:
    """
    De quién puede ver la tabla por persona: todos si ve la empresa, su
    gente si es líder, nadie si no. `None` es «todos».
    """
    if ve_todo(usuario):
        return None
    if usuario.rol != "lider":
        return set()
    areas = supervision.areas_visibles(usuario)
    if not areas:
        return set()
    return {
        uid for (uid,) in db.query(User.id).filter(
            User.tenant_id == usuario.tenant_id, User.area.in_(areas), User.rol != "admin",
        )
    }


def _personas(tareas: list[Tarea], compromisos: list[Tarea], aplazamientos: list[HistorialCambio],
              permitidos: set[int] | None, ahora: datetime) -> list[dict]:
    por_tarea = {t.id: t for t in tareas}
    aplazos = Counter(
        por_tarea[h.entidad_id].asignado_a for h in aplazamientos
        if h.entidad == "tarea" and h.entidad_id in por_tarea and por_tarea[h.entidad_id].asignado_a
    )
    del_periodo = defaultdict(list)
    for t in compromisos:
        if t.asignado_a:
            del_periodo[t.asignado_a].append(t)
    abiertas = defaultdict(list)
    for t in tareas:
        if t.asignado_a and t.estado != "completada" and _activo(t.proyecto):
            abiertas[t.asignado_a].append(t)

    nombres = {t.asignado_a: t.asignado for t in tareas if t.asignado_a and t.asignado}
    filas = []
    for uid in set(del_periodo) | set(abiertas):
        if permitidos is not None and uid not in permitidos:
            continue
        persona = nombres.get(uid)
        suyas = abiertas.get(uid, [])
        horas = [float(t.horas_estimadas) for t in suyas if t.horas_estimadas is not None]
        filas.append({
            "usuario_id": uid,
            "nombre": persona.nombre if persona else f"Usuario #{uid}",
            "area": persona.area if persona else None,
            "compromisos": _contar(del_periodo.get(uid, []), ahora),
            "abiertas": len(suyas),
            "vencidas_hoy": sum(1 for t in suyas if con_zona(t.fecha_fin) and con_zona(t.fecha_fin) < ahora),
            # Vacío es «no se sabe», nunca cero: una tarea sin estimar no
            # cuesta cero horas.
            "horas_abiertas": round(sum(horas), 1) if horas else None,
            "sin_estimar": len(suyas) - len(horas),
            "aplazamientos": aplazos.get(uid, 0),
        })
    filas.sort(key=lambda f: (-f["vencidas_hoy"], -f["compromisos"]["vencidas"],
                              f["compromisos"]["pct"] if f["compromisos"]["pct"] is not None else 101,
                              f["nombre"]))
    return filas


# ── Alcance ──────────────────────────────────────────────────────────

def _descripcion_alcance(usuario: User) -> str:
    if ve_todo(usuario):
        return "Toda la empresa"
    if usuario.rol == "lider":
        areas = supervision.areas_visibles(usuario)
        if areas:
            return f"Los proyectos de {', '.join(areas)} y en los que participas"
    return "Los proyectos en los que participas"


# ── El informe ───────────────────────────────────────────────────────

def construir(db: Session, usuario: User, desde: date | None = None, hasta: date | None = None,
              area: str | None = None) -> dict:
    desde, hasta = resolver_periodo(desde, hasta)
    ant_desde, ant_hasta = periodo_anterior(desde, hasta)
    ini, fin = limites(desde, hasta)
    ant_ini, ant_fin = limites(ant_desde, ant_hasta)
    ahora = datetime.now(timezone.utc)
    area = (area or "").strip() or None

    # Todos los visibles, archivados incluidos: un proyecto cerrado en el
    # periodo está archivado, y es justo lo que el informe tiene que contar.
    base = aplicar_filtro_proyectos(
        db.query(Proyecto).filter(Proyecto.tenant_id == usuario.tenant_id), usuario,
    ).options(
        joinedload(Proyecto.lider),
        selectinload(Proyecto.areas_extra),
        selectinload(Proyecto.cierres),
        selectinload(Proyecto.items_presupuesto).selectinload(ItemPresupuesto.pagos),
        selectinload(Proyecto.tareas),
    )
    todos = base.all()
    proyectos = base.filter(condicion_area(area)).all() if area else todos
    ids = [p.id for p in proyectos]
    activos = [p for p in proyectos if _activo(p)]

    tareas = (
        db.query(Tarea)
        .options(joinedload(Tarea.asignado))
        .filter(Tarea.proyecto_id.in_(ids), Tarea.parent_id.is_(None))
        .all()
    ) if ids else []

    # ── Compromisos y entregas ──
    compromisos = _del_periodo(tareas, ini, fin)
    cumplimiento = _contar(compromisos, ahora)
    cumplimiento_ant = _contar(_del_periodo(tareas, ant_ini, ant_fin), ahora)
    entregas = _entregas(tareas, ini, fin)
    entregas_ant = _entregas(tareas, ant_ini, ant_fin)

    # ── Aplazamientos del periodo y del anterior ──
    movimientos = _aplazamientos(db, ids, ant_ini)
    aplazos = [h for h in movimientos if _en(h.fecha, ini, fin)]
    aplazos_ant = [h for h in movimientos if _en(h.fecha, ant_ini, ant_fin)]
    por_tarea = {t.id: t for t in tareas}
    # Solo las tareas de primer nivel, como todo el informe.
    aplazos_tareas = [h for h in aplazos if h.entidad == "tarea" and h.entidad_id in por_tarea]
    aplazos_proyectos = [h for h in aplazos if h.entidad == "proyecto"]
    nombre_de = {p.id: p for p in proyectos}
    mas_aplazados = Counter()
    dias_por_proyecto = Counter()
    for h in aplazos_tareas + aplazos_proyectos:
        mas_aplazados[h.proyecto_id] += 1
        dias_por_proyecto[h.proyecto_id] += _dias_movidos(h)

    # ── Cierres y nuevos ──
    cierres = _cierres(proyectos, ini, fin)
    cierres_ant = _cierres(proyectos, ant_ini, ant_fin)
    nuevos = [p for p in proyectos if _en(p.creado_en, ini, fin)]
    nuevos_ant = [p for p in proyectos if _en(p.creado_en, ant_ini, ant_fin)]

    # ── Salud y movimiento (foto de hoy) ──
    con_movimiento = _con_movimiento(db, ids, tareas, ini, fin)
    ultimo = _ultimo_movimiento(db, [p.id for p in activos], tareas, activos)
    vencidas_por_proyecto = Counter(
        t.proyecto_id for t in tareas
        if t.estado != "completada" and con_zona(t.fecha_fin) and con_zona(t.fecha_fin) < ahora
    )
    salud_de: dict[int, str] = {}
    plazo_de: dict[int, float | None] = {}
    for p in activos:
        plazo_de[p.id] = _plazo_consumido_pct(p)
        salud_de[p.id] = _salud(p, plazo_de[p.id])

    quietos = []
    for p in activos:
        # Un proyecto creado dentro del periodo no lleva tiempo quieto.
        if p.id in con_movimiento or not con_zona(p.creado_en) or con_zona(p.creado_en) >= ini:
            continue
        u = ultimo.get(p.id)
        quietos.append({
            "id": p.id, "nombre": p.nombre, "area": p.area or SIN_AREA,
            "lider_nombre": p.lider_nombre, "avance_pct": p.avance_pct,
            "ultimo_movimiento": u.isoformat() if u else None,
            "dias_sin_movimiento": (hoy() - dia_local(u)).days if u else None,
        })
    quietos.sort(key=lambda f: -(f["dias_sin_movimiento"] or 0))
    ids_quietos = {q["id"] for q in quietos}

    en_riesgo = []
    for p in activos:
        salud = salud_de[p.id]
        if salud not in ("rojo", "amarillo"):
            continue
        motivos = []
        estimada = con_zona(p.fecha_fin_estimada)
        if estimada and estimada < ahora and (p.avance_pct or 0) < 100:
            motivos.append(f"Debía entregarse el {_fecha_texto(estimada)} y va en {p.avance_pct}%")
        elif plazo_de[p.id] is not None:
            motivos.append(f"Va en {p.avance_pct}% con el {plazo_de[p.id]}% del tiempo consumido")
        if vencidas_por_proyecto[p.id]:
            n = vencidas_por_proyecto[p.id]
            motivos.append(f"{n} tarea{'s' if n != 1 else ''} vencida{'s' if n != 1 else ''}")
        if mas_aplazados[p.id]:
            n = mas_aplazados[p.id]
            motivos.append(f"Se movieron fechas {n} {'vez' if n == 1 else 'veces'} en el periodo")
        if p.id in ids_quietos:
            motivos.append("Sin movimiento en el periodo")
        en_riesgo.append({
            "id": p.id, "nombre": p.nombre, "area": p.area or SIN_AREA,
            "lider_nombre": p.lider_nombre, "estado": p.estado,
            "salud": salud, "avance_pct": p.avance_pct,
            "plazo_consumido_pct": plazo_de[p.id],
            "fecha_fin_estimada": estimada.isoformat() if estimada else None,
            "motivos": motivos,
        })
    en_riesgo.sort(key=lambda f: (0 if f["salud"] == "rojo" else 1, f["avance_pct"] or 0))

    # ── Actividades diarias ──
    actividades = _actividades(db, usuario, area, desde, hasta, ant_desde, ant_hasta)

    # ── Por área ──
    areas: dict[str, dict] = {}

    def _fila_area(nombre: str) -> dict:
        return areas.setdefault(nombre, {
            "area": nombre, "proyectos_responsable": 0, "proyectos_participa": 0,
            "_avances": [], "en_riesgo": 0, "_compromisos": [], "aplazamientos": 0,
            "finalizados": 0, "cancelados": 0,
        })

    for p in activos:
        involucradas = p.areas_involucradas or [SIN_AREA]
        for a in involucradas:
            fila = _fila_area(a)
            if a == (p.area or SIN_AREA):
                fila["proyectos_responsable"] += 1
            else:
                fila["proyectos_participa"] += 1
            fila["_avances"].append(p.avance_pct or 0)
            if salud_de[p.id] in ("rojo", "amarillo"):
                fila["en_riesgo"] += 1
    for t in compromisos:
        _fila_area(_area_de_tarea(t))["_compromisos"].append(t)
    for h in aplazos_tareas:
        _fila_area(_area_de_tarea(por_tarea[h.entidad_id]))["aplazamientos"] += 1
    for c in cierres:
        _fila_area(c["area"])["finalizados" if c["tipo"] == FINALIZADO else "cancelados"] += 1
    for nombre, a in actividades["por_area"].items():
        if a["esperados"]:
            _fila_area(nombre)

    # Con un área elegida, la tabla muestra esa área: las demás aparecen solo
    # porque comparten proyectos con ella, y en esa vista son ruido.
    if area:
        areas = {k: v for k, v in areas.items() if k == area}

    por_area = []
    for nombre, f in areas.items():
        avances = f.pop("_avances")
        compromisos_area = f.pop("_compromisos")
        act_area = actividades["por_area"].get(nombre)
        por_area.append({
            **f,
            "proyectos_activos": f["proyectos_responsable"] + f["proyectos_participa"],
            "avance_promedio": round(sum(avances) / len(avances), 1) if avances else None,
            "compromisos": _contar(compromisos_area, ahora),
            "actividades_pct": act_area["pct"] if act_area else None,
            "actividades_esperados": act_area["esperados"] if act_area else 0,
        })
    # Alfabético, como toda lista de áreas del portal; «Sin área» al final.
    por_area.sort(key=lambda f: (f["area"] == SIN_AREA, clave_alfabetica(f["area"])))

    # ── Personas ──
    permitidos = _quienes_ve(db, usuario)
    personas = None if permitidos == set() else _personas(tareas, compromisos, aplazos, permitidos, ahora)

    # ── Presupuesto ──
    presupuesto = _presupuesto(proyectos, usuario, ini, fin, ant_ini, ant_fin)

    resumen_cierres = _resumen_cierres(cierres)
    resumen_cierres_ant = _resumen_cierres(cierres_ant)
    salud = Counter(salud_de.values())
    avances_activos = [p.avance_pct or 0 for p in activos]

    return {
        "periodo": describir(desde, hasta, ahora),
        "alcance": {
            "descripcion": _descripcion_alcance(usuario),
            "toda_empresa": ve_todo(usuario),
            "area": area,
            # Sin el filtro de `area`: el selector sigue ofreciendo todas.
            "areas_disponibles": sorted({a for p in todos for a in p.areas_involucradas}, key=clave_alfabetica),
            "ve_personas": personas is not None,
            "ve_presupuesto": presupuesto is not None,
        },
        "resumen": {
            "proyectos_activos": len(activos),
            "por_estado": [
                {"clave": e, "etiqueta": ESTADOS_PROYECTO[e], "n": n}
                for e, n in sorted(Counter(p.estado for p in activos).items(),
                                   key=lambda kv: list(ESTADOS_PROYECTO).index(kv[0])
                                   if kv[0] in ESTADOS_PROYECTO else 99)
                if e in ESTADOS_PROYECTO
            ],
            "avance_promedio": round(sum(avances_activos) / len(avances_activos), 1) if avances_activos else None,
            "nuevos": len(nuevos),
            "nuevos_anterior": len(nuevos_ant),
            **resumen_cierres,
            "finalizados_anterior": resumen_cierres_ant["finalizados"],
            "cancelados_anterior": resumen_cierres_ant["cancelados"],
            "con_movimiento": sum(1 for p in activos if p.id in con_movimiento),
            "quietos": len(quietos),
        },
        "salud": [
            {"clave": s, "etiqueta": SALUD[s], "n": salud.get(s, 0), "pct": _pct(salud.get(s, 0), len(activos))}
            for s in ("rojo", "amarillo", "verde", "sin_datos")
        ],
        "cumplimiento": {
            **cumplimiento,
            "pct_anterior": cumplimiento_ant["pct"],
            "juzgadas_anterior": cumplimiento_ant["juzgadas"],
            "variacion_puntos": _variacion(cumplimiento["pct"], cumplimiento_ant["pct"]),
        },
        "entregas": {
            **entregas,
            "total_anterior": entregas_ant["total"],
            "pct_anterior": entregas_ant["pct"],
            "variacion_puntos": _variacion(entregas["pct"], entregas_ant["pct"]),
            "creadas": sum(1 for t in tareas if _en(t.creado_en, ini, fin)),
        },
        "aplazamientos": {
            "tareas": len(aplazos_tareas),
            "tareas_distintas": len({h.entidad_id for h in aplazos_tareas}),
            "dias_tareas": sum(_dias_movidos(h) for h in aplazos_tareas),
            "proyectos": len(aplazos_proyectos),
            "dias_proyectos": sum(_dias_movidos(h) for h in aplazos_proyectos),
            "total_anterior": sum(
                1 for h in aplazos_ant
                if h.entidad == "proyecto" or h.entidad_id in por_tarea
            ),
            "mas_aplazados": [
                {"id": pid, "nombre": nombre_de[pid].nombre, "area": nombre_de[pid].area or SIN_AREA,
                 "veces": n, "dias": dias_por_proyecto[pid]}
                for pid, n in sorted(mas_aplazados.items(),
                                     key=lambda kv: (-kv[1], -dias_por_proyecto[kv[0]]))[:TOP_APLAZADOS]
            ],
        },
        "tendencia_entregas": serie(
            Counter(dia_local(t.fecha_completada) for t in tareas
                    if t.estado == "completada" and _en(t.fecha_completada, ini, fin)),
            desde, hasta,
        ),
        "por_area": por_area,
        "en_riesgo": en_riesgo,
        "quietos": quietos,
        "cierres": cierres,
        "actividades": {k: v for k, v in actividades.items() if k != "por_area"},
        "presupuesto": presupuesto,
        "personas": personas,
    }
