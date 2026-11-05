"""
Endpoints internos de Marcaciones.

Casi todo es de LECTURA: la pantalla muestra y descarga. Lo que llega del
reloj entra por `router_sincronizacion.py` con una clave propia. Lo único que
se escribe aquí es la justificación de una novedad (`PUT/DELETE
/justificacion`), con `solo_lectura_no` y el alcance de `permisos`: qué ve
cada quien lo decide `permisos.alcance_de`, antes de leer.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import solo_lectura_no
from app.core.dias_habiles import hoy
from app.core.modulos import contratado, requiere_modulo
from app.models.user import User
from app.modules.marcaciones import service
from app.modules.marcaciones.permisos import alcance_de
from app.modules.marcaciones.schemas import JustificacionIn

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


@router.put("/justificacion")
def justificar(
    datos: JustificacionIn,
    db: Session = Depends(get_db),
    usuario: User = Depends(solo_lectura_no),
    _: User = Depends(requiere_modulo("marcaciones")),
):
    """El motivo de una novedad de una persona un día. Repetirlo lo corrige; la novedad sigue contando."""
    return service.justificar(db, usuario, alcance_de(usuario), datos.emp_code, datos.fecha, datos.tipo, datos.texto)


@router.delete("/justificacion", status_code=204)
def quitar_justificacion(
    emp_code: str = Query(max_length=30),
    fecha: date = Query(),
    tipo: str = Query(max_length=30),
    db: Session = Depends(get_db),
    usuario: User = Depends(solo_lectura_no),
    _: User = Depends(requiere_modulo("marcaciones")),
):
    service.quitar_justificacion(db, usuario, alcance_de(usuario), emp_code, fecha, tipo)
    return Response(status_code=204)


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
