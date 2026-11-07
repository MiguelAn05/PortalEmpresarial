"""
Endpoints de Fichas de seguridad.

Leer es de cualquiera que entre al módulo; escribir exige la capacidad
`fichas_seguridad.gestionar` (`permisos.exigir_gestionar`) y, antes que ella,
`solo_lectura_no`. Los archivos no se sirven desde `/uploads`: se bajan por
`/versiones/{id}/archivo`, que mira el contrato y el rol de cada descarga.

Las rutas con `versiones/` van antes que las de `/{ficha_id}` por claridad:
no chocan (distinto número de tramos), pero así se ve de un vistazo.
"""
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.archivos import ruta_documento_privado
from app.core.database import get_db
from app.core.deps import solo_lectura_no
from app.core.modulos import contratado, requiere_modulo
from app.models.user import User
from app.modules.fichas_seguridad import permisos, service
from app.modules.fichas_seguridad.schemas import FichaEditar, VersionEditar

router = APIRouter(
    prefix="/fichas-seguridad", tags=["Fichas de seguridad"],
    dependencies=[Depends(contratado("fichas_seguridad"))],
)

MODULO = "fichas_seguridad"


@router.get("")
def listar(
    q: str | None = Query(None, max_length=100),
    estado: str = Query("activas", max_length=10),
    db: Session = Depends(get_db),
    usuario: User = Depends(requiere_modulo(MODULO)),
):
    """Las fichas de la empresa, con su versión vigente. Se busca por nombre o código, sin tildes."""
    return service.listar(db, usuario.tenant_id, q, estado)


@router.get("/versiones/{version_id}/archivo")
def descargar(
    version_id: int,
    db: Session = Depends(get_db),
    usuario: User = Depends(requiere_modulo(MODULO)),
):
    """
    El PDF de una versión, también de las anteriores y de las fichas
    desactivadas. `no-store`: no se queda en la caché de un computador
    compartido, que es lo que son los de varias sedes.
    """
    version = service.obtener_version(db, usuario.tenant_id, version_id)
    return FileResponse(
        ruta_documento_privado(version.ruta),
        media_type="application/pdf",
        filename=version.nombre_original,
        content_disposition_type="inline",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/versiones/{version_id}/vigente")
def hacer_vigente(
    version_id: int,
    db: Session = Depends(get_db),
    usuario: User = Depends(solo_lectura_no),
    _: User = Depends(requiere_modulo(MODULO)),
):
    """Vuelve vigente una versión anterior (por ejemplo, si se subió una equivocada). No borra nada."""
    permisos.exigir_gestionar(db, usuario)
    version = service.obtener_version(db, usuario.tenant_id, version_id)
    ficha = service.obtener_ficha(db, usuario.tenant_id, version.ficha_id)
    return service.serializar_ficha(service.hacer_vigente(db, ficha, version), con_versiones=True)


@router.patch("/versiones/{version_id}")
def editar_version(
    version_id: int,
    datos: VersionEditar,
    db: Session = Depends(get_db),
    usuario: User = Depends(solo_lectura_no),
    _: User = Depends(requiere_modulo(MODULO)),
):
    """Corrige el número, la fecha de emisión o las observaciones de una versión. El PDF no cambia."""
    permisos.exigir_gestionar(db, usuario)
    version = service.obtener_version(db, usuario.tenant_id, version_id)
    ficha = service.obtener_ficha(db, usuario.tenant_id, version.ficha_id)
    # La versión se vuelve a tomar de la ficha recién cargada, para comparar contra sus hermanas.
    version = next(v for v in ficha.versiones if v.id == version.id)
    return service.serializar_ficha(service.editar_version(db, ficha, version, datos), con_versiones=True)


@router.post("", status_code=201)
async def crear(
    nombre_producto: str = Form(...),
    version: str = Form(...),
    fecha_emision: date = Form(...),
    archivo: UploadFile = File(...),
    codigo_producto: str | None = Form(None),
    observaciones: str | None = Form(None),
    db: Session = Depends(get_db),
    usuario: User = Depends(solo_lectura_no),
    _: User = Depends(requiere_modulo(MODULO)),
):
    """Una ficha nueva con su primera versión (el PDF). Primero se valida, después se guarda el archivo."""
    permisos.exigir_gestionar(db, usuario)
    datos = service.validar_ficha(
        db, usuario.tenant_id, nombre_producto, codigo_producto, version, fecha_emision, observaciones,
    )
    info = await service.guardar_pdf(archivo)
    return service.serializar_ficha(service.registrar_ficha(db, usuario, datos, info), con_versiones=True)


@router.get("/{ficha_id}")
def detalle(
    ficha_id: int,
    db: Session = Depends(get_db),
    usuario: User = Depends(requiere_modulo(MODULO)),
):
    """Una ficha con todas sus versiones, la vigente marcada."""
    return service.serializar_ficha(service.obtener_ficha(db, usuario.tenant_id, ficha_id), con_versiones=True)


@router.post("/{ficha_id}/versiones", status_code=201)
async def subir_version(
    ficha_id: int,
    version: str = Form(...),
    fecha_emision: date = Form(...),
    archivo: UploadFile = File(...),
    observaciones: str | None = Form(None),
    db: Session = Depends(get_db),
    usuario: User = Depends(solo_lectura_no),
    _: User = Depends(requiere_modulo(MODULO)),
):
    """Una versión nueva de una ficha: queda vigente y las anteriores se conservan."""
    permisos.exigir_gestionar(db, usuario)
    ficha = service.obtener_ficha(db, usuario.tenant_id, ficha_id)
    datos = service.validar_version(ficha, version, fecha_emision, observaciones)
    info = await service.guardar_pdf(archivo)
    return service.serializar_ficha(service.registrar_version(db, usuario, ficha, datos, info), con_versiones=True)


@router.patch("/{ficha_id}")
def editar(
    ficha_id: int,
    datos: FichaEditar,
    db: Session = Depends(get_db),
    usuario: User = Depends(solo_lectura_no),
    _: User = Depends(requiere_modulo(MODULO)),
):
    """Corrige el nombre o el código, o la desactiva (y reactiva). Desactivar no borra nada."""
    permisos.exigir_gestionar(db, usuario)
    ficha = service.obtener_ficha(db, usuario.tenant_id, ficha_id)
    return service.serializar_ficha(service.editar(db, ficha, datos), con_versiones=True)


@router.delete("/{ficha_id}", status_code=204)
def eliminar(
    ficha_id: int,
    incluir_versiones: bool = Query(False),
    db: Session = Depends(get_db),
    usuario: User = Depends(solo_lectura_no),
    _: User = Depends(requiere_modulo(MODULO)),
):
    """
    Borra la ficha y TODAS sus versiones, pero solo si se pide a propósito con
    `incluir_versiones=true`. Sin eso responde 409 y ofrece desactivarla.
    """
    permisos.exigir_gestionar(db, usuario)
    ficha = service.obtener_ficha(db, usuario.tenant_id, ficha_id)
    service.eliminar(db, ficha, incluir_versiones)
