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
from app.models.master_planner import Proyecto, Tarea
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

    planeado = sum(p.presupuesto_total for p in proyectos)
    pagado = sum(p.presupuesto_pagado for p in proyectos)

    resumen = {
        "proyectos_activos": len(proyectos),
        "pqrs_abiertas": pqrs_abiertas,
        "presupuesto_planeado": planeado,
        "presupuesto_pagado": pagado,
        "pagado_pct": round((pagado / planeado) * 100, 1) if planeado else None,
        "indicadores_en_rojo": None,   # se llena abajo solo si puede verlos
    }

    if "indicadores" in modulos_de(usuario):
        anio, mes = ind_service.periodo_por_defecto()
        tablero = ind_service.construir_tablero(
            db, usuario.tenant_id, anio, mes,
            None if ve_todos_los_indicadores(usuario) else usuario.area,
        )
        resumen["indicadores_en_rojo"] = tablero["resumen"]["rojo"]
        resumen["periodo_indicadores"] = f"{tablero['mes_nombre']} {anio}"

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
