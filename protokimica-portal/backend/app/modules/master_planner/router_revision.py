"""
Endpoints de la aprobación de documentos de una tarea.

La regla vive en `revision.py`; aquí solo se busca lo que se pidió, se
revisa que quien pide lo pueda ver y se guarda. Ver la tarea alcanza para
ver su documento —es su trabajo—, y quien firma un paso ve la tarea aunque
no tenga nada más en el proyecto (ver `permisos.py`).
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core import hoja_calculo
from app.core.archivos import guardar_documento_privado, ruta_documento_privado
from app.core.database import get_db
from app.core.deps import get_current_tenant_id, get_current_user, solo_lectura_no
from app.core.modulos import contratado
from app.models.master_planner import DocumentoVersion, ObservacionDocumento, Proyecto, Tarea
from app.models.user import User
from app.modules.master_planner import revision
from app.modules.master_planner.permisos import puede_ver_proyecto
from app.modules.master_planner.schemas import (
    EnviarDocumento, ObservacionAtender, ObservacionCrear, RespuestaDocumento, RevisionConfigurar,
)

router = APIRouter(
    prefix="/master-planner", tags=["Master Planner — documentos"],
    dependencies=[Depends(contratado("master_planner"))],
)

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _tarea(db: Session, tarea_id: int, tenant_id: int, usuario: User) -> Tarea:
    tarea = (
        db.query(Tarea)
        .join(Proyecto, Tarea.proyecto_id == Proyecto.id)
        .filter(Tarea.id == tarea_id, Proyecto.tenant_id == tenant_id)
        .first()
    )
    if not tarea or not puede_ver_proyecto(db, tarea.proyecto, usuario):
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    return tarea


def _version(db: Session, version_id: int, tenant_id: int, usuario: User) -> DocumentoVersion:
    version = (
        db.query(DocumentoVersion)
        .join(Tarea, DocumentoVersion.tarea_id == Tarea.id)
        .join(Proyecto, Tarea.proyecto_id == Proyecto.id)
        .filter(DocumentoVersion.id == version_id, Proyecto.tenant_id == tenant_id)
        .first()
    )
    if not version or not puede_ver_proyecto(db, version.tarea.proyecto, usuario):
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    return version


def _observacion(db: Session, obs_id: int, tenant_id: int, usuario: User) -> ObservacionDocumento:
    obs = db.get(ObservacionDocumento, obs_id)
    if obs is None:
        raise HTTPException(status_code=404, detail="Observación no encontrada.")
    _version(db, obs.version_id, tenant_id, usuario)
    return obs


@router.get("/plantillas-revision")
def listar_plantillas(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    return [
        {
            "id": p.id, "nombre": p.nombre, "descripcion": p.descripcion,
            "pasos": [{"orden": s.orden, "nombre": s.nombre} for s in p.pasos],
        }
        for p in revision.plantillas_activas(db, tenant_id)
    ]


@router.get("/revisiones/pendientes")
def mis_documentos_pendientes(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Lo que espera mi firma y lo mío que me devolvieron."""
    return revision.pendientes(db, tenant_id, current_user)


@router.get("/tareas/{tarea_id}/revision")
def obtener_revision(
    tarea_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    return revision.serializar(_tarea(db, tarea_id, tenant_id, current_user), current_user)


@router.put("/tareas/{tarea_id}/revision")
def configurar_revision(
    tarea_id: int,
    payload: RevisionConfigurar,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    tarea = _tarea(db, tarea_id, tenant_id, current_user)
    revision.configurar(db, tarea, payload.plantilla_id, payload.revisores, current_user)
    db.commit()
    db.refresh(tarea)
    return revision.serializar(tarea, current_user)


@router.delete("/tareas/{tarea_id}/revision")
def quitar_revision(
    tarea_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    tarea = _tarea(db, tarea_id, tenant_id, current_user)
    revision.quitar(db, tarea, current_user)
    db.commit()
    db.refresh(tarea)
    return revision.serializar(tarea, current_user)


@router.post("/tareas/{tarea_id}/documentos", status_code=status.HTTP_201_CREATED)
async def subir_documento(
    tarea_id: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    tarea = _tarea(db, tarea_id, tenant_id, current_user)
    revision.validar_subida(tarea, current_user)
    datos = await guardar_documento_privado(archivo, revision.SUBCARPETA)
    revision.registrar_version(db, tarea, datos, current_user)
    db.commit()
    db.refresh(tarea)
    return revision.serializar(tarea, current_user)


@router.post("/tareas/{tarea_id}/documentos/enviar")
def enviar_documento(
    tarea_id: int,
    payload: EnviarDocumento,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    tarea = _tarea(db, tarea_id, tenant_id, current_user)
    revision.enviar(db, tarea, current_user, payload.comentario)
    db.commit()
    db.refresh(tarea)
    return revision.serializar(tarea, current_user)


@router.get("/documentos/{version_id}")
def obtener_documento(
    version_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Lo que necesita el visor: la versión con sus observaciones y la tarea."""
    version = _version(db, version_id, tenant_id, current_user)
    tarea = version.tarea
    return {
        "tarea": {
            "id": tarea.id, "titulo": tarea.titulo, "proyecto_nombre": tarea.proyecto_nombre,
            "asignado_nombre": tarea.asignado_nombre, "fecha_fin": revision.iso(tarea.fecha_fin),
            "entregable": tarea.entregable,
        },
        "revision": revision.serializar(tarea, current_user),
        "version": revision.serializar_version(version, tarea, current_user, con_observaciones=True),
        "es_la_ultima": revision.ultima_version(tarea) is version,
    }


@router.get("/documentos/{version_id}/archivo")
def descargar_documento(
    version_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """
    El archivo, solo para quien ve la tarea. `no-store`: un estado financiero
    no se queda en la caché de un computador compartido.
    """
    version = _version(db, version_id, tenant_id, current_user)
    return FileResponse(
        ruta_documento_privado(version.ruta),
        media_type=MEDIA_TYPES[version.tipo],
        filename=version.nombre_original,
        content_disposition_type="inline" if version.tipo == "pdf" else "attachment",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


def _version_excel(db: Session, version_id: int, tenant_id: int, usuario: User) -> DocumentoVersion:
    version = _version(db, version_id, tenant_id, usuario)
    if version.tipo != "xlsx":
        raise HTTPException(status_code=400, detail="Este documento no es un Excel: ábrelo en el visor de PDF.")
    return version


@router.get("/documentos/{version_id}/hojas")
def hojas_del_documento(
    version_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Los nombres de las hojas de un Excel, en el orden del libro."""
    version = _version_excel(db, version_id, tenant_id, current_user)
    return {"hojas": hoja_calculo.nombres_de_hojas(ruta_documento_privado(version.ruta))}


@router.get("/documentos/{version_id}/hojas/{indice}")
def hoja_del_documento(
    version_id: int,
    indice: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """
    Los VALORES de una hoja, para revisarla en pantalla sin descargarla. Lo
    lee el servidor (`core/hoja_calculo.py`): la misma regla de quién ve el
    archivo, y nada que instalar en el navegador.
    """
    version = _version_excel(db, version_id, tenant_id, current_user)
    return hoja_calculo.leer_hoja(ruta_documento_privado(version.ruta), indice)


@router.post("/documentos/{version_id}/responder")
def responder_documento(
    version_id: int,
    payload: RespuestaDocumento,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    version = _version(db, version_id, tenant_id, current_user)
    tarea = version.tarea
    revision.responder(db, tarea, version, payload.decision, payload.comentario, current_user)
    db.commit()
    db.refresh(tarea)
    return revision.serializar(tarea, current_user)


@router.post("/documentos/{version_id}/observaciones", status_code=status.HTTP_201_CREATED)
def agregar_observacion(
    version_id: int,
    payload: ObservacionCrear,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    version = _version(db, version_id, tenant_id, current_user)
    obs = revision.agregar_observacion(version.tarea, version, payload.model_dump(), current_user)
    db.commit()
    db.refresh(obs)
    return revision.serializar_observacion(obs, version.tarea, version, current_user)


@router.patch("/observaciones/{obs_id}")
def atender_observacion(
    obs_id: int,
    payload: ObservacionAtender,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    obs = _observacion(db, obs_id, tenant_id, current_user)
    version = obs.version
    revision.marcar_atendida(version.tarea, obs, payload.atendida, current_user)
    db.commit()
    db.refresh(obs)
    return revision.serializar_observacion(obs, version.tarea, version, current_user)


@router.delete("/observaciones/{obs_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_observacion(
    obs_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    obs = _observacion(db, obs_id, tenant_id, current_user)
    version = obs.version
    revision.borrar_observacion(version.tarea, version, obs, current_user)
    db.commit()
