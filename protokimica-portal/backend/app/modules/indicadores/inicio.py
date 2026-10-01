"""
Lo que Indicadores le aporta a la página de Inicio: lo que falta registrar
del último mes cerrado, y cuántos están en rojo en el titular de la empresa.
Ver `core/inicio.py`.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.core import inicio as base
from app.core import supervision
from app.core.modulos import modulos_de, ve_todos_los_indicadores
from app.models.indicadores import Indicador
from app.models.user import User
from app.modules.indicadores import service as ind_service


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
        query = query.filter(supervision.condicion_area(Indicador.area, usuario))

    pendientes = []
    for ind in query.all():
        tiene = any(m.anio == anio and m.mes == mes and m.valor is not None
                    for m in ind.mediciones)
        if not tiene:
            pendientes.append({
                "id": ind.id, "nombre": ind.nombre, "area": ind.area,
                "anio": anio, "mes": mes,
            })
    return pendientes[:base.TOPE_LISTA]


def _titular(db: Session, usuario: User, momento: datetime) -> dict:
    if "indicadores" not in modulos_de(usuario):
        # La tarjeta se pinta igual, sin cifra: quien no entra al módulo no
        # tiene por qué ver cuántos están en rojo.
        return {"indicadores_en_rojo": None}

    resumen = {}
    anio, mes = ind_service.periodo_por_defecto()
    areas = None if ve_todos_los_indicadores(usuario) else supervision.areas_visibles(usuario)
    tablero = ind_service.construir_tablero(db, usuario.tenant_id, anio, mes, areas=areas)
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
        db, usuario.tenant_id, anio_ant, mes_ant, areas=areas)
    resumen["indicadores_rojo_anterior"] = tablero_ant["resumen"]["rojo"]
    resumen["periodo_anterior"] = base.MESES_CORTOS[mes_ant - 1].lower()
    return resumen


APORTE = base.AporteInicio(
    pendientes=(
        base.Pendientes(
            clave="indicadores_por_registrar", calcular=_indicadores_por_registrar,
            # Lo que falta registrar no es urgente —no tiene un plazo que ya
            # pasó—, pero sí es trabajo pendiente.
            por_atender=len,
        ),
    ),
    titular=_titular,
)
