"""
Guardar los archivos que sube la gente: fotos, facturas, videos, evidencias.

Lo usan PQRS, Master Planner, Indicadores, Autorizaciones y Notas crédito.
Nació dentro de PQRS y los demás módulos lo importaban de ahí, así que
ninguno se podía instalar sin PQRS; por eso vive en `core`.

Los nombres son UUID: un archivo nunca cambia de contenido, y por eso nginx
lo cachea un día (ver `frontend/nginx.conf`).
"""
import io
import os
import uuid
import zipfile

from fastapi import HTTPException, UploadFile

from app.core.config import settings

EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".pdf", ".webp"}
MAX_TAMANIO_MB = 10

# Videos: no validamos duración en el servidor (requeriría ffmpeg/procesamiento
# adicional), así que controlamos el peso del archivo. 20MB es suficiente para
# un clip corto (~20-30 seg) en buena calidad sin dejar que la carpeta de
# uploads crezca sin control. El límite de tiempo real se sugiere en el
# frontend al momento de grabar/seleccionar el video.
EXTENSIONES_VIDEO_PERMITIDAS = {".mp4", ".mov", ".webm"}
MAX_TAMANIO_VIDEO_MB = 20


async def guardar_archivo(
    archivo: UploadFile,
    subfolder: str,
    extensiones_permitidas: set[str] | None = None,
    max_mb: int | None = None,
) -> str:
    """Guarda un archivo subido (público o interno) y retorna la ruta relativa.
    Por defecto valida como imagen/documento; pasa extensiones_permitidas y
    max_mb para validar otro tipo de archivo (ej. video)."""
    extensiones = extensiones_permitidas or EXTENSIONES_PERMITIDAS
    limite_mb = max_mb or MAX_TAMANIO_MB

    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in extensiones:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido. Usa: {', '.join(extensiones)}"
        )

    contenido = await archivo.read()
    if len(contenido) > limite_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo no puede superar {limite_mb}MB."
        )

    carpeta = os.path.join(settings.UPLOAD_DIR, subfolder)
    os.makedirs(carpeta, exist_ok=True)

    nombre_unico = f"{uuid.uuid4().hex}{ext}"
    ruta = os.path.join(carpeta, nombre_unico)

    with open(ruta, "wb") as f:
        f.write(contenido)

    return f"/uploads/{subfolder}/{nombre_unico}"


# ── Documentos privados ─────────────────────────────────────────
#
# Los que se aprueban (estados financieros, conciliaciones) no van a
# `/uploads`, que se sirve sin preguntar quién pide: van a DOCUMENTOS_DIR,
# que no está montado en ninguna URL, y salen por un endpoint que revisa el
# permiso de cada descarga.
#
# Y el tipo se decide por el CONTENIDO, no por la extensión: renombrar un
# ejecutable a `.pdf` es lo primero que se intenta, y el visor lo abriría.

MAX_DOCUMENTO_MB = 20
TIPOS_DOCUMENTO_PRIVADO = {"pdf": ".pdf", "xlsx": ".xlsx"}


def tipo_de_documento(contenido: bytes) -> str | None:
    """'pdf', 'xlsx' o None, según lo que de verdad hay en el archivo."""
    if contenido[:5] == b"%PDF-":
        return "pdf"
    # Un .xlsx es un ZIP con el libro adentro. Cualquier ZIP empieza igual,
    # así que se mira que traiga `xl/workbook.xml`.
    if contenido[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(contenido)) as z:
                if "xl/workbook.xml" in z.namelist():
                    return "xlsx"
        except zipfile.BadZipFile:
            return None
    return None


async def guardar_documento_privado(archivo: UploadFile, subfolder: str) -> dict:
    """
    Guarda un PDF o un Excel fuera de lo público. Devuelve la ruta RELATIVA a
    DOCUMENTOS_DIR, el tipo, el tamaño y el nombre original.
    """
    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo llegó vacío. Vuelve a elegirlo.")
    if len(contenido) > MAX_DOCUMENTO_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"El documento no puede superar {MAX_DOCUMENTO_MB} MB. "
                   "Si es un PDF escaneado, guárdalo con menos resolución.",
        )
    tipo = tipo_de_documento(contenido)
    if tipo is None:
        raise HTTPException(
            status_code=400,
            detail="Solo se aceptan documentos PDF o Excel (.xlsx). Si es un .xls "
                   "viejo, ábrelo en Excel y guárdalo como .xlsx.",
        )

    carpeta = os.path.join(settings.DOCUMENTOS_DIR, subfolder)
    os.makedirs(carpeta, exist_ok=True)
    nombre_unico = f"{uuid.uuid4().hex}{TIPOS_DOCUMENTO_PRIVADO[tipo]}"
    with open(os.path.join(carpeta, nombre_unico), "wb") as f:
        f.write(contenido)

    return {
        "ruta": f"{subfolder}/{nombre_unico}",
        "tipo": tipo,
        "tamano": len(contenido),
        "nombre_original": os.path.basename(archivo.filename or f"documento{TIPOS_DOCUMENTO_PRIVADO[tipo]}")[:255],
    }


def ruta_documento_privado(ruta_relativa: str) -> str:
    """
    La ruta en disco de un documento privado, sin salirse de su carpeta.

    La ruta sale de la base y no de la petición, pero se revisa igual: un
    `..` guardado por error no puede terminar sirviendo otro archivo.
    """
    base = os.path.realpath(settings.DOCUMENTOS_DIR)
    completa = os.path.realpath(os.path.join(base, ruta_relativa))
    if not completa.startswith(base + os.sep) or not os.path.isfile(completa):
        raise HTTPException(
            status_code=404,
            detail="El archivo de este documento no está en el servidor. Pídele a quien lo subió que lo vuelva a cargar.",
        )
    return completa
