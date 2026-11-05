"""
Endpoints internos de Marcaciones.

Todo es de LECTURA: la pantalla muestra y descarga, no escribe. Lo que llega
del reloj entra por `router_sincronizacion.py` con una clave propia. Por eso
aquí no hay `solo_lectura_no`: no hay nada que un rol de solo lectura pueda
romper, y qué ve cada quien lo decide `permisos.alcance_de`, antes de leer.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dias_habiles import hoy
from app.core.modulos import contratado, requiere_modulo
from app.models.user import User
from app.modules.marcaciones import service
from app.modules.marcaciones.permisos import alcance_de

router = APIRouter(
    prefix="/marcaciones", tags=["Marcaciones"],
    dependencies=[Depends(contratado("marcaciones"))],
)


@router.get("/dia")
def dia(
    fecha: date | None = None,
    area: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
    usuario: User = Depends(requiere_modulo("marcaciones")),
):
    """
    Qué pasa con cada persona un día: dónde está, qué turno tiene, qué marcó y
    qué novedades lleva, más los totales por área y por líder. Sin `fecha`, hoy.
    La pantalla lo vuelve a pedir cada pocos segundos para verse en vivo.
    """
    return service.dia(db, usuario.tenant_id, alcance_de(usuario), fecha or hoy(), area)


@router.get("/estado")
def estado(
    db: Session = Depends(get_db),
    usuario: User = Depends(requiere_modulo("marcaciones")),
):
    """Si el script del reloj está mandando datos: lo que se ve puede estar atrasado si no."""
    return service.estado(db, usuario.tenant_id)


@router.get("/persona/{emp_code}")
def persona(
    emp_code: str,
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    usuario: User = Depends(requiere_modulo("marcaciones")),
):
    """El detalle de una persona, día por día. Por defecto, los últimos 14 días."""
    hasta = hasta or hoy()
    desde = desde or hasta - timedelta(days=13)
    return service.persona(db, usuario.tenant_id, alcance_de(usuario), emp_code, desde, hasta)


@router.get("/informe")
def informe(
    desde: date,
    hasta: date,
    area: str | None = Query(None, max_length=100),
    emp_code: str | None = Query(None, max_length=30),
    solo_novedades: bool = False,
    db: Session = Depends(get_db),
    usuario: User = Depends(requiere_modulo("marcaciones")),
):
    """El informe de un rango (hasta 93 días): totales, por área, por persona y día a día."""
    return service.informe(db, usuario.tenant_id, alcance_de(usuario), desde, hasta, area, emp_code, solo_novedades)


@router.get("/informe.csv")
def informe_csv(
    desde: date,
    hasta: date,
    area: str | None = Query(None, max_length=100),
    emp_code: str | None = Query(None, max_length=30),
    solo_novedades: bool = False,
    db: Session = Depends(get_db),
    usuario: User = Depends(requiere_modulo("marcaciones")),
):
    """El mismo informe como CSV (una fila por persona y día), con el alcance de quien lo pide."""
    datos = service.informe(db, usuario.tenant_id, alcance_de(usuario), desde, hasta, area, emp_code, solo_novedades)
    return Response(
        content=service.informe_csv(datos),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="marcaciones_{desde}_{hasta}.csv"'},
    )
