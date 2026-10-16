"""
Una PQRS como origen de una OMP. Ver `core/origenes_omp.py`.

La OMP arranca con lo que ya se sabe del caso: el radicado, lo que el
cliente contó y el área CAUSANTE —la que tiene que cambiar algo—, no la
responsable, que es quien gestionó la PQRS.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.origenes_omp import PropuestaOMP
from app.models.pqrs import PQRSAsociado
from app.models.user import User
from app.modules.pqrs.permisos import obtener_visible


def _propuesta(db: Session, tenant_id: int, pqrs_id: int, usuario: User) -> PropuestaOMP | None:
    # Una PQRS fuera de su alcance (los puntos de venta) no existe para
    # esta persona: tampoco como origen de una OMP.
    try:
        pqrs = obtener_visible(db, tenant_id, pqrs_id, usuario)
    except HTTPException:
        return None

    asociado = db.get(PQRSAsociado, pqrs.asociado_id) if pqrs.asociado_id else None
    radicado = pqrs.codigo_seguimiento or f"#{pqrs.id}"
    causa = asociado.nombre if asociado else "sin causa marcada"
    return PropuestaOMP(
        referencia=f"PQRS {radicado}",
        titulo=f"{causa} — PQRS {radicado}",
        descripcion=pqrs.descripcion or "",
        area=pqrs.area_causante,
        sugiere=bool(asociado and asociado.sugiere_omp),
        motivo=(f"La causa «{asociado.nombre}» está marcada para volverse OMP."
                if asociado and asociado.sugiere_omp else None),
    )


ORIGENES = {"pqrs": _propuesta}
