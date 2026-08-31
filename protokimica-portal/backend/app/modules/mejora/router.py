"""
Endpoints de Oportunidades de Mejora (OMP).

`requiere_modulo("mejora")` va en TODOS, incluidas las lecturas: esconder el
botón en el menú es cortesía, no seguridad. Y el filtro por área se impone
aquí, no en el frontend — mandar otro `?area=` no abre nada.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_tenant_id, solo_lectura_no
from app.core.modulos import requiere_modulo
from app.models.mejora import AccionMejora, Oportunidad
from app.models.user import User
from app.modules.mejora import permisos, service
from app.modules.mejora.schemas import (
    AccionActualizar, AccionCrear, AccionOut, CambioEstado, OportunidadActualizar,
    OportunidadCrear, OportunidadDetalleOut, OportunidadOut, Verificacion,
)

router = APIRouter(
    prefix="/mejora", tags=["Oportunidades de mejora"],
    dependencies=[Depends(requiere_modulo("mejora"))],
)


def _buscar(db: Session, omp_id: int, tenant_id: int, usuario: User) -> Oportunidad:
    oportunidad = (
        db.query(Oportunidad)
        .filter(Oportunidad.id == omp_id, Oportunidad.tenant_id == tenant_id)
        .first()
    )
    return permisos.exigir_acceso(oportunidad, usuario)


@router.get("", response_model=list[OportunidadOut])
def listar(
    estado: str | None = None,
    area: str | None = None,
    indicador_id: int | None = None,
    abiertas: bool | None = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
):
    query = db.query(Oportunidad).filter(Oportunidad.tenant_id == tenant_id)
    query = permisos.aplicar_filtro_area(query, usuario, Oportunidad)

    if estado:
        query = query.filter(Oportunidad.estado == estado)
    if area:
        query = query.filter(Oportunidad.area == area)
    if indicador_id:
        query = query.filter(Oportunidad.indicador_id == indicador_id)
    if abiertas:
        query = query.filter(Oportunidad.estado.notin_(["cerrada", "descartada"]))

    return query.order_by(Oportunidad.creado_en.desc()).all()


@router.post("", response_model=OportunidadDetalleOut, status_code=status.HTTP_201_CREATED)
def crear(
    payload: OportunidadCrear,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    permisos.exigir_puede_gestionar(usuario)

    # Sin periodo no hay contra qué comparar cuando toque verificar: la OMP
    # nacería sin forma de demostrar si sirvió.
    if payload.indicador_id and not payload.periodo_anio:
        raise HTTPException(
            status_code=400,
            detail=("Falta el periodo del indicador. Es el mes cuya medición "
                    "disparó la oportunidad, y es contra el que se compara "
                    "después para saber si funcionó."),
        )

    # «Sin área» es una decisión, no un olvido: una oportunidad de toda la
    # empresa se manda con area=null a propósito y la ve todo el mundo. Solo
    # cuando el campo NO viene se hereda el área de quien la abre, para que
    # nadie tenga que elegirla de una lista cada vez.
    area = payload.area if "area" in payload.model_fields_set else usuario.area

    oportunidad = Oportunidad(
        tenant_id=tenant_id,
        area=area,
        creado_por=usuario.id,
        **payload.model_dump(exclude={"area"}),
    )
    db.add(oportunidad)
    db.commit()
    db.refresh(oportunidad)

    service.asignar_codigo(db, oportunidad, tenant_id)
    return oportunidad


@router.get("/{omp_id}", response_model=OportunidadDetalleOut)
def obtener(
    omp_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
):
    return _buscar(db, omp_id, tenant_id, usuario)


@router.patch("/{omp_id}", response_model=OportunidadDetalleOut)
def actualizar(
    omp_id: int,
    payload: OportunidadActualizar,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    permisos.exigir_puede_gestionar(usuario)
    oportunidad = _buscar(db, omp_id, tenant_id, usuario)

    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(oportunidad, campo, valor)

    db.commit()
    db.refresh(oportunidad)
    return oportunidad


@router.patch("/{omp_id}/estado", response_model=OportunidadDetalleOut)
def cambiar_estado(
    omp_id: int,
    payload: CambioEstado,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    permisos.exigir_puede_gestionar(usuario)
    oportunidad = _buscar(db, omp_id, tenant_id, usuario)
    return service.cambiar_estado(db, oportunidad, payload.estado)


@router.get("/{omp_id}/verificacion")
def consultar_verificacion(
    omp_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
):
    """
    Lo necesario para verificar: el valor de antes, el de después y si eso
    es una mejora — ya resuelto, porque saber si subir es bueno depende de
    la dirección del indicador y esa regla vive en el servidor.
    """
    oportunidad = _buscar(db, omp_id, tenant_id, usuario)
    return service.sugerir_verificacion(db, oportunidad)


@router.post("/{omp_id}/verificacion", response_model=OportunidadDetalleOut)
def registrar_verificacion(
    omp_id: int,
    payload: Verificacion,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    permisos.exigir_puede_gestionar(usuario)
    oportunidad = _buscar(db, omp_id, tenant_id, usuario)
    return service.registrar_verificacion(
        db, oportunidad, payload.eficaz, payload.nota, payload.valor_verificado,
    )


@router.delete("/{omp_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    omp_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    """
    Borrar es para lo que se abrió por error. Lo que se intentó y no
    funcionó se DESCARTA, que deja rastro: el historial de mejora es
    justamente lo que se audita.
    """
    if usuario.rol != "admin":
        raise HTTPException(
            status_code=403,
            detail=("Solo un administrador borra una oportunidad. Si esta ya no "
                    "aplica, descártala: así queda el registro de que se evaluó."),
        )
    oportunidad = _buscar(db, omp_id, tenant_id, usuario)
    db.delete(oportunidad)
    db.commit()


# ── Acciones del plan ────────────────────────────────────────────────

@router.post("/{omp_id}/acciones", response_model=AccionOut,
             status_code=status.HTTP_201_CREATED)
def agregar_accion(
    omp_id: int,
    payload: AccionCrear,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    permisos.exigir_puede_gestionar(usuario)
    oportunidad = _buscar(db, omp_id, tenant_id, usuario)

    if oportunidad.esta_cerrada:
        raise HTTPException(
            status_code=400,
            detail="Esta oportunidad ya está cerrada: no admite acciones nuevas.",
        )

    accion = AccionMejora(omp_id=oportunidad.id, **payload.model_dump())
    db.add(accion)
    db.commit()
    db.refresh(accion)
    return accion


@router.patch("/{omp_id}/acciones/{accion_id}", response_model=AccionOut)
def actualizar_accion(
    omp_id: int,
    accion_id: int,
    payload: AccionActualizar,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    oportunidad = _buscar(db, omp_id, tenant_id, usuario)
    accion = (
        db.query(AccionMejora)
        .filter(AccionMejora.id == accion_id, AccionMejora.omp_id == oportunidad.id)
        .first()
    )
    if not accion:
        raise HTTPException(status_code=404, detail="Acción no encontrada.")

    # Quien tiene la acción asignada puede marcarla, aunque no sea líder: si
    # solo el líder pudiera, terminaría actualizando el trabajo de otros de
    # oídas, que es como se llenan de mentiras estos registros.
    es_suya = accion.responsable_id == usuario.id
    if not es_suya:
        permisos.exigir_puede_gestionar(usuario)

    datos = payload.model_dump(exclude_unset=True)
    if "completada" in datos:
        accion.fecha_completada = service._ahora() if datos["completada"] else None
    for campo, valor in datos.items():
        setattr(accion, campo, valor)

    db.commit()
    db.refresh(accion)
    return accion


@router.delete("/{omp_id}/acciones/{accion_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_accion(
    omp_id: int,
    accion_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    permisos.exigir_puede_gestionar(usuario)
    oportunidad = _buscar(db, omp_id, tenant_id, usuario)
    accion = (
        db.query(AccionMejora)
        .filter(AccionMejora.id == accion_id, AccionMejora.omp_id == oportunidad.id)
        .first()
    )
    if not accion:
        raise HTTPException(status_code=404, detail="Acción no encontrada.")

    db.delete(accion)
    db.commit()
