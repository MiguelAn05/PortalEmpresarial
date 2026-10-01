"""
Lo que PQRS le aporta a la página de Inicio: las solicitudes de la persona
y las cifras de atención en el titular de la empresa. Ver `core/inicio.py`.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core import inicio as base
from app.core.fechas import con_zona
from app.models.pqrs import PQRSSolicitud
from app.models.user import User
from app.modules.pqrs.pendientes import ESTADOS_ABIERTOS as ESTADOS_CON_PLAZO


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

    ahora = base.ahora()
    limite = ahora + timedelta(days=base.DIAS_AVISO)
    vencidas, por_vencer = [], []

    for p in solicitudes:
        # Una resuelta ya no corre contra el reloj: la respuesta salió y solo
        # falta que el cliente la confirme. Sin esto le aparecía al agente
        # como vencida, que es un pendiente que ya no existe. La regla es la
        # del módulo (`pendientes.ESTADOS_ABIERTOS`), no una copia local.
        if p.estado not in ESTADOS_CON_PLAZO:
            continue
        sla = con_zona(p.fecha_limite_sla)
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

    vencidas.sort(key=lambda x: con_zona(x["fecha_limite_sla"]))
    por_vencer.sort(key=lambda x: con_zona(x["fecha_limite_sla"]))

    return base.bandeja(vencidas, por_vencer, abiertas=len(solicitudes))


def _titular(db: Session, usuario: User, momento: datetime) -> dict:
    pqrs_abiertas = (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.tenant_id == usuario.tenant_id,
                PQRSSolicitud.estado != "cerrado")
        .count()
    )

    # Un cero de PQRS abiertas no dice si el equipo trabajó o si nadie
    # escribió. Lo que se cerró este mes sí.
    pqrs_cerradas_mes = (
        db.query(PQRSSolicitud)
        .filter(PQRSSolicitud.tenant_id == usuario.tenant_id,
                PQRSSolicitud.estado == "cerrado",
                PQRSSolicitud.fecha_cierre.isnot(None),
                PQRSSolicitud.fecha_cierre >= base.inicio_del_mes(momento))
        .count()
    )
    return {"pqrs_abiertas": pqrs_abiertas, "pqrs_cerradas_mes": pqrs_cerradas_mes}


APORTE = base.AporteInicio(
    pendientes=(
        base.Pendientes(
            clave="mis_pqrs", calcular=_mis_pqrs,
            urgentes=base.urgentes_de_bandeja, por_atender=base.por_atender_de_bandeja,
        ),
    ),
    titular=_titular,
)
