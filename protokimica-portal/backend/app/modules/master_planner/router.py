"""
Endpoints del módulo Master Planner.
Reutiliza disparar_webhook_n8n y guardar_archivo de PQRS: son
utilidades genéricas (no específicas de PQRS), y así evitamos
duplicar la misma lógica de subida de archivos y webhooks.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.deps import (
    get_current_user, get_current_tenant_id, solo_lectura_no, puede_comentar,
)
from app.models.user import User
from app.models.master_planner import (
    Proyecto, ProyectoArea, ItemPresupuesto, PagoItem, Tarea, TareaActualizacion,
    HistorialCambio,
)
from app.modules.master_planner.schemas import (
    ProyectoCreate, ProyectoUpdate, ProyectoOut,
    ItemPresupuestoCreate, ItemPresupuestoUpdate, ItemPresupuestoOut,
    AprobacionIn, PagoIn, PagoOut,
    TareaCreate, TareaUpdate, TareaOut, SubtareaCreate,
    TareaActualizacionOut, UsuarioAsignableOut, HistorialCambioOut,
)
from app.modules.master_planner.historial import (
    instantanea, registrar_cambios, registrar_evento,
)
from app.modules.master_planner.permisos import (
    aplicar_filtro_proyectos, puede_ver_proyecto, puede_ver_presupuesto, ve_todo, condicion_area,
    solo_aprueba_pagos, solo_registra_pagos, puede_cerrar_proyecto,
)
from app.modules.master_planner.resumen import construir_resumen
from app.modules.master_planner import cierre
from app.modules.master_planner.notificaciones import (
    avisar_tarea_asignada, avisar_proyecto_creado, avisar_proyecto_cerrado,
)
from app.modules.master_planner.outlook import (
    sincronizar_tarea, borrar_evento_de_tarea, borrar_evento_en_calendario_de,
    eventos_del_usuario,
)
from app.modules.pqrs.service import disparar_webhook_n8n, guardar_archivo

router = APIRouter(prefix="/master-planner", tags=["Master Planner"])


@router.get("/resumen")
def obtener_resumen(
    area: str | None = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """
    Resumen gerencial ya calculado: KPIs, presupuesto planeado vs ejecutado
    por área, semáforo y replanificaciones por proyecto, cumplimiento de
    fechas y carga por responsable. Se calcula aquí para que el número
    signifique lo mismo en pantalla que en cualquier reporte posterior.
    """
    return construir_resumen(db, tenant_id, current_user, area)


def _get_proyecto_o_404(
    db: Session, proyecto_id: int, tenant_id: int, usuario: User | None = None,
) -> Proyecto:
    proyecto = db.query(Proyecto).filter(
        Proyecto.id == proyecto_id, Proyecto.tenant_id == tenant_id,
    ).first()
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    # 404 y no 403 a propósito: un 403 confirmaría que el proyecto existe.
    if usuario is not None and not puede_ver_proyecto(db, proyecto, usuario):
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return proyecto


def _get_proyecto_presupuesto_o_404(
    db: Session, proyecto_id: int, tenant_id: int, usuario: User,
) -> Proyecto:
    """
    Como `_get_proyecto_o_404`, pero además exige permiso sobre el dinero:
    tener una tarea asignada en un proyecto ajeno no da acceso a su
    presupuesto.
    """
    proyecto = _get_proyecto_o_404(db, proyecto_id, tenant_id, usuario)
    if not puede_ver_presupuesto(proyecto, usuario):
        raise HTTPException(
            status_code=403,
            detail="No tienes acceso al presupuesto de un proyecto de otra área.",
        )
    return proyecto


def _get_item_presupuesto_o_404(
    db: Session, item_id: int, tenant_id: int, usuario: User | None = None,
) -> ItemPresupuesto:
    item = (
        db.query(ItemPresupuesto)
        .join(Proyecto, ItemPresupuesto.proyecto_id == Proyecto.id)
        .filter(ItemPresupuesto.id == item_id, Proyecto.tenant_id == tenant_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Ítem de presupuesto no encontrado.")
    if usuario is not None and not puede_ver_presupuesto(item.proyecto, usuario):
        raise HTTPException(status_code=404, detail="Ítem de presupuesto no encontrado.")
    return item


def _sincronizar_cierre(tarea: Tarea) -> None:
    """
    Mantiene `fecha_completada` alineada con el estado. Se sella al completar
    y se limpia si la tarea se reabre, para que el cumplimiento no quede
    midiendo contra un cierre que ya no existe.
    """
    if tarea.estado == "completada":
        if not tarea.fecha_completada:
            tarea.fecha_completada = datetime.now(timezone.utc)
    else:
        tarea.fecha_completada = None


def _get_tarea_o_404(
    db: Session, tarea_id: int, tenant_id: int, usuario: User | None = None,
) -> Tarea:
    tarea = (
        db.query(Tarea)
        .join(Proyecto, Tarea.proyecto_id == Proyecto.id)
        .filter(Tarea.id == tarea_id, Proyecto.tenant_id == tenant_id)
        .first()
    )
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    if usuario is not None and not puede_ver_proyecto(db, tarea.proyecto, usuario):
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    return tarea


def _sincronizar_areas(db: Session, proyecto: Proyecto, areas: list[str]) -> None:
    """
    Reemplaza las áreas participantes del proyecto. El área responsable no
    se duplica aquí: si viene en la lista, se descarta.
    """
    deseadas = {a for a in areas if a and a != proyecto.area}
    actuales = {a.area for a in proyecto.areas_extra}

    for extra in list(proyecto.areas_extra):
        if extra.area not in deseadas:
            proyecto.areas_extra.remove(extra)
    for area in deseadas - actuales:
        proyecto.areas_extra.append(ProyectoArea(area=area))


# ── Proyectos ───────────────────────────────────────────────────

@router.post("/proyectos", response_model=ProyectoOut, status_code=status.HTTP_201_CREATED)
def crear_proyecto(
    payload: ProyectoCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(solo_lectura_no),
):
    datos = payload.model_dump()
    areas = datos.pop("areas_participantes", None) or []

    # Sin líder, el proyecto no lo vería NADIE: desde que la visibilidad es
    # por participación personal, un proyecto sin líder y sin tareas queda
    # fuera de la lista de todo el mundo apenas se guarda. Quien lo crea
    # queda como líder hasta que se asigne a alguien más.
    if not datos.get("lider_id"):
        datos["lider_id"] = usuario.id

    proyecto = Proyecto(tenant_id=tenant_id, **datos)
    db.add(proyecto)
    _sincronizar_areas(db, proyecto, areas)
    db.commit()
    db.refresh(proyecto)

    avisar_proyecto_creado(db, proyecto)
    return proyecto


@router.get("/proyectos", response_model=list[ProyectoOut])
def listar_proyectos(
    estado: str | None = None,
    area: str | None = None,
    archivados: bool = False,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """
    Por defecto solo los proyectos activos; `archivados=true` devuelve el
    archivo. Siempre acotado a lo que el usuario tiene permitido ver.
    """
    query = (
        db.query(Proyecto)
        # El nombre del líder se lee de la relación al serializar: sin esto,
        # cada proyecto de la lista dispara su propia consulta.
        .options(selectinload(Proyecto.lider))
        .filter(
            Proyecto.tenant_id == tenant_id,
            Proyecto.archivado.is_(archivados),
        )
    )
    query = aplicar_filtro_proyectos(query, current_user)
    if estado:
        query = query.filter(Proyecto.estado == estado)
    if area:
        # Incluye los proyectos donde el área participa, no solo los que
        # lidera: si no, Mercadeo pierde de vista un proyecto de TICS en el
        # que trabaja apenas filtra por su propia área.
        query = query.filter(condicion_area(area))
    return query.order_by(Proyecto.creado_en.desc()).all()


@router.get("/proyectos/{proyecto_id}", response_model=ProyectoOut)
def obtener_proyecto(
    proyecto_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    return _get_proyecto_o_404(db, proyecto_id, tenant_id, current_user)


@router.patch("/proyectos/{proyecto_id}", response_model=ProyectoOut)
def actualizar_proyecto(
    proyecto_id: int,
    payload: ProyectoUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    proyecto = _get_proyecto_o_404(db, proyecto_id, tenant_id, current_user)
    antes = instantanea(proyecto, "proyecto")

    cambios = payload.model_dump(exclude_unset=True)
    areas = cambios.pop("areas_participantes", None)
    for campo, valor in cambios.items():
        setattr(proyecto, campo, valor)
    if areas is not None:
        _sincronizar_areas(db, proyecto, areas)
    if payload.estado == "cerrado" and not proyecto.fecha_fin_real:
        proyecto.fecha_fin_real = datetime.now(timezone.utc)

    registrar_cambios(
        db, "proyecto", proyecto.id, proyecto.id,
        antes, instantanea(proyecto, "proyecto"), current_user.id,
        entidad_nombre=proyecto.nombre,
    )
    db.commit()
    db.refresh(proyecto)
    return proyecto


@router.post("/proyectos/{proyecto_id}/cerrar")
async def cerrar_proyecto(
    proyecto_id: int,
    tipo: str = Form(...),                      # finalizado | cancelado
    entregables: str | None = Form(None),
    motivo: str | None = Form(None),
    observaciones: str | None = Form(None),
    evidencia: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    """
    Finaliza o cancela el proyecto dejando su acta.

    Los dos casos archivan el proyecto —sale de las vistas del día a día—
    pero no se borra nada: siempre se puede retomar.
    """
    proyecto = _get_proyecto_o_404(db, proyecto_id, tenant_id, current_user)

    if not puede_cerrar_proyecto(proyecto, current_user):
        raise HTTPException(
            status_code=403,
            detail=(
                "Solo el líder del proyecto o un administrador pueden cerrarlo. "
                "Pídele a quien lo lidera que lo haga."
            ),
        )

    ruta = await guardar_archivo(evidencia, "cierres") if evidencia is not None else None
    antes = instantanea(proyecto, "proyecto")

    try:
        acta = cierre.cerrar(
            proyecto, current_user, tipo,
            entregables=entregables, motivo=motivo,
            observaciones=observaciones, evidencia=ruta,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.add(acta)
    registrar_cambios(
        db, "proyecto", proyecto.id, proyecto.id,
        antes, instantanea(proyecto, "proyecto"), current_user.id,
        entidad_nombre=proyecto.nombre,
    )
    db.commit()
    db.refresh(acta)

    avisar_proyecto_cerrado(db, proyecto, acta)
    return cierre.acta_a_dict(acta)


@router.post("/proyectos/{proyecto_id}/retomar")
def retomar_proyecto(
    proyecto_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    """Vuelve a poner el proyecto en ejecución. El acta anterior queda anulada."""
    proyecto = _get_proyecto_o_404(db, proyecto_id, tenant_id, current_user)

    if not puede_cerrar_proyecto(proyecto, current_user):
        raise HTTPException(
            status_code=403,
            detail="Solo el líder del proyecto o un administrador pueden retomarlo.",
        )

    antes = instantanea(proyecto, "proyecto")
    try:
        cierre.retomar(proyecto, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    registrar_cambios(
        db, "proyecto", proyecto.id, proyecto.id,
        antes, instantanea(proyecto, "proyecto"), current_user.id,
        entidad_nombre=proyecto.nombre,
    )
    db.commit()
    db.refresh(proyecto)
    return {"mensaje": "El proyecto volvió a ejecución.", "estado": proyecto.estado}


@router.get("/proyectos/{proyecto_id}/cierres")
def historial_de_cierres(
    proyecto_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """
    Las actas del proyecto, la vigente primero. Normalmente hay una sola;
    hay varias cuando el proyecto se cerró, se retomó y se volvió a cerrar.
    """
    proyecto = _get_proyecto_o_404(db, proyecto_id, tenant_id, current_user)
    return [cierre.acta_a_dict(a) for a in proyecto.cierres]


@router.delete("/proyectos/{proyecto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_proyecto(
    proyecto_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    """
    Borrado definitivo, permitido solo si el proyecto no tiene tareas: la
    relación es en cascada y arrastraría tareas, actualizaciones y sus
    evidencias sin posibilidad de recuperarlas. Para sacar de circulación
    un proyecto con historial se usa `archivado` (PATCH /proyectos/{id}).
    """
    proyecto = _get_proyecto_o_404(db, proyecto_id, tenant_id, current_user)

    total_tareas = db.query(Tarea).filter(Tarea.proyecto_id == proyecto_id).count()
    if total_tareas:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"El proyecto tiene {total_tareas} tarea(s) y no se puede eliminar. "
                "Archívalo para sacarlo de la vista sin perder el historial, o "
                "elimina primero sus tareas."
            ),
        )

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
    current_user: User = Depends(solo_lectura_no),
):
    _get_proyecto_presupuesto_o_404(db, proyecto_id, tenant_id, current_user)
    item = ItemPresupuesto(proyecto_id=proyecto_id, **payload.model_dump())
    db.add(item)
    db.flush()  # necesitamos el id del ítem para dejarlo en el historial

    registrar_evento(
        db, "proyecto", proyecto_id, proyecto_id, "presupuesto_agregado",
        current_user.id, valor_nuevo=f"{item.concepto} · {item.valor_total:.0f}",
        entidad_nombre=item.proyecto.nombre,
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/presupuesto/{item_id}", response_model=ItemPresupuestoOut)
def actualizar_item_presupuesto(
    item_id: int,
    payload: ItemPresupuestoUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    """Se usa sobre todo para registrar el valor ejecutado (lo realmente gastado)."""
    item = _get_item_presupuesto_o_404(db, item_id, tenant_id, current_user)
    ejecutado_anterior = float(item.valor_ejecutado or 0)

    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(item, campo, valor)

    ejecutado_nuevo = float(item.valor_ejecutado or 0)
    if ejecutado_nuevo != ejecutado_anterior:
        registrar_evento(
            db, "proyecto", item.proyecto_id, item.proyecto_id, "presupuesto_ejecutado",
            current_user.id,
            valor_anterior=f"{item.concepto} · {ejecutado_anterior:.0f}",
            valor_nuevo=f"{item.concepto} · {ejecutado_nuevo:.0f}",
            entidad_nombre=item.proyecto.nombre,
        )

    db.commit()
    db.refresh(item)
    return item


@router.get("/proyectos/{proyecto_id}/presupuesto", response_model=list[ItemPresupuestoOut])
def listar_presupuesto(
    proyecto_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    _get_proyecto_presupuesto_o_404(db, proyecto_id, tenant_id, current_user)
    return (
        db.query(ItemPresupuesto)
        .filter(ItemPresupuesto.proyecto_id == proyecto_id)
        .order_by(ItemPresupuesto.creado_en.asc())
        .all()
    )


@router.patch("/presupuesto/{item_id}/aprobar", response_model=ItemPresupuestoOut)
def aprobar_item_presupuesto(
    item_id: int,
    payload: AprobacionIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_aprueba_pagos),
):
    """
    Administracion autoriza cuanto se puede desembolsar por este item.

    El valor aprobado no tiene que ser igual al planeado: se puede aprobar
    menos de lo presupuestado. Lo que no se admite es aprobar por debajo de
    lo que ya se pago, porque dejaria el item con un saldo negativo.
    """
    item = _get_item_presupuesto_o_404(db, item_id, tenant_id, current_user)

    if payload.valor_aprobado < 0:
        raise HTTPException(status_code=400, detail="El valor aprobado no puede ser negativo.")

    ya_pagado = item.valor_pagado
    if payload.valor_aprobado < ya_pagado:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No se puede aprobar {payload.valor_aprobado:,.0f} si ya se pagaron "
                f"{ya_pagado:,.0f}. Elimina primero los pagos que sobren."
            ),
        )

    anterior = float(item.valor_aprobado) if item.esta_aprobado else None
    item.valor_aprobado = payload.valor_aprobado
    item.aprobado_por = current_user.id
    item.aprobado_en = datetime.now(timezone.utc)
    item.nota_aprobacion = payload.nota

    registrar_evento(
        db, "proyecto", item.proyecto_id, item.proyecto_id,
        "presupuesto_aprobado", current_user.id,
        valor_anterior=(f"{item.concepto} · {anterior:.0f}" if anterior is not None else None),
        valor_nuevo=f"{item.concepto} · {payload.valor_aprobado:.0f}",
        entidad_nombre=item.proyecto.nombre,
    )
    db.commit()
    db.refresh(item)
    return item


@router.delete("/presupuesto/{item_id}/aprobar", response_model=ItemPresupuestoOut)
def revocar_aprobacion(
    item_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_aprueba_pagos),
):
    """Deja el item sin aprobar. No se puede si ya tiene pagos registrados."""
    item = _get_item_presupuesto_o_404(db, item_id, tenant_id, current_user)

    if item.pagos:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Este item ya tiene {len(item.pagos)} pago(s) registrados. "
                "Elimina los pagos antes de revocar la aprobacion."
            ),
        )

    anterior = float(item.valor_aprobado) if item.esta_aprobado else None
    item.valor_aprobado = None
    item.aprobado_por = None
    item.aprobado_en = None
    item.nota_aprobacion = None

    registrar_evento(
        db, "proyecto", item.proyecto_id, item.proyecto_id,
        "aprobacion_revocada", current_user.id,
        valor_anterior=(f"{item.concepto} · {anterior:.0f}" if anterior is not None else None),
        entidad_nombre=item.proyecto.nombre,
    )
    db.commit()
    db.refresh(item)
    return item


@router.post("/presupuesto/{item_id}/pagos", response_model=PagoOut,
             status_code=status.HTTP_201_CREATED)
async def registrar_pago(
    item_id: int,
    valor: float = Form(...),
    fecha: datetime | None = Form(None),
    concepto: str | None = Form(None),
    soporte: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_registra_pagos),
):
    """
    Tesoreria registra un abono contra un item ya aprobado.

    Se guardan los abonos uno por uno y no un total editable: los pagos
    reales van por partes (anticipo, contra entrega, saldo) y asi queda
    cuando se pago cada cosa y con que soporte.
    """
    item = _get_item_presupuesto_o_404(db, item_id, tenant_id, current_user)

    if not item.esta_aprobado:
        raise HTTPException(
            status_code=400,
            detail=(
                "Este item todavia no esta aprobado. Administracion tiene que "
                "aprobar el pago antes de que Tesoreria lo registre."
            ),
        )
    if valor <= 0:
        raise HTTPException(status_code=400, detail="El valor del pago tiene que ser mayor que cero.")

    pendiente = item.pendiente_de_pago
    if valor > pendiente + 1:  # un peso de tolerancia por decimales
        raise HTTPException(
            status_code=400,
            detail=(
                f"El pago de {valor:,.0f} supera lo que falta por pagar "
                f"({pendiente:,.0f}). Si el valor aprobado cambio, pidele a "
                "Administracion que lo actualice."
            ),
        )

    ruta = await guardar_archivo(soporte, "pagos") if soporte is not None else None

    pago = PagoItem(
        item_id=item.id,
        valor=valor,
        fecha=fecha or datetime.now(timezone.utc),
        concepto=concepto,
        soporte=ruta,
        registrado_por=current_user.id,
    )
    db.add(pago)
    db.flush()

    registrar_evento(
        db, "proyecto", item.proyecto_id, item.proyecto_id,
        "pago_registrado", current_user.id,
        valor_nuevo=f"{item.concepto} · {valor:.0f}",
        entidad_nombre=item.proyecto.nombre,
    )
    db.commit()
    db.refresh(pago)
    return pago


@router.delete("/pagos/{pago_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_pago(
    pago_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_registra_pagos),
):
    """Anula un abono mal registrado. Queda en el historial del proyecto."""
    pago = (
        db.query(PagoItem)
        .join(ItemPresupuesto, PagoItem.item_id == ItemPresupuesto.id)
        .join(Proyecto, ItemPresupuesto.proyecto_id == Proyecto.id)
        .filter(PagoItem.id == pago_id, Proyecto.tenant_id == tenant_id)
        .first()
    )
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado.")

    registrar_evento(
        db, "proyecto", pago.item.proyecto_id, pago.item.proyecto_id,
        "pago_anulado", current_user.id,
        valor_anterior=f"{pago.item.concepto} · {float(pago.valor):.0f}",
        entidad_nombre=pago.item.proyecto.nombre,
    )
    db.delete(pago)
    db.commit()


@router.delete("/presupuesto/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_item_presupuesto(
    item_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    item = _get_item_presupuesto_o_404(db, item_id, tenant_id, current_user)

    # Borrar un item con pagos borraria el rastro de una plata que ya salio.
    if item.pagos:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Este item tiene {len(item.pagos)} pago(s) registrados por "
                f"{item.valor_pagado:,.0f}. No se puede eliminar sin borrar antes "
                "esos pagos."
            ),
        )

    registrar_evento(
        db, "proyecto", item.proyecto_id, item.proyecto_id, "presupuesto_eliminado",
        current_user.id, valor_anterior=f"{item.concepto} · {item.valor_total:.0f}",
        entidad_nombre=item.proyecto.nombre,
    )
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


@router.get("/tareas-vencidas-por-persona")
def tareas_vencidas_por_persona(
    incluir_por_vencer: int = 3,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """
    Las tareas vencidas de cada persona, con su correo y solo las suyas.

    Lo consume el resumen semanal. `incluir_por_vencer` agrega las que vencen
    dentro de esos días: avisar antes de que se venza sirve para actuar;
    avisar después solo sirve para reclamar.

    Se salta los proyectos archivados: un proyecto cerrado o cancelado no
    puede seguir generando pendientes a nadie.
    """
    ahora = datetime.now(timezone.utc)
    limite = ahora + timedelta(days=incluir_por_vencer)

    tareas = (
        db.query(Tarea)
        .join(Proyecto, Tarea.proyecto_id == Proyecto.id)
        .filter(
            Proyecto.tenant_id == tenant_id,
            Proyecto.archivado.is_(False),
            Tarea.asignado_a.isnot(None),
            Tarea.estado != "completada",
            Tarea.fecha_fin.isnot(None),
        )
        .all()
    )

    por_persona: dict[int, list] = {}
    for t in tareas:
        fin = t.fecha_fin if t.fecha_fin.tzinfo else t.fecha_fin.replace(tzinfo=timezone.utc)
        if fin > limite:
            continue
        por_persona.setdefault(t.asignado_a, []).append({
            "tarea_id": t.id,
            "titulo": t.titulo,
            "proyecto": t.proyecto.nombre,
            "prioridad": t.prioridad,
            "estado": t.estado,
            "avance_pct": t.avance_pct,
            "fecha_fin": fin.isoformat(),
            "dias": (fin.date() - ahora.date()).days,   # negativo = vencida
            "vencida": fin < ahora,
        })

    destinatarios = []
    for usuario_id, fichas in por_persona.items():
        usuario = db.get(User, usuario_id)
        if not usuario or not usuario.email or not usuario.activo:
            continue
        fichas.sort(key=lambda f: f["dias"])
        destinatarios.append({
            "email": usuario.email,
            "nombre": usuario.nombre,
            "vencidas": sum(1 for f in fichas if f["vencida"]),
            "por_vencer": sum(1 for f in fichas if not f["vencida"]),
            "tareas": fichas,
        })

    destinatarios.sort(key=lambda d: (-d["vencidas"], -d["por_vencer"]))
    return {
        "generado_en": ahora.isoformat(),
        "total_personas": len(destinatarios),
        "destinatarios": destinatarios,
    }


@router.get("/calendario/outlook")
def mi_calendario_de_outlook(
    desde: str,
    hasta: str,
    current_user: User = Depends(get_current_user),
):
    """
    Los eventos de Outlook de QUIEN PIDE, para pintarlos junto a las tareas.

    Siempre el calendario propio: no recibe un usuario por parámetro a
    propósito. Poder consultar el de otro convertiría el portal en una
    ventana a la agenda personal de los compañeros, y el permiso de
    aplicación que tiene el backend no pondría ninguna objeción.

    `desde` y `hasta` van en ISO 8601 (2026-08-01T00:00:00).
    """
    return eventos_del_usuario(current_user.email, desde, hasta)


@router.get("/tareas", response_model=list[TareaOut])
def listar_todas_las_tareas(
    estado: str | None = None,
    area: str | None = None,
    proyecto_id: int | None = None,
    incluir_subtareas: bool = False,
    incluir_archivados: bool = False,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """
    Tablero global: tareas de los proyectos activos que el usuario puede ver.
    Las subtareas quedan fuera por defecto — viven dentro de su tarea
    padre como checklist, no como tarjetas sueltas del Kanban.
    """
    query = (
        db.query(Tarea)
        .join(Proyecto, Tarea.proyecto_id == Proyecto.id)
        .filter(Proyecto.tenant_id == tenant_id)
    )
    query = aplicar_filtro_proyectos(query, current_user)
    if not incluir_archivados:
        query = query.filter(Proyecto.archivado.is_(False))
    if not incluir_subtareas:
        query = query.filter(Tarea.parent_id.is_(None))
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
    current_user: User = Depends(solo_lectura_no),
):
    proyecto = _get_proyecto_o_404(db, proyecto_id, tenant_id, current_user)
    tarea = Tarea(proyecto_id=proyecto_id, **payload.model_dump())
    db.add(tarea)
    db.commit()
    db.refresh(tarea)

    if tarea.asignado_a:
        avisar_tarea_asignada(db, tarea, proyecto.nombre)

    sincronizar_tarea(db, tarea, proyecto.nombre)
    return tarea


@router.get("/proyectos/{proyecto_id}/tareas", response_model=list[TareaOut])
def listar_tareas_de_proyecto(
    proyecto_id: int,
    incluir_subtareas: bool = False,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    _get_proyecto_o_404(db, proyecto_id, tenant_id, current_user)
    query = db.query(Tarea).filter(Tarea.proyecto_id == proyecto_id)
    if not incluir_subtareas:
        query = query.filter(Tarea.parent_id.is_(None))
    return query.order_by(Tarea.creado_en.asc()).all()


@router.post(
    "/tareas/{tarea_id}/subtareas",
    response_model=TareaOut, status_code=status.HTTP_201_CREATED,
)
def crear_subtarea(
    tarea_id: int,
    payload: SubtareaCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    """
    Crea una subtarea colgando de `tarea_id`. Hereda el proyecto del padre
    y se limita a un nivel: una subtarea no puede tener subtareas, para que
    el checklist no se convierta en un árbol imposible de leer.
    """
    padre = _get_tarea_o_404(db, tarea_id, tenant_id, current_user)
    if padre.parent_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Una subtarea no puede tener subtareas. Solo se admite un nivel.",
        )

    subtarea = Tarea(
        proyecto_id=padre.proyecto_id,
        parent_id=padre.id,
        area=padre.area,
        **payload.model_dump(),
    )
    db.add(subtarea)
    db.commit()
    db.refresh(subtarea)

    if subtarea.asignado_a:
        avisar_tarea_asignada(db, subtarea, padre.proyecto.nombre)

    return subtarea


@router.get("/tareas/mias", response_model=list[TareaOut])
def listar_mis_tareas(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """
    Tareas asignadas al usuario logueado en cualquier proyecto activo.
    Aquí sí entran las subtareas: si alguien es responsable de una, tiene
    que verla en su lista aunque en el tablero viva dentro de su padre.
    """
    return (
        db.query(Tarea)
        .join(Proyecto, Tarea.proyecto_id == Proyecto.id)
        .filter(
            Proyecto.tenant_id == tenant_id,
            Proyecto.archivado.is_(False),
            Tarea.asignado_a == current_user.id,
        )
        .order_by(Tarea.fecha_fin.asc().nullslast())
        .all()
    )


@router.get("/tareas/{tarea_id}", response_model=TareaOut)
def obtener_tarea(
    tarea_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """
    Una tarea sola, con sus subtareas. Lo usa el detalle del frontend para
    releer del servidor tras cada cambio en vez de arrastrar una copia que
    se queda desactualizada. Va después de /tareas/mias a propósito: FastAPI
    resuelve por orden de declaración y "mias" tiene que ganar.
    """
    return _get_tarea_o_404(db, tarea_id, tenant_id, current_user)


@router.patch("/tareas/{tarea_id}", response_model=TareaOut)
def actualizar_tarea(
    tarea_id: int,
    payload: TareaUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    tarea = _get_tarea_o_404(db, tarea_id, tenant_id, current_user)
    asignado_anterior = tarea.asignado_a
    antes = instantanea(tarea, "tarea")

    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(tarea, campo, valor)

    _sincronizar_cierre(tarea)
    registrar_cambios(
        db, "tarea", tarea.id, tarea.proyecto_id,
        antes, instantanea(tarea, "tarea"), current_user.id,
        entidad_nombre=tarea.titulo,
    )
    db.commit()
    db.refresh(tarea)

    if tarea.asignado_a and tarea.asignado_a != asignado_anterior:
        avisar_tarea_asignada(db, tarea, tarea.proyecto.nombre)

    # Si cambió de responsable, el evento viejo queda en el calendario del
    # anterior: hay que quitarlo de ahí antes de crear el nuevo.
    if asignado_anterior and tarea.asignado_a != asignado_anterior and tarea.outlook_evento_id:
        borrar_evento_en_calendario_de(db, asignado_anterior, tarea.outlook_evento_id)
        tarea.outlook_evento_id = None
        db.commit()

    sincronizar_tarea(db, tarea, tarea.proyecto.nombre)
    return tarea


@router.delete("/tareas/{tarea_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_tarea(
    tarea_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    tarea = _get_tarea_o_404(db, tarea_id, tenant_id, current_user)
    # Antes del delete: después ya no se sabe de quién era ni qué evento tenía.
    borrar_evento_de_tarea(db, tarea)
    db.delete(tarea)
    db.commit()


# ── Historial de cambios ────────────────────────────────────────

@router.get("/proyectos/{proyecto_id}/historial", response_model=list[HistorialCambioOut])
def historial_de_proyecto(
    proyecto_id: int,
    solo_proyecto: bool = False,
    limite: int = 200,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """
    Historial del proyecto y, por defecto, también el de sus tareas — que es
    como gerencia quiere leerlo: una sola línea de tiempo de todo lo que se
    movió. Con `solo_proyecto=true` se limita a los cambios del proyecto.
    """
    _get_proyecto_o_404(db, proyecto_id, tenant_id, current_user)
    query = db.query(HistorialCambio).filter(HistorialCambio.proyecto_id == proyecto_id)
    if solo_proyecto:
        query = query.filter(HistorialCambio.entidad == "proyecto")
    return query.order_by(HistorialCambio.fecha.desc()).limit(limite).all()


@router.get("/tareas/{tarea_id}/historial", response_model=list[HistorialCambioOut])
def historial_de_tarea(
    tarea_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    _get_tarea_o_404(db, tarea_id, tenant_id, current_user)
    return (
        db.query(HistorialCambio)
        .filter(HistorialCambio.entidad == "tarea", HistorialCambio.entidad_id == tarea_id)
        .order_by(HistorialCambio.fecha.desc())
        .all()
    )


@router.get("/historial", response_model=list[HistorialCambioOut])
def historial_general(
    campo: str | None = None,
    limite: int = 100,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Actividad reciente de los proyectos que el usuario puede ver."""
    query = (
        db.query(HistorialCambio)
        .join(Proyecto, HistorialCambio.proyecto_id == Proyecto.id)
        .filter(Proyecto.tenant_id == tenant_id, Proyecto.archivado.is_(False))
    )
    query = aplicar_filtro_proyectos(query, current_user)
    if campo:
        query = query.filter(HistorialCambio.campo == campo)
    return query.order_by(HistorialCambio.fecha.desc()).limit(limite).all()


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
    current_user: User = Depends(puede_comentar),
):
    tarea = _get_tarea_o_404(db, tarea_id, tenant_id, current_user)

    # Gerencia puede dejar comentarios, pero mover el avance es planeacion y
    # su rol es de consulta.
    if avance_pct_nuevo is not None and current_user.rol == "gerencia":
        raise HTTPException(
            status_code=403,
            detail="Tu usuario puede comentar, pero no modificar el avance de una tarea.",
        )

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
        antes = instantanea(tarea, "tarea")
        tarea.avance_pct = avance_pct_nuevo
        if avance_pct_nuevo >= 100:
            tarea.estado = "completada"
        _sincronizar_cierre(tarea)
        # También pasa por el historial: llegar al 100% desde aquí mueve el
        # estado igual que hacerlo a mano, y gerencia tiene que verlo igual.
        registrar_cambios(
            db, "tarea", tarea.id, tarea.proyecto_id,
            antes, instantanea(tarea, "tarea"), current_user.id,
            entidad_nombre=tarea.titulo,
        )

    db.commit()
    db.refresh(actualizacion)
    return actualizacion


@router.get("/tareas/{tarea_id}/actualizaciones", response_model=list[TareaActualizacionOut])
def listar_actualizaciones(
    tarea_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    _get_tarea_o_404(db, tarea_id, tenant_id, current_user)
    return (
        db.query(TareaActualizacion)
        .filter(TareaActualizacion.tarea_id == tarea_id)
        .order_by(TareaActualizacion.fecha.desc())
        .all()
    )
