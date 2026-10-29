"""
Aprobación de documentos dentro de una tarea.

Una tarea puede pedir que su documento lo aprueben otras personas, en orden,
antes de darse por cumplida. En Protokimica: la analista sube los estados
financieros, el Contador los revisa y la Revisora Fiscal los firma.

**No es un módulo aparte: es una tarea con un paso más.** La fecha límite es
la `fecha_fin` de la tarea y la de finalización, `fecha_completada`, que se
sella sola con la última firma. Lo que se repite cada mes se repite como
tarea («Repetir tarea»), con los mismos revisores.

Reglas:

- **La plantilla dice QUÉ pasos hay; la tarea dice QUIÉN los firma.** Al
  activar el flujo se copian a `mp_revision_pasos`, como las cadenas de
  conceptos de PQRS: cambiar la plantilla no mueve los documentos en camino.
- **El estado es el de la última versión** (`borrador → en_revision →
  devuelta | aprobada`). Devolver cierra la versión, y la siguiente arranca
  desde el PRIMER paso: quien ya aprobó lo hizo sobre un archivo que cambió.
- **Firma solo quien tiene el turno** (más `admin`, que destraba), con un
  solo endpoint para aprobar y devolver: el orden lo impone el servidor.
- **Devolver dice qué corregir**: con un comentario o con al menos una
  observación del paso. Una devolución muda obliga a una llamada.
- **La tarea no se completa a mano** mientras el documento no esté aprobado:
  si se pudiera, «completada» diría que se firmó algo que nadie firmó.
- Quien firma no puede ser quien hace el documento: dos manos distintas.
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import hoja_calculo
from app.core.archivos import ruta_documento_privado
from app.models.master_planner import (
    DocumentoVersion, ObservacionDocumento, PlantillaRevision, PlantillaRevisionPaso,
    Proyecto, RevisionEvento, RevisionPaso, Tarea,
)
from app.models.user import User
from app.modules.master_planner.historial import instantanea, registrar_cambios, registrar_evento

# La cadena con la que arranca una empresa. Se edita desde la base hasta que
# llegue la pantalla de plantillas; una empresa sin contabilidad la ignora.
PLANTILLAS_INICIALES = [
    {
        "nombre": "Revisión contable",
        "descripcion": "Lo prepara quien tiene la tarea, lo revisa el Contador y lo firma la Revisora Fiscal.",
        "pasos": ["Contador", "Revisora Fiscal"],
    },
]

# Quien no modifica nada en el portal tampoco firma un documento.
ROLES_QUE_NO_FIRMAN = {"lectura", "gerencia"}

SUBCARPETA = "mp-documentos"


def ahora() -> datetime:
    return datetime.now(timezone.utc)


# ── Plantillas ──────────────────────────────────────────────────

def sembrar_plantillas(db: Session, tenant_id: int) -> None:
    """Crea las plantillas de arranque si la empresa no tiene ninguna. Idempotente."""
    hay = db.query(PlantillaRevision.id).filter(PlantillaRevision.tenant_id == tenant_id).first()
    if hay:
        return
    for p in PLANTILLAS_INICIALES:
        plantilla = PlantillaRevision(tenant_id=tenant_id, nombre=p["nombre"], descripcion=p["descripcion"])
        plantilla.pasos = [PlantillaRevisionPaso(orden=i, nombre=n) for i, n in enumerate(p["pasos"], start=1)]
        db.add(plantilla)
    db.commit()


def plantillas_activas(db: Session, tenant_id: int) -> list[PlantillaRevision]:
    sembrar_plantillas(db, tenant_id)
    return (
        db.query(PlantillaRevision)
        .filter(PlantillaRevision.tenant_id == tenant_id, PlantillaRevision.activa.is_(True))
        .order_by(PlantillaRevision.nombre)
        .all()
    )


# ── Lectura del estado ──────────────────────────────────────────

def ultima_version(tarea: Tarea) -> DocumentoVersion | None:
    return tarea.versiones[-1] if tarea.versiones else None


def estado_documento(tarea: Tarea) -> str | None:
    """None si la tarea no pide aprobación; si no, el estado de su documento."""
    if not tarea.revision_pasos:
        return None
    version = ultima_version(tarea)
    return version.estado if version else "sin_documento"


def paso_en_turno(tarea: Tarea, version: DocumentoVersion | None) -> RevisionPaso | None:
    if version is None or version.estado != "en_revision":
        return None
    return next((p for p in tarea.revision_pasos if p.orden == version.paso_actual), None)


def veces_devuelto(tarea: Tarea) -> int:
    """Sale de los eventos, no de un contador aparte."""
    return sum(1 for v in tarea.versiones for e in v.eventos if e.accion == "devuelto")


def bloquea_completar(tarea: Tarea) -> bool:
    """Si la tarea tiene un documento que todavía no está aprobado."""
    if not tarea.revision_pasos:
        return False
    version = ultima_version(tarea)
    return version is None or version.estado != "aprobada"


def mensaje_no_se_completa(tarea: Tarea) -> str:
    ultimo = tarea.revision_pasos[-1]
    return (
        f"Esta tarea se completa sola cuando {ultimo.nombre} ({ultimo.revisor_nombre}) "
        "apruebe el documento. Súbelo y envíalo a revisión desde el detalle de la tarea."
    )


# ── Quién puede qué ─────────────────────────────────────────────

def puede_trabajar_documento(tarea: Tarea, usuario: User) -> bool:
    """Subir versiones y enviarlas: quien tiene la tarea, el líder del proyecto y admin."""
    if usuario.rol in ROLES_QUE_NO_FIRMAN:
        return False
    return (
        usuario.rol == "admin"
        or tarea.asignado_a == usuario.id
        or (tarea.proyecto is not None and tarea.proyecto.lider_id == usuario.id)
    )


def puede_responder(tarea: Tarea, version: DocumentoVersion | None, usuario: User) -> bool:
    paso = paso_en_turno(tarea, version)
    if paso is None or usuario.rol in ROLES_QUE_NO_FIRMAN:
        return False
    return usuario.rol == "admin" or paso.revisor_id == usuario.id


def es_revisor(tarea: Tarea, usuario_id: int | None) -> bool:
    return usuario_id is not None and any(p.revisor_id == usuario_id for p in tarea.revision_pasos)


def _exigir_trabajo(tarea: Tarea, usuario: User) -> None:
    if not puede_trabajar_documento(tarea, usuario):
        quien = tarea.asignado_nombre or "el responsable de la tarea"
        raise HTTPException(
            status_code=403,
            detail=f"El documento lo sube y lo envía {quien} (o el líder del proyecto).",
        )


# ── Configurar el flujo en una tarea ────────────────────────────

def configurar(
    db: Session, tarea: Tarea, plantilla_id: int, revisores: list[int], usuario: User,
) -> None:
    """
    Copia la plantilla a la tarea con las personas elegidas. Reemplaza lo que
    hubiera, pero no con un documento esperando una firma: cambiarle el
    revisor a alguien que ya lo está mirando se lo quitaría de las manos.
    """
    version = ultima_version(tarea)
    if version is not None and version.estado == "en_revision":
        raise HTTPException(
            status_code=409,
            detail="El documento está en revisión: espera a que lo aprueben o lo devuelvan para cambiar quién firma.",
        )

    tenant_id = tarea.proyecto.tenant_id
    plantilla = (
        db.query(PlantillaRevision)
        .filter(PlantillaRevision.id == plantilla_id, PlantillaRevision.tenant_id == tenant_id)
        .first()
    )
    if plantilla is None or not plantilla.activa:
        raise HTTPException(status_code=400, detail="Esa cadena de revisión no existe o está desactivada. Elige otra.")
    if len(revisores) != len(plantilla.pasos):
        raise HTTPException(
            status_code=400,
            detail=f"«{plantilla.nombre}» tiene {len(plantilla.pasos)} pasos: elige una persona para cada uno.",
        )
    if len(set(revisores)) != len(revisores):
        raise HTTPException(status_code=400, detail="Cada paso lo firma una persona distinta: si no, la segunda firma no revisa nada.")

    usuarios = {
        u.id: u for u in db.query(User).filter(User.id.in_(revisores), User.tenant_id == tenant_id).all()
    }
    for paso, revisor_id in zip(plantilla.pasos, revisores):
        revisor = usuarios.get(revisor_id)
        if revisor is None or not revisor.activo:
            raise HTTPException(status_code=400, detail=f"Elige un usuario activo para «{paso.nombre}».")
        if revisor.rol in ROLES_QUE_NO_FIRMAN:
            raise HTTPException(
                status_code=400,
                detail=f"{revisor.nombre} tiene un usuario de consulta y no puede firmar «{paso.nombre}». "
                       "Cámbiale el rol en Administración › Usuarios o elige a otra persona.",
            )
        if tarea.asignado_a and revisor_id == tarea.asignado_a:
            raise HTTPException(
                status_code=400,
                detail=f"{revisor.nombre} tiene la tarea: no puede firmar «{paso.nombre}» su propio documento.",
            )

    antes = ", ".join(f"{p.nombre}: {p.revisor_nombre}" for p in tarea.revision_pasos) or None
    tarea.revision_pasos.clear()
    db.flush()
    for paso, revisor_id in zip(plantilla.pasos, revisores):
        tarea.revision_pasos.append(RevisionPaso(orden=paso.orden, nombre=paso.nombre, revisor_id=revisor_id))
    despues = ", ".join(f"{p.nombre}: {usuarios[r].nombre}" for p, r in zip(plantilla.pasos, revisores))
    registrar_evento(
        db, "tarea", tarea.id, tarea.proyecto_id, "aprobacion_documento", usuario.id,
        valor_anterior=antes, valor_nuevo=f"{plantilla.nombre} — {despues}",
        entidad_nombre=tarea.titulo,
    )


def quitar(db: Session, tarea: Tarea, usuario: User) -> None:
    """Solo si nunca se envió nada: lo que ya pasó por revisión es constancia."""
    if any(v.enviado_en for v in tarea.versiones):
        raise HTTPException(
            status_code=409,
            detail="Este documento ya pasó por revisión: quitar el flujo borraría la constancia de quién lo revisó. "
                   "Si ya no se necesita, cancela la tarea.",
        )
    antes = ", ".join(f"{p.nombre}: {p.revisor_nombre}" for p in tarea.revision_pasos)
    tarea.revision_pasos.clear()
    tarea.versiones.clear()
    registrar_evento(
        db, "tarea", tarea.id, tarea.proyecto_id, "aprobacion_documento", usuario.id,
        valor_anterior=antes, valor_nuevo=None, entidad_nombre=tarea.titulo,
    )


def copiar_pasos(origen: Tarea, destino: Tarea) -> None:
    """Para «Repetir tarea»: los mismos revisores, sin el documento."""
    for p in origen.revision_pasos:
        destino.revision_pasos.append(RevisionPaso(orden=p.orden, nombre=p.nombre, revisor_id=p.revisor_id))


# ── El recorrido del documento ──────────────────────────────────

def validar_subida(tarea: Tarea, usuario: User) -> None:
    """
    Si se puede subir una versión ahora. Va aparte para llamarla ANTES de
    guardar el archivo: un permiso que falla no deja basura en disco.
    """
    if not tarea.revision_pasos:
        raise HTTPException(status_code=400, detail="Esta tarea no pide aprobación de documento. Actívala primero en el detalle de la tarea.")
    _exigir_trabajo(tarea, usuario)

    version = ultima_version(tarea)
    if version is not None and version.estado == "en_revision":
        paso = paso_en_turno(tarea, version)
        raise HTTPException(
            status_code=409,
            detail=f"La versión {version.numero} la está revisando {paso.revisor_nombre if paso else 'alguien'}. "
                   "Si hay que cambiarla, pídele que la devuelva.",
        )
    if version is not None and version.estado == "aprobada" and tarea.estado == "completada":
        raise HTTPException(
            status_code=409,
            detail="El documento ya está aprobado y la tarea cumplida. Si hay que corregir algo, reabre la tarea primero.",
        )


def registrar_version(db: Session, tarea: Tarea, archivo: dict, usuario: User) -> DocumentoVersion:
    """
    Una versión nueva. Si la última nunca se envió, se REEMPLAZA (era un
    borrador: no hay nada que conservar de él). Si está en revisión, no: el
    revisor estaría mirando un archivo distinto del que se le cambió.
    """
    validar_subida(tarea, usuario)
    version = ultima_version(tarea)
    if version is not None and version.estado == "borrador":
        version.nombre_original = archivo["nombre_original"]
        version.ruta = archivo["ruta"]
        version.tipo = archivo["tipo"]
        version.tamano = archivo["tamano"]
        version.subido_por = usuario.id
        version.subido_en = ahora()
        return version

    numero = (
        db.query(func.max(DocumentoVersion.numero)).filter(DocumentoVersion.tarea_id == tarea.id).scalar() or 0
    ) + 1
    nueva = DocumentoVersion(
        tarea_id=tarea.id, numero=numero, estado="borrador", subido_por=usuario.id, **archivo,
    )
    tarea.versiones.append(nueva)
    db.flush()
    return nueva


def enviar(db: Session, tarea: Tarea, usuario: User, comentario: str | None) -> DocumentoVersion:
    _exigir_trabajo(tarea, usuario)
    version = ultima_version(tarea)
    if version is None or version.estado != "borrador":
        raise HTTPException(status_code=409, detail="No hay una versión nueva para enviar. Sube el documento primero.")

    primero = tarea.revision_pasos[0]
    version.estado = "en_revision"
    version.paso_actual = primero.orden
    version.enviado_en = ahora()
    version.eventos.append(RevisionEvento(
        accion="enviado", paso_orden=primero.orden, paso_nombre=primero.nombre,
        comentario=(comentario or "").strip() or None, usuario_id=usuario.id,
    ))
    # Mientras alguien lo revisa, la tarea está andando — no «pendiente».
    if tarea.estado == "pendiente":
        antes = instantanea(tarea, "tarea")
        tarea.estado = "en_proceso"
        registrar_cambios(db, "tarea", tarea.id, tarea.proyecto_id, antes, instantanea(tarea, "tarea"),
                          usuario.id, entidad_nombre=tarea.titulo)
    return version


def responder(
    db: Session, tarea: Tarea, version: DocumentoVersion, decision: str,
    comentario: str | None, usuario: User,
) -> DocumentoVersion:
    if version.id != (ultima_version(tarea).id if tarea.versiones else None) or version.estado != "en_revision":
        raise HTTPException(status_code=409, detail="Esta versión ya no está esperando una firma. Recarga para ver la actual.")
    paso = paso_en_turno(tarea, version)
    if not puede_responder(tarea, version, usuario):
        raise HTTPException(
            status_code=403,
            detail=f"El turno es de {paso.nombre} ({paso.revisor_nombre})." if paso else "Este documento no espera tu firma.",
        )

    comentario = (comentario or "").strip() or None
    if decision == "devolver":
        tiene_observaciones = any(
            o.paso_orden == paso.orden and not o.atendida for o in version.observaciones
        )
        if not comentario and not tiene_observaciones:
            raise HTTPException(
                status_code=400,
                detail="Para devolverlo di qué hay que corregir: escribe un comentario o marca observaciones en el documento.",
            )
        version.estado = "devuelta"
        version.paso_actual = None
        version.cerrado_en = ahora()
        version.eventos.append(RevisionEvento(
            accion="devuelto", paso_orden=paso.orden, paso_nombre=paso.nombre,
            comentario=comentario, usuario_id=usuario.id,
        ))
        return version

    version.eventos.append(RevisionEvento(
        accion="aprobado", paso_orden=paso.orden, paso_nombre=paso.nombre,
        comentario=comentario, usuario_id=usuario.id,
    ))
    siguiente = next((p for p in tarea.revision_pasos if p.orden > paso.orden), None)
    if siguiente is not None:
        version.paso_actual = siguiente.orden
        return version

    # La última firma: el documento queda aprobado y la tarea, cumplida.
    version.estado = "aprobada"
    version.paso_actual = None
    version.cerrado_en = ahora()
    antes = instantanea(tarea, "tarea")
    tarea.estado = "completada"
    tarea.avance_pct = 100
    tarea.sincronizar_cierre()
    registrar_cambios(db, "tarea", tarea.id, tarea.proyecto_id, antes, instantanea(tarea, "tarea"),
                      usuario.id, entidad_nombre=tarea.titulo)
    return version


# ── Observaciones ───────────────────────────────────────────────

def agregar_observacion(
    tarea: Tarea, version: DocumentoVersion, datos: dict, usuario: User,
) -> ObservacionDocumento:
    if not puede_responder(tarea, version, usuario):
        raise HTTPException(
            status_code=403,
            detail="Las observaciones las marca quien tiene el turno de revisar, mientras el documento está en revisión.",
        )
    ancla = _ancla(version, datos)
    paso = paso_en_turno(tarea, version)
    obs = ObservacionDocumento(
        usuario_id=usuario.id, paso_orden=paso.orden, paso_nombre=paso.nombre,
        **ancla, texto=datos["texto"].strip(),
    )
    version.observaciones.append(obs)
    return obs


def _ancla(version: DocumentoVersion, datos: dict) -> dict:
    """
    Dónde queda la observación: un punto de una página en un PDF, una celda
    de una hoja en un Excel, o nada (general). Cada tipo con lo suyo: un
    número de página en un Excel no apunta a ninguna parte.
    """
    en_pagina = any(datos.get(k) is not None for k in ("pagina", "pos_x", "pos_y"))
    en_celda = any(datos.get(k) for k in ("hoja", "celda"))
    if en_pagina:
        if version.tipo != "pdf":
            raise HTTPException(status_code=400, detail="En un Excel la observación va en una celda, no en una página.")
        if datos.get("pagina") is None or datos.get("pos_x") is None or datos.get("pos_y") is None:
            raise HTTPException(status_code=400, detail="Un punto en el documento necesita su página y su lugar en ella.")
        return {"pagina": datos["pagina"], "pos_x": datos["pos_x"], "pos_y": datos["pos_y"]}
    if en_celda:
        if version.tipo != "xlsx":
            raise HTTPException(status_code=400, detail="En un PDF la observación va en un punto de la página, no en una celda.")
        celda = (datos.get("celda") or "").strip().upper()
        hoja = (datos.get("hoja") or "").strip()
        if not hoja or not hoja_calculo.PATRON_CELDA.match(celda):
            raise HTTPException(status_code=400, detail="Indica la hoja y la celda como las escribe Excel, por ejemplo C14.")
        # La hoja tiene que ser de ESTE archivo: si no, quien corrige busca
        # una pestaña que no existe.
        if hoja not in hoja_calculo.nombres_de_hojas(ruta_documento_privado(version.ruta)):
            raise HTTPException(status_code=400, detail=f"El Excel no tiene una hoja llamada «{hoja}».")
        return {"hoja": hoja, "celda": celda}
    return {}


def borrar_observacion(tarea: Tarea, version: DocumentoVersion, obs: ObservacionDocumento, usuario: User) -> None:
    """La quita quien la escribió, mientras sigue siendo su turno: después ya es constancia."""
    if obs.usuario_id != usuario.id or not puede_responder(tarea, version, usuario):
        raise HTTPException(status_code=403, detail="Una observación la quita quien la escribió, mientras sigue siendo su turno.")
    version.observaciones.remove(obs)


def marcar_atendida(tarea: Tarea, obs: ObservacionDocumento, atendida: bool, usuario: User) -> None:
    """Quien corrige va tachando lo que ya arregló para la versión siguiente."""
    _exigir_trabajo(tarea, usuario)
    obs.atendida = atendida
    obs.atendida_por = usuario.id if atendida else None
    obs.atendida_en = ahora() if atendida else None


# ── Lo que viaja a la pantalla ──────────────────────────────────

def iso(fecha):
    return fecha.isoformat() if fecha else None


def serializar_observacion(obs: ObservacionDocumento, tarea: Tarea, version: DocumentoVersion, usuario: User) -> dict:
    return {
        "id": obs.id,
        "texto": obs.texto,
        "pagina": obs.pagina,
        "pos_x": obs.pos_x,
        "pos_y": obs.pos_y,
        "hoja": obs.hoja,
        "celda": obs.celda,
        "paso_nombre": obs.paso_nombre,
        "usuario_nombre": obs.usuario_nombre,
        "creado_en": iso(obs.creado_en),
        "atendida": obs.atendida,
        "puede_borrar": obs.usuario_id == usuario.id and puede_responder(tarea, version, usuario),
        "puede_atender": puede_trabajar_documento(tarea, usuario) and version.estado == "devuelta",
    }


def serializar_version(version: DocumentoVersion, tarea: Tarea, usuario: User, con_observaciones=False) -> dict:
    paso = paso_en_turno(tarea, version)
    salida = {
        "id": version.id,
        "numero": version.numero,
        "nombre_original": version.nombre_original,
        "tipo": version.tipo,
        "tamano": version.tamano,
        "estado": version.estado,
        "paso_actual": version.paso_actual,
        "turno_de": {"nombre": paso.nombre, "revisor_nombre": paso.revisor_nombre} if paso else None,
        "subido_por_nombre": version.subido_por_nombre,
        "subido_en": iso(version.subido_en),
        "enviado_en": iso(version.enviado_en),
        "cerrado_en": iso(version.cerrado_en),
        "total_observaciones": len(version.observaciones),
        "observaciones_pendientes": sum(1 for o in version.observaciones if not o.atendida),
        "eventos": [
            {
                "accion": e.accion, "paso_nombre": e.paso_nombre, "comentario": e.comentario,
                "usuario_nombre": e.usuario_nombre, "fecha": iso(e.fecha),
            }
            for e in version.eventos
        ],
        "puede_responder": puede_responder(tarea, version, usuario),
    }
    if con_observaciones:
        salida["observaciones"] = [serializar_observacion(o, tarea, version, usuario) for o in version.observaciones]
    return salida


def serializar(tarea: Tarea, usuario: User) -> dict:
    """Todo el flujo de una tarea, con lo que cada quien puede hacer ya resuelto."""
    version = ultima_version(tarea)
    paso = paso_en_turno(tarea, version)
    trabaja = puede_trabajar_documento(tarea, usuario)
    return {
        "activo": bool(tarea.revision_pasos),
        "estado": estado_documento(tarea),
        "pasos": [
            {
                "orden": p.orden, "nombre": p.nombre, "revisor_id": p.revisor_id,
                "revisor_nombre": p.revisor_nombre,
                "en_turno": paso is not None and paso.orden == p.orden,
            }
            for p in tarea.revision_pasos
        ],
        "veces_devuelto": veces_devuelto(tarea),
        "versiones": [serializar_version(v, tarea, usuario) for v in reversed(tarea.versiones)],
        "puede_configurar": usuario.rol not in ROLES_QUE_NO_FIRMAN and (version is None or version.estado != "en_revision"),
        "puede_subir": trabaja and bool(tarea.revision_pasos) and (
            version is None or version.estado in ("borrador", "devuelta")
            or (version.estado == "aprobada" and tarea.estado != "completada")
        ),
        "puede_enviar": trabaja and version is not None and version.estado == "borrador",
    }


def pendientes(db: Session, tenant_id: int, usuario: User) -> dict:
    """
    Lo que le toca a esta persona: documentos que esperan SU firma, y los
    suyos que le devolvieron. Las dos bandejas de un flujo con dos manos.
    """
    en_revision = (
        db.query(DocumentoVersion)
        .join(Tarea, DocumentoVersion.tarea_id == Tarea.id)
        .join(Proyecto, Tarea.proyecto_id == Proyecto.id)
        .join(RevisionPaso, (RevisionPaso.tarea_id == Tarea.id) & (RevisionPaso.orden == DocumentoVersion.paso_actual))
        .filter(
            Proyecto.tenant_id == tenant_id,
            DocumentoVersion.estado == "en_revision",
            RevisionPaso.revisor_id == usuario.id,
        )
        .order_by(Tarea.fecha_fin.asc().nullslast())
        .all()
    )
    devueltas = (
        db.query(DocumentoVersion)
        .join(Tarea, DocumentoVersion.tarea_id == Tarea.id)
        .join(Proyecto, Tarea.proyecto_id == Proyecto.id)
        .filter(
            Proyecto.tenant_id == tenant_id,
            DocumentoVersion.estado == "devuelta",
            Tarea.asignado_a == usuario.id,
        )
        .order_by(Tarea.fecha_fin.asc().nullslast())
        .all()
    )

    def ficha(version: DocumentoVersion) -> dict:
        tarea = version.tarea
        ultimo = version.eventos[-1] if version.eventos else None
        return {
            "tarea_id": tarea.id,
            "titulo": tarea.titulo,
            "proyecto_nombre": tarea.proyecto_nombre,
            "asignado_nombre": tarea.asignado_nombre,
            "fecha_fin": iso(tarea.fecha_fin),
            "version": serializar_version(version, tarea, usuario),
            "ultimo_movimiento": {
                "accion": ultimo.accion, "usuario_nombre": ultimo.usuario_nombre,
                "comentario": ultimo.comentario, "fecha": iso(ultimo.fecha),
            } if ultimo else None,
        }

    return {
        "por_revisar": [ficha(v) for v in en_revision],
        # Solo la última versión de cada tarea: una devuelta que ya tiene una
        # versión nueva ya se está corrigiendo.
        "por_corregir": [ficha(v) for v in devueltas if ultima_version(v.tarea) is v],
    }
