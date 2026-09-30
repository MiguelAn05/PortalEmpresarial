"""
Guardar los archivos que sube la gente: fotos, facturas, videos, evidencias.

Lo usan PQRS, Master Planner, Indicadores, Autorizaciones y Notas crédito.
Nació dentro de PQRS y los demás módulos lo importaban de ahí, así que
ninguno se podía instalar sin PQRS; por eso vive en `core`.

Los nombres son UUID: un archivo nunca cambia de contenido, y por eso nginx
lo cachea un día (ver `frontend/nginx.conf`).
"""
import os
import uuid

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
