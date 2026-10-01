"""
Lo que el Master Planner le aporta a la página de Inicio: las tareas de la
persona, los proyectos y el presupuesto en el titular de la empresa, y el
trabajo del equipo de un líder. Ver `core/inicio.py`.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core import inicio as base
from app.core import supervision
from app.core.fechas import con_zona
from app.models.master_planner import ItemPresupuesto, PagoItem, Proyecto, Tarea
from app.models.user import User
from app.modules.master_planner.permisos import aplicar_filtro_proyectos

# Cuántos meses entran en la gráfica de ejecución presupuestal. Siete cabe
# sin apretar en pantalla y alcanza para ver una tendencia; con doce las
# barras quedan tan delgadas que no se comparan.
MESES_SERIE = 7


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

    ahora = base.ahora()
    limite = ahora + timedelta(days=base.DIAS_AVISO)
    vencidas, por_vencer = [], []

    for t in tareas:
        fin = con_zona(t.fecha_fin)
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

    vencidas.sort(key=lambda x: con_zona(x["fecha_fin"]))
    por_vencer.sort(key=lambda x: con_zona(x["fecha_fin"]))

    return base.bandeja(vencidas, por_vencer, abiertas=len(tareas))


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
    periodos = base.meses_hacia_atras(MESES_SERIE)
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
            fecha = con_zona(fecha)
            if fecha and fecha >= desde and (fecha.year, fecha.month) in acumulado:
                acumulado[(fecha.year, fecha.month)]["pagado"] += float(valor or 0)

        aprobaciones = (
            db.query(ItemPresupuesto.aprobado_en, ItemPresupuesto.valor_aprobado)
            .filter(ItemPresupuesto.proyecto_id.in_(ids_proyectos),
                    ItemPresupuesto.aprobado_en.isnot(None))
            .all()
        )
        for fecha, valor in aprobaciones:
            fecha = con_zona(fecha)
            if fecha and fecha >= desde and (fecha.year, fecha.month) in acumulado:
                acumulado[(fecha.year, fecha.month)]["aprobado"] += float(valor or 0)

    return [
        {
            "anio": anio,
            "mes": mes,
            "etiqueta": base.MESES_CORTOS[mes - 1],
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
    activos.sort(key=lambda p: con_zona(p.fecha_fin_estimada) or lejos)

    return [
        {
            "id": p.id,
            "nombre": p.nombre,
            "estado": p.estado,
            "avance_pct": p.avance_pct,
            "fecha_fin": p.fecha_fin_estimada,
        }
        for p in activos[:base.TOPE_LISTA]
    ]


def _titular(db: Session, usuario: User, momento: datetime) -> dict:
    proyectos_q = db.query(Proyecto).filter(
        Proyecto.tenant_id == usuario.tenant_id, Proyecto.archivado.is_(False),
    )
    proyectos = aplicar_filtro_proyectos(proyectos_q, usuario).all()
    inicio_mes = base.inicio_del_mes(momento)

    planeado = sum(p.presupuesto_total for p in proyectos)
    aprobado = sum(p.presupuesto_aprobado for p in proyectos)
    pagado = sum(p.presupuesto_pagado for p in proyectos)

    return {
        "proyectos_activos": len(proyectos),
        "proyectos_nuevos_mes": len([
            p for p in proyectos
            if con_zona(p.creado_en) and con_zona(p.creado_en) >= inicio_mes
        ]),
        "proyectos": _proyectos_al_frente(proyectos),
        "presupuesto_planeado": planeado,
        "presupuesto_aprobado": aprobado,
        "presupuesto_pagado": pagado,
        "pagado_pct": round((pagado / planeado) * 100, 1) if planeado else None,
        # El % que de verdad importa: lo pagado sobre lo APROBADO es la deuda
        # real. Lo planeado puede no aprobarse nunca.
        "pagado_pct_aprobado": round((pagado / aprobado) * 100, 1) if aprobado else None,
        "serie_presupuesto": _serie_presupuesto(db, [p.id for p in proyectos]),
    }


def _mi_area(db: Session, usuario: User, ids_equipo: list[int], momento: datetime) -> dict:
    """Los proyectos del área y qué tiene pendiente su gente."""
    proyectos = (
        db.query(Proyecto)
        .filter(Proyecto.tenant_id == usuario.tenant_id,
                Proyecto.archivado.is_(False),
                Proyecto.area.in_(supervision.areas_visibles(usuario)))
        .all()
    )

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
        if con_zona(t.fecha_fin) and con_zona(t.fecha_fin) < momento
    ]

    return {
        "proyectos": [
            {"id": p.id, "nombre": p.nombre, "estado": p.estado, "avance_pct": p.avance_pct}
            for p in sorted(proyectos, key=lambda x: x.avance_pct)[:base.TOPE_LISTA]
        ],
        "total_proyectos": len(proyectos),
        "tareas_abiertas_equipo": len(tareas_equipo),
        "tareas_vencidas_equipo": len(vencidas_equipo),
    }


APORTE = base.AporteInicio(
    pendientes=(
        base.Pendientes(
            clave="mis_tareas", calcular=_mis_tareas,
            urgentes=base.urgentes_de_bandeja, por_atender=base.por_atender_de_bandeja,
        ),
    ),
    titular=_titular,
    mi_area=_mi_area,
)
