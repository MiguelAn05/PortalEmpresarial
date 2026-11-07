"""
Endpoints de los documentos que genera Fichas de seguridad: certificados de
análisis (AP-F-06) y fichas de datos de seguridad (AP-F-08).

El orden del flujo es el de la pantalla: `extraer` (se lee el PDF y se propone, no
guarda nada) → la persona revisa → `generar` (guarda y devuelve el registro) →
`/{id}/archivo` (baja el PDF). Todo lo que lee o escribe exige
la capacidad `fichas_seguridad.gestionar`; consultar y bajar, solo el módulo.

Este router se incluye ANTES que el de fichas: `/documentos` no puede caer en
`/{ficha_id}`.
"""
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.core.archivos import ruta_documento_privado
from app.core.database import get_db
from app.core.deps import solo_lectura_no
from app.core.modulos import contratado, requiere_modulo
from app.models.user import User
from app.modules.fichas_seguridad import documentos, lectura_reglas, permisos

router = APIRouter(
    prefix="/fichas-seguridad/documentos", tags=["Fichas de seguridad · documentos"],
    dependencies=[Depends(contratado("fichas_seguridad"))],
)

MODULO = "fichas_seguridad"


@router.post("/extraer")
async def extraer(
    tipo: str = Form(...),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: User = Depends(solo_lectura_no),
    _: User = Depends(requiere_modulo(MODULO)),
):
    """
    Lee el documento del proveedor (un PDF con texto, hasta 20 MB) y PROPONE los
    datos. No guarda nada: ni el archivo ni la lectura, y el documento no sale
    del servidor.
    """
    permisos.exigir_gestionar(db, usuario)
    documentos.exigir_tipo(tipo)
    contenido = await archivo.read(documentos.MAX_BYTES_LECTURA + 1)
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo llegó vacío. Vuelve a elegirlo.")
    if len(contenido) > documentos.MAX_BYTES_LECTURA:
        raise HTTPException(
            status_code=400,
            detail="El documento no puede superar 20 MB. Si es un PDF escaneado, guárdalo con menos resolución.",
        )
    leidos, avisos = await run_in_threadpool(lectura_reglas.leer, tipo, contenido)
    return documentos.propuesta(tipo, leidos, db, usuario.tenant_id, avisos)


@router.post("/vista-previa")
def vista_previa(
    tipo: str = Body(...),
    datos: dict = Body(...),
    db: Session = Depends(get_db),
    usuario: User = Depends(solo_lectura_no),
    _: User = Depends(requiere_modulo(MODULO)),
):
    """El PDF en línea con lo que hay en pantalla, sin guardar nada."""
    permisos.exigir_gestionar(db, usuario)
    documentos.exigir_tipo(tipo)
    limpio = documentos.validar_datos(tipo, datos)
    documentos.completar_codigo(db, usuario.tenant_id, limpio)
    return Response(
        documentos.vista_previa(tipo, limpio), media_type="application/pdf",
        headers={"Content-Disposition": "inline", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/generar", status_code=201)
def generar(
    tipo: str = Body(...),
    datos: dict = Body(...),
    db: Session = Depends(get_db),
    usuario: User = Depends(solo_lectura_no),
    _: User = Depends(requiere_modulo(MODULO)),
):
    """Guarda el documento con sus datos y su PDF, y devuelve el registro (el PDF se baja por `/{id}/archivo`)."""
    permisos.exigir_gestionar(db, usuario)
    return documentos.serializar(documentos.generar(db, usuario, tipo, datos))


@router.get("")
def listar(
    q: str | None = Query(None, max_length=100),
    tipo: str | None = Query(None, max_length=30),
    db: Session = Depends(get_db),
    usuario: User = Depends(requiere_modulo(MODULO)),
):
    """El historial de lo generado, del más reciente al más antiguo. Se busca por producto, código, proveedor o lote."""
    return documentos.listar(db, usuario.tenant_id, q, tipo)


@router.get("/{documento_id}")
def detalle(
    documento_id: int,
    db: Session = Depends(get_db),
    usuario: User = Depends(requiere_modulo(MODULO)),
):
    """Un documento con los datos con los que se generó (sirve para volver a generarlo corrigiendo algo)."""
    return documentos.serializar(documentos.obtener(db, usuario.tenant_id, documento_id), con_datos=True)


@router.get("/{documento_id}/archivo")
def descargar(
    documento_id: int,
    db: Session = Depends(get_db),
    usuario: User = Depends(requiere_modulo(MODULO)),
):
    """El PDF tal como se generó, sin caché (los computadores de las sedes son compartidos)."""
    d = documentos.obtener(db, usuario.tenant_id, documento_id)
    return FileResponse(
        ruta_documento_privado(d.ruta), media_type="application/pdf", filename=d.nombre_archivo,
        content_disposition_type="attachment",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
