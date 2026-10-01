"""
El inicio del portal, armado según quién entra.

La página es primero la bandeja de trabajo de la persona y después el reporte
de la empresa. Para un agente de Logística "cómo va la empresa" es ruido; lo
que necesita es qué le toca hoy. Para gerencia es al revés.

Todo se calcula en el servidor y se entrega listo: el frontend no tiene que
pedir cinco endpoints distintos y armar el rompecabezas.

**Este archivo no conoce a ningún módulo.** Cada uno aporta sus piezas en su
propio `inicio.py` —las tareas el Master Planner, las solicitudes PQRS, lo
que falta registrar Indicadores— y aquí solo se reúnen (ver
`core/inicio.py`). Un módulo que no está instalado, o que la empresa no
tiene contratado, no aporta su tarjeta.
"""
from sqlalchemy.orm import Session

from app.core import inicio as base
from app.core import registro, supervision
from app.core.modulos import modulos_de, paquete_contratado
from app.models.user import User


def _aportes(usuario: User) -> list[base.AporteInicio]:
    """Las piezas de los módulos que la empresa del usuario tiene contratados."""
    return [
        pieza.APORTE for pieza in registro.piezas("inicio")
        if hasattr(pieza, "APORTE")
        and paquete_contratado(usuario.tenant, registro.paquete_de(pieza))
    ]


def _resumen_empresa(db: Session, usuario: User, aportes, momento) -> dict | None:
    """
    Las cifras de titular. Solo para quien responde por el conjunto: a un
    agente no le aporta y le quita espacio a lo suyo.
    """
    if usuario.rol not in ("admin", "gerencia", "lider"):
        return None
    resumen = {}
    for aporte in aportes:
        if aporte.titular:
            resumen.update(aporte.titular(db, usuario, momento))
    return resumen


def _mi_area(db: Session, usuario: User, aportes, momento) -> dict | None:
    """
    Lo que un líder necesita para su reunión de equipo: el trabajo de su
    área y qué tiene pendiente su gente.
    """
    if usuario.rol != "lider" or not usuario.area:
        return None

    equipo = db.query(User).filter(
        User.tenant_id == usuario.tenant_id,
        User.area.in_(supervision.areas_visibles(usuario)),
        User.activo.is_(True),
    ).all()
    ids_equipo = [u.id for u in equipo]

    area = {"area": usuario.area, "personas": len(equipo)}
    for aporte in aportes:
        if aporte.mi_area:
            area.update(aporte.mi_area(db, usuario, ids_equipo, momento))
    return area


def construir_inicio(db: Session, usuario: User) -> dict:
    aportes = _aportes(usuario)
    momento = base.ahora()

    respuesta = {
        "usuario": {
            "nombre": usuario.nombre,
            "rol": usuario.rol,
            "area": usuario.area,
        },
        "modulos": modulos_de(usuario),
    }

    # Cuántas cosas reclaman atención hoy. `total_urgente` es el número que
    # decide si la tarjeta de pendientes sale en rojo o en calma.
    urgentes = por_atender = 0
    for aporte in aportes:
        for tarjeta in aporte.pendientes:
            valor = tarjeta.calcular(db, usuario)
            respuesta[tarjeta.clave] = valor
            urgentes += tarjeta.urgentes(valor)
            por_atender += tarjeta.por_atender(valor)

    respuesta["total_urgente"] = urgentes
    respuesta["total_pendiente"] = por_atender
    respuesta["empresa"] = _resumen_empresa(db, usuario, aportes, momento)
    respuesta["mi_area"] = _mi_area(db, usuario, aportes, momento)
    return respuesta
