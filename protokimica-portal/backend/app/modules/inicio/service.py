"""
El inicio del portal, armado según quién entra.

La página es primero la bandeja de trabajo de la persona y después el reporte
de la empresa. Para un agente de Logística "cómo va la empresa" es ruido; lo
que necesita es qué le toca hoy. Para gerencia es al revés.

Todo se calcula aquí y se entrega listo: el frontend no tiene que pedir cinco
endpoints distintos y armar el rompecabezas.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.modulos import modulos_de, ve_todos_los_indicadores
from app.models.indicadores import Indicador
from app.models.master_planner import ItemPresupuesto, PagoItem, Proyecto, Tarea
from app.models.pqrs import PQRSSolicitud
from app.models.user import User
from app.modules.indicadores import service as ind_service
from app.modules.master_planner.permisos import aplicar_filtro_proyectos

# Cuántos días antes se considera que algo "está por vencer". Igual que en
# Master Planner, para que la misma tarea no salga como urgente en un sitio
# y tranquila en otro.
DIAS_AVISO = 3

# Cuántos elementos se listan por tarjeta. El inicio es un titular con
# enlaces, no la vista completa: para eso está cada módulo.
TOPE_LISTA = 5

# Cuántos meses entran en la gráfica de ejecución presupuestal. Siete cabe
# sin apretar en pantalla y alcanza para ver una tendencia; con doce las
# barras quedan tan delgadas que no se comparan.
MESES_SERIE = 7

MESES_CORTOS = [
    "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
]


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _aware(f: datetime | None) -> datetime | None:
    """Postgres devuelve fechas con zona y SQLite sin ella."""
    if f is None:
        return None
    return f if f.tzinfo else f.replace(tzinfo=timezone.utc)


def _mis_tareas(db: Session, usuario: User) -> dict:
    """Tareas asignadas a la persona, en proyectos activos."""
    tareas = (
        db.query(Tarea)
        .join(Proyecto, Tarea.proyecto_id == Proyecto.id)
        .filter(
            Proyecto.tenant_id == usuario.tenant_id,
            Proyecto.archivado.is_(False),
            Tarea.asignado_a == usuario.id,
            Tarea.estado != "completada",
        )
        .all()
    )

    ahora = _ahora()
    limite = ahora + timedelta(days=DIAS_AVISO)
    vencidas, por_vencer = [], []

    for t in tareas:
        fin = _aware(t.fecha_fin)
        if not fin:
            continue
        destino = vencidas if fin < ahora else (por_vencer if fin <= limite else None)
        if destino is None:
            continue
        destino.append({
            "id": t.id,
            "titulo": t.titulo,
            "proyecto": t.proyecto.nombre if t.proyecto else None,
            "fecha_fin": t.fecha_fin,
            "prioridad": t.prioridad,
        })

    vencidas.sort(key=lambda x: _aware(x["fecha_fin"]))
    por_vencer.sort(key=lambda x: _aware(x["fecha_fin"]))

    return {
        "abiertas": len(tareas),
        "vencidas": len(vencidas),
        "por_vencer": len(por_vencer),
        "lista": (vencidas + por_vencer)[:TOPE_LISTA],
    }


def _mis_pqrs(db: Session, usuario: User) -> dict:
    """PQRS asignadas a la persona y sin cerrar."""
    solicitudes = (
        db.query(PQRSSolicitud)
        .filter(
            PQRSSolicitud.tenant_id == usuario.tenant_id,
            PQRSSolicitud.asignado_a == usuario.id,
            PQRSSolicitud.estado != "cerrado",
        )
        .all()
    )

    ahora = _ahora()
    limite = ahora + timedelta(days=DIAS_AVISO)
    vencidas, por_vencer = [], []

    for p in solicitudes:
        sla = _aware(p.fecha_limite_sla)
        if not sla:
            continue
        destino = vencidas if sla < ahora else (por_vencer if sla <= limite else None)
        if destino is None:
            continue
        destino.append({
            "id": p.id,
            "codigo": p.codigo_seguimiento or p.radicado_calidad or f"#{p.id}",
            "tipo": p.tipo,
            "cliente": p.empresa or p.cliente_nombre,
            "fecha_limite_sla": p.fecha_limite_sla,
            "estado": p.estado,
        })

    vencidas.sort(key=lambda x: _aware(x["fecha_limite_sla"]))
    por_vencer.sort(key=lambda x: _aware(x["fecha_limite_sla"]))

    return {
        "abiertas": len(solicitudes),
        "vencidas": len(vencidas),
        "por_vencer": len(por_vencer),
        "lista": (vencidas + por_vencer)[:TOPE_LISTA],
    }


def _indicadores_por_registrar(db: Session, usuario: User) -> list[dict]:
    """
    Indicadores manuales del último mes cerrado que todavía no tienen valor.
    Solo para quien entra al módulo; a un agente no le sirve de nada.
    """
    if "indicadores" not in modulos_de(usuario):
        return []

    anio, mes = ind_service.periodo_por_defecto()
    query = db.query(Indicador).filter(
        Indicador.tenant_id == usuario.tenant_id,
        Indicador.activo.is_(True),
        Indicador.tipo_captura != "automatico",
    )
    if not ve_todos_los_indicadores(usuario):
        query = query.filter(Indicador.area == usuario.area)

    pendientes = []
    for ind in query.all():
        tiene = any(m.anio == anio and m.mes == mes and m.valor is not None
                    for m in ind.mediciones)
        if not tiene:
            pendientes.append({
                "id": ind.id, "nombre": ind.nombre, "area": ind.area,
                "anio": anio, "mes": mes,
            })
    return pendientes[:TOPE_LISTA]


def _meses_hacia_atras(cuantos: int) -> list[tuple[int, int]]:
    """Los últimos N periodos (año, mes), del más viejo al más nuevo."""
    hoy = _ahora()
    anio, mes = hoy.year, hoy.month
    periodos = []
    for _ in range(cuantos):
        periodos.append((anio, mes))
        mes -= 1
        if mes == 0:
            mes, anio = 12, anio - 1
    return list(reversed(periodos))


def _serie_presupuesto(db: Session, ids_proyectos: list[int]) -> list[dict]:
    """
    Cuánto se aprobó y cuánto se pagó cada mes.

    Son las dos manos del presupuesto: `Administración` aprueba y `Tesorería`
    desembolsa. Verlas juntas mes a mes es lo que muestra si lo aprobado se
    está ejecutando o se está quedando represado.

    Se agrupa en Python y no con `date_trunc` a propósito: las pruebas corren
    sobre SQLite y producción sobre Postgres, y esa función no existe igual en
    las dos.
    """
    periodos = _meses_hacia_atras(MESES_SERIE)
    acumulado = {p: {"aprobado": 0.0, "pagado": 0.0} for p in periodos}

    if ids_proyectos:
        desde = datetime(periodos[0][0], periodos[0][1], 1, tzinfo=timezone.utc)

        pagos = (
            db.query(PagoItem.fecha, PagoItem.valor)
            .join(ItemPresupuesto, PagoItem.item_id == ItemPresupuesto.id)
            .filter(ItemPresupuesto.proyecto_id.in_(ids_proyectos))
            .all()
        )
        for fecha, valor in pagos:
            fecha = _aware(fecha)
            if fecha and fecha >= desde and (fecha.year, fecha.month) in acumulado:
                acumulado[(fecha.year, fecha.month)]["pagado"] += float(valor or 0)

        aprobaciones = (
            db.query(ItemPresupuesto.aprobado_en, ItemPresupuesto.valor_aprobado)
            .filter(ItemPresupuesto.proyecto_id.in_(ids_proyectos),
                    ItemPresupuesto.aprobado_en.isnot(None))
            .all()
        )
        for fecha, valor in aprobaciones:
            fecha = _aware(fecha)
            if fecha and fecha >= desde and (fecha.year, fecha.month) in acumulado:
                acumulado[(fecha.year, fecha.month)]["aprobado"] += float(valor or 0)

    return [
        {
            "anio": anio,
            "mes": mes,
            "etiqueta": MESES_CORTOS[mes - 1],
            "aprobado": round(acumulado[(anio, mes)]["aprobado"], 2),
            "pagado": round(acumulado[(anio, mes)]["pagado"], 2),
        }
        for (anio, mes) in periodos
    ]


def _proyectos_al_frente(proyectos: list) -> list[dict]:
    """
    Los proyectos activos ordenados por el que vence primero.

    Ordenar por fecha de entrega y no por avance responde la pregunta que de
    verdad se hace en una reunión: qué se vence pronto y cómo va. Los que no
    tienen fecha van al final, no primero: sin plazo no hay urgencia.
    """
    activos = [p for p in proyectos if p.estado in ("planeacion", "en_ejecucion")]
    lejos = datetime(2999, 1, 1, tzinfo=timezone.utc)
    activos.sort(key=lambda p: _aware(p.fecha_fin_estimada) or lejos)

    return [
        {
            "id": p.id,
            "nombre": p.nombre,
            "estado": p.estado,
            "avance_pct": p.avance_pct,
            "fecha_fin": p.fecha_fin_estimada,
        }
        for p in activos[:TOPE_LISTA]
    ]


def _resumen_empresa(db: Session, usuario: User) -> dict | None:
    """
    Las cuatro cifras de titular. Solo para quien responde por el conjunto:
    a un agente no le aporta y le quita espacio a lo suyo.
    """
    if usuario.rol not in ("admin", "gerencia", "lider"):
        return None

    proyectos_q = db.query(Proyecto).filter(
        Proyecto.tenant_id == usuario.tenant_id, Proyecto.archivado.is_(False),
    )
    proyectos = aplicar_filtro_proyectos(proyectos_q, usuario).all()

    pqrs_abiertas = (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.tenant_id == usuario.tenant_id,
                PQRSSolicitud.estado != "cerrado")
        .count()
    )

    # Un cero de PQRS abiertas no dice si el equipo trabajó o si nadie
    # escribió. Lo que se cerró este mes sí.
    inicio_mes = _ahora().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    pqrs_cerradas_mes = (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.tenant_id == usuario.tenant_id,
                PQRSSolicitud.estado == "cerrado",
                PQRSSolicitud.fecha_cierre.isnot(None),
                PQRSSolicitud.fecha_cierre >= inicio_mes)
        .count()
    )

    planeado = sum(p.presupuesto_total for p in proyectos)
    aprobado = sum(p.presupuesto_aprobado for p in proyectos)
    pagado = sum(p.presupuesto_pagado for p in proyectos)

    resumen = {
        "proyectos_activos": len(proyectos),
        "proyectos_nuevos_mes": len([
            p for p in proyectos
            if _aware(p.creado_en) and _aware(p.creado_en) >= inicio_mes
        ]),
        "proyectos": _proyectos_al_frente(proyectos),
        "pqrs_abiertas": pqrs_abiertas,
        "pqrs_cerradas_mes": pqrs_cerradas_mes,
        "presupuesto_planeado": planeado,
        "presupuesto_aprobado": aprobado,
        "presupuesto_pagado": pagado,
        "pagado_pct": round((pagado / planeado) * 100, 1) if planeado else None,
        # El % que de verdad importa: lo pagado sobre lo APROBADO es la deuda
        # real. Lo planeado puede no aprobarse nunca.
        "pagado_pct_aprobado": round((pagado / aprobado) * 100, 1) if aprobado else None,
        "serie_presupuesto": _serie_presupuesto(db, [p.id for p in proyectos]),
        "indicadores_en_rojo": None,   # se llena abajo solo si puede verlos
    }

    if "indicadores" in modulos_de(usuario):
        anio, mes = ind_service.periodo_por_defecto()
        area = None if ve_todos_los_indicadores(usuario) else usuario.area
        tablero = ind_service.construir_tablero(db, usuario.tenant_id, anio, mes, area)
        resumen["indicadores_en_rojo"] = tablero["resumen"]["rojo"]
        resumen["periodo_indicadores"] = f"{tablero['mes_nombre']} {anio}"
        # Cuántos tienen dato: «2 en rojo» pesa distinto sobre 3 que sobre 40.
        # Se suman los tres colores y no "todo menos sin_datos", porque el
        # resumen trae además totales y un porcentaje que puede venir en None.
        resumen["indicadores_medidos"] = sum(
            tablero["resumen"].get(color, 0) or 0
            for color in ("verde", "amarillo", "rojo")
        )

        # Contra el mes anterior, para saber si vamos mejorando. Es una
        # segunda pasada del tablero, no una consulta suelta: el semáforo se
        # calcula, no se guarda, y duplicarlo aquí lo dejaría desalineado con
        # el módulo de Indicadores.
        anio_ant, mes_ant = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
        tablero_ant = ind_service.construir_tablero(
            db, usuario.tenant_id, anio_ant, mes_ant, area)
        resumen["indicadores_rojo_anterior"] = tablero_ant["resumen"]["rojo"]
        resumen["periodo_anterior"] = MESES_CORTOS[mes_ant - 1].lower()

    return resumen


def _mi_area(db: Session, usuario: User) -> dict | None:
    """
    Lo que un líder necesita para su reunión de equipo: sus proyectos y qué
    tiene pendiente su gente.
    """
    if usuario.rol != "lider" or not usuario.area:
        return None

    proyectos = (
        db.query(Proyecto)
        .filter(Proyecto.tenant_id == usuario.tenant_id,
                Proyecto.archivado.is_(False),
                Proyecto.area == usuario.area)
        .all()
    )

    ahora = _ahora()
    equipo = db.query(User).filter(
        User.tenant_id == usuario.tenant_id,
        User.area == usuario.area,
        User.activo.is_(True),
    ).all()
    ids_equipo = [u.id for u in equipo]

    tareas_equipo = []
    if ids_equipo:
        tareas_equipo = (
            db.query(Tarea)
            .join(Proyecto, Tarea.proyecto_id == Proyecto.id)
            .filter(Proyecto.tenant_id == usuario.tenant_id,
                    Proyecto.archivado.is_(False),
                    Tarea.asignado_a.in_(ids_equipo),
                    Tarea.estado != "completada")
            .all()
        )

    vencidas_equipo = [
        t for t in tareas_equipo
        if _aware(t.fecha_fin) and _aware(t.fecha_fin) < ahora
    ]

    return {
        "area": usuario.area,
        "personas": len(equipo),
        "proyectos": [
            {"id": p.id, "nombre": p.nombre, "estado": p.estado, "avance_pct": p.avance_pct}
            for p in sorted(proyectos, key=lambda x: x.avance_pct)[:TOPE_LISTA]
        ],
        "total_proyectos": len(proyectos),
        "tareas_abiertas_equipo": len(tareas_equipo),
        "tareas_vencidas_equipo": len(vencidas_equipo),
    }


def construir_inicio(db: Session, usuario: User) -> dict:
    tareas = _mis_tareas(db, usuario)
    pqrs = _mis_pqrs(db, usuario)
    indicadores = _indicadores_por_registrar(db, usuario)

    return {
        "usuario": {
            "nombre": usuario.nombre,
            "rol": usuario.rol,
            "area": usuario.area,
        },
        "modulos": modulos_de(usuario),
        "mis_tareas": tareas,
        "mis_pqrs": pqrs,
        "indicadores_por_registrar": indicadores,
        # Cuántas cosas reclaman atención hoy. Es el número que decide si la
        # tarjeta de pendientes sale en rojo o en calma.
        "total_urgente": tareas["vencidas"] + pqrs["vencidas"],
        "total_pendiente": (
            tareas["vencidas"] + tareas["por_vencer"]
            + pqrs["vencidas"] + pqrs["por_vencer"]
            + len(indicadores)
        ),
        "empresa": _resumen_empresa(db, usuario),
        "mi_area": _mi_area(db, usuario),
    }
