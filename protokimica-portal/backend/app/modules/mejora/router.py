"""
Endpoints de Oportunidades de Mejora (OMP).

`requiere_modulo("mejora")` va en TODOS, incluidas las lecturas: esconder el
botón en el menú es cortesía, no seguridad. Y el filtro por área se impone
aquí, no en el frontend — mandar otro `?area=` no abre nada.

**Ojo con el orden de las rutas:** `/catalogos` va declarada ANTES que
`/{omp_id}`, o el path variable se la come y pedir los catálogos responde
«oportunidad no encontrada».
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_tenant_id, solo_lectura_no
from app.core.modulos import requiere_modulo
from app.models.mejora import (
    CLASIFICACIONES, ESTADOS_ACCION, TIPOS_RESPONSABLE, AccionMejora, CambioMejora,
    ItemCatalogo, Oportunidad, RelacionMejora, ResponsableMejora, SeguimientoMejora,
)
from app.models.user import User
from app.modules.mejora import catalogos as cat
from app.modules.mejora import permisos, service
from app.modules.mejora.schemas import (
    AccionActualizar, AccionCrear, AccionOut, CambioEstado, CambioOut, CatalogosOut,
    ItemCatalogoActualizar, ItemCatalogoCrear, ItemCatalogoOut, OportunidadActualizar,
    OportunidadCrear, OportunidadDetalleOut, OportunidadOut, ResponsableCrear,
    ResponsableOut, SeguimientoCrear, SeguimientoOut, ValidacionSGC, Verificacion,
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


def _validar_catalogos(db: Session, tenant_id: int, datos: dict) -> None:
    """Que el proceso sea un proceso y el tratamiento un tratamiento."""
    for campo, tipo in (("proceso_id", "proceso"), ("fuente_id", "fuente"),
                        ("tratamiento_id", "tratamiento")):
        if campo in datos:
            service.validar_item(db, tenant_id, tipo, datos[campo])


def _validar_clasificacion(valor: str | None) -> None:
    if valor is not None and valor not in CLASIFICACIONES:
        raise HTTPException(
            status_code=400,
            detail=f"La clasificación tiene que ser una de: {', '.join(CLASIFICACIONES)}.",
        )


def _agregar_responsables(db: Session, omp_id: int, entradas: list[ResponsableCrear]) -> None:
    for entrada in entradas:
        if entrada.tipo not in TIPOS_RESPONSABLE:
            raise HTTPException(
                status_code=400,
                detail=("Un responsable es de resolución o de seguimiento: "
                        f"'{entrada.tipo}' no es ninguno de los dos."),
            )
        if entrada.usuario_id is None and not (entrada.nombre_texto or "").strip():
            raise HTTPException(
                status_code=400,
                detail=("Cada responsable necesita un usuario del portal o un "
                        "nombre escrito. Los comités van como nombre."),
            )
        db.add(ResponsableMejora(
            omp_id=omp_id, tipo=entrada.tipo, usuario_id=entrada.usuario_id,
            nombre_texto=(entrada.nombre_texto or "").strip() or None,
        ))


# ── Catálogos del formato ────────────────────────────────────────────
# Van antes que `/{omp_id}` a propósito: si no, la ruta variable se las come.

@router.get("/catalogos", response_model=CatalogosOut)
def obtener_catalogos(
    incluir_inactivos: bool = False,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """
    Proceso, fuente y tratamiento, tal como Calidad los tenga hoy.

    Se siembran solos la primera vez: una empresa nueva no puede quedarse sin
    poder abrir una acción porque a alguien se le olvidó correr un script.
    """
    return service.listar_catalogos(db, tenant_id, incluir_inactivos)


@router.post("/catalogos", response_model=ItemCatalogoOut,
             status_code=status.HTTP_201_CREATED)
def crear_item_catalogo(
    payload: ItemCatalogoCrear,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    """Calidad agrega un proceso o una fuente sin esperar un despliegue."""
    permisos.exigir_sgc(usuario)

    if payload.tipo not in cat.TIPOS:
        raise HTTPException(
            status_code=400,
            detail=f"El catálogo tiene que ser uno de: {', '.join(cat.TIPOS)}.",
        )

    nombre = payload.nombre.strip()
    if service.item_por_nombre(db, tenant_id, payload.tipo, nombre):
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe «{nombre}» en {payload.tipo}. Si estaba desactivado, actívalo.",
        )

    item = ItemCatalogo(
        tenant_id=tenant_id, tipo=payload.tipo, codigo=payload.codigo,
        nombre=nombre, orden=payload.orden, activo=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/catalogos/{item_id}", response_model=ItemCatalogoOut)
def actualizar_item_catalogo(
    item_id: int,
    payload: ItemCatalogoActualizar,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    """
    Renombrar o desactivar. No hay borrado: las acciones viejas siguen
    apuntando a su proceso y el reporte tiene que poder decir de cuál eran.
    """
    permisos.exigir_sgc(usuario)

    item = (
        db.query(ItemCatalogo)
        .filter(ItemCatalogo.id == item_id, ItemCatalogo.tenant_id == tenant_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Ese valor del catálogo no existe.")

    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(item, campo, valor.strip() if campo == "nombre" else valor)

    db.commit()
    db.refresh(item)
    return item


# ── Oportunidades ────────────────────────────────────────────────────

@router.get("", response_model=list[OportunidadOut])
def listar(
    estado: str | None = None,
    area: str | None = None,
    proceso_id: int | None = None,
    tratamiento_id: int | None = None,
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
    if proceso_id:
        query = query.filter(Oportunidad.proceso_id == proceso_id)
    if tratamiento_id:
        query = query.filter(Oportunidad.tratamiento_id == tratamiento_id)
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
    service.sembrar_catalogos(db, tenant_id)

    # Sin periodo no hay contra qué comparar cuando toque verificar: la OMP
    # nacería sin forma de demostrar si sirvió.
    if payload.indicador_id and not payload.periodo_anio:
        raise HTTPException(
            status_code=400,
            detail=("Falta el periodo del indicador. Es el mes cuya medición "
                    "disparó la oportunidad, y es contra el que se compara "
                    "después para saber si funcionó."),
        )

    datos = payload.model_dump(exclude={"area", "responsables"})
    _validar_catalogos(db, tenant_id, datos)
    _validar_clasificacion(payload.clasificacion)

    # «Sin área» es una decisión, no un olvido: una oportunidad de toda la
    # empresa se manda con area=null a propósito y la ve todo el mundo. Solo
    # cuando el campo NO viene se hereda el área de quien la abre, para que
    # nadie tenga que elegirla de una lista cada vez.
    area = payload.area if "area" in payload.model_fields_set else usuario.area

    # El proceso y la fuente se proponen cuando no vienen. El tratamiento no
    # se adivina: decide qué campos son obligatorios, y ponerle uno por
    # defecto le pediría a la gente una causa raíz que quizá no aplica.
    if datos.get("proceso_id") is None:
        propuesto = service.proceso_propuesto(db, tenant_id, area)
        datos["proceso_id"] = propuesto.id if propuesto else None
    if datos.get("fuente_id") is None:
        propuesta = service.fuente_propuesta(db, tenant_id, payload.origen)
        datos["fuente_id"] = propuesta.id if propuesta else None
    if datos.get("fecha_registro") is None:
        datos["fecha_registro"] = date.today()

    oportunidad = Oportunidad(
        tenant_id=tenant_id, area=area, creado_por=usuario.id, **datos,
    )
    db.add(oportunidad)
    db.commit()
    db.refresh(oportunidad)

    if payload.responsables:
        _agregar_responsables(db, oportunidad.id, payload.responsables)
        db.commit()

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

    datos = payload.model_dump(exclude_unset=True)
    _validar_catalogos(db, tenant_id, datos)
    if "clasificacion" in datos:
        _validar_clasificacion(datos["clasificacion"])

    for campo, valor in datos.items():
        service.registrar_cambio(
            db, oportunidad.id, campo, getattr(oportunidad, campo), valor, usuario.id,
        )
        setattr(oportunidad, campo, valor)

    # Cambiar de proceso cambia el reporte en el que sale, así que necesita
    # su número allá. El anterior no se recicla: renumerar correría todas las
    # que venían después y una referencia de auditoría dejaría de servir.
    if "proceso_id" in datos:
        oportunidad.consecutivo = service.siguiente_consecutivo(
            db, tenant_id, oportunidad.proceso_id,
        )

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
    return service.cambiar_estado(db, oportunidad, payload.estado, usuario.id)


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
        db, oportunidad, payload.eficaz, payload.nota,
        payload.valor_verificado, usuario.id,
    )


@router.post("/{omp_id}/validacion-sgc", response_model=OportunidadDetalleOut)
def validar_sgc(
    omp_id: int,
    payload: ValidacionSGC,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    """
    El visto bueno de Calidad, sin el cual no se cierra.

    Va aparte de la verificación a propósito: quien ejecutó la acción dice
    si el indicador mejoró, y el SGC dice si la evidencia alcanza. Un solo
    botón dejaba que el mismo que hizo el trabajo lo diera por bueno.
    """
    permisos.exigir_sgc(usuario)
    oportunidad = _buscar(db, omp_id, tenant_id, usuario)
    return service.validar_cierre_sgc(db, oportunidad, usuario.id, payload.nota)


@router.get("/{omp_id}/historial", response_model=list[CambioOut])
def historial(
    omp_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
):
    """Quién cambió qué y cuándo. Lo más nuevo primero."""
    oportunidad = _buscar(db, omp_id, tenant_id, usuario)
    return (
        db.query(CambioMejora)
        .filter(CambioMejora.omp_id == oportunidad.id)
        .order_by(CambioMejora.fecha.desc(), CambioMejora.id.desc())
        .all()
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


# ── Responsables (columnas E y F) ────────────────────────────────────

@router.post("/{omp_id}/responsables", response_model=list[ResponsableOut],
             status_code=status.HTTP_201_CREATED)
def agregar_responsable(
    omp_id: int,
    payload: ResponsableCrear,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    permisos.exigir_puede_gestionar(usuario)
    oportunidad = _buscar(db, omp_id, tenant_id, usuario)

    _agregar_responsables(db, oportunidad.id, [payload])
    db.commit()
    db.refresh(oportunidad)
    return oportunidad.responsables


@router.delete("/{omp_id}/responsables/{responsable_id}",
               status_code=status.HTTP_204_NO_CONTENT)
def quitar_responsable(
    omp_id: int,
    responsable_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    permisos.exigir_puede_gestionar(usuario)
    oportunidad = _buscar(db, omp_id, tenant_id, usuario)
    fila = (
        db.query(ResponsableMejora)
        .filter(ResponsableMejora.id == responsable_id,
                ResponsableMejora.omp_id == oportunidad.id)
        .first()
    )
    if not fila:
        raise HTTPException(status_code=404, detail="Ese responsable no está en la lista.")

    db.delete(fila)
    db.commit()


# ── Seguimientos (columnas S, T y U) ─────────────────────────────────

@router.post("/{omp_id}/seguimientos", response_model=SeguimientoOut,
             status_code=status.HTTP_201_CREATED)
def agregar_seguimiento(
    omp_id: int,
    payload: SeguimientoCrear,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    """
    Una entrada más en la bitácora.

    Lo puede escribir cualquiera que vea la oportunidad, no solo el líder:
    quien ejecuta la acción es quien sabe cómo va, y obligarlo a contárselo
    al líder para que él lo escriba es cómo estos registros se llenan de
    resúmenes de segunda mano.
    """
    oportunidad = _buscar(db, omp_id, tenant_id, usuario)

    if oportunidad.esta_cerrada:
        raise HTTPException(
            status_code=400,
            detail=("Esta oportunidad ya está cerrada: su seguimiento no se "
                    "modifica. Si el problema volvió, abre una nueva."),
        )

    seguimiento = SeguimientoMejora(
        omp_id=oportunidad.id,
        fecha=payload.fecha or date.today(),
        autor_id=usuario.id,
        contenido=payload.contenido.strip(),
        adjunto=payload.adjunto,
    )
    db.add(seguimiento)
    db.commit()
    db.refresh(seguimiento)
    return seguimiento


@router.delete("/{omp_id}/seguimientos/{seguimiento_id}",
               status_code=status.HTTP_204_NO_CONTENT)
def eliminar_seguimiento(
    omp_id: int,
    seguimiento_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    """
    Solo su autor o un administrador, y solo mientras la OMP siga abierta.

    Un seguimiento ajeno no se borra: es el registro de lo que alguien dijo
    que estaba pasando en una fecha, y esa es la parte que se audita.
    """
    oportunidad = _buscar(db, omp_id, tenant_id, usuario)
    seguimiento = (
        db.query(SeguimientoMejora)
        .filter(SeguimientoMejora.id == seguimiento_id,
                SeguimientoMejora.omp_id == oportunidad.id)
        .first()
    )
    if not seguimiento:
        raise HTTPException(status_code=404, detail="Ese seguimiento no existe.")

    if usuario.rol != "admin" and seguimiento.autor_id != usuario.id:
        raise HTTPException(
            status_code=403,
            detail=("Solo quien escribió el seguimiento puede quitarlo. Si dice "
                    "algo equivocado, agrega uno nuevo que lo aclare."),
        )

    db.delete(seguimiento)
    db.commit()


# ── Hallazgos similares (columna J) ──────────────────────────────────

@router.post("/{omp_id}/relacionadas/{otra_id}", status_code=status.HTTP_204_NO_CONTENT)
def relacionar(
    omp_id: int,
    otra_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
    _: User = Depends(solo_lectura_no),
):
    """
    Amarra dos oportunidades que tratan el mismo hallazgo.

    Es lo que le da sentido al «¿existen hallazgos similares?» del formato:
    un Sí que no dice cuáles no le sirve a nadie para revisar qué ya se
    intentó. Se guarda en las dos direcciones porque la pregunta se hace
    desde cualquiera de las dos.
    """
    permisos.exigir_puede_gestionar(usuario)
    if omp_id == otra_id:
        raise HTTPException(
            status_code=400, detail="Una oportunidad no se relaciona consigo misma.",
        )

    oportunidad = _buscar(db, omp_id, tenant_id, usuario)
    otra = _buscar(db, otra_id, tenant_id, usuario)

    existentes = {
        (fila.omp_id, fila.relacionada_id)
        for fila in db.query(RelacionMejora).filter(
            RelacionMejora.omp_id.in_([oportunidad.id, otra.id])
        ).all()
    }
    for a, b in ((oportunidad.id, otra.id), (otra.id, oportunidad.id)):
        if (a, b) not in existentes:
            db.add(RelacionMejora(omp_id=a, relacionada_id=b))

    oportunidad.hallazgos_similares = True
    otra.hallazgos_similares = True
    db.commit()


@router.get("/{omp_id}/relacionadas", response_model=list[OportunidadOut])
def listar_relacionadas(
    omp_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
):
    oportunidad = _buscar(db, omp_id, tenant_id, usuario)
    ids = [
        fila.relacionada_id
        for fila in db.query(RelacionMejora)
        .filter(RelacionMejora.omp_id == oportunidad.id).all()
    ]
    if not ids:
        return []

    query = db.query(Oportunidad).filter(
        Oportunidad.tenant_id == tenant_id, Oportunidad.id.in_(ids),
    )
    return permisos.aplicar_filtro_area(query, usuario, Oportunidad).all()


# ── Acciones del plan (columna P) ────────────────────────────────────

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

    datos = payload.model_dump()
    # El número de la tarea en el plan. Del máximo, como todo consecutivo:
    # contar las que hay devuelve un número repetido en cuanto se borra una.
    if datos.get("orden") is None:
        datos["orden"] = max((a.orden for a in oportunidad.acciones), default=0) + 1

    accion = AccionMejora(omp_id=oportunidad.id, **datos)
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
    if "estado" in datos:
        if datos["estado"] not in ESTADOS_ACCION:
            raise HTTPException(
                status_code=400,
                detail=f"El estado de una tarea es uno de: {', '.join(ESTADOS_ACCION)}.",
            )
        accion.fecha_completada = (
            service._ahora() if datos["estado"] == "cumplida" else None
        )

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
