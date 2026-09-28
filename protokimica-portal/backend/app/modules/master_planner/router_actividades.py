"""
Actividades diarias: lo que se repite y no pertenece a ningún proyecto.

**Una tarea termina; una actividad diaria no.** Por eso están aparte y no
como una casilla «se repite» dentro de una tarea: una tarea tiene proyecto,
fecha de entrega, avance y entregable, y nada de eso significa algo en algo
que se hace todos los martes. La mitad de las columnas habrían quedado
vacías en la mitad de las filas.

Va en su propio router y no al final de `router.py` —que ya pasa de mil
líneas— porque es una función completa con su propio vocabulario. Comparte
el prefijo `/master-planner`, así que para quien consume la API es el mismo
módulo.

Qué se esperaba de cada día no se guarda: se deduce de la frecuencia (ver
`actividades.py`). Lo único escrito en la base es lo que de verdad se hizo.
"""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core import dias_habiles, supervision
from app.core.database import get_db
from app.core.deps import get_current_user, get_current_tenant_id, solo_lectura_no
from app.models.master_planner import (
    FRECUENCIAS, ActividadDiaria, ActividadRegistro,
)
from app.models.user import User
from app.modules.master_planner import actividades as act
from app.modules.master_planner.permisos import ve_todo
from app.modules.master_planner.schemas import (
    ActividadActualizar, ActividadCrear, ActividadOut, MesActividadOut,
    CumplimientoActividadOut, RegistroActividadCrear, RegistroActividadOut,
)

router = APIRouter(prefix="/master-planner", tags=["Master Planner — Actividades diarias"])


def _hoy() -> date:
    """
    «Hoy» es el de la ZONA DE LA EMPRESA, no el de UTC.

    En UTC, a partir de las siete de la noche en Colombia ya es el día
    siguiente: quien marcara una actividad a las 7:30 p. m. la habría visto
    registrada mañana, y hoy le seguiría apareciendo sin registrar.
    """
    return dias_habiles.hoy()


def _puede_asignar(usuario: User, asignado_a: int | None, db: Session) -> bool:
    """
    Uno crea las suyas; un líder crea para la gente de su área.

    `admin` siempre puede: es quien destraba cuando alguien está de
    vacaciones o quedó mal configurado.
    """
    if usuario.rol == "admin" or not asignado_a or asignado_a == usuario.id:
        return True
    if usuario.rol != "lider":
        return False
    destino = db.get(User, asignado_a)
    return bool(destino and destino.area in supervision.areas_visibles(usuario))


def _visibles(query, usuario: User):
    """
    Las suyas, las que creó, y las de su área si la supervisa. Misma regla
    que el resto del módulo: lo ajeno no se esconde a medias, no aparece.
    """
    if ve_todo(usuario):
        return query
    return query.filter(
        or_(
            ActividadDiaria.asignado_a == usuario.id,
            ActividadDiaria.creado_por == usuario.id,
            ActividadDiaria.area.in_(supervision.areas_visibles(usuario)),
        )
    )


def _actividad_o_404(db: Session, actividad_id: int, tenant_id: int, usuario: User):
    actividad = _visibles(
        db.query(ActividadDiaria).filter(
            ActividadDiaria.id == actividad_id,
            ActividadDiaria.tenant_id == tenant_id,
        ),
        usuario,
    ).first()
    if not actividad:
        # 404 y no 403, como en todo el módulo: un 403 confirma que existe.
        raise HTTPException(status_code=404, detail="Esa actividad no existe.")
    return actividad


def _salida(db: Session, actividad: ActividadDiaria, hoy: date) -> ActividadOut:
    """La actividad tal como la necesita la pantalla, ya resuelta."""
    registrada = (
        db.query(ActividadRegistro.id)
        .filter(
            ActividadRegistro.actividad_id == actividad.id,
            ActividadRegistro.fecha == hoy,
        )
        .first()
        is not None
    )
    return ActividadOut(
        id=actividad.id,
        titulo=actividad.titulo,
        asignado_a=actividad.asignado_a,
        asignado_nombre=actividad.asignado_nombre,
        area=actividad.area,
        frecuencia=actividad.frecuencia,
        dias_semana=act.leer_dias(actividad.dias_semana),
        dia_mes=actividad.dia_mes,
        solo_dias_habiles=actividad.solo_dias_habiles,
        desde=actividad.desde,
        hasta=actividad.hasta,
        activa=actividad.activa,
        creado_en=actividad.creado_en,
        frecuencia_texto=act.descripcion_frecuencia(actividad),
        toca_hoy=bool(actividad.activa and act.se_espera_el(actividad, hoy)),
        registrada_hoy=registrada,
    )


def _validar_frecuencia(frecuencia: str, dias_semana, dia_mes) -> None:
    if frecuencia not in FRECUENCIAS:
        raise HTTPException(
            status_code=400,
            detail=f"La frecuencia debe ser una de: {', '.join(FRECUENCIAS)}.",
        )
    if frecuencia == "semanal" and not act.leer_dias(act.escribir_dias(dias_semana or [])):
        raise HTTPException(
            status_code=400,
            detail=("Marca al menos un día de la semana, o la actividad no le "
                    "tocaría nunca a nadie."),
        )
    if frecuencia == "mensual" and not dia_mes:
        raise HTTPException(
            status_code=400,
            detail="Elige qué día del mes: sin eso no hay cuándo esperarla.",
        )


@router.get("/actividades", response_model=list[ActividadOut])
def listar_actividades(
    solo_mias: bool = False,
    incluir_inactivas: bool = False,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    query = _visibles(
        db.query(ActividadDiaria).filter(ActividadDiaria.tenant_id == tenant_id),
        current_user,
    )
    if solo_mias:
        query = query.filter(ActividadDiaria.asignado_a == current_user.id)
    if not incluir_inactivas:
        query = query.filter(ActividadDiaria.activa.is_(True))

    hoy = _hoy()
    return [_salida(db, a, hoy) for a in query.order_by(ActividadDiaria.titulo.asc()).all()]


@router.post("/actividades", response_model=ActividadOut, status_code=status.HTTP_201_CREATED)
def crear_actividad(
    payload: ActividadCrear,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    _validar_frecuencia(payload.frecuencia, payload.dias_semana, payload.dia_mes)

    if not _puede_asignar(current_user, payload.asignado_a, db):
        raise HTTPException(
            status_code=403,
            detail=("Solo puedes crear actividades para ti o para alguien de tu "
                    "área. Si es de otra área, pídeselo a su líder."),
        )

    # Sin responsable es de quien la crea: una actividad diaria que no es de
    # nadie no la hace nadie.
    asignado_a = payload.asignado_a or current_user.id
    responsable = db.get(User, asignado_a)

    actividad = ActividadDiaria(
        tenant_id=tenant_id,
        titulo=payload.titulo.strip(),
        asignado_a=asignado_a,
        # El área se hereda del responsable, no se pide: es un campo menos en
        # un formulario que tiene que ser corto, y es la que decide en qué
        # indicador cuenta.
        area=responsable.area if responsable else current_user.area,
        frecuencia=payload.frecuencia,
        dias_semana=act.escribir_dias(payload.dias_semana),
        dia_mes=payload.dia_mes if payload.frecuencia == "mensual" else None,
        solo_dias_habiles=payload.solo_dias_habiles,
        # Desde hoy salvo que se diga otra cosa. **Nunca antes de existir**:
        # si arrancara el primero del mes, una actividad creada hoy nacería
        # con todos los días anteriores incumplidos.
        desde=payload.desde or _hoy(),
        creado_por=current_user.id,
    )
    db.add(actividad)
    db.commit()
    db.refresh(actividad)
    return _salida(db, actividad, _hoy())


@router.patch("/actividades/{actividad_id}", response_model=ActividadOut)
def actualizar_actividad(
    actividad_id: int,
    payload: ActividadActualizar,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    actividad = _actividad_o_404(db, actividad_id, tenant_id, current_user)
    datos = payload.model_dump(exclude_unset=True)

    if "asignado_a" in datos and not _puede_asignar(current_user, datos["asignado_a"], db):
        raise HTTPException(
            status_code=403,
            detail="Solo puedes asignar actividades a alguien de tu área.",
        )

    _validar_frecuencia(
        datos.get("frecuencia", actividad.frecuencia),
        datos.get("dias_semana", act.leer_dias(actividad.dias_semana)),
        datos.get("dia_mes", actividad.dia_mes),
    )

    if "dias_semana" in datos:
        datos["dias_semana"] = act.escribir_dias(datos["dias_semana"])

    # Desactivarla CIERRA su periodo: sin `hasta`, apagar una actividad hoy
    # dejaría el resto del mes contándose como incumplido.
    if datos.get("activa") is False and actividad.activa:
        actividad.hasta = _hoy()
    elif datos.get("activa") is True and not actividad.activa:
        actividad.hasta = None

    for campo, valor in datos.items():
        setattr(actividad, campo, valor)

    db.commit()
    db.refresh(actividad)
    return _salida(db, actividad, _hoy())


@router.delete("/actividades/{actividad_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_actividad(
    actividad_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    """
    Borrar de verdad, y solo lo que no dejó rastro.

    Una actividad con registros es la constancia de que alguien hizo su
    trabajo: eso se DESACTIVA, que la saca de la lista de hoy y deja de
    esperar días nuevos sin borrar lo ya hecho. Borrar queda para la que se
    creó por error.
    """
    actividad = _actividad_o_404(db, actividad_id, tenant_id, current_user)

    registros = (
        db.query(ActividadRegistro)
        .filter(ActividadRegistro.actividad_id == actividad.id)
        .count()
    )
    if registros:
        raise HTTPException(
            status_code=409,
            detail=(f"«{actividad.titulo}» ya tiene {registros} registro(s) de que "
                    "se hizo. Desactívala: deja de pedirse desde hoy y lo ya "
                    "registrado se conserva."),
        )

    db.delete(actividad)
    db.commit()


@router.post(
    "/actividades/{actividad_id}/registros",
    response_model=RegistroActividadOut, status_code=status.HTTP_201_CREATED,
)
def registrar_actividad(
    actividad_id: int,
    payload: RegistroActividadCrear,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    """
    Dejar constancia de que la actividad se hizo un día.

    La fecha puede ser anterior —quien no alcanzó a marcar el viernes lo
    marca el lunes, y el cumplimiento tiene que contarlo en el viernes— pero
    **nunca futura**: dar por hecho algo que todavía no pasa no es un
    descuido, es dar por cumplido lo que no está.
    """
    actividad = _actividad_o_404(db, actividad_id, tenant_id, current_user)
    hoy = _hoy()
    fecha = payload.fecha or hoy

    if fecha > hoy:
        raise HTTPException(
            status_code=400, detail="No se puede registrar un día que todavía no llega.",
        )
    if not act.se_espera_el(actividad, fecha):
        raise HTTPException(
            status_code=400,
            detail=(f"Ese día no tocaba «{actividad.titulo}» "
                    f"({act.descripcion_frecuencia(actividad).lower()})."),
        )

    ya = (
        db.query(ActividadRegistro)
        .filter(
            ActividadRegistro.actividad_id == actividad.id,
            ActividadRegistro.fecha == fecha,
        )
        .first()
    )
    if ya:
        # Sin esto, dos clics seguidos dejarían el día contado dos veces y el
        # cumplimiento pasaría del 100%.
        raise HTTPException(status_code=409, detail="Ese día ya está registrado.")

    registro = ActividadRegistro(
        actividad_id=actividad.id,
        fecha=fecha,
        usuario_id=current_user.id,
        comentario=(payload.comentario or "").strip() or None,
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


@router.delete(
    "/actividades/{actividad_id}/registros/{fecha}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def quitar_registro(
    actividad_id: int,
    fecha: date,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    """Desmarcar: se marcó por error, o se marcó la actividad equivocada."""
    _actividad_o_404(db, actividad_id, tenant_id, current_user)
    registro = (
        db.query(ActividadRegistro)
        .filter(
            ActividadRegistro.actividad_id == actividad_id,
            ActividadRegistro.fecha == fecha,
        )
        .first()
    )
    if not registro:
        raise HTTPException(status_code=404, detail="Ese día no está registrado.")
    db.delete(registro)
    db.commit()


@router.get(
    "/actividades/{actividad_id}/registros", response_model=list[RegistroActividadOut],
)
def listar_registros(
    actividad_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """El registro de lo realizado: qué días se hizo, quién lo marcó y cuándo."""
    _actividad_o_404(db, actividad_id, tenant_id, current_user)
    return (
        db.query(ActividadRegistro)
        .filter(ActividadRegistro.actividad_id == actividad_id)
        .order_by(ActividadRegistro.fecha.desc())
        .limit(120)
        .all()
    )


@router.get(
    "/actividades/{actividad_id}/cumplimiento", response_model=CumplimientoActividadOut,
)
def cumplimiento_de_actividad(
    actividad_id: int,
    anio: int | None = None,
    mes: int | None = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """
    Cuántas veces tocaba en el mes y cuántas se registró.

    Lo calcula el SERVIDOR con la misma función que alimenta el indicador: si
    la pantalla lo contara aparte, el día que cambie la regla de los días
    hábiles diría un número distinto del reporte.
    """
    actividad = _actividad_o_404(db, actividad_id, tenant_id, current_user)
    hoy = _hoy()
    desde, hasta = act.corte_del_mes(anio or hoy.year, mes or hoy.month, hoy)
    return CumplimientoActividadOut(**act.cumplimiento(db, actividad, desde, hasta))


@router.get("/actividades/{actividad_id}/mes", response_model=MesActividadOut)
def mes_de_actividad(
    actividad_id: int,
    anio: int | None = None,
    mes: int | None = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """
    El mes día por día: qué tocaba, qué se hizo y qué falta.

    Es lo que la pantalla pinta en vez de una lista de registros que crecía
    para siempre. Lo arma el SERVIDOR porque decidir si un día «no aplica» o
    «está sin registrar» es la misma regla del indicador —días hábiles,
    festivos, frecuencia—, y repetida en el navegador terminaría diciendo
    otra cosa el día que se agregue un festivo.
    """
    actividad = _actividad_o_404(db, actividad_id, tenant_id, current_user)
    hoy = _hoy()
    return MesActividadOut(**act.mapa_del_mes(db, actividad, anio or hoy.year, mes or hoy.month, hoy))
