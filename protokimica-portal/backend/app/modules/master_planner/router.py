"""
Endpoints del módulo Master Planner.
Reutiliza disparar_webhook_n8n y guardar_archivo de PQRS: son
utilidades genéricas (no específicas de PQRS), y así evitamos
duplicar la misma lógica de subida de archivos y webhooks.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_tenant_id, solo_lectura_no
from app.models.user import User
from app.models.master_planner import Proyecto, ItemPresupuesto, Tarea, TareaActualizacion
from app.modules.master_planner.schemas import (
    ProyectoCreate, ProyectoUpdate, ProyectoOut,
    ItemPresupuestoCreate, ItemPresupuestoOut,
    TareaCreate, TareaUpdate, TareaOut,
    TareaActualizacionOut, UsuarioAsignableOut,
)
from app.modules.pqrs.service import disparar_webhook_n8n, guardar_archivo

router = APIRouter(prefix="/master-planner", tags=["Master Planner"])


def _get_proyecto_o_404(db: Session, proyecto_id: int, tenant_id: int) -> Proyecto:
    proyecto = db.query(Proyecto).filter(
        Proyecto.id == proyecto_id, Proyecto.tenant_id == tenant_id,
    ).first()
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return proyecto


def _get_tarea_o_404(db: Session, tarea_id: int, tenant_id: int) -> Tarea:
    tarea = (
        db.query(Tarea)
        .join(Proyecto, Tarea.proyecto_id == Proyecto.id)
        .filter(Tarea.id == tarea_id, Proyecto.tenant_id == tenant_id)
        .first()
    )
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    return tarea


# ── Proyectos ───────────────────────────────────────────────────

@router.post("/proyectos", response_model=ProyectoOut, status_code=status.HTTP_201_CREATED)
def crear_proyecto(
    payload: ProyectoCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    proyecto = Proyecto(tenant_id=tenant_id, **payload.model_dump())
    db.add(proyecto)
    db.commit()
    db.refresh(proyecto)
    return proyecto


@router.get("/proyectos", response_model=list[ProyectoOut])
def listar_proyectos(
    estado: str | None = None,
    area: str | None = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    query = db.query(Proyecto).filter(Proyecto.tenant_id == tenant_id)
    if estado:
        query = query.filter(Proyecto.estado == estado)
    if area:
        query = query.filter(Proyecto.area == area)
    return query.order_by(Proyecto.creado_en.desc()).all()


@router.get("/proyectos/{proyecto_id}", response_model=ProyectoOut)
def obtener_proyecto(
    proyecto_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return _get_proyecto_o_404(db, proyecto_id, tenant_id)


@router.patch("/proyectos/{proyecto_id}", response_model=ProyectoOut)
def actualizar_proyecto(
    proyecto_id: int,
    payload: ProyectoUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    proyecto = _get_proyecto_o_404(db, proyecto_id, tenant_id)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(proyecto, campo, valor)
    if payload.estado == "cerrado" and not proyecto.fecha_fin_real:
        proyecto.fecha_fin_real = datetime.now(timezone.utc)
    db.commit()
    db.refresh(proyecto)
    return proyecto


@router.delete("/proyectos/{proyecto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_proyecto(
    proyecto_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    proyecto = _get_proyecto_o_404(db, proyecto_id, tenant_id)
    db.delete(proyecto)
    db.commit()


# ── Presupuesto ─────────────────────────────────────────────────

@router.post(
    "/proyectos/{proyecto_id}/presupuesto",
    response_model=ItemPresupuestoOut, status_code=status.HTTP_201_CREATED,
)
def agregar_item_presupuesto(
    proyecto_id: int,
    payload: ItemPresupuestoCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    _get_proyecto_o_404(db, proyecto_id, tenant_id)
    item = ItemPresupuesto(proyecto_id=proyecto_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/proyectos/{proyecto_id}/presupuesto", response_model=list[ItemPresupuestoOut])
def listar_presupuesto(
    proyecto_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    _get_proyecto_o_404(db, proyecto_id, tenant_id)
    return (
        db.query(ItemPresupuesto)
        .filter(ItemPresupuesto.proyecto_id == proyecto_id)
        .order_by(ItemPresupuesto.creado_en.asc())
        .all()
    )


@router.delete("/presupuesto/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_item_presupuesto(
    item_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    item = (
        db.query(ItemPresupuesto)
        .join(Proyecto, ItemPresupuesto.proyecto_id == Proyecto.id)
        .filter(ItemPresupuesto.id == item_id, Proyecto.tenant_id == tenant_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Ítem de presupuesto no encontrado.")
    db.delete(item)
    db.commit()


# ── Tareas ──────────────────────────────────────────────────────

@router.get("/usuarios-asignables", response_model=list[UsuarioAsignableOut])
def listar_usuarios_asignables(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """
    Lista liviana (id, nombre, área) de usuarios activos del tenant,
    para poblar dropdowns de asignación (líder de proyecto, asignado
    de tarea). A diferencia de GET /usuarios (solo admin), este queda
    disponible para cualquier usuario autenticado: cualquier rol
    puede necesitar asignar una tarea a un compañero.
    """
    return (
        db.query(User)
        .filter(User.tenant_id == tenant_id, User.activo == True)
        .order_by(User.nombre)
        .all()
    )


@router.get("/tareas", response_model=list[TareaOut])
def listar_todas_las_tareas(
    estado: str | None = None,
    area: str | None = None,
    proyecto_id: int | None = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Tablero global: todas las tareas de todos los proyectos del tenant."""
    query = (
        db.query(Tarea)
        .join(Proyecto, Tarea.proyecto_id == Proyecto.id)
        .filter(Proyecto.tenant_id == tenant_id)
    )
    if estado:
        query = query.filter(Tarea.estado == estado)
    if area:
        query = query.filter(Tarea.area == area)
    if proyecto_id:
        query = query.filter(Tarea.proyecto_id == proyecto_id)
    return query.order_by(Tarea.creado_en.desc()).all()


@router.post(
    "/proyectos/{proyecto_id}/tareas",
    response_model=TareaOut, status_code=status.HTTP_201_CREATED,
)
def crear_tarea(
    proyecto_id: int,
    payload: TareaCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    proyecto = _get_proyecto_o_404(db, proyecto_id, tenant_id)
    tarea = Tarea(proyecto_id=proyecto_id, **payload.model_dump())
    db.add(tarea)
    db.commit()
    db.refresh(tarea)

    if tarea.asignado_a:
        disparar_webhook_n8n("mp-tarea-asignada", {
            "tarea_id": tarea.id,
            "titulo": tarea.titulo,
            "proyecto": proyecto.nombre,
            "asignado_a": tarea.asignado_a,
        })

    return tarea


@router.get("/proyectos/{proyecto_id}/tareas", response_model=list[TareaOut])
def listar_tareas_de_proyecto(
    proyecto_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    _get_proyecto_o_404(db, proyecto_id, tenant_id)
    return (
        db.query(Tarea)
        .filter(Tarea.proyecto_id == proyecto_id)
        .order_by(Tarea.creado_en.asc())
        .all()
    )


@router.get("/tareas/mias", response_model=list[TareaOut])
def listar_mis_tareas(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Tareas asignadas al usuario logueado, en cualquier proyecto del tenant."""
    return (
        db.query(Tarea)
        .join(Proyecto, Tarea.proyecto_id == Proyecto.id)
        .filter(Proyecto.tenant_id == tenant_id, Tarea.asignado_a == current_user.id)
        .order_by(Tarea.fecha_fin.asc().nullslast())
        .all()
    )


@router.patch("/tareas/{tarea_id}", response_model=TareaOut)
def actualizar_tarea(
    tarea_id: int,
    payload: TareaUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    tarea = _get_tarea_o_404(db, tarea_id, tenant_id)
    asignado_anterior = tarea.asignado_a

    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(tarea, campo, valor)
    db.commit()
    db.refresh(tarea)

    if tarea.asignado_a and tarea.asignado_a != asignado_anterior:
        disparar_webhook_n8n("mp-tarea-asignada", {
            "tarea_id": tarea.id,
            "titulo": tarea.titulo,
            "proyecto": tarea.proyecto.nombre,
            "asignado_a": tarea.asignado_a,
        })

    return tarea


@router.delete("/tareas/{tarea_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_tarea(
    tarea_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    tarea = _get_tarea_o_404(db, tarea_id, tenant_id)
    db.delete(tarea)
    db.commit()


# ── Línea de tiempo de actualizaciones (reemplaza el log del Excel) ──

@router.post(
    "/tareas/{tarea_id}/actualizaciones",
    response_model=TareaActualizacionOut, status_code=status.HTTP_201_CREATED,
)
async def agregar_actualizacion(
    tarea_id: int,
    comentario: str | None = Form(None),
    avance_pct_nuevo: int | None = Form(None),
    evidencia: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    tarea = _get_tarea_o_404(db, tarea_id, tenant_id)

    if avance_pct_nuevo is not None and not (0 <= avance_pct_nuevo <= 100):
        raise HTTPException(status_code=400, detail="avance_pct_nuevo debe estar entre 0 y 100.")

    ruta_evidencia = None
    if evidencia is not None:
        ruta_evidencia = await guardar_archivo(evidencia, "mp-evidencias")

    actualizacion = TareaActualizacion(
        tarea_id=tarea_id,
        usuario_id=current_user.id,
        comentario=comentario,
        avance_pct_nuevo=avance_pct_nuevo,
        adjunto_evidencia=ruta_evidencia,
    )
    db.add(actualizacion)

    if avance_pct_nuevo is not None:
        tarea.avance_pct = avance_pct_nuevo
        if avance_pct_nuevo >= 100:
            tarea.estado = "completada"

    db.commit()
    db.refresh(actualizacion)
    return actualizacion


@router.get("/tareas/{tarea_id}/actualizaciones", response_model=list[TareaActualizacionOut])
def listar_actualizaciones(
    tarea_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    _get_tarea_o_404(db, tarea_id, tenant_id)
    return (
        db.query(TareaActualizacion)
        .filter(TareaActualizacion.tarea_id == tarea_id)
        .order_by(TareaActualizacion.fecha.desc())
        .all()
    )
